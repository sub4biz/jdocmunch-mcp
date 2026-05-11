# Changelog

## [1.60.0] — 2026-05-11

### New: `find_similar_sections` — multi-signal dedup detection

Every wiki of size accumulates "three pages that all say the same
thing." This tool surfaces them. Multi-signal scoring fuses embedding
cosine (when the index has embeddings) with title + body lexical
Jaccard, gated by a cheap title-token pre-filter to keep cost bounded
on large wikis.

Output is cluster-shaped: one entry per group of overlapping sections,
each with a `canonical` (recommended keeper, ranked by backlink_count +
byte_length) and `variants` to fold in. Verdict tiers per cluster:

- `near_duplicate` — combined score ≥ `near_duplicate_threshold` (0.92)
- `overlapping_topic` — combined score ∈ `[min_score, threshold)`
- `parallel_tutorial` — cluster members live in different doc
  directories (suggests parallel guides that should cross-reference
  rather than be merged)

Defaults: `min_score=0.7`, `max_clusters=50`, `max_sections=1000`.
Parser-artifact filter drops zero-byte-range wrapper sections so they
don't cluster with their own heading-level twins.

Read-only. Inspired by `find_similar_symbols` in jcodemunch-mcp (see
`C:/MCPs/PRD_sibling_parity_v1.md` §6.2). **Completes the jDoc Phase-1
batch from the sibling-parity PRD** (joins `check_section_delete_safe`
+ `get_section_blast_radius`).

### New: `get_section_blast_radius` — transitive impact of a section change

Companion to `get_backlinks` (which is depth 1 only). Walks the inbound
reference graph to `max_depth` (default 3) and classifies each hit as
`anchor` (link targets this section's slug), `doc` (link targets the
enclosing doc), or `tutorial` (section appears in a Next/Prev / toctree
chain).

Returns `direct_impact` (depth 1), `transitive_impact` (depth ≥ 2), a
`summary` of counts, and a normalised `blast_score` in [0, 1] so blast
radius is comparable across sections of different size.

Read-only. Inspired by `get_blast_radius` in jcodemunch-mcp (see
`C:/MCPs/PRD_sibling_parity_v1.md` §6.3).

### New: `check_section_delete_safe` — composite deletion preflight

First Phase-1 deliverable from the sibling-parity PRD. Answers the
question every wiki maintainer asks every week: *can I safely remove
this section?*

Fuses four channels into a single verdict plus up to five ranked
blockers and a one-line `recommended_action`:

1. **Tutorial-path membership** — section is part of a Next/Prev chain,
   Sphinx toctree, VuePress sidebar, or ordered-filename sequence. High
   severity — deleting breaks readers walking the chain.
2. **Anchor-specific backlinks** — other sections link to `doc#slug`.
   High severity — those anchored links 404 once the section is gone.
3. **Transitive doc-level backlinks** — BFS over inbound refs to
   `transitive_depth` (default 3). Medium severity above a threshold of
   3 referers.
4. **Recent-edit recency** — section's source touched within
   `recent_edit_days` (default 14), or sits in FreshnessProbe's
   `edited_uncommitted` bucket. Low severity — defer deletion.

Verdict tiers (highest first): `tutorial_path_blocking`,
`anchor_referenced`, `backlinks_blocking`, `recently_edited_blocking`,
`safe_to_delete`.

Read-only. Composes existing primitives (`get_tutorial_path`,
`get_backlinks`, `FreshnessProbe`) — no new persisted state, no
INDEX_VERSION bump.

Inspired by `check_delete_safe` in jcodemunch-mcp (see
`C:/MCPs/PRD_sibling_parity_v1.md` §6.1).

## [1.9.0] — 2026-04-19

### New: Hybrid BM25 + semantic search

- **`search_sections` now fuses lexical and semantic scores** when the index has embeddings. New parameters match jcodemunch-mcp's shape:
  - `semantic` — `null`/omit (auto — hybrid when embeddings exist), `true` (force hybrid), `false` (force lexical-only)
  - `semantic_only` — skip lexical entirely, rank purely by embedding cosine
  - `semantic_weight` — 0.0–1.0 weight of the semantic channel in fusion (default 0.5)
- Each channel min-max-normalized to [0,1] within the candidate set, then weighted sum. When `embed_query` returns `None` (provider disabled at query time), hybrid gracefully degrades to lexical. Zero performance impact when the index has no embeddings.
- `_meta.search_mode` now reports one of `hybrid`, `semantic_only`, or `lexical` (replacing the previous binary `semantic`/`lexical`). `_meta.semantic_weight` is surfaced on hybrid calls.

### New: `use_embeddings="auto"` default

- `index_local` and `doc_index_repo` now default `use_embeddings` to `"auto"` — embeddings are generated automatically whenever an embedding provider is configured (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, or sentence-transformers installed). Explicit `true`/`false` still honored.
- `index-file` now preserves embedding parity: when re-indexing a single file into an index that already has embeddings, the new sections get embedded too (previously left empty).

### Tests

- 16 new tests covering `should_embed` flag resolution, hybrid fusion ranking, `semantic=False` short-circuit, semantic-only, `semantic_weight=0` reduction to lexical, graceful degradation, and search_mode reporting (400 total).

## [1.8.1] — 2026-04-15

### Documentation
- **Hermes Agent integration** — added "Works with" section to README with Hermes Agent config example; submitted optional skill PR to [NousResearch/hermes-agent#10413](https://github.com/NousResearch/hermes-agent/pull/10413)

## [1.7.1] — 2026-04-09

### New features

- **`meta_fields` support** — control which `_meta` fields appear in tool responses via `JDOCMUNCH_META_FIELDS` env var. Matches jcodemunch-mcp's `meta_fields` affordance. Values: unset/`[]` = strip `_meta` entirely (default, maximum token savings), `null`/`all`/`*` = include all fields, comma-separated list = include only those fields (e.g. `timing_ms,powered_by`).

### Tests

- 11 new tests for meta_fields config parsing and filtering (358 total)

## [1.7.0] — 2026-04-09

### New: Full `init` onboarding

- **`jdocmunch-mcp init`** — One-command setup matching jcodemunch-mcp's UX:
  - Detects installed MCP clients (Claude Code CLI, Claude Desktop, Cursor, Windsurf, Continue)
  - Patches each client's config JSON to add jdocmunch as an MCP server
  - Installs a Doc Exploration Policy into CLAUDE.md (global or project scope)
  - Installs Cursor rules (`.cursor/rules/jdocmunch.mdc`) and Windsurf rules (`.windsurfrules`)
  - Installs enforcement hooks (PreToolUse, PostToolUse, PreCompact)
  - Indexes the current working directory
  - Supports `--dry-run`, `--demo`, `--yes`, `--no-backup`, `--client`, `--claude-md`, `--hooks`, `--index`
  - Interactive prompts for scope selection when run in a terminal

### New: `claude-md` subcommand

- **`jdocmunch-mcp claude-md`** — Print the Doc Exploration Policy to stdout
- **`jdocmunch-mcp claude-md --install global|project`** — Append policy to CLAUDE.md (idempotent)

### New: `index-file` single-file re-index

- **`jdocmunch-mcp index-file <path>`** — Re-index a single doc file within an existing index without re-walking the entire folder. Finds the owning index automatically, re-parses, and updates in place via incremental_save.
- PostToolUse hook now spawns `index-file <path>` instead of `index-local --path <dir>` for faster, more targeted re-indexing after edits.

### Tests

- 20 new tests for client detection, config patching, CLAUDE.md injection, Cursor/Windsurf rules, claude-md command, index-file tool, CLI dispatch (347 total)

## [1.6.0] — 2026-04-09

### New: CLI hook system for Claude Code

- **`hook-pretooluse`** — PreToolUse hook that intercepts `Read` on large doc files (.md, .rst, .adoc, .txt, etc.) and suggests `search_sections` + `get_section` instead. Warns via stderr; allows the read to proceed (Edit workflow requires Read first).
- **`hook-posttooluse`** — PostToolUse hook that auto-reindexes after `Edit`/`Write` on doc files. Spawns `jdocmunch-mcp index-local` as a fire-and-forget background process.
- **`hook-precompact`** — PreCompact hook that generates a session snapshot (indexed repos, doc/section counts) before Claude Code context compaction, injected as `systemMessage`.
- **`index-local --path <dir>`** — CLI equivalent of the MCP `index_local` tool, callable from shell hooks without a live MCP session.
- **`init --hooks`** — One-command installer that merges all three enforcement hooks into `~/.claude/settings.json`. Additive (preserves existing hooks), creates `.bak` backup by default. Supports `--dry-run`.

### Fixed

- Version mismatch between `__init__.py` and `pyproject.toml` — both now track 1.6.0.

### Tests

- 29 new tests for hooks + init (327 total)

Closes [#8](https://github.com/jgravelle/jdocmunch-mcp/issues/8). Thanks @Will-Luck for the detailed feature request.

## [1.5.3] — 2026-04-07

### Changed
- Switch MCP tool responses from pretty-printed JSON to compact JSON — saves 30-40% tokens per response (jcodemunch-mcp#219)

## [1.5.2] — 2026-04-06

### Added
- **`contrib/build-deb.sh`** — Community-contributed Debian/Ubuntu packaging script for Proxmox and other Linux deployments. Includes venv isolation, systemd unit, and streamable HTTP wrapper. Contributed by @Tikilou. Closes #7.

## [1.5.0] — 2026-04-01

### New tools

- **`get_broken_links(repo)`** — scan all indexed doc sections for internal cross-references that no longer resolve. Checks markdown `[text](target)` links, RST `:ref:`/`:doc:` directives, and anchor-only links (`#heading`). External links (http/https/mailto) are skipped. Each broken entry reports `source_file`, `source_section`, `target`, and `reason` (`file_not_found` | `section_not_found` | `anchor_not_found`). Pure index scan — no re-reading source files.
- **`get_doc_coverage(repo, symbol_ids)`** — given a list of jcodemunch symbol IDs, reports which symbols are mentioned in section titles (documented) vs absent (undocumented). Bridges jcodemunch ↔ jdocmunch. `symbol_ids` capped at 200. Output: `{documented, undocumented, coverage_pct}`.

### Tests

- 26 new tests (298 total)

## [1.4.6] — 2026-03-31

### Housekeeping

- Added `LICENSE` file (dual-use: free for non-commercial, paid for commercial)

## [1.4.0] — 2026-03-13

### New features

- **`get_section_context` tool** — returns a target section's full content alongside its ancestor heading chain (root→parent) and immediate child summaries, all under a configurable `max_tokens` budget. Eliminates the need for whole-file reads when a section alone is too thin to answer a question.
- **sentence-transformers embedding backend** — fully offline embeddings via `sentence-transformers` (default model `all-MiniLM-L6-v2`, override with `JDOCMUNCH_ST_MODEL`). Auto-detected as fallback after Gemini/OpenAI. Nothing leaves the machine.
- **tiktoken-aware token counting** — `count_tokens()` in `storage/token_tracker.py` uses `tiktoken` when installed (cl100k_base), falling back to bytes/4 when not present. Opt-in: no new required dependency.
- **`incremental` parameter on `index_local` and `index_repo`** — callers can now pass `incremental: false` to force a full re-index without deleting the existing index first.

### Performance and correctness

- **In-memory index cache** — `load_index()` now caches parsed `DocIndex` objects keyed by path + `mtime_ns`. Zero `json.load()` calls on repeated tool calls against the same unchanged repo.
- **True incremental GitHub indexing** — `index_repo(incremental=True)` now fetches the HEAD commit SHA first and exits immediately (no tree or file fetches) when the SHA matches the stored value. HEAD SHA stored in the index.
- **Hierarchical section IDs** — slugs are now prefixed with the ancestor heading chain (e.g. `installation/prerequisites` instead of bare `prerequisites`). A new heading inserted in one branch no longer renumbers IDs in other branches. `INDEX_VERSION` bumped to `2` — existing indexes are automatically re-indexed on first access.

### Documentation

- SPEC, ARCHITECTURE, USER_GUIDE, and README audited and reconciled against code reality
- `verify` parameter correctly described as cache integrity verification, not live-source drift detection
- Section ID format updated to show hierarchical slug paths
- Embedding environment variables (`OPENAI_API_KEY`, `JDOCMUNCH_EMBEDDING_PROVIDER`, `JDOCMUNCH_ST_MODEL`) documented throughout

### Tests

- 8 new `get_section_context` tests (248 → 256 total)

---

## [1.1.0] — 2026-03-08

- OpenAPI 3.x / Swagger 2.x parser (`parser/openapi_parser.py`)
- `.yaml`, `.yml`, `.json` files content-sniffed: indexed when spec contains `openapi:` or `swagger:` key; skipped otherwise
- Operations grouped by tag → `## Tag` sections; each endpoint becomes a `### METHOD /path` subsection with parameters, request body, and responses rendered
- Schemas / Definitions section appended with property types and required markers
- `pyyaml>=6.0` already a hard dependency (no new deps)
- 25 new tests (176 → 201 total)

---

## [1.0.0] — 2026-03-07

First stable release. API is now frozen under semantic versioning — no breaking
changes without a major version bump.

### Stable feature set

**Document formats** (11 formats, 14 extensions):
- `.md`, `.markdown`, `.mdx` — Markdown (ATX + setext headings, MDX preprocessing)
- `.txt` — plain text paragraph splitting
- `.rst` — RST heading/adornment parser
- `.adoc`, `.asciidoc`, `.asc` — AsciiDoc `=` heading parser
- `.ipynb` — Jupyter notebook JSON → Markdown conversion
- `.html`, `.htm` — HTML → text conversion, chrome stripped
- `.yaml`, `.yml`, `.json` — OpenAPI 3.x / Swagger 2.x specs (content-sniffed)

**Indexing**
- Incremental indexing: hash-based change detection, only changed/new files re-parsed, atomic save
- Full indexing with gitignore-aware file discovery and security filtering

**Retrieval**
- O(1) section lookup via `__post_init__` id→section dict
- Byte-offset content retrieval with SHA-256 content hash verification
- Token savings tracking (raw file size vs. section response size)

**AI summaries**
- Claude Haiku (`ANTHROPIC_API_KEY`) or Gemini Flash (`GOOGLE_API_KEY`) for section summaries
- Graceful fallback to heading text when no AI key is set

**Security**
- Path traversal protection on all file I/O
- Secret file detection (`.env`, `.pem`, credentials, keys)
- Binary file filtering
- Max file size enforcement

**Test coverage**: 201 tests passing.

### Breaking changes from 0.x
None — the index schema and MCP tool interface are unchanged from 0.1.x.

---

## [0.1.5] — 2026-03-07

- OpenAPI/Swagger parser (`parser/openapi_parser.py`)
- `.yaml`, `.yml`, `.json` added to `ALL_EXTENSIONS` with content sniffing
- `pyyaml>=6.0` added as a hard dependency
- 25 new tests (176 → 201)

## [0.1.4] — 2026-03-07

- Incremental indexing for both `index_local` and `index_repo`
- `DocStore.detect_changes()` and `DocStore.incremental_save()`
- O(1) section lookup via `DocIndex.__post_init__`
- `time.time()` → `time.perf_counter()` across all tools
- 7 new incremental indexing tests (169 → 176)

## [0.1.3] — 2026-03-06

- HTML parser (`parser/html_parser.py`): `<h1>`–`<h6>` → Markdown headings, chrome stripped
- Double `load_index()` fix: `_index` parameter on `get_section_content`
- Token savings: `os.path.getsize()` replaces per-section content summing

## [0.1.2] — 2026-03-05

- Jupyter notebook parser (`parser/notebook_parser.py`)
- AsciiDoc parser (`parser/asciidoc_parser.py`)
- RST parser (`parser/rst_parser.py`)
- Plain text paragraph parser (`parser/text_parser.py`)

## [0.1.1] — 2026-03-04

- Markdown parser with ATX + setext heading support
- Section hierarchy wiring (`parser/hierarchy.py`)
- `DocStore` with atomic save, path traversal protection, secret file detection
- MCP tools: `index_local`, `index_repo`, `get_section`, `get_sections`, `get_toc`,
  `get_toc_tree`, `get_document_outline`, `search_sections`, `list_repos`, `delete_index`
