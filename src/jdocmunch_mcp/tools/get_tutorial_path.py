"""get_tutorial_path — reconstruct an ordered tutorial chain (v1.22.0).

A tutorial in real docs is rarely tagged as one — authors thread it via
``Next:`` / ``Previous:`` links, frontmatter ``next:`` / ``prev:`` keys,
or simply ordered filenames (``01-intro.md`` / ``02-setup.md``).

This tool walks any of those signals from a starting section and returns
the linear chain. Three detection strategies, tried in order:

  1. **Frontmatter next/prev** — when the section's owning doc has YAML
     frontmatter with ``next:`` and/or ``prev:`` keys pointing at other
     doc paths.
  2. **Inline Next:/Previous: links** — markdown link lines beginning
     with ``Next:``, ``Next →``, ``Previous:``, or ``← Prev`` whose
     target resolves to another doc in the index.
  3. **Ordered filename prefix** — files named ``NN-name.<ext>`` where
     NN is a 2+ digit prefix; the chain runs in numeric order.

Returns ``{start, chain:[{section_id, doc_path, title}], strategy,
truncated}``. Cycles are broken once a doc repeats. Length cap at 50
keeps pathological inputs bounded.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from ..storage import DocStore

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?\n)---\s*\n", re.DOTALL)
# Matches lines like "Next: [Setup](setup.md)" or "Next →: foo.md".
_NEXT_LINK_RE = re.compile(
    r"^\s*(?:next|→\s*next|next\s*→)\s*[:→]?\s*(?:\[[^\]]*\]\(([^)]+)\)|(\S+\.\w+))",
    re.IGNORECASE | re.MULTILINE,
)
_PREV_LINK_RE = re.compile(
    r"^\s*(?:prev(?:ious)?|←\s*prev|prev\s*←)\s*[:←]?\s*(?:\[[^\]]*\]\(([^)]+)\)|(\S+\.\w+))",
    re.IGNORECASE | re.MULTILINE,
)
_NUMBER_PREFIX_RE = re.compile(r"^(\d{2,})[-_.]")
_MAX_CHAIN = 50


def _frontmatter(text: str) -> dict:
    if not text:
        return {}
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _section_for_doc(doc_path: str, sections: list) -> Optional[dict]:
    """Return the level-1 (or first) section of ``doc_path``."""
    candidates = [s for s in sections if s.get("doc_path") == doc_path]
    if not candidates:
        return None
    candidates.sort(key=lambda s: (s.get("level", 99), s.get("byte_start", 0)))
    return candidates[0]


def _resolve_link(target: str, source_doc: str, doc_paths: set) -> Optional[str]:
    """Resolve a link target against the set of indexed doc paths."""
    if not target:
        return None
    target = target.split("#", 1)[0].strip()
    if not target:
        return None
    # Same-doc anchors are not tutorial links.
    if target in doc_paths:
        return target
    # Relative resolution.
    import posixpath
    src_dir = posixpath.dirname(source_doc.replace("\\", "/"))
    joined = posixpath.normpath(posixpath.join(src_dir, target.replace("\\", "/")))
    if joined in doc_paths:
        return joined
    return None


def _content_of(store, owner: str, name: str, doc_path: str) -> str:
    file_path = store._safe_content_path(store._content_dir(owner, name), doc_path)
    if not file_path or not file_path.exists():
        return ""
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _frontmatter_chain(store, owner: str, name: str, start_doc: str, doc_paths: set) -> list[str]:
    """Walk frontmatter next: links from start_doc forward."""
    chain = [start_doc]
    seen = {start_doc}
    cur = start_doc
    while len(chain) < _MAX_CHAIN:
        text = _content_of(store, owner, name, cur)
        fm = _frontmatter(text)
        nxt = fm.get("next")
        if not isinstance(nxt, str):
            break
        resolved = _resolve_link(nxt, cur, doc_paths)
        if not resolved or resolved in seen:
            break
        chain.append(resolved)
        seen.add(resolved)
        cur = resolved
    return chain if len(chain) > 1 else []


def _inline_link_chain(store, owner: str, name: str, start_doc: str, doc_paths: set) -> list[str]:
    """Walk inline Next:/Previous: links from start_doc forward."""
    chain = [start_doc]
    seen = {start_doc}
    cur = start_doc
    while len(chain) < _MAX_CHAIN:
        text = _content_of(store, owner, name, cur)
        m = _NEXT_LINK_RE.search(text)
        if not m:
            break
        target = m.group(1) or m.group(2)
        resolved = _resolve_link(target or "", cur, doc_paths)
        if not resolved or resolved in seen:
            break
        chain.append(resolved)
        seen.add(resolved)
        cur = resolved
    return chain if len(chain) > 1 else []


def _ordered_filename_chain(start_doc: str, doc_paths: set) -> list[str]:
    """Build the chain from start_doc by ordered numeric filename prefix."""
    import posixpath
    start_norm = start_doc.replace("\\", "/")
    src_dir = posixpath.dirname(start_norm)
    siblings = [
        p for p in doc_paths
        if posixpath.dirname(p.replace("\\", "/")) == src_dir
    ]
    numbered: list[tuple[int, str]] = []
    for p in siblings:
        base = posixpath.basename(p)
        m = _NUMBER_PREFIX_RE.match(base)
        if m:
            numbered.append((int(m.group(1)), p))
    if len(numbered) < 2:
        return []
    numbered.sort()
    ordered_paths = [p for _, p in numbered]
    if start_norm not in ordered_paths:
        return []
    start_idx = ordered_paths.index(start_norm)
    return ordered_paths[start_idx:]


def get_tutorial_path(
    repo: str,
    section_id: str,
    storage_path: Optional[str] = None,
) -> dict:
    t0 = time.perf_counter()
    store = DocStore(base_path=storage_path)
    owner, name = store._resolve_repo(repo)
    index = store.load_index(owner, name)
    if not index:
        return {"error": f"Repo not found: {repo}"}

    sec = index.get_section(section_id)
    if not sec:
        return {"error": f"Section not found: {section_id}"}

    start_doc = sec.get("doc_path", "")
    if not start_doc:
        return {"error": "Section has no doc_path"}

    doc_paths_set = set(index.doc_paths)

    chain_paths: list[str] = []
    strategy = "none"
    for fn, label in (
        (_frontmatter_chain, "frontmatter"),
        (_inline_link_chain, "inline_link"),
    ):
        result = fn(store, owner, name, start_doc, doc_paths_set)
        if result:
            chain_paths = result
            strategy = label
            break
    if not chain_paths:
        result = _ordered_filename_chain(start_doc, doc_paths_set)
        if result:
            chain_paths = result
            strategy = "ordered_filename"

    chain: list[dict] = []
    for dp in chain_paths:
        s = _section_for_doc(dp, index.sections)
        if not s:
            continue
        chain.append(
            {
                "section_id": s.get("id"),
                "doc_path": dp,
                "title": s.get("title", ""),
            }
        )

    return {
        "repo": f"{owner}/{name}",
        "start": {"section_id": section_id, "doc_path": start_doc},
        "chain": chain,
        "strategy": strategy,
        "truncated": len(chain_paths) >= _MAX_CHAIN,
        "_meta": {
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "chain_length": len(chain),
        },
    }
