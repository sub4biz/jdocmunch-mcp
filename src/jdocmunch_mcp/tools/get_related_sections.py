"""get_related_sections — retrieve structural and/or semantic neighbors (v2.0.0)."""

from __future__ import annotations

import time
from typing import Optional

from ..retrieval.related import get_related
from ..storage import DocStore


def get_related_sections(
    repo: str,
    section_id: str,
    mode: str = "both",
    top_n: int = 5,
    min_score: float = 0.6,
    max_per_kind: int = 10,
    storage_path: Optional[str] = None,
) -> dict:
    """Return related sections for ``section_id``.

    ``mode`` ∈ {"structural", "semantic", "both"} (default both).
    Semantic neighbors require an index built with embeddings; absent
    that, the semantic list is empty and a hint is emitted.
    """
    t0 = time.perf_counter()
    if mode not in ("structural", "semantic", "both"):
        return {"error": f"Unknown mode: {mode!r}. Use 'structural', 'semantic', or 'both'."}

    store = DocStore(base_path=storage_path)
    owner, name = store._resolve_repo(repo)
    index = store.load_index(owner, name)
    if not index:
        return {"error": f"Repo not found: {repo}"}

    target = index.get_section(section_id)
    if not target:
        return {"error": f"Section not found: {section_id}"}

    out = get_related(
        index.sections,
        section_id,
        mode=mode,
        top_n=top_n,
        min_score=min_score,
        max_per_kind=max_per_kind,
    )

    meta: dict = {
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "structural_count": len(out.get("structural", [])),
        "semantic_count": len(out.get("semantic", [])),
        "mode": mode,
    }
    if mode in ("semantic", "both") and not index._has_embeddings():
        meta["hint"] = (
            "Semantic neighbors require embeddings. Re-index with use_embeddings=True "
            "or set GOOGLE_API_KEY / OPENAI_API_KEY."
        )

    return {
        "repo": f"{owner}/{name}",
        "section_id": section_id,
        "title": target.get("title", ""),
        "structural": out.get("structural", []),
        "semantic": out.get("semantic", []),
        "_meta": meta,
    }
