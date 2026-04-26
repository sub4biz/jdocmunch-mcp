"""MCP server for jdocmunch-mcp."""

import argparse
import asyncio
import json
import os
import sys
import traceback
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource

from .tools.index_local import index_local
from .tools.index_repo import index_repo
from .tools.list_repos import list_repos
from .tools.get_toc import get_toc
from .tools.get_toc_tree import get_toc_tree
from .tools.get_document_outline import get_document_outline
from .tools.search_sections import search_sections
from .tools.get_section import get_section
from .tools.get_sections import get_sections
from .tools.get_section_context import get_section_context
from .tools.section_neighbors import section_neighbors
from .tools.get_section_summary import get_section_summary
from .tools.get_orphan_sections import get_orphan_sections
from .tools.get_section_path import get_section_path
from .tools.delete_index import delete_index
from .tools.get_broken_links import get_broken_links
from .tools.get_doc_coverage import get_doc_coverage
from .tools.get_backlinks import get_backlinks
from .tools.get_stale_pages import get_stale_pages
from .tools.get_wiki_stats import get_wiki_stats
from .tools.analyze_perf import analyze_perf
from .tools.get_session_stats import get_session_stats
from .tools.check_embedding_drift import check_embedding_drift
from .tools.find_code_examples import find_code_examples
from .tools.link_code_to_symbols import link_code_to_symbols
from .tools.openapi_tools import (
    find_endpoint,
    list_endpoints_by_tag,
    find_operations_using_schema,
    get_schema_graph,
)
from .tools.glossary_tools import lookup_term, list_terms
from .tools.get_related_sections import get_related_sections
from .tools.get_section_diff import get_section_diff
from .tools.get_doc_health import get_doc_health
from .tools.get_tutorial_path import get_tutorial_path
from .tools.get_undocumented_symbols import get_undocumented_symbols
from .tools.tune_weights import tune_weights
from .tools.repo_group_tools import list_repo_groups, define_repo_group
from .tools.verify_index import verify_index


server = Server("jdocmunch-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="index_local",
            description="Index a local folder containing documentation files (.md, .txt, .rst). Parses by heading hierarchy into sections for efficient retrieval. Embeddings auto-enable when a provider is configured (GOOGLE_API_KEY, OPENAI_API_KEY, or sentence-transformers).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to local folder (absolute or relative, supports ~ for home directory)"
                    },
                    "use_ai_summaries": {
                        "type": "boolean",
                        "description": "Use AI to generate section summaries (requires ANTHROPIC_API_KEY or GOOGLE_API_KEY). When false, uses heading text.",
                        "default": True
                    },
                    "use_embeddings": {
                        "description": "Generate semantic embeddings for each section, enabling hybrid (BM25+semantic) search. true/false/\"auto\". \"auto\" (default) enables embeddings when an embedding provider is configured (GOOGLE_API_KEY, OPENAI_API_KEY, or sentence-transformers installed).",
                        "default": "auto"
                    },
                    "extra_ignore_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional gitignore-style patterns to exclude from indexing"
                    },
                    "follow_symlinks": {
                        "type": "boolean",
                        "description": "Whether to follow symlinks. Default false for security.",
                        "default": False
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum number of doc files to index. Raise this for large doc trees. Default 500.",
                        "default": 500
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional repo identifier override. Use this when two folders share the same name (e.g. both named 'docs'). If omitted, the folder name is used. Example: 'requests-docs', 'flask-docs'."
                    },
                    "incremental": {
                        "type": "boolean",
                        "description": "When true (default), only re-index files that changed since the last index. Set to false to force a full re-index.",
                        "default": True
                    },
                    "autotune": {
                        "type": "boolean",
                        "description": "v1.29+ — when true, runs tune_weights against accumulated ranking events at the end of indexing. No-op when telemetry isn't enabled.",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="doc_index_repo",
            description="Index a GitHub repository's documentation. Fetches .md/.txt files, parses sections, and saves to local storage. Embeddings auto-enable when a provider is configured (GOOGLE_API_KEY, OPENAI_API_KEY, or sentence-transformers).",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "GitHub repository URL or owner/repo string"
                    },
                    "use_ai_summaries": {
                        "type": "boolean",
                        "description": "Use AI to generate section summaries.",
                        "default": True
                    },
                    "use_embeddings": {
                        "description": "Generate semantic embeddings for each section. true/false/\"auto\". \"auto\" (default) enables embeddings when an embedding provider is configured.",
                        "default": "auto"
                    },
                    "incremental": {
                        "type": "boolean",
                        "description": "When true (default), skip all HTTP fetches if the HEAD commit SHA is unchanged; otherwise only re-index changed files. Set to false to force a full re-index.",
                        "default": True
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="doc_list_repos",
            description="List all indexed documentation repositories.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_toc",
            description="Get a flat table of contents for all sections in a repo, sorted by document order. Content is excluded — use get_section to retrieve content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "path_glob": {
                        "type": "string",
                        "description": "v1.36+ — fnmatch glob restricting results to matching doc_paths (e.g. 'api/**/*.md', 'reference/*'). Default: no filter."
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_toc_tree",
            description="Get a nested table of contents tree per document. Shows parent/child heading relationships. Content is excluded.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "path_glob": {
                        "type": "string",
                        "description": "v1.36+ — fnmatch glob restricting results to matching doc_paths. Default: no filter."
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_document_outline",
            description="Get the section hierarchy for a single document file, without content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier"
                    },
                    "doc_path": {
                        "type": "string",
                        "description": "Path to the document within the repository (e.g., 'README.md')"
                    }
                },
                "required": ["repo", "doc_path"]
            }
        ),
        Tool(
            name="search_sections",
            description="Search sections by relevance. Hybrid (BM25 lexical + semantic embedding) fusion when the index was built with use_embeddings=true; falls back to lexical-only otherwise. Returns summaries only — use get_section for full content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "doc_path": {
                        "type": "string",
                        "description": "Optional: limit search to a specific document"
                    },
                    "path_glob": {
                        "type": "string",
                        "description": "v1.36+ — fnmatch glob restricting results to matching doc_paths (e.g. 'api/**/*.md'). Stacks with doc_path."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10
                    },
                    "semantic": {
                        "type": "boolean",
                        "description": "null/omit (auto — hybrid when embeddings exist), true (force hybrid), false (force lexical-only). Zero performance cost when the index has no embeddings."
                    },
                    "semantic_only": {
                        "type": "boolean",
                        "description": "Skip lexical scoring; rank purely by embedding cosine similarity.",
                        "default": False
                    },
                    "semantic_weight": {
                        "type": "number",
                        "description": "Weight (0.0–1.0) of semantic component in hybrid fusion. Lexical gets 1 - weight. Default 0.5.",
                        "default": 0.5
                    },
                    "role": {
                        "type": "string",
                        "description": "Optional v1.19+ role filter. Values: concept, tutorial, how_to, reference, api, example, troubleshooting, changelog, faq, other."
                    },
                    "profile": {
                        "type": "string",
                        "enum": ["install", "debug", "explain", "api"],
                        "description": "v1.32+ — task-aware retrieval profile. install/debug/explain/api each boost a small role set so matching sections rank ahead. Explicit role= overrides."
                    },
                    "dedupe": {
                        "type": "boolean",
                        "default": False,
                        "description": "v1.34+ — collapse near-duplicate sections to a single representative based on the v1.34 cluster sidecar. _meta.deduped reports suppressed member ids."
                    },
                    "repo_group": {
                        "type": "string",
                        "description": "v1.26+ — fan out across the named repo group (defined via define_repo_group). When set, the per-repo `repo` arg is ignored; results from each member repo are fused via RRF."
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_section",
            description="Retrieve the full content of a specific section using byte-range reads. Use after identifying section IDs via search_sections or get_toc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier"
                    },
                    "section_id": {
                        "type": "string",
                        "description": "Section ID from get_toc, search_sections, or get_document_outline"
                    },
                    "verify": {
                        "type": "boolean",
                        "description": "Verify content hash matches stored hash (detects source drift)",
                        "default": False
                    },
                    "strip_boilerplate": {
                        "type": "boolean",
                        "description": "v1.24+ — when true, suppress repeated cross-section fragments (footers, nav, license headers) before returning content.",
                        "default": False
                    },
                    "compress_code": {
                        "type": "boolean",
                        "description": "v1.35+ — when true, drop blank lines and full-line comments inside fenced code blocks before returning. _meta.code_compressed_bytes reports bytes saved.",
                        "default": False
                    }
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="get_sections",
            description="Batch content retrieval for multiple sections in one call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier"
                    },
                    "section_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of section IDs to retrieve"
                    },
                    "verify": {
                        "type": "boolean",
                        "description": "Verify content hashes",
                        "default": False
                    },
                    "strip_boilerplate": {
                        "type": "boolean",
                        "description": "v1.24+ — strip repeated cross-section fragments per section before returning.",
                        "default": False
                    },
                    "compress_code": {
                        "type": "boolean",
                        "description": "v1.35+ — drop blank lines and full-line comments inside fenced code blocks before returning. _meta.code_compressed_bytes reports total bytes saved.",
                        "default": False
                    }
                },
                "required": ["repo", "section_ids"]
            }
        ),
        Tool(
            name="get_section_context",
            description="Retrieve a section with its full hierarchy context: ancestor headings (root → parent) for orientation, the target section's content, and immediate child summaries. Prevents 'section too thin' without falling back to whole-file reads.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "section_id": {
                        "type": "string",
                        "description": "Target section ID from get_toc, search_sections, etc."
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Approximate token budget for the target section's content (bytes/4 estimate). Ancestors and child summaries are always included.",
                        "default": 2000
                    },
                    "include_children": {
                        "type": "boolean",
                        "description": "Include immediate child section summaries (no content reads). Default true.",
                        "default": True
                    },
                    "include_related": {
                        "type": "boolean",
                        "description": "v1.20+ adaptive context: append structural + semantic neighbor summaries.",
                        "default": False
                    },
                    "strip_boilerplate": {
                        "type": "boolean",
                        "description": "v1.24+ — strip repeated cross-section fragments before returning the target section content.",
                        "default": False
                    }
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="section_neighbors",
            description="v1.37+ — return prev/next siblings (in document order), parent, and first child for a section. Handles only (id, title, level, doc_path) — no content. Use for fast sequential navigation without re-querying search_sections.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "section_id": {
                        "type": "string",
                        "description": "Target section ID from get_toc, search_sections, etc."
                    }
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="get_section_path",
            description="v1.40+ — return the breadcrumb chain (root → ... → target) for a section_id. Walks parent_id upward; cycle-protected. Handles only ({id, title, level, doc_path}) per step plus depth.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "section_id": {
                        "type": "string",
                        "description": "Target section ID from get_toc, search_sections, etc."
                    }
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="get_orphan_sections",
            description="v1.39+ — list sections whose doc_path receives zero inbound references from any other doc. Companion to get_broken_links and get_stale_pages: documentation that exists but nobody links to.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "include_same_doc": {
                        "type": "boolean",
                        "description": "If true, count intra-document anchor links as inbound (e.g. a TOC at the top of a page). Default false — only cross-document references count.",
                        "default": False
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_section_summary",
            description="v1.38+ — return full indexed metadata (title, summary, role, tags, metadata, parent_id, children, content_hash, byte_start/end, byte_length) for one section without fetching content. Use to inspect role/tags before deciding whether to read the content via get_section.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "section_id": {
                        "type": "string",
                        "description": "Target section ID from get_toc, search_sections, etc."
                    }
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="delete_index",
            description="Remove a repo index and its cached raw files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_broken_links",
            description=(
                "Scan indexed doc files for internal cross-references that no longer resolve. "
                "Checks markdown links, RST :ref:/:doc: directives, and anchor-only links (#heading). "
                "External links (http/https) are skipped. "
                "Output: list of {source_file, source_section, target, reason} where reason is "
                "'file_not_found', 'section_not_found', or 'anchor_not_found'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_doc_coverage",
            description=(
                "Check which jcodemunch symbols have matching documentation in this doc index. "
                "Given a list of jcodemunch symbol IDs, reports which symbols are mentioned in "
                "section titles (documented) vs absent (undocumented). "
                "Bridges jcodemunch <-> jdocmunch. symbol_ids capped at 200. "
                "Output: {documented, undocumented, coverage_pct}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Doc repo identifier (owner/repo or just repo name)"
                    },
                    "symbol_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of jcodemunch symbol IDs to check coverage for"
                    }
                },
                "required": ["repo", "symbol_ids"]
            }
        ),
        Tool(
            name="get_backlinks",
            description=(
                "Find all sections that link TO a given document (inverse reference graph). "
                "Useful for the LLM Wiki pattern: when a source changes, find which wiki pages reference it. "
                "Output: list of {source_file, source_section, source_section_id, link}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "doc_path": {
                        "type": "string",
                        "description": "Target document path to find backlinks for (e.g., 'raw/article.md' or 'wiki/concepts/auth.md')"
                    }
                },
                "required": ["repo", "doc_path"]
            }
        ),
        Tool(
            name="get_stale_pages",
            description=(
                "Find wiki pages whose declared sources have been modified on disk. "
                "Convention: wiki pages include YAML frontmatter with a 'sources' list of relative paths "
                "to raw source files. This tool checks whether those source files have changed since the "
                "page was last indexed. Output: list of {doc_path, title, stale_sources} where each "
                "stale source has a reason: 'modified', 'missing', or 'untracked'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    },
                    "sources_dir": {
                        "type": "string",
                        "description": "Base directory for resolving relative source paths. If omitted, uses the index's source_root."
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_wiki_stats",
            description=(
                "Wiki health dashboard. Returns: orphan pages (zero inbound internal links), "
                "most-linked pages (top 10), tag distribution, total internal link count, "
                "and sections-per-doc min/max/avg. Use for periodic wiki lint checks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "Repository identifier (owner/repo or just repo name)"
                    }
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="analyze_perf",
            description=(
                "Per-tool latency analysis. window='session' reads the in-memory ring "
                "(last 512 calls per tool — always available); window='1h'|'24h'|'7d'|'all' "
                "reads the persistent SQLite sink at ~/.doc-index/telemetry.db (opt-in via "
                "JDOCMUNCH_PERF_TELEMETRY=1). Returns {window, telemetry_enabled, source, "
                "per_tool:{tool:{count,p50_ms,p95_ms,max_ms,errors,error_rate}}}."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "enum": ["session", "1h", "24h", "7d", "all"],
                        "default": "session",
                        "description": "Time window. 'session' uses the in-memory ring; longer windows require JDOCMUNCH_PERF_TELEMETRY=1."
                    }
                }
            }
        ),
        Tool(
            name="get_session_stats",
            description=(
                "Session self-monitor: returns {latency_per_tool, total_tokens_saved}. "
                "Lightweight; reads the in-memory latency ring + persistent savings counter. "
                "For windowed analysis use analyze_perf."
            ),
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="find_code_examples",
            description=(
                "Search fenced code blocks across the indexed docs by BM25 over the block "
                "content. Returns one row per block with {block_id, section_id, doc_path, "
                "title, lang, byte_start, byte_end, snippet, _score}. Optional lang filter "
                "(e.g. 'python', 'bash'). Use after index_local; requires INDEX_VERSION>=3."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "jdocmunch repo identifier"},
                    "query": {"type": "string", "description": "Free-form code-content query"},
                    "lang": {"type": "string", "description": "Optional case-insensitive language filter"},
                    "max_results": {"type": "integer", "default": 10}
                },
                "required": ["repo", "query"]
            }
        ),
        Tool(
            name="link_code_to_symbols",
            description=(
                "Best-effort bridge from doc code blocks to jcodemunch code symbols. "
                "For each block, tokenizes identifiers and looks them up via "
                "jcodemunch's search_symbols. Returns {by_block, by_symbol, _meta} where "
                "_meta.bridge_available reports whether jcodemunch-mcp is importable."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "jdocmunch repo identifier"},
                    "code_repo": {"type": "string", "description": "jcodemunch repo identifier"},
                    "max_examples": {"type": "integer", "default": 200},
                    "max_symbols_per_block": {"type": "integer", "default": 5}
                },
                "required": ["repo", "code_repo"]
            }
        ),
        Tool(
            name="find_endpoint",
            description=(
                "Find OpenAPI operations by path glob, method, and/or tag. All filters AND'd. "
                "Returns one row per match with {section_id, doc_path, method, path, "
                "operationId, summary, tags, deprecated}. Requires the spec to have been "
                "indexed under v1.18+ so structured metadata is present."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "path": {"type": "string", "description": "fnmatch glob (e.g. '/pets/*'); case-sensitive"},
                    "method": {"type": "string", "description": "HTTP method; case-insensitive"},
                    "tag": {"type": "string", "description": "Exact tag match"}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="list_endpoints_by_tag",
            description=(
                "Return every operation whose tags list contains the given tag (exact). "
                "Convenience wrapper around find_endpoint with only a tag filter."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "tag": {"type": "string"}
                },
                "required": ["repo", "tag"]
            }
        ),
        Tool(
            name="find_operations_using_schema",
            description=(
                "Return every operation whose request body or any response references the "
                "given schema. Each row gets a referenced_in list of all schema names that "
                "operation pulls in (so you can see the broader dependency cluster)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "schema_name": {"type": "string"}
                },
                "required": ["repo", "schema_name"]
            }
        ),
        Tool(
            name="get_schema_graph",
            description=(
                "BFS walk of the schema reference graph from a root schema name. Returns "
                "{root, nodes:{name:{type, properties, required, refs}}, edges:[[from, to]], "
                "unresolved}. max_depth bounds the walk (default 5)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "schema_name": {"type": "string"},
                    "max_depth": {"type": "integer", "default": 5}
                },
                "required": ["repo", "schema_name"]
            }
        ),
        Tool(
            name="lookup_term",
            description=(
                "Glossary lookup. Returns every entry whose term equals the query (case-"
                "insensitive, exact). Glossary entries are extracted at index time from "
                "**Term** — definition Markdown patterns and RST .. glossary:: blocks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "term": {"type": "string"}
                },
                "required": ["repo", "term"]
            }
        ),
        Tool(
            name="list_terms",
            description=(
                "List glossary terms in alphabetical order, optionally filtered by prefix. "
                "Capped at max_results (default 100)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "prefix": {"type": "string"},
                    "max_results": {"type": "integer", "default": 100}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_related_sections",
            description=(
                "v2.0+ related-section graph. Returns structural neighbors (siblings, "
                "children, parent, optional cousins) and semantic neighbors (top-N "
                "cosine over stored embeddings, score >= min_score). mode: structural "
                "| semantic | both."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "section_id": {"type": "string"},
                    "mode": {"type": "string", "enum": ["structural", "semantic", "both"], "default": "both"},
                    "top_n": {"type": "integer", "default": 5},
                    "min_score": {"type": "number", "default": 0.6},
                    "max_per_kind": {"type": "integer", "default": 10}
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="get_section_diff",
            description=(
                "Unified diff between the indexed snapshot and the current on-disk byte "
                "range for a section. Returns hashes + diff text; identical=true when "
                "the section is in sync with disk."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "section_id": {"type": "string"}
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="get_doc_health",
            description=(
                "One-shot index health diagnostics. Returns section_count, doc_count, "
                "role_distribution, freshness counts, broken_link_count, drift status, "
                "BM25 corpus sanity, and embedding coverage."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="get_tutorial_path",
            description=(
                "Reconstruct an ordered tutorial chain starting from section_id. Detects "
                "frontmatter next:/prev: keys, inline 'Next:' / 'Previous:' markdown links, "
                "or ordered numeric filename prefixes (01-intro.md). Returns chain[] of "
                "{section_id, doc_path, title} plus the strategy used."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "section_id": {"type": "string"}
                },
                "required": ["repo", "section_id"]
            }
        ),
        Tool(
            name="get_undocumented_symbols",
            description=(
                "Best-effort inverse coverage: enumerate symbols in the jcodemunch code_repo "
                "and return those whose name (or qualified name) does not appear anywhere in "
                "this doc index. _meta.bridge_available=false when jcodemunch-mcp is not "
                "importable in this environment."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "code_repo": {"type": "string"},
                    "max_symbols": {"type": "integer", "default": 1000}
                },
                "required": ["repo", "code_repo"]
            }
        ),
        Tool(
            name="list_repo_groups",
            description=(
                "List defined repo groups (v1.26+). Each group is a named alias for a "
                "set of indexed repos that search_sections can fan out across via the "
                "repo_group kwarg."
            ),
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="define_repo_group",
            description=(
                "Create, replace, or delete a repo group (v1.26+). Empty repos list "
                "deletes the group. Persisted to ~/.doc-index/_groups.jsonc (JSONC — "
                "hand-edits welcome)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "repos": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["name", "repos"]
            }
        ),
        Tool(
            name="tune_weights",
            description=(
                "Online weight tuning. Reads ranking_events from "
                "~/.doc-index/telemetry.db (requires JDOCMUNCH_PERF_TELEMETRY=1) "
                "and proposes a per-repo semantic_weight step. dry_run=true skips "
                "the disk write. min_events gates against early overfitting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Optional — single repo to tune. Omit to scan all repos with events."},
                    "min_events": {"type": "integer", "default": 50},
                    "dry_run": {"type": "boolean", "default": False}
                }
            }
        ),
        Tool(
            name="verify_index",
            description=(
                "Byte-offset integrity check. Walks every section, byte-range-reads "
                "its current on-disk content, recomputes SHA-256, and compares to the "
                "stored content_hash. Reports drift / missing / error counts plus the "
                "drifting section ids. Sample N sections via the sample arg for cheap "
                "CI checks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "sample": {"type": "integer", "description": "Only verify the first N sections."}
                },
                "required": ["repo"]
            }
        ),
        Tool(
            name="check_embedding_drift",
            description=(
                "Embedding-drift canary. Without args, re-embeds the saved CANARY_STRINGS "
                "and reports per-canary cosine drift; alarm fires when max_drift > threshold "
                "(default 0.05 ≈ cosine<0.95). Pass capture=true to seed the snapshot first "
                "(idempotent unless force=true). Catches silent provider model upgrades that "
                "would otherwise corrupt index recall without changing dim."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "capture": {
                        "type": "boolean",
                        "default": False,
                        "description": "Embed CANARY_STRINGS and persist the snapshot."
                    },
                    "force": {
                        "type": "boolean",
                        "default": False,
                        "description": "With capture=true, overwrite an existing snapshot."
                    },
                    "threshold": {
                        "type": "number",
                        "default": 0.05,
                        "description": "Max allowed drift (1 - cosine). Default 0.05."
                    }
                }
            }
        ),
    ]


@server.list_resources()
async def list_resources() -> list[Resource]:
    """Return empty resource list for client compatibility (e.g. Windsurf)."""
    return []


@server.list_prompts()
async def list_prompts() -> list:
    """Return empty prompt list for client compatibility (e.g. Windsurf)."""
    return []


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls.

    v1.14.0: every dispatch is timed and recorded into the per-tool latency
    ring (and persistent SQLite sink when ``JDOCMUNCH_PERF_TELEMETRY=1``).
    """
    import time as _time
    from .storage.token_tracker import record_tool_latency as _record_latency

    storage_path = os.environ.get("DOC_INDEX_PATH")

    _t0 = _time.perf_counter()
    _ok = True
    _repo = arguments.get("repo") if isinstance(arguments, dict) else None

    try:
        if name == "index_local":
            result = index_local(
                path=arguments["path"],
                name=arguments.get("name"),
                use_ai_summaries=arguments.get("use_ai_summaries", True),
                use_embeddings=arguments.get("use_embeddings", "auto"),
                storage_path=storage_path,
                extra_ignore_patterns=arguments.get("extra_ignore_patterns"),
                follow_symlinks=arguments.get("follow_symlinks", False),
                incremental=arguments.get("incremental", True),
                max_files=arguments.get("max_files", 500),
                autotune=arguments.get("autotune", False),
            )
        elif name in ("doc_index_repo", "index_repo"):  # index_repo kept for backward compat
            result = await index_repo(
                url=arguments["url"],
                use_ai_summaries=arguments.get("use_ai_summaries", True),
                use_embeddings=arguments.get("use_embeddings", "auto"),
                storage_path=storage_path,
                incremental=arguments.get("incremental", True),
            )
        elif name in ("doc_list_repos", "list_repos"):  # list_repos kept for backward compat
            result = list_repos(storage_path=storage_path)
        elif name == "get_toc":
            result = get_toc(
                repo=arguments["repo"],
                path_glob=arguments.get("path_glob"),
                storage_path=storage_path,
            )
        elif name == "get_toc_tree":
            result = get_toc_tree(
                repo=arguments["repo"],
                path_glob=arguments.get("path_glob"),
                storage_path=storage_path,
            )
        elif name == "get_document_outline":
            result = get_document_outline(
                repo=arguments["repo"],
                doc_path=arguments["doc_path"],
                storage_path=storage_path,
            )
        elif name == "search_sections":
            result = search_sections(
                repo=arguments.get("repo"),
                query=arguments["query"],
                doc_path=arguments.get("doc_path"),
                path_glob=arguments.get("path_glob"),
                max_results=arguments.get("max_results", 10),
                semantic=arguments.get("semantic"),
                semantic_only=arguments.get("semantic_only", False),
                semantic_weight=arguments.get("semantic_weight", 0.5),
                role=arguments.get("role"),
                profile=arguments.get("profile"),
                dedupe=arguments.get("dedupe", False),
                repo_group=arguments.get("repo_group"),
                storage_path=storage_path,
            )
        elif name == "get_section":
            result = get_section(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                verify=arguments.get("verify", False),
                strip_boilerplate=arguments.get("strip_boilerplate", False),
                compress_code=arguments.get("compress_code", False),
                storage_path=storage_path,
            )
        elif name == "get_sections":
            result = get_sections(
                repo=arguments["repo"],
                section_ids=arguments["section_ids"],
                verify=arguments.get("verify", False),
                strip_boilerplate=arguments.get("strip_boilerplate", False),
                compress_code=arguments.get("compress_code", False),
                storage_path=storage_path,
            )
        elif name == "get_section_context":
            result = get_section_context(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                max_tokens=arguments.get("max_tokens", 2000),
                include_children=arguments.get("include_children", True),
                include_related=arguments.get("include_related", False),
                strip_boilerplate=arguments.get("strip_boilerplate", False),
                storage_path=storage_path,
            )
        elif name == "section_neighbors":
            result = section_neighbors(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                storage_path=storage_path,
            )
        elif name == "get_section_summary":
            result = get_section_summary(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                storage_path=storage_path,
            )
        elif name == "get_orphan_sections":
            result = get_orphan_sections(
                repo=arguments["repo"],
                include_same_doc=arguments.get("include_same_doc", False),
                storage_path=storage_path,
            )
        elif name == "get_section_path":
            result = get_section_path(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                storage_path=storage_path,
            )
        elif name == "delete_index":
            result = delete_index(
                repo=arguments["repo"],
                storage_path=storage_path,
            )
        elif name == "get_broken_links":
            result = get_broken_links(
                repo=arguments["repo"],
                storage_path=storage_path,
            )
        elif name == "get_doc_coverage":
            result = get_doc_coverage(
                repo=arguments["repo"],
                symbol_ids=arguments["symbol_ids"],
                storage_path=storage_path,
            )
        elif name == "get_backlinks":
            result = get_backlinks(
                repo=arguments["repo"],
                doc_path=arguments["doc_path"],
                storage_path=storage_path,
            )
        elif name == "get_stale_pages":
            result = get_stale_pages(
                repo=arguments["repo"],
                sources_dir=arguments.get("sources_dir"),
                storage_path=storage_path,
            )
        elif name == "get_wiki_stats":
            result = get_wiki_stats(
                repo=arguments["repo"],
                storage_path=storage_path,
            )
        elif name == "analyze_perf":
            result = analyze_perf(
                window=arguments.get("window", "session"),
                storage_path=storage_path,
            )
        elif name == "get_session_stats":
            result = get_session_stats(storage_path=storage_path)
        elif name == "check_embedding_drift":
            result = check_embedding_drift(
                capture=arguments.get("capture", False),
                force=arguments.get("force", False),
                threshold=arguments.get("threshold", 0.05),
                storage_path=storage_path,
            )
        elif name == "find_code_examples":
            result = find_code_examples(
                repo=arguments["repo"],
                query=arguments["query"],
                lang=arguments.get("lang"),
                max_results=arguments.get("max_results", 10),
                storage_path=storage_path,
            )
        elif name == "link_code_to_symbols":
            result = link_code_to_symbols(
                repo=arguments["repo"],
                code_repo=arguments["code_repo"],
                max_examples=arguments.get("max_examples", 200),
                max_symbols_per_block=arguments.get("max_symbols_per_block", 5),
                storage_path=storage_path,
            )
        elif name == "find_endpoint":
            result = find_endpoint(
                repo=arguments["repo"],
                path=arguments.get("path"),
                method=arguments.get("method"),
                tag=arguments.get("tag"),
                storage_path=storage_path,
            )
        elif name == "list_endpoints_by_tag":
            result = list_endpoints_by_tag(
                repo=arguments["repo"],
                tag=arguments["tag"],
                storage_path=storage_path,
            )
        elif name == "find_operations_using_schema":
            result = find_operations_using_schema(
                repo=arguments["repo"],
                schema_name=arguments["schema_name"],
                storage_path=storage_path,
            )
        elif name == "get_schema_graph":
            result = get_schema_graph(
                repo=arguments["repo"],
                schema_name=arguments["schema_name"],
                max_depth=arguments.get("max_depth", 5),
                storage_path=storage_path,
            )
        elif name == "lookup_term":
            result = lookup_term(
                repo=arguments["repo"],
                term=arguments["term"],
                storage_path=storage_path,
            )
        elif name == "list_terms":
            result = list_terms(
                repo=arguments["repo"],
                prefix=arguments.get("prefix"),
                max_results=arguments.get("max_results", 100),
                storage_path=storage_path,
            )
        elif name == "get_related_sections":
            result = get_related_sections(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                mode=arguments.get("mode", "both"),
                top_n=arguments.get("top_n", 5),
                min_score=arguments.get("min_score", 0.6),
                max_per_kind=arguments.get("max_per_kind", 10),
                storage_path=storage_path,
            )
        elif name == "get_section_diff":
            result = get_section_diff(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                storage_path=storage_path,
            )
        elif name == "get_doc_health":
            result = get_doc_health(
                repo=arguments["repo"],
                storage_path=storage_path,
            )
        elif name == "get_tutorial_path":
            result = get_tutorial_path(
                repo=arguments["repo"],
                section_id=arguments["section_id"],
                storage_path=storage_path,
            )
        elif name == "get_undocumented_symbols":
            result = get_undocumented_symbols(
                repo=arguments["repo"],
                code_repo=arguments["code_repo"],
                max_symbols=arguments.get("max_symbols", 1000),
                storage_path=storage_path,
            )
        elif name == "tune_weights":
            result = tune_weights(
                repo=arguments.get("repo"),
                min_events=arguments.get("min_events", 50),
                dry_run=arguments.get("dry_run", False),
                storage_path=storage_path,
            )
        elif name == "list_repo_groups":
            result = list_repo_groups(storage_path=storage_path)
        elif name == "define_repo_group":
            result = define_repo_group(
                name=arguments["name"],
                repos=arguments["repos"],
                storage_path=storage_path,
            )
        elif name == "verify_index":
            result = verify_index(
                repo=arguments["repo"],
                sample=arguments.get("sample"),
                storage_path=storage_path,
            )
        else:
            result = {"error": f"Unknown tool: {name}"}

        if isinstance(result, dict):
            result.setdefault("_meta", {})["powered_by"] = "jdocmunch-mcp by jgravelle · https://github.com/jgravelle/jdocmunch-mcp"

            # meta_fields filtering (matches jcodemunch-mcp behaviour)
            from .config import get_meta_fields
            meta_fields = get_meta_fields()
            if meta_fields == []:
                result.pop("_meta", None)
            elif isinstance(meta_fields, list):
                existing_meta = result.pop("_meta", {})
                _meta: dict[str, Any] = {}
                if "powered_by" in meta_fields:
                    _meta["powered_by"] = existing_meta.get("powered_by", "")
                for field in meta_fields:
                    if field in existing_meta:
                        _meta[field] = existing_meta[field]
                if _meta:
                    result["_meta"] = _meta

        return [TextContent(type="text", text=json.dumps(result, separators=(',', ':')))]

    except Exception as e:
        _ok = False
        print(traceback.format_exc(), file=sys.stderr)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}, separators=(',', ':')))]
    finally:
        _record_latency(
            tool=name,
            duration_ms=(_time.perf_counter() - _t0) * 1000.0,
            ok=_ok,
            repo=_repo if isinstance(_repo, str) else None,
            base_path=storage_path,
        )


async def run_server():
    """Run the MCP server."""
    from jdocmunch_mcp import __version__
    from mcp.server.stdio import stdio_server
    print(f"jdocmunch-mcp {__version__} by jgravelle · https://github.com/jgravelle/jdocmunch-mcp", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def main(argv: Optional[list] = None):
    """Main entry point."""
    from .security import verify_package_integrity
    verify_package_integrity()

    parser = argparse.ArgumentParser(
        prog="jdocmunch-mcp",
        description="jDocMunch MCP — structured documentation retrieval server.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- serve (default) ---
    subparsers.add_parser("serve", help="Run the MCP server (default)")

    # --- init ---
    init_parser = subparsers.add_parser(
        "init",
        help="One-command onboarding: detect clients, write config, install policy, hooks, index",
    )
    init_parser.add_argument(
        "--hooks", action="store_true",
        help="Install enforcement hooks into ~/.claude/settings.json",
    )
    init_parser.add_argument(
        "--index", action="store_true",
        help="Index the current working directory",
    )
    init_parser.add_argument(
        "--client", dest="clients", action="append",
        help="MCP client to configure (auto|none|claude-code|claude-desktop|cursor|windsurf|continue)",
    )
    init_parser.add_argument(
        "--claude-md", dest="claude_md", choices=["global", "project"],
        help="Install Doc Exploration Policy into CLAUDE.md",
    )
    init_parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without making changes",
    )
    init_parser.add_argument(
        "--demo", action="store_true",
        help="Demo mode: dry-run with benefit summary",
    )
    init_parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Accept all defaults non-interactively",
    )
    init_parser.add_argument(
        "--no-backup", action="store_true",
        help="Skip creating .bak backups before modifying files",
    )

    # --- claude-md ---
    cmd_parser = subparsers.add_parser(
        "claude-md",
        help="Print or install the Doc Exploration Policy for CLAUDE.md",
    )
    cmd_parser.add_argument(
        "--install", choices=["global", "project"],
        help="Append policy to CLAUDE.md (global or project scope)",
    )

    # --- index-file ---
    if_parser = subparsers.add_parser(
        "index-file",
        help="Re-index a single file within an existing index",
    )
    if_parser.add_argument(
        "file", help="Path to the file to re-index",
    )

    # --- index-local ---
    il_parser = subparsers.add_parser(
        "index-local",
        help="Index a local folder (CLI equivalent of the MCP index_local tool)",
    )
    il_parser.add_argument(
        "--path", required=True,
        help="Path to the folder to index",
    )
    il_parser.add_argument(
        "--name",
        help="Optional repo identifier override",
    )

    # --- verify-index (v1.27.0) ---
    vi_parser = subparsers.add_parser(
        "verify-index",
        help="Byte-offset integrity check across an indexed repo",
    )
    vi_parser.add_argument("--repo", required=True, help="jdocmunch repo identifier")
    vi_parser.add_argument("--sample", type=int, default=None,
                           help="Verify only the first N sections (cheap CI mode)")

    # --- hook-pretooluse ---
    subparsers.add_parser(
        "hook-pretooluse",
        help="PreToolUse hook: intercept Read on large doc files (reads stdin)",
    )

    # --- hook-posttooluse ---
    subparsers.add_parser(
        "hook-posttooluse",
        help="PostToolUse hook: auto-reindex doc files after Edit/Write (reads stdin)",
    )

    # --- hook-precompact ---
    subparsers.add_parser(
        "hook-precompact",
        help="PreCompact hook: session snapshot before context compaction (reads stdin)",
    )

    args = parser.parse_args(argv)

    # Default to serve when no subcommand given
    if args.command is None or args.command == "serve":
        asyncio.run(run_server())
        return

    if args.command == "init":
        from .cli.init import run_init
        rc = run_init(
            clients=args.clients,
            claude_md=args.claude_md,
            hooks=args.hooks,
            index=args.index,
            dry_run=args.dry_run,
            demo=args.demo,
            yes=args.yes,
            no_backup=args.no_backup,
        )
        sys.exit(rc)

    if args.command == "claude-md":
        from .cli.init import run_claude_md
        sys.exit(run_claude_md(install=args.install))

    if args.command == "index-file":
        from .tools.index_file import index_file_cli
        result = index_file_cli(args.file)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("success") else 1)
        return

    if args.command == "index-local":
        from .tools.index_local import index_local
        result = index_local(path=args.path, name=args.name)
        print(json.dumps(result, indent=2))
        return

    if args.command == "verify-index":
        from .tools.verify_index import verify_index as _verify
        result = _verify(repo=args.repo, sample=args.sample)
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get("drift_count", 0) == 0 else 2)

    if args.command == "hook-pretooluse":
        from .cli.hooks import run_pretooluse
        sys.exit(run_pretooluse())

    if args.command == "hook-posttooluse":
        from .cli.hooks import run_posttooluse
        sys.exit(run_posttooluse())

    if args.command == "hook-precompact":
        from .cli.hooks import run_precompact
        sys.exit(run_precompact())


if __name__ == "__main__":
    main()
