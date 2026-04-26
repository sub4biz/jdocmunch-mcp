"""Persistent token savings tracker for jDocMunch.

Records cumulative tokens saved across all tool calls by comparing
raw file sizes against actual MCP response sizes.

Stored in ~/.doc-index/_savings.json
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Optional

_SAVINGS_FILE = "_savings.json"
_BYTES_PER_TOKEN = 4
_TELEMETRY_URL = "https://j.gravelle.us/APIs/savings/post.php"
_SAVINGS_LOCK = threading.Lock()

PRICING = {
    "claude_opus":  15.00 / 1_000_000,  # Claude Opus 4.6 — $15.00 / 1M input tokens
    "gpt5_latest":  10.00 / 1_000_000,  # GPT-5.2 (latest flagship GPT) — $10.00 / 1M input tokens
}


def _savings_path(base_path: Optional[str] = None) -> Path:
    root = Path(base_path) if base_path else Path.home() / ".doc-index"
    root.mkdir(parents=True, exist_ok=True)
    return root / _SAVINGS_FILE


def _get_or_create_anon_id(data: dict) -> str:
    if "anon_id" not in data:
        data["anon_id"] = str(uuid.uuid4())
    return data["anon_id"]


def _share_savings(delta: int, anon_id: str) -> None:
    def _post() -> None:
        try:
            import httpx
            httpx.post(
                _TELEMETRY_URL,
                json={"delta": delta, "anon_id": anon_id},
                timeout=3.0,
            )
        except Exception:
            pass

    threading.Thread(target=_post, daemon=True).start()


def record_savings(tokens_saved: int, base_path: Optional[str] = None) -> int:
    """Add tokens_saved to the running total. Returns new cumulative total."""
    path = _savings_path(base_path)
    with _SAVINGS_LOCK:
        try:
            data = json.loads(path.read_text()) if path.exists() else {}
        except Exception:
            data = {}

        delta = max(0, tokens_saved)
        total = data.get("total_tokens_saved", 0) + delta
        data["total_tokens_saved"] = total

        if delta > 0 and os.environ.get("JDOCMUNCH_SHARE_SAVINGS", "1") != "0":
            anon_id = _get_or_create_anon_id(data)
            _share_savings(delta, anon_id)

        try:
            path.write_text(json.dumps(data))
        except Exception:
            pass

    return total


def get_total_saved(base_path: Optional[str] = None) -> int:
    """Return the current cumulative total without modifying it."""
    path = _savings_path(base_path)
    try:
        return json.loads(path.read_text()).get("total_tokens_saved", 0)
    except Exception:
        return 0


def count_tokens(text: str) -> int:
    """Count tokens in text.

    Uses ``tiktoken`` (cl100k_base) when installed for an accurate count.
    Falls back to the bytes/4 heuristic when tiktoken is not available,
    keeping it as a zero-cost optional dependency.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text.encode("utf-8")) // _BYTES_PER_TOKEN)


def estimate_savings(raw_bytes: int, response_bytes: int) -> int:
    """Estimate tokens saved: (raw - response) / bytes_per_token."""
    return max(0, (raw_bytes - response_bytes) // _BYTES_PER_TOKEN)


def cost_avoided(tokens_saved: int, total_tokens_saved: int) -> dict:
    """Return cost avoided estimates for this call and the running total."""
    return {
        "cost_avoided": {
            model: round(tokens_saved * rate, 4)
            for model, rate in PRICING.items()
        },
        "total_cost_avoided": {
            model: round(total_tokens_saved * rate, 4)
            for model, rate in PRICING.items()
        },
    }


# ---------------------------------------------------------------------------
# v1.14.0 — per-tool latency telemetry
#
# Two tiers:
#
# 1. **In-memory ring** — `_tool_latencies: dict[tool, deque(maxlen=512)]`
#    + `_tool_errors: dict[tool, int]`. Free, always on. Powers the
#    `latency_stats()` view used by `analyze_perf(window="session")` and
#    by the `get_session_stats` tool.
#
# 2. **Persistent SQLite sink** — opt-in via `JDOCMUNCH_PERF_TELEMETRY=1`
#    or `perf_telemetry_enabled` config flag. Writes one row per tool call
#    to `~/.doc-index/telemetry.db` for `analyze_perf(window=1h|24h|7d|all)`.
#    Trimmed in 1k-row batches when over `JDOCMUNCH_PERF_TELEMETRY_MAX_ROWS`
#    (default 100k).
#
# Backward-compatible: nothing changes in default behavior. The ring is
# in-memory only unless the user opts into the SQLite sink.
# ---------------------------------------------------------------------------

_LATENCY_LOCK = threading.Lock()
_TOOL_LATENCIES: "dict[str, deque[float]]" = {}
_TOOL_ERRORS: "dict[str, int]" = {}
_RING_MAXLEN = 512


def _telemetry_enabled() -> bool:
    flag = os.environ.get("JDOCMUNCH_PERF_TELEMETRY", "")
    return flag.strip() not in ("", "0", "false", "False", "no")


def _telemetry_db_path(base_path: Optional[str] = None) -> Path:
    root = Path(base_path) if base_path else Path.home() / ".doc-index"
    root.mkdir(parents=True, exist_ok=True)
    return root / "telemetry.db"


def _ensure_telemetry_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_calls (
            ts REAL NOT NULL,
            tool TEXT NOT NULL,
            duration_ms REAL NOT NULL,
            ok INTEGER NOT NULL,
            repo TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_ts ON tool_calls(tool, ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_calls_ts ON tool_calls(ts)")


def _max_persisted_rows() -> int:
    try:
        return int(os.environ.get("JDOCMUNCH_PERF_TELEMETRY_MAX_ROWS", "100000"))
    except ValueError:
        return 100000


def record_tool_latency(
    tool: str,
    duration_ms: float,
    ok: bool = True,
    repo: Optional[str] = None,
    base_path: Optional[str] = None,
) -> None:
    """Record one tool-call latency.

    Always pushes onto the in-memory ring. When telemetry is enabled,
    also appends a row to the SQLite sink (autocommit; one fresh
    connection per call to keep cross-thread safety simple).
    """
    if not tool:
        return
    with _LATENCY_LOCK:
        ring = _TOOL_LATENCIES.get(tool)
        if ring is None:
            ring = deque(maxlen=_RING_MAXLEN)
            _TOOL_LATENCIES[tool] = ring
        ring.append(float(duration_ms))
        if not ok:
            _TOOL_ERRORS[tool] = _TOOL_ERRORS.get(tool, 0) + 1

    if not _telemetry_enabled():
        return

    try:
        path = _telemetry_db_path(base_path)
        conn = sqlite3.connect(str(path), isolation_level=None, timeout=2.0)
        try:
            _ensure_telemetry_schema(conn)
            conn.execute(
                "INSERT INTO tool_calls (ts, tool, duration_ms, ok, repo) VALUES (?, ?, ?, ?, ?)",
                (time.time(), tool, float(duration_ms), 1 if ok else 0, repo),
            )
            # Trim in 1k-row batches to amortize cost.
            cap = _max_persisted_rows()
            (count,) = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()
            if count > cap:
                excess = (count - cap) + 1000
                conn.execute(
                    "DELETE FROM tool_calls WHERE rowid IN ("
                    "SELECT rowid FROM tool_calls ORDER BY ts ASC LIMIT ?)",
                    (excess,),
                )
        finally:
            conn.close()
    except Exception:
        # Telemetry must never break a working tool call.
        pass


def _percentile(sorted_xs: list, p: float) -> float:
    """Nearest-rank percentile. p in [0, 100]."""
    if not sorted_xs:
        return 0.0
    if len(sorted_xs) == 1:
        return float(sorted_xs[0])
    idx = max(0, min(len(sorted_xs) - 1, int(round((p / 100.0) * (len(sorted_xs) - 1)))))
    return float(sorted_xs[idx])


def latency_stats() -> dict:
    """Return per-tool latency stats from the in-memory ring.

    Output:
        {tool: {count, p50_ms, p95_ms, max_ms, errors, error_rate}}
    """
    with _LATENCY_LOCK:
        snapshot = {tool: list(ring) for tool, ring in _TOOL_LATENCIES.items()}
        errors_snapshot = dict(_TOOL_ERRORS)

    out: dict = {}
    for tool, samples in snapshot.items():
        if not samples:
            continue
        s = sorted(samples)
        errs = int(errors_snapshot.get(tool, 0))
        count = len(samples)
        out[tool] = {
            "count": count,
            "p50_ms": round(_percentile(s, 50), 2),
            "p95_ms": round(_percentile(s, 95), 2),
            "max_ms": round(max(s), 2),
            "errors": errs,
            "error_rate": round(errs / count, 4) if count else 0.0,
        }
    return out


def latency_db_query(window: str, base_path: Optional[str] = None) -> dict:
    """Read aggregated stats from the persistent telemetry DB.

    ``window`` ∈ {"1h", "24h", "7d", "all"} — anything else returns empty.
    Returns ``{tool: {count, p50_ms, p95_ms, max_ms, errors, error_rate}}``.
    """
    deltas = {"1h": 3600, "24h": 86400, "7d": 7 * 86400, "all": None}
    if window not in deltas:
        return {}
    path = _telemetry_db_path(base_path)
    if not path.exists():
        return {}

    delta = deltas[window]
    cutoff = time.time() - delta if delta is not None else 0.0

    try:
        conn = sqlite3.connect(str(path), timeout=2.0)
        try:
            cursor = conn.execute(
                "SELECT tool, duration_ms, ok FROM tool_calls WHERE ts >= ?",
                (cutoff,),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()
    except Exception:
        return {}

    by_tool: dict[str, list] = {}
    errs_by_tool: dict[str, int] = {}
    for tool, ms, ok in rows:
        by_tool.setdefault(tool, []).append(float(ms))
        if not ok:
            errs_by_tool[tool] = errs_by_tool.get(tool, 0) + 1

    out: dict = {}
    for tool, samples in by_tool.items():
        s = sorted(samples)
        count = len(samples)
        errs = errs_by_tool.get(tool, 0)
        out[tool] = {
            "count": count,
            "p50_ms": round(_percentile(s, 50), 2),
            "p95_ms": round(_percentile(s, 95), 2),
            "max_ms": round(max(s), 2),
            "errors": errs,
            "error_rate": round(errs / count, 4) if count else 0.0,
        }
    return out


def reset_latency_state() -> None:
    """Test hook — clear the in-memory ring and error counts."""
    with _LATENCY_LOCK:
        _TOOL_LATENCIES.clear()
        _TOOL_ERRORS.clear()
