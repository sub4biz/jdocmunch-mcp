"""Surface sections drifting from index state (v1.47.0).

The v1.16 FreshnessProbe classifies every section into ``fresh``,
``edited_uncommitted``, or ``stale_index`` buckets. `get_doc_health`
exposes the *counts*. `get_stale_pages` lists pages whose source has
diverged. Neither returns the actual section list of recently-edited
sections without re-running search_sections.

This tool walks every section through FreshnessProbe and returns the
ones in the non-fresh buckets — a pre-flight check before deciding
whether to re-index.
"""

from __future__ import annotations

import time
from typing import Optional

from ..retrieval.freshness import FreshnessProbe
from ..storage import DocStore


def get_recent_changes(
    repo: str,
    include_stale: bool = True,
    include_edited: bool = True,
    storage_path: Optional[str] = None,
) -> dict:
    """Return sections whose source has drifted since indexing.

    Args:
        repo: Repository identifier.
        include_stale: Surface sections in ``stale_index`` bucket
            (this section's byte range no longer hashes the same).
            Default True.
        include_edited: Surface sections in ``edited_uncommitted``
            bucket (file's full-file hash diverged but this section's
            range still matches). Default True.
        storage_path: Custom storage path.

    Returns:
        ``{repo, changes: [{id, title, doc_path, level, freshness},
        ...], change_count, by_bucket: {edited_uncommitted: N,
        stale_index: M}, total_sections, _meta}``. Sorted by
        ``(doc_path, byte_start)`` for stable output.
    """
    t0 = time.perf_counter()
    store = DocStore(base_path=storage_path)
    owner, name = store._resolve_repo(repo)
    index = store.load_index(owner, name)

    if not index:
        return {"error": f"Repo not found: {repo}"}

    probe = FreshnessProbe(store, owner, name, index)
    by_bucket = {"edited_uncommitted": 0, "stale_index": 0}
    changes: list = []
    for sec in index.sections:
        bucket = probe.annotate(dict(sec))  # don't mutate the source dict
        if bucket == "fresh":
            continue
        if bucket == "stale_index" and not include_stale:
            continue
        if bucket == "edited_uncommitted" and not include_edited:
            continue
        if bucket in by_bucket:
            by_bucket[bucket] += 1
        # Skip synthetic level-0 doc-roots (parser artifact).
        if sec.get("level") == 0:
            continue
        changes.append({
            "id": sec.get("id"),
            "title": sec.get("title"),
            "doc_path": sec.get("doc_path"),
            "level": sec.get("level"),
            "freshness": bucket,
        })

    changes.sort(key=lambda r: (r.get("doc_path", ""), r.get("id", "")))

    return {
        "repo": f"{owner}/{name}",
        "changes": changes,
        "change_count": len(changes),
        "by_bucket": by_bucket,
        "total_sections": len(index.sections),
        "_meta": {
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "include_stale": include_stale,
            "include_edited": include_edited,
            "indexed_at": index.indexed_at,
        },
    }
