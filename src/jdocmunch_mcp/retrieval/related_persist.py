"""Persisted related-section adjacency list (v1.24.0).

The v1.20 ``retrieval/related.py`` module computes structural and
semantic neighbors on demand. For large indexes this is acceptable for
occasional calls but expensive when ``get_related_sections`` runs in a
hot path or when ``get_section_context(include_related=True)`` is used
broadly. v1.24 builds the adjacency list once at index time and
persists it as a JSON sidecar; the on-demand path stays as the fallback
when the sidecar is missing or stale.

Sidecar location: ``~/.doc-index/<owner>/<name>.related.json``.

Schema:

    {
        "version": 1,
        "captured_at": "...",
        "section_count": int,
        "by_section": {
            "<section_id>": {
                "structural": [{"id", "title", "level", "kind"}, ...],
                "semantic":   [{"id", "title", "level", "score"}, ...]
            },
            ...
        }
    }

Build cost is O(N) for structural edges (parent/child/sibling). Semantic
edges are computed when embeddings are present and run O(N²) over the
embedding set; we cap output at top-5 per section so the sidecar size
stays linear in N.

This module is purely additive on the 1.x line — `get_related_sections`
still returns identical shapes when the sidecar is absent.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

from .related import semantic_neighbors, structural_neighbors

_FILENAME = "{name}.related.json"
_LOCK = threading.Lock()
_SCHEMA_VERSION = 1


def _path(base_path: Optional[str], owner: str, name: str) -> Path:
    root = Path(base_path) if base_path else Path.home() / ".doc-index"
    safe_owner = (owner or "").strip().replace("/", "_").replace("\\", "_") or "_"
    safe_name = (name or "").strip().replace("/", "_").replace("\\", "_") or "_"
    return root / safe_owner / _FILENAME.format(name=safe_name)


def build(sections: list, *, top_n_semantic: int = 5, min_score: float = 0.6) -> dict:
    """Compute the full adjacency list from a list of section dicts."""
    by_section: dict = {}
    for sec in sections:
        sid = sec.get("id") if isinstance(sec, dict) else getattr(sec, "id", None)
        if not sid:
            continue
        # Section objects vs dicts — tolerate both.
        section_dicts = [
            s if isinstance(s, dict) else _section_to_dict(s) for s in sections
        ]
        struct = structural_neighbors(section_dicts, sid)
        sem = semantic_neighbors(section_dicts, sid, top_n=top_n_semantic, min_score=min_score)
        by_section[sid] = {"structural": struct, "semantic": sem}
    return {
        "version": _SCHEMA_VERSION,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "section_count": len(by_section),
        "by_section": by_section,
    }


def _section_to_dict(sec) -> dict:
    """Best-effort dict view of a Section dataclass for the structural walk."""
    return {
        "id": getattr(sec, "id", ""),
        "title": getattr(sec, "title", ""),
        "level": getattr(sec, "level", 0),
        "parent_id": getattr(sec, "parent_id", "") or "",
        "embedding": getattr(sec, "embedding", []) or [],
    }


def write(
    base_path: Optional[str],
    owner: str,
    name: str,
    sections: list,
    *,
    top_n_semantic: int = 5,
    min_score: float = 0.6,
) -> int:
    """Build + atomically write the adjacency list. Returns section count."""
    data = build(sections, top_n_semantic=top_n_semantic, min_score=min_score)
    path = _path(base_path, owner, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _LOCK:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    return data["section_count"]


def load(base_path: Optional[str], owner: str, name: str) -> Optional[dict]:
    """Return the persisted adjacency dict, or None when absent / corrupt."""
    path = _path(base_path, owner, name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        if data.get("version") != _SCHEMA_VERSION:
            return None
        return data
    except Exception:
        return None


def lookup(
    base_path: Optional[str],
    owner: str,
    name: str,
    section_id: str,
) -> Optional[dict]:
    """Return ``{structural, semantic}`` for one section from the sidecar.

    Returns None when the sidecar is absent or the section_id is missing
    from it (caller should fall back to on-demand build).
    """
    data = load(base_path, owner, name)
    if not data:
        return None
    return (data.get("by_section") or {}).get(section_id)


def purge(base_path: Optional[str], owner: str, name: str) -> bool:
    """Delete the sidecar. Returns True on success."""
    path = _path(base_path, owner, name)
    if path.exists():
        try:
            path.unlink()
            return True
        except OSError:
            return False
    return False
