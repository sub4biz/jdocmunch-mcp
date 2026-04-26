"""find_code_examples — search fenced code blocks across the index (v1.17.0).

This is the differentiator: most doc-retrieval tools treat code as opaque
prose. jdocmunch indexes each fenced block as a first-class addressable
unit (byte_range + lang + parent section), so an agent can ask "show me
Python install examples" and get the literal block — not the surrounding
narrative.

Scoring is BM25 over the code body, with a tag-style boost when the lang
matches an explicit ``lang`` filter. Snippet returned is the first ~400
chars of the block body (single-line collapse for compact display).

Returns one dict per block: {block_id, section_id, doc_path, lang,
title, snippet, score}.
"""

from __future__ import annotations

import time
from typing import Optional

from ..retrieval.bm25 import _bm25_field, FIELD_WEIGHTS
from ..retrieval.tokenize import tokenize
from ..storage import DocStore


def _snippet(text: str, n: int = 400) -> str:
    if not text:
        return ""
    out = text[:n]
    if len(text) > n:
        out += "..."
    return out


def find_code_examples(
    repo: str,
    query: str,
    lang: Optional[str] = None,
    max_results: int = 10,
    storage_path: Optional[str] = None,
) -> dict:
    """Search code blocks in the indexed repo by BM25 over the block content.

    Args:
        repo: Repository identifier (owner/repo or bare name).
        query: Free-form query; tokens scored against the code body.
        lang: Optional case-insensitive filter (e.g. "python", "bash").
        max_results: Cap on returned blocks (default 10).
        storage_path: Override DOC_INDEX_PATH for testing.
    """
    t0 = time.perf_counter()
    store = DocStore(base_path=storage_path)
    owner, name = store._resolve_repo(repo)
    index = store.load_index(owner, name)
    if not index:
        return {"error": f"Repo not found: {repo}"}

    query_terms = tokenize(query)
    if not query_terms:
        return {
            "repo": f"{owner}/{name}",
            "query": query,
            "results": [],
            "_meta": {
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "result_count": 0,
                "reason": "empty_query_after_tokenization",
            },
        }

    # Build a synthetic per-block stats block so length normalization on
    # code-block bodies is meaningful — we only have the blocks visible
    # right now, not all blocks across all sections, so use a single-pass
    # estimate.
    block_records: list = []
    avg_dl = 0.0
    for sec in index.sections:
        for blk in sec.get("code_blocks", []) or []:
            blk_lang = (blk.get("lang") or "").strip().lower()
            if lang and blk_lang != lang.strip().lower():
                continue
            tokens = tokenize(blk.get("content", "") or "")
            if not tokens:
                continue
            block_records.append(
                {
                    "section": sec,
                    "block": blk,
                    "tokens": tokens,
                    "dl": len(tokens),
                }
            )
            avg_dl += len(tokens)
    n = len(block_records)
    if n == 0:
        return {
            "repo": f"{owner}/{name}",
            "query": query,
            "results": [],
            "_meta": {
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "result_count": 0,
                "reason": "no_code_blocks_for_filter",
                "lang_filter": lang,
            },
        }
    avg_dl /= n if n else 1

    # Cheap doc-frequency over the visible block set.
    df: dict[str, int] = {}
    for rec in block_records:
        for term in set(rec["tokens"]):
            df[term] = df.get(term, 0) + 1

    scored: list = []
    for rec in block_records:
        score = _bm25_field(
            query_terms,
            rec["block"].get("content", ""),
            avg_dl,
            df,
            n,
        )
        if score > 0:
            scored.append((score, rec))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, rec in scored[:max_results]:
        sec = rec["section"]
        blk = rec["block"]
        results.append(
            {
                "block_id": blk.get("block_id", ""),
                "section_id": sec.get("id", ""),
                "doc_path": sec.get("doc_path", ""),
                "title": sec.get("title", ""),
                "lang": blk.get("lang", ""),
                "byte_start": blk.get("byte_start", 0),
                "byte_end": blk.get("byte_end", 0),
                "snippet": _snippet(blk.get("content", "")),
                "_score": float(score),
            }
        )

    return {
        "repo": f"{owner}/{name}",
        "query": query,
        "results": results,
        "_meta": {
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "result_count": len(results),
            "lang_filter": lang,
            "blocks_scanned": n,
        },
    }
