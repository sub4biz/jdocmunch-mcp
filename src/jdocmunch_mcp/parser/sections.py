"""Section dataclass, ID utilities, slug generation, hash, and content extraction."""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Section:
    """A section of a document, identified by heading hierarchy."""
    id: str              # "repo::doc_path::heading_slug#level"
    repo: str
    doc_path: str
    title: str
    content: str         # Full section text including subsections
    level: int           # 1-6 (heading level); 0 = pre-first-heading root
    parent_id: str       # "" if top-level
    children: list       # child IDs (list[str], but no forward ref)
    byte_start: int = 0
    byte_end: int = 0
    summary: str = ""
    tags: list = field(default_factory=list)
    references: list = field(default_factory=list)
    content_hash: str = ""
    embedding: list = field(default_factory=list)  # semantic embedding vector (empty = not embedded)
    # v1.17.0: extracted fenced code blocks. Each entry:
    #   {"block_id": str, "lang": str, "content": str,
    #    "byte_start": int, "byte_end": int}
    # block_id format: "{section_id}::code#{n}" (n is 0-based per section).
    code_blocks: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        d = {
            "id": self.id,
            "repo": self.repo,
            "doc_path": self.doc_path,
            "title": self.title,
            "level": self.level,
            "parent_id": self.parent_id,
            "children": self.children,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "summary": self.summary,
            "tags": self.tags,
            "references": self.references,
            "content_hash": self.content_hash,
        }
        if self.embedding:
            d["embedding"] = self.embedding
        if self.code_blocks:
            d["code_blocks"] = self.code_blocks
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Section":
        """Deserialize from a dict."""
        return cls(
            id=data["id"],
            repo=data["repo"],
            doc_path=data["doc_path"],
            title=data["title"],
            content=data.get("content", ""),
            level=data["level"],
            parent_id=data.get("parent_id", ""),
            children=data.get("children", []),
            byte_start=data.get("byte_start", 0),
            byte_end=data.get("byte_end", 0),
            summary=data.get("summary", ""),
            tags=data.get("tags", []),
            references=data.get("references", []),
            content_hash=data.get("content_hash", ""),
            embedding=data.get("embedding", []),
            code_blocks=data.get("code_blocks", []),
        )


def slugify(text: str) -> str:
    """Convert heading text to a URL-safe slug.

    Lowercases, replaces non-alphanumeric sequences with hyphens,
    strips leading/trailing hyphens.
    """
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text or "section"


def make_section_id(repo: str, doc_path: str, slug: str, level: int) -> str:
    """Build a stable section ID: {repo}::{doc_path}::{slug}#{level}."""
    return f"{repo}::{doc_path}::{slug}#{level}"


def make_hierarchical_slug(
    heading_text: str,
    heading_level: int,
    slug_stack: list,   # mutable list of (level: int, full_path_slug: str)
    used_slugs: dict,   # mutable collision tracker
) -> str:
    """Compute a stable, hierarchical slug for a heading.

    The slug is prefixed with the ancestor chain so that same-named headings
    under different parents are automatically distinct, e.g.::

        installation/prerequisites    (not just 'prerequisites')
        usage/configuration/advanced  (not just 'advanced')

    This prevents the collision-suffix counter from renumbering when a new
    same-named heading is inserted earlier in the document.

    Mutates ``slug_stack`` and ``used_slugs`` in place.
    Returns the full hierarchical slug to pass to ``make_section_id``.
    """
    # Drop any ancestors at the same or deeper level
    while slug_stack and slug_stack[-1][0] >= heading_level:
        slug_stack.pop()

    parent_path = slug_stack[-1][1] if slug_stack else ""
    leaf = slugify(heading_text)
    full_path = f"{parent_path}/{leaf}" if parent_path else leaf
    full_path = resolve_slug_collision(full_path, used_slugs)

    slug_stack.append((heading_level, full_path))
    return full_path


def resolve_slug_collision(slug: str, used_slugs: dict) -> str:
    """Return a unique slug, appending -2, -3, etc. on collision.

    Args:
        slug: The desired slug.
        used_slugs: Mutable dict mapping slug -> count of uses so far.

    Returns:
        A unique slug. Updates used_slugs in place.
    """
    if slug not in used_slugs:
        used_slugs[slug] = 1
        return slug

    count = used_slugs[slug] + 1
    used_slugs[slug] = count
    candidate = f"{slug}-{count}"
    # Recurse in case the candidate is also taken (unlikely but safe)
    while candidate in used_slugs:
        count += 1
        used_slugs[slug] = count
        candidate = f"{slug}-{count}"
    used_slugs[candidate] = 1
    return candidate


def compute_content_hash(content: str) -> str:
    """SHA-256 of the section content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# --- Reference and Tag Extraction ---

_URL_RE = re.compile(r"https?://[^\s\)\"\']+")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z][A-Za-z0-9_-]*)", re.MULTILINE)


def extract_references(content: str) -> list:
    """Extract URLs and markdown link targets from content."""
    refs = []
    # Markdown links first
    for _, url in _MD_LINK_RE.findall(content):
        if url not in refs:
            refs.append(url)
    # Bare URLs not already captured
    for url in _URL_RE.findall(content):
        if url not in refs:
            refs.append(url)
    return refs


def extract_tags(content: str) -> list:
    """Extract #hashtag style tags from content."""
    return list(dict.fromkeys(_TAG_RE.findall(content)))
