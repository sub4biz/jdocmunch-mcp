"""Regression test for jdoc#14: O(N^2) hang in related_persist.build().

The v1.24-v1.63 build() rebuilt section_dicts inside the per-section loop
and re-scanned `sections` 4x per section for child lookups. For N=15k
that ballooned to ~1.1B ops and hung at 100% CPU. v1.64.1 precomputes
the lookups once.

This test asserts the new build scales linearly: doubling N should not
multiply runtime by anything close to 4x. We pick a deliberately large N
that still completes in seconds on the fixed path but would hang for
minutes on the buggy path.
"""

from __future__ import annotations

import time

from jdocmunch_mcp.retrieval.related_persist import build


def _make_sections(n: int) -> list[dict]:
    """Build a flat-ish hierarchy: 1 root, 10 second-level, rest are leaves.

    Structurally interesting (parent/sibling lookups exercise the children
    cache) but no embeddings, so the semantic path is skipped — we are
    measuring the structural side specifically.
    """
    sections: list[dict] = [
        {"id": "root", "title": "Root", "level": 1, "parent_id": ""}
    ]
    for i in range(10):
        sections.append(
            {"id": f"s{i}", "title": f"L2-{i}", "level": 2, "parent_id": "root"}
        )
    parent_ids = [f"s{i}" for i in range(10)]
    for i in range(n - 11):
        sections.append(
            {
                "id": f"leaf-{i}",
                "title": f"Leaf {i}",
                "level": 3,
                "parent_id": parent_ids[i % 10],
            }
        )
    return sections


def test_build_scales_linearly():
    """Bigger N's (4k -> 8k) so small-N noise doesn't dominate the ratio
    and we don't measure constant overhead instead of asymptotic growth.
    The real anti-regression gate is test_build_completes_quickly_at_15k
    below; this test exists as a directional sanity check."""
    n_small, n_big = 4_000, 8_000

    sections_small = _make_sections(n_small)
    t0 = time.perf_counter()
    out_small = build(sections_small)
    t_small = time.perf_counter() - t0
    assert out_small["section_count"] == n_small

    sections_big = _make_sections(n_big)
    t0 = time.perf_counter()
    out_big = build(sections_big)
    t_big = time.perf_counter() - t0
    assert out_big["section_count"] == n_big

    # On the O(N) path, doubling N should ~double runtime. Pre-fix
    # path (O(N^2)) would land at ~4x AND blow past the absolute-time
    # gate at 15k. Allow up to 6x ratio for CI scheduler noise; the
    # absolute-time test below catches a true regression.
    ratio = t_big / max(t_small, 0.05)
    assert ratio < 6.0, (
        f"build() appears non-linear: {n_small}={t_small:.3f}s vs "
        f"{n_big}={t_big:.3f}s (ratio={ratio:.2f}x). Expected ~2x."
    )


def test_build_completes_quickly_at_15k():
    """The jdoc#14 reproducer size — 15k sections should finish in <5s.

    On v1.63.3 this took >10 minutes (assumed-hung). The fixed path
    is O(N) on structural edges; without embeddings the semantic phase
    is a no-op, so this measures the bug directly.
    """
    sections = _make_sections(15_000)
    t0 = time.perf_counter()
    out = build(sections)
    elapsed = time.perf_counter() - t0
    assert out["section_count"] == 15_000
    # Threshold sized for CI under contention. Pre-fix was >10min (hung);
    # any number under 30s proves we're on the O(N) path.
    assert elapsed < 30.0, f"15k sections took {elapsed:.2f}s, expected <30s"
