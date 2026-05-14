# Changelog

## [1.65.0] - 2026-05-14 - prefer-newest walk order on truncation (jdoc#16)

Follow-up to jdoc#15 (@LuigiNicaPRO). When the corpus exceeds `max_files`
and truncation kicks in, the previous walker took the first `max_files`
in filesystem-walk order -- non-deterministic from the user's
perspective. A file edited 4 minutes before the index call could be
silently dropped while older files made the cut. Reported by
@LuigiNicaPRO as suggestion #4 on jdoc#15; deferred to its own ship.

New `sort_by` kwarg on `index_local` and `discover_doc_files`:

- `sort_by="newest"` **(new default):** when `discovered > max_files`,
  sorts by mtime descending so the indexed subset is always the N
  most recently-edited files. Recent edits are always in the index
  regardless of filesystem-walk position.
- `sort_by="walk_order"`: pre-1.65 behavior. Useful for deterministic
  reproducible builds where mtimes shift but content doesn't.

The sort only runs on the truncation path (`discovered > max_files`),
so corpora under the cap pay zero cost. mtime is captured in the same
`stat()` call that already does the size check, so no extra syscalls
either.

Regression coverage in `tests/test_index_local_sort_by.py` (6 tests).

## [1.64.2] - 2026-05-14 - silent truncation footgun in `index_local` (jdoc#15)

Reported by @LuigiNicaPRO: `index_local()` on a 5,705-file Obsidian Vault
returned `success: true` and `file_count: 498` with no programmatic
signal that ~90% of the corpus had been silently dropped. Default
`max_files=500` was buried in the schema; the cap-hit hint was a
free-text `note` string in the response.

Four fixes:

1. **Default `max_files` raised from 500 to 10,000.** Modern doc repos
   and Obsidian Vaults routinely exceed 500.
2. **Walker counts past the cap** (up to a 20x safety ceiling) so
   `discovered` reflects the true corpus size, not the cap. Returns a
   new tuple shape `(files, warnings, discovered_count)`.
3. **Structured top-level truncation fields**: when the cap is hit, the
   response now includes `truncated: true`, `discovered: <total>`,
   `indexed: <max_files>`. Programmatic detection is trivial:
   `if result.get("truncated"):`. When the corpus fits, `truncated:
   false` is set explicitly.
4. **Structured warning entry** in the existing `warnings` array
   alongside the legacy `note` string (kept for back-compat).

Both the full-index and incremental code paths surface the new fields.

Walker order is still filesystem order -- prefer-newest is a useful
future enhancement (@LuigiNicaPRO's suggestion #4) but lands cleanest
in a separate ship since it changes which subset gets indexed, not
just how truncation is reported.

Regression coverage in `tests/test_index_local_truncation.py` (6 tests).

## [1.64.1] - 2026-05-14 - O(N^2) hang in `related_persist.build()` (jdoc#14)

Reported by @LuigiNicaPRO with a py-spy backtrace and a working local
patch in hand: `index_local` on a 10-20k-section repo hung at 100% CPU
on a single thread. The docstring claimed `build()` was O(N) on
structural edges; it was actually O(N^2) on two stacked patterns:

1. `section_dicts` was rebuilt inside the per-section loop on every
   iteration -- O(N) work x N iterations = O(N^2) before any neighbor
   computation began.
2. `structural_neighbors()` rebuilt its by-id map and called
   `_children_of(parent_id, sections)` up to 4 times per section, each
   a linear scan -- another O(N) per outer iteration.

Fix: precompute `section_dicts`, the by-id map, and a new
parent->children map once before the loop and thread them into the
per-section calls via two new optional kwargs on `structural_neighbors`
and `semantic_neighbors`. External callers ignore the new kwargs and
keep the original behavior bit-for-bit -- the cache parameters are
prefixed `_` to mark them as internal hot-path use only.

Bench (Windows / Python 3.14): the fixed path indexes 10k sections in
~0.6s. The pre-fix path on the same input ran for minutes before being
killed.

Regression coverage in `tests/test_related_persist_perf.py`: asserts
the build scales linearly between 2k and 4k sections (ratio <3.5x) and
that 15k completes in <5s.

## [1.64.0] - 2026-05-14 - `tool_profile` + `disabled_tools` config (#297)

Reported by @AlexJ-StL in #297: Google Antigravity caps MCP-server tool
counts at 50, but jdocmunch shipped 60 tools with no way to trim them
short of disabling the whole server. Sibling-parity gap with jcm, which
has had `tool_profile` and `disabled_tools` since v1.78.

Two new env-var-driven knobs in `server.py`:

- `JDOCMUNCH_TOOL_PROFILE=core|standard|full` (default `full`).
  - `core` (13 tools): index + the navigation/search essentials.
  - `standard` (~50 tools): core + analysis/cross-reference tools.
  - `full` (60 tools): everything, current behavior.
- `JDOCMUNCH_DISABLED_TOOLS=tool1,tool2,...` removes named tools from
  both the listed schema and the call dispatcher. Composes with
  `tool_profile`.

Filtering is enforced in `list_tools()` (schema visibility) AND
`call_tool()` (call-time rejection) so a client that cached the schema
gets a clear error if it invokes a disabled tool. `jdocmunch_guide`
survives tier filtering (so a one-line CLAUDE.md keeps working at any
tier) but honors `disabled_tools` (it's documentation, not a control
surface) -- mirrors jcm v1.108.8's issue-#298 resolution.

Antigravity users with the full munch suite can now run:

```jsonc
// per-server env vars
"jdocmunch": { "env": { "JDOCMUNCH_TOOL_PROFILE": "core" } }
```

to fit under the 50-tool cap.

## [1.63.3] - 2026-05-13 - `jdocmunch_guide` sibling-parity tool

Adds `jdocmunch_guide` -- the doc-MCP sibling of `jcodemunch_guide` (jcm
since v1.84.0). Returns the version-current CLAUDE.md / AGENT.md policy
snippet for jdocmunch-mcp so an agent can keep a one-line CLAUDE.md
(`"Call jdocmunch_guide and strictly follow its instructions."`) instead
of pasting a static block that drifts from the installed version.

Backstory: GitHub issue #296 (Codex Desktop compatibility report by
@rknighton) noted that jcodemunch-mcp ships a guide tool but jdocmunch-mcp
doesn't, leaving agents told to call `<pkg>_guide first` without an
onboarding entry point for the doc surface. Sibling parity closes the
gap. Companion v1.12.2 release of jdatamunch-mcp ships `jdatamunch_guide`
on the same shape.

Tool count 59 -> 60. No tool, schema, or wire-format change for existing
tools. 1205 tests pass (1199 + 6 new in `test_v1_63_3.py`).

## [1.63.2] - 2026-05-12 - drift-proof __version__ via importlib.metadata

`src/jdocmunch_mcp/__init__.py` now derives `__version__` from
`importlib.metadata.version("jdocmunch-mcp")` instead of a hardcoded
literal. Reads the wheel's metadata at import time, so pyproject.toml
and the runtime version string can no longer disagree by construction.

Backstory: v1.63.0 shipped with the hardcoded `__version__` stuck at
1.60.0 (three minors stale) because nothing cross-checked it against
pyproject. v1.63.1 added a `tests/test_version_sync.py` regex guard,
but jcodemunch-mcp already had a better pattern. This release ports
that pattern over and retires the test (no longer reachable code).

When run from a source checkout without pip install, `__version__`
resolves to `"unknown"`. The replay-runner's `_resolve_version()`
already falls back to parsing `pyproject.toml` in that case, so
baseline-result filenames stay correct on source builds.

No tool, schema, or wire-format changes.

## [1.63.1] - 2026-05-12 - CI green: fixture query rename + full-history checkout

Patch release that turns master green again. Two independent CI fixes,
no behavior change for installed users.

1. Replay fixture: the `wiki stats` query in `self_v1_11_0.json` collided
   with the `### Stats` H3 subheadings that v1.62.0 and v1.63.0 hand-added
   to CHANGELOG.md. BM25 ranked those short, dense sections above the
   target wiki-benchmark page, dropping MRR from 1.0 to 0.925 (over the
   0.06 gate). Renamed to `wiki benchmark`. Expected target returns to
   rank 1 with a clean margin and the slug `jdocmunch-mcp-wiki-benchmark`
   is the unambiguous lexical anchor for it.
2. Workflow checkout: both `test.yml` and `replay.yml` now set
   `fetch-depth: 0` on `actions/checkout@v5`. The shallow default broke
   `tests/test_v1_35_0.py::TestChangelogGenerator::test_runs_against_real_repo`
   on any push whose HEAD wasn't itself a `release:` commit, because
   `scripts/generate_changelog.py` walks `git log` for release subjects
   and a depth-1 clone had none to match.

No tool, schema, or wire-format changes. v1.63.1 baseline result captured
at `benchmarks/replay/results/self_v1_11_0-v1.63.1.json` (1.0 / 1.0 / 1.0).

## [1.63.0] — 2026-05-12 — `get_doc_pr_risk_profile` (Phase-2 sibling-parity COMPLETE)

Composite doc-PR risk profile. Fuses five orthogonal signals over a
caller-supplied list of changed sections into a 0-1 `risk_score` with
overall `risk_level` (low / medium / high / critical), a ranked top-5
list of blockers, and a one-line `recommended_action`. Mirrors jcm's
`get_pr_risk_profile`.

### Signals

| Signal                | Source                                              |
|-----------------------|-----------------------------------------------------|
| `volume`              | changed sections / total sections (×10 cap)         |
| `blast_radius`        | mean blast_score for modified + deleted sections    |
| `backlink_burden`     | avg inbound references per changed section / 5     |
| `tutorial_disruption` | % of changes on tutorial chains                     |
| `role_weight`         | % of changes hitting tutorial/reference/guide roles |

Weights: `volume 0.15 + blast 0.30 + backlinks 0.20 + tutorial 0.20 + role 0.15`.
Thresholds: `≤0.25 low / ≤0.50 medium / ≤0.75 high / >0.75 critical`.

### Input shape

Caller passes `changed_sections` as either bare section IDs (str,
defaults to `kind=modified`) or `{section_id, kind}` dicts where
`kind ∈ {added, modified, deleted}`. Added sections skip backlink
lookup since they cannot have inbound refs yet.

The tool does **not** diff anything itself — pair with `get_recent_changes`
or compute the list from `git diff` in your CI step.

### Stats

- Tool count: 59 (+ `get_doc_pr_risk_profile`)
- Tests: 1196 passed (+12 new — 5 pure-function + 7 integration)

This completes Phase 2 of the sibling-parity PRD across all three munches.

---

## [1.62.0] — 2026-05-12 — `doc_health_radar` + `diff_doc_health_radar`

Six-axis health radar for documentation indexes, plus a pure-function
diff helper. Third leg of the suite-wide radar pattern (jcm's
`health_radar.py` + jData's `data_health_radar`).

### Axes

Each axis scores 0-100 (higher = healthier):

| Axis                | Source                                              |
|---------------------|-----------------------------------------------------|
| `freshness`           | fresh / (fresh + edited + stale) × 100            |
| `link_integrity`      | linear penalty per broken link (relative to sections) |
| `orphan_health`       | linear penalty per orphan section                 |
| `embedding_coverage`  | embedded sections / total sections × 100          |
| `role_coverage`       | sections with non-unknown role / total × 100      |
| `drift_health`        | canary clean → 100; alarm → 0; no canary → omitted|

`freshness` is omitted when section_count is zero. `drift_health` is
omitted when no embedding-drift canary has been captured. Omitted axes
appear in `omitted_axes` and never silently penalise the composite —
radars stay comparable across repos with different setup states.

### `diff_doc_health_radar`

Pure function: takes two radar payloads, returns per-axis deltas,
composite delta, grade change, regression + improvement lists at a
3-point threshold, and a one-line verdict. No I/O.

### Stats

- Tool count: 58 (+ `doc_health_radar`, `diff_doc_health_radar`)
- Tests: 1184 passed (+12 new; 12 pre-existing baseline-gate failures unaffected)

---

## [1.61.0] — 2026-05-12

### New: explicit-paths indexing

`index_local` gains a `paths=[...]` parameter that bypasses the directory
walk and indexes only the listed files / subdirs. Each entry can be
absolute or relative to the `path` root. Useful for batch-indexing
exactly the doc files an agent already knows about — e.g. *the docs git
just touched*, *the pages in this PR's diff*, *the markdown matched by
fd / rg* — without the cost (or surprise) of a full-tree walk.

Security: explicit paths are validated the same way as walk-discovered
files — entries outside the root, path-traversal attempts, and symlink
escapes are rejected with per-entry `warnings`. Unsupported extensions
are warned-and-skipped rather than silently passed.

CLI: new `--paths-from FILE` flag on `jdocmunch-mcp index-local`. Use
`-` for stdin to make the command pipe-friendly with `find`, `fd`,
`fzf`, and `rg`:

```bash
git diff --name-only HEAD~5 -- '*.md' \
  | jdocmunch-mcp index-local --path docs/ --paths-from -
```

Empty input is treated as an error so the command doesn't silently fall
through to a full-tree index. Lines beginning with `#` are skipped.

### Notes
- Fully additive — `paths` defaults to `None`, preserving every existing
  call shape. The MCP `index_local` tool's `inputSchema` gains an
  optional `paths: list[string]` field with the same semantics.
- 10 new tests in `test_v1_61_0.py`. 1174 passed.

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
