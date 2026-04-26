"""Weighted section search returning summaries only."""

import time
from typing import Optional

from ..storage import DocStore
from ..storage.token_tracker import estimate_savings, record_savings, cost_avoided


def search_sections(
    repo: str,
    query: str,
    doc_path: Optional[str] = None,
    max_results: int = 10,
    semantic: Optional[bool] = None,
    semantic_only: bool = False,
    semantic_weight: float = 0.5,
    lexical_engine: str = "bm25",
    storage_path: Optional[str] = None,
) -> dict:
    """Search sections with BM25-style lexical + optional semantic fusion.

    Lexical scoring:
      title exact match:    +20
      title substring:      +10
      title word overlap:   +5 per word
      summary match:        +8 (substring), +2 per word
      tag match:            +3 per tag
      content word match:   +1 per word (capped at 5)

    Params:
      semantic:        None (auto — hybrid when embeddings exist), True (force
                       hybrid), False (force lexical-only).
      semantic_only:   Skip lexical; rank purely by embedding cosine similarity.
      semantic_weight: Weight (0.0–1.0) of semantic component in hybrid fusion.
    """
    t0 = time.perf_counter()
    store = DocStore(base_path=storage_path)
    owner, name = store._resolve_repo(repo)
    index = store.load_index(owner, name)

    if not index:
        return {"error": f"Repo not found: {repo}"}

    has_emb = index._has_embeddings()
    if semantic_only:
        mode = "semantic_only" if has_emb else "lexical"
    elif semantic is False:
        mode = "lexical"
    elif has_emb and (semantic is True or semantic is None) and 0.0 < semantic_weight <= 1.0:
        mode = "hybrid"
    else:
        mode = "lexical"

    results = index.search(
        query,
        doc_path=doc_path,
        max_results=max_results,
        semantic=semantic,
        semantic_only=semantic_only,
        semantic_weight=semantic_weight,
        lexical_engine=lexical_engine,
    )

    # Calculate token savings: matched docs full bytes vs summary-only response
    matched_doc_paths = {r.get("doc_path") for r in results}
    raw_bytes = sum(
        len(s.get("content", "").encode("utf-8"))
        for s in index.sections
        if s.get("doc_path") in matched_doc_paths
    )
    response_bytes = sum(len(str(r).encode("utf-8")) for r in results)
    tokens_saved = estimate_savings(raw_bytes, response_bytes)
    total = record_savings(tokens_saved, storage_path)
    ca = cost_avoided(tokens_saved, total)

    latency_ms = int((time.perf_counter() - t0) * 1000)
    meta = {
        "latency_ms": latency_ms,
        "sections_returned": len(results),
        "tokens_saved": tokens_saved,
        "search_mode": mode,
        **ca,
    }
    if mode == "hybrid":
        meta["semantic_weight"] = semantic_weight
    meta["lexical_engine"] = lexical_engine
    if not has_emb and mode == "lexical":
        meta["tip"] = "Re-index with use_embeddings=True for semantic search (better recall on paraphrased queries)"

    return {
        "repo": f"{owner}/{name}",
        "query": query,
        "results": results,
        "result_count": len(results),
        "_meta": meta,
    }
