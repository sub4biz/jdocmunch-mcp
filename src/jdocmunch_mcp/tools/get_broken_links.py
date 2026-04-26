"""get_broken_links tool: Detect internal cross-references that no longer resolve."""

import os
import posixpath
import re
import time
from typing import Optional

from ..storage import DocStore

# Links that start with these are external — skip them
_EXTERNAL_SCHEMES = ("http://", "https://", "ftp://", "mailto:", "tel:")

# RST cross-reference patterns: :ref:`target`, :doc:`target`
_RST_REF_RE = re.compile(r":(?:ref|doc):`([^`]+)`")

# RST explicit hyperlink targets: `text <target>`_
_RST_HYPERLINK_RE = re.compile(r"`[^`]+\s+<([^>]+)>`_")


def _is_external(href: str) -> bool:
    return any(href.startswith(s) for s in _EXTERNAL_SCHEMES)


def _split_href(href: str) -> tuple:
    """Split href into (file_part, anchor_part). Either may be empty string."""
    if "#" in href:
        file_part, anchor = href.split("#", 1)
    else:
        file_part, anchor = href, ""
    return file_part.strip(), anchor.strip()


def _resolve_file_path(source_doc: str, target_file: str) -> str:
    """Resolve a relative link target against the source document's directory.

    source_doc: e.g.  'docs/guide/install.md'
    target_file: e.g. '../api.md'
    Returns: normalized path like 'docs/api.md'
    """
    if target_file.startswith("/"):
        # Absolute path within the repo root
        return target_file.lstrip("/")
    source_dir = posixpath.dirname(source_doc.replace("\\", "/"))
    joined = posixpath.join(source_dir, target_file.replace("\\", "/"))
    return posixpath.normpath(joined)


def _anchor_matches_section(anchor: str, doc_path: str, sections: list) -> bool:
    """Return True if any section in doc_path has a slug matching the anchor.

    Comparison is case-insensitive but preserves hyphens and underscores —
    'foo-bar' must NOT match 'foobar'. The hierarchical slug stored in the
    section ID (e.g. ``installation/prerequisites``) is canonical; anchors
    typically reference only the leaf, so we accept either the full path or
    the trailing path segment.
    """
    target = anchor.strip().lower()
    if not target:
        return False
    for sec in sections:
        if sec.get("doc_path") != doc_path:
            continue
        # Section ID format: repo::doc_path::slug#level
        raw_id = sec.get("id", "")
        slug_part = raw_id.split("::")[-1].split("#")[0] if "::" in raw_id else ""
        slug_lower = slug_part.lower()
        if slug_lower == target:
            return True
        # Hierarchical slugs encode ancestor chain ('install/prereqs'); accept the leaf.
        leaf = slug_lower.rsplit("/", 1)[-1]
        if leaf == target:
            return True
        # Also accept the title rendered through the same slugify rules used at parse time.
        from ..parser.sections import slugify
        if slugify(sec.get("title", "")) == target:
            return True
    return False


def get_broken_links(
    repo: str,
    storage_path: Optional[str] = None,
) -> dict:
    """Scan indexed doc files for internal cross-references that no longer resolve.

    Checks:
    - Markdown links [text](target) with relative file paths
    - RST :ref: and :doc: directives
    - Anchor-only links (#heading) within the same doc

    External links (http/https/mailto) are skipped.
    Output: list of {source_file, source_section, source_section_id, target, reason}
    """
    t0 = time.perf_counter()
    store = DocStore(base_path=storage_path)
    owner, name = store._resolve_repo(repo)
    index = store.load_index(owner, name)

    if not index:
        return {"error": f"Repo not found: {repo}"}

    doc_path_set = set(index.doc_paths)
    sections = index.sections
    broken: list = []

    for sec in sections:
        source_doc = sec.get("doc_path", "")
        sec_id = sec.get("id", "")
        sec_title = sec.get("title", "")
        refs = sec.get("references", [])

        # Collect internal refs from the stored references list
        internal_refs = [r for r in refs if r and not _is_external(r)]

        # Also scan content for RST patterns if content is present
        content = sec.get("content", "")
        if content:
            for m in _RST_REF_RE.finditer(content):
                ref = m.group(1).strip()
                if not _is_external(ref) and ref not in internal_refs:
                    internal_refs.append(ref)
            for m in _RST_HYPERLINK_RE.finditer(content):
                ref = m.group(1).strip()
                if not _is_external(ref) and ref not in internal_refs:
                    internal_refs.append(ref)

        for href in internal_refs:
            file_part, anchor = _split_href(href)

            # Anchor-only link (e.g. #installation): relative to the current document
            if not file_part and anchor:
                if not _anchor_matches_section(anchor, source_doc, sections):
                    broken.append({
                        "source_file": source_doc,
                        "source_section": sec_title,
                        "source_section_id": sec_id,
                        "target": href,
                        "reason": "anchor_not_found",
                    })
                continue

            # Skip non-file refs (bare words like "external-project", RST directives without paths)
            if not file_part:
                continue

            # Skip things that look like mailto: or protocol:// but weren't caught above
            if ":" in file_part and not file_part.startswith("."):
                continue

            resolved = _resolve_file_path(source_doc, file_part)

            if resolved not in doc_path_set:
                broken.append({
                    "source_file": source_doc,
                    "source_section": sec_title,
                    "source_section_id": sec_id,
                    "target": href,
                    "reason": "file_not_found",
                })
                continue

            # File exists; now check anchor if present
            if anchor and not _anchor_matches_section(anchor, resolved, sections):
                broken.append({
                    "source_file": source_doc,
                    "source_section": sec_title,
                    "source_section_id": sec_id,
                    "target": href,
                    "reason": "section_not_found",
                })

    return {
        "result": {
            "repo": f"{owner}/{name}",
            "docs_scanned": len(doc_path_set),
            "sections_scanned": len(sections),
            "broken_link_count": len(broken),
            "broken_links": broken,
        },
        "_meta": {
            "timing_ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    }
