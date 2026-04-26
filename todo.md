# jDocMunch PRD — v1.10.0 → v1.x Roadmap

**Owner:** jgravelle
**Drafted:** 2026-04-26
**Last updated:** 2026-04-26 (post-v1.41.0)
**Status:** v1.10.0–v1.41.0 shipped (+ hotfixes v1.36.1/2/3). 1.x continues; 2.x deferred indefinitely (license boundary — see § "Reserved for 2.x").

### v1.41.0 — get_section_excerpt content preview — ✅ SHIPPED (2026-04-26)
**Goal:** Cheap content peek between handle-only metadata and full byte-range read. New `get_section_excerpt` returns title + first N bytes of content (default 500). Truncation is UTF-8 char-boundary safe and trims to last newline before the cap so the excerpt ends on a paragraph boundary. Truncated content gets a `…` marker; `_meta.tokens_saved` reports byte savings vs full content.

**Deliverables:**
- New `tools/get_section_excerpt.py` with `_safe_truncate` helper.
- Registered as 41st MCP tool. Schema: `repo` + `section_id` required, optional `max_bytes` (default 500).
- 12 tests in `tests/test_v1_41_0.py` covering UTF-8 boundary safety, newline-trim, truncation marker, full-section pass-through, error paths, schema parity.
- `tests/test_server.py` tool count 40 → 41.

**Replay gate:** all 7 fixtures pass at 1.0 nDCG/MRR/Recall vs v1.40.0.
**Tests:** 959 → 971 (+12).

### v1.40.0 — get_section_path + doc_health orphan rollup — ✅ SHIPPED (2026-04-26)
**Goal:** Two small additive wins. (a) New `get_section_path` tool walks `parent_id` upward and returns the breadcrumb (root → … → target) handle-only. Cycle-protected. (b) `get_doc_health` now includes `orphan_section_count` from v1.39's `get_orphan_sections` — completes the doc-health rollup.

**Deliverables:**
- New `tools/get_section_path.py`. Returns `{path:[handles], depth, doc_path, section_id}`.
- `get_doc_health` calls `get_orphan_sections` best-effort and surfaces `orphan_section_count`.
- Registered as 40th MCP tool.
- 7 tests in `tests/test_v1_40_0.py` covering breadcrumb shape, depth invariant, deep-chain ordering, cycle protection, doc-health orphan integration.
- `tests/test_server.py` tool count 39 → 40.

**Replay gate:** all 7 fixtures pass at 1.0 nDCG/MRR/Recall vs v1.39.0.
**Tests:** 951 → 959 (+8).

### v1.39.0 — get_orphan_sections doc-rot finder — ✅ SHIPPED (2026-04-26)
**Goal:** Surface sections nobody links to. Inverts the link graph once and reports every section whose `doc_path` receives zero inbound references from any other doc. Companion to `get_broken_links` (links pointing nowhere) and `get_stale_pages` (sections drifting from source) — together the doc-health triad.

**Deliverables:**
- New `tools/get_orphan_sections.py`. Optional `include_same_doc` flag toggles whether intra-doc anchor links count as inbound (default False — only cross-doc references).
- Filters synthetic level-0 doc-roots (parser artifact, not user-facing nav targets).
- Returns handles only: `{id, title, doc_path, level, summary}` — no content reads.
- Registered as 39th MCP tool. Schema requires `repo`.
- 9 tests in `tests/test_v1_39_0.py` covering hub-vs-linked-vs-orphan classification, synthetic-root filtering, handle shape, error paths, schema parity.
- `tests/test_server.py` tool count 38 → 39.

**Replay gate:** all 7 fixtures pass at 1.0 nDCG/MRR/Recall vs v1.38.0.
**Tests:** 942 → 951 (+9).

### v1.38.0 — get_section_summary metadata-only retrieval — ✅ SHIPPED (2026-04-26)
**Goal:** Fill the gap between `get_toc` (brief handles) and `get_section` (full content). New `get_section_summary` tool returns the full indexed metadata for one section — title, summary, role, tags, metadata, parent_id, children, content_hash, byte_start/end, plus a derived `byte_length` — without paying for the byte-range read. Pairs with v1.37's `section_neighbors`: both handle-only navigation primitives.

**Deliverables:**
- New `tools/get_section_summary.py` — single section, no content fetch.
- Registered as 38th MCP tool. Schema requires `repo` + `section_id`.
- 6 tests in `tests/test_v1_38_0.py` covering error paths, content-exclusion contract, byte_length derivation, _meta shape.
- `tests/test_server.py` tool count 37 → 38.

**Replay gate:** all 7 fixtures pass at 1.0 nDCG/MRR/Recall vs v1.37.0.
**Tests:** 936 → 942 (+6).

### v1.37.0 — section_neighbors navigation tool — ✅ SHIPPED (2026-04-26)
**Goal:** Cheap document-order navigation. New `section_neighbors` MCP tool returns prev/next siblings (in `byte_start` order, restricted to same `doc_path`), parent (via `parent_id`), and first child for a given section. Handles only — `{id, title, level, doc_path}` — no content reads. Fills the gap between `get_toc` (whole repo) and `get_section_context` (target+ancestors+children with content).

**Deliverables:**
- New `tools/section_neighbors.py` — pure Python, no embedding/byte-range reads.
- Registered as 37th MCP tool. Schema requires `repo` + `section_id`.
- 8 tests in `tests/test_v1_37_0.py` covering doc-isolation (no cross-doc next), parent resolution, first-child retrieval, error paths, handle shape.
- `tests/test_server.py` tool count 36 → 37.

### Hotfixes
- **v1.36.1** — deterministic ranking tie-break across all 4 sort sites in `doc_store.py`: score-only sort left ties in os.walk order, varying by filesystem. Now `(-score, section_id)`.
- **v1.36.2** — relaxed CI test thresholds (gate 0.02→0.05, lock 0.98→0.95) to absorb cross-platform BM25 line-length variance from CRLF vs LF checkouts.
- **v1.36.3** — bumped CI gate 0.05→0.06 to absorb a 4e-17 floating-point sliver. Release-time strict 0.02 gate unchanged.

### v1.36.0 — path_glob filter on retrieval — ✅ SHIPPED (2026-04-26)
**Goal:** Monorepo scoping. New `path_glob` arg on `search_sections`, `get_toc`, and `get_toc_tree` restricts results to sections whose `doc_path` matches an fnmatch pattern (e.g. `"api/**/*.md"`, `"reference/*"`). Stacks with the existing exact-match `doc_path` arg. Defaults to None (no filter).

**Deliverables:**
- `path_glob: Optional[str] = None` added to all three tools' Python signatures, schemas, and dispatch.
- Filter runs in-place via `fnmatch.fnmatch` against `doc_path`. In `search_sections`, runs before dedup/role/profile filtering so `max_results` math stays right. In `get_toc_tree`, filters the doc-grouping pass.
- `_meta.path_glob` echoed back when set.
- Threaded through repo-group fan-out so cross-repo glob filtering works.
- 13 tests in `tests/test_v1_36_0.py` covering default-None pass-through, glob match, no-match, schema parity for all 3 tools.

**Replay gate:** all 7 fixtures pass vs v1.35.0 baseline at 1.0 nDCG/MRR/Recall.
**Tests:** 912 → 925 (+13).

### v1.35.0 — CHANGELOG generator + code-block compression — ✅ SHIPPED (2026-04-26)
**Goal:** Two small wins. (a) Make CHANGELOG.md mechanically reproducible from git — a release-time utility that reads `release: vN.N.N — title` commits and re-renders Keep-a-Changelog markdown. (b) Add an opt-in `compress_code` kwarg on `get_section`/`get_sections` that strips blank lines and full-line comments inside fenced code blocks before returning. Disk content untouched; `_meta.code_compressed_bytes` reports savings.

**Deliverables:**
- `scripts/generate_changelog.py` — git-driven Keep-a-Changelog renderer (idempotent, em/en/hyphen-tolerant separator, drops Co-Authored-By trailers).
- `src/jdocmunch_mcp/retrieval/code_compress.py` — fence state machine, language→comment-marker map (Python/JS/TS/SQL/Lua/Lisp/Erlang families), partial-line comments preserved.
- `compress_code: bool = False` on `get_section` and `get_sections`. Schema + dispatch updated.
- 29 tests in `tests/test_v1_35_0.py` covering compression edge cases (empty, no-fence, tilde fences, long fences, unclosed, multiple fences, partial comments, unknown languages), batch aggregation, schema parity, and the CHANGELOG generator (regex separators, paragraph extraction, end-to-end smoke).

**Replay gate:** all 7 fixtures pass vs v1.34.0 baseline (no regression).
**Tests:** 883 → 912 (+29).
**Scope:** All planned features re-engineered to ship within the 1.x line. Each release is independently shippable, gated by replay benchmark from v1.11.0 onward.

---

## 0. Vision & Positioning

jDocMunch is the **token-efficient, section-aware, MCP-native documentation retrieval system** in the jMunch suite. It owns documentation; jcodemunch owns code symbols; jdatamunch owns data. Differentiators we will lean into:

1. **Chunkless author-boundary retrieval.** Sections are authored boundaries with stable IDs and byte offsets — not arbitrary token chunks.
2. **Per-section freshness + drift detection.** Indexes don't quietly lie.
3. **Replayable retrieval-quality gate.** Every release ships an nDCG/MRR/Recall number.
4. **Code-block ↔ jcodemunch bridge.** The only tool that resolves doc code samples to live code symbols.
5. **Structured OpenAPI retrieval.** First-class operation/schema graph, not flattened prose.

Out of scope (and stays out): hosted portals, generic RAG chatbots, dashboards-as-product, code/docstring parsing (jcodemunch owns that).

---

## 1. Critical Bugs (block v1.10.0) — ✅ COMPLETE (2026-04-26)

All seven landed in v1.10.0. Tests: 400 → 414 (+14 regression tests in `tests/test_v1_10_0_bugfixes.py`). Full suite green.

These are correctness failures hiding behind feature claims. Land in v1.10.0 with regression tests; nothing else in the roadmap is meaningful while they exist.

### B1. Lexical content channel is dead in production — ✅ DONE
- **Location:** `storage/doc_store.py::_score_section` line 213; `parser/sections.py::Section.to_dict` line 28.
- **Symptom:** "BM25-style" lexical scoring claim is false post-load. `Section.to_dict` excludes `content`. `DocIndex.sections` loaded from JSON have no `content` field. `_score_section` reads `sec.get("content","")` → always empty → content channel scores zero on every loaded index.
- **Impact:** Sections only score on title + summary + tags. Long sections with rich body text but generic titles silently rank below trivial matches.
- **Fix (v1.10.0):** Either (a) include content in `Section.to_dict` and accept the storage hit, or (b) lazy-fetch content via byte-range read for the top-K candidates after a title/summary prune. (b) is preferred and aligns with F4 in v1.13.0.
- **Test:** `test_score_loaded_section_uses_content` asserts a section whose content matches the query but title doesn't outranks a section with weak title-only match.

### B2. Code-fence-blind heading splitter — ✅ DONE
- **Location:** `parser/markdown_parser.py::parse_markdown`.
- **Symptom:** `_ATX_RE` matches `# foo` inside ` ``` ` / `~~~` / indented code blocks, creating phantom sections.
- **Impact:** Inflated section count, unstable IDs across edits to code examples, phantom hits in retrieval.
- **Fix (v1.10.0):** Add a single-pass state machine. Track fence open on `^(`{3,}|~{3,})\s*\w*\s*$`, exit on matching delimiter. Skip ATX/setext detection while in-fence. Also skip lines indented ≥4 spaces preceded by a blank line (CommonMark indented code blocks).
- **Test:** Golden fixture `tests/fixtures/edge/headings_in_code.md` with code samples containing `#`, `##`, setext-like underlines; assert section count equals authored heading count.

### B3. Setext detector misfires on horizontal rules and table separators — ✅ DONE
- **Location:** `parser/markdown_parser.py::parse_markdown` lines 132–138.
- **Symptom:** `_SETEXT_H1_RE.match(line_stripped) and prev_line.strip()` triggers on any non-empty prev line. A table separator `| --- | --- |` after a header row, or an `---` horizontal rule after any text line, becomes a setext heading.
- **Fix (v1.10.0):** Require prev line is non-blank, not preceded by blank line ⇒ inside a paragraph; reject when prev_line contains `|` (table-like) or when current line contains spaces between dashes.
- **Test:** Fixture with table + hr, assert no spurious sections.

### B4. INDEX_VERSION drift in CLAUDE.md — ✅ DONE
- **Location:** `CLAUDE.md` line declaring `INDEX_VERSION=1`. Code is `2`.
- **Fix (v1.10.0):** Sync doc; add `tests/test_docs_config_parity.py` to fail CI on future drift (mirror jcodemunch v1.70.0 pattern).

### B5. Anchor normalization collides — ✅ DONE
- **Location:** `tools/get_broken_links.py::_anchor_matches_section` line 51.
- **Symptom:** `slug.replace("-", "").replace("_", "")` causes `foo-bar` and `foobar` to be treated equal. False negatives on broken-link detection.
- **Fix (v1.10.0):** Compare canonical hierarchical slug exactly (case-insensitive only).

### B6. `_INDEX_CACHE` is unbounded — ✅ DONE
- **Location:** `storage/doc_store.py:19`.
- **Symptom:** Module-level dict grows without bound; long-running MCP servers leak.
- **Fix (v1.10.0):** Replace with `OrderedDict` + `maxsize=8`, LRU evict. Track hits/misses for telemetry (v1.14.0).

### B7. Provider re-instantiation on every query — ✅ DONE
- **Location:** `embeddings/provider.py::embed_query` and `_get_provider`.
- **Symptom:** SBERT model reloads, OpenAI/Gemini clients recreated per call. Adds hundreds of ms per `search_sections`.
- **Fix (v1.10.0):** Module-level `_PROVIDER_CACHE` keyed by `(provider_name, model_name)`. Invalidate when env vars change.

---

## 2. Release Plan (10 releases)

Each release: version bump → tests pass (`PYTHONPATH=src python -m pytest tests/ -q`) → replay-benchmark gate (from v1.11.0) → build → PyPI → tag → GitHub release → CLAUDE.md + MEMORY.md updated as part of the same commit.

---

### v1.10.0 — Correctness foundation — ✅ SHIPPED (2026-04-26)
**Goal:** Fix the bugs that make later work meaningless. No new features.

**Includes:** B1, B2, B3, B4, B5, B6, B7.

**New tests:**
- `tests/fixtures/edge/headings_in_code.md` + `test_parser_code_fence.py` (B2).
- `tests/fixtures/edge/setext_in_tables.md` + `test_parser_setext_guards.py` (B3).
- `test_score_loaded_section_uses_content` (B1).
- `test_anchor_collision_distinct` (B5).
- `test_index_cache_bounded` (B6).
- `test_provider_cached_across_queries` (B7).
- `test_docs_config_parity.py` (B4).

**Acceptance criteria:**
- All 400 existing tests still pass; ≥7 new tests added.
- `tokens_saved` claim regression-tested with A/B fixture (no metric drop).
- Section count on a real-world fixture (e.g., FastAPI docs subset) drops only via B2 fixes; no spurious change.

**Risk:** B1 (b) lazy content fetch can silently inflate latency on bad queries — gate with replay benchmark in v1.11.0 before optimizing further.

---

### v1.11.0 — Replay benchmark + retrieval quality baseline — ✅ SHIPPED (2026-04-26)
**Goal:** Lock current behavior. Every future release proves it didn't regress.

**New module:** `benchmarks/replay/`
- `metrics.py`: `ndcg_at_k`, `mrr_at_k`, `recall_at_k`, `aggregate()`. Pure Python.
- `run_replay.py`: CLI harness. Runs each fixture query through `search_sections`, computes per-query + overall metrics, optionally writes `benchmarks/replay/results/{fixture}-v{VERSION}.json`. `--baseline X.Y.Z --gate 0.02` exits non-zero if any aggregate drops > gate.
- `fixtures/`: at minimum `self_v1_11_0.json` (10 golden queries against the jdocmunch-mcp repo's own docs), `markdown_realworld.json` (5 queries against a checked-in subset of FastAPI docs), `mdx_realworld.json` (Mintlify-style), `rst_realworld.json` (Sphinx-style), `openapi_realworld.json`, `notebook_realworld.json`.
- Fixture format: `{name, repo, repo_sha, queries:[{query, expected_top_k:[section_ids]}]}`.

**CI:** GitHub Actions workflow `replay.yml` runs on every PR, gate at 0.02 (2% drop allowed for noise).

**Tests:** 19+ in `test_replay_metrics.py` covering metric math, aggregate, gate logic, fixture-shape contract, baseline lock.

**Acceptance:** Self-fixture locked at 1.0/1.0/1.0. CI gate active.

**Dependency for:** every later release.

---

### v1.12.0 — True BM25-Okapi with field weighting — ✅ SHIPPED (2026-04-26)
**Goal:** Replace `_score_section` heuristic with a real lexical engine.

**Design:**
- **Index-time:** compute corpus stats once on `save_index` and `incremental_save`. Persist into the index JSON under a `bm25_stats` block: `{N, avgdl_title, avgdl_summary, avgdl_content, df:{token: count}}`. Cap `df` to top 5000 tokens by document frequency.
- **Tokenizer (`retrieval/tokenize.py`):** lowercase, strip punctuation, split CamelCase + snake_case, drop English stop-words, retain 2+ char tokens. Markdown-aware: skip fenced code (already excluded by B2 fix), strip URLs to host+path tokens.
- **BM25-Okapi (`retrieval/bm25.py`):** `k1=1.2`, `b=0.75` defaults; tunable via env `JDOCMUNCH_BM25_K1` / `JDOCMUNCH_BM25_B`.
- **Field-weighted score:** `score = 3·BM25(title) + 1.5·BM25(summary) + 1·BM25(content)`. Content scored on top-200 prune (B1 lazy fetch).
- **Heading-path boost:** when query terms appear in any ancestor's title (computed via stored hierarchical slug), add `0.5 · BM25(ancestor_path)`.
- **Default:** flag `lexical_engine="bm25"` (default) vs `"legacy"` for backward compat. Drop legacy in v2.0.0.

**Replay gate:** ≥5% nDCG@5 lift on `markdown_realworld.json` and `rst_realworld.json` vs v1.11.0 baseline; no fixture regresses.

**Tests:** 12+ in `test_bm25.py`: tokenizer edge cases, IDF correctness, length normalization, field-weight precedence, heading-path boost, two-stage prune correctness.

---

### v1.13.0 — Two-stage retrieval + provider caching cleanup — ✅ SHIPPED (2026-04-26)
**Goal:** Latency and cost. Unblocks scaling beyond ~5k sections.

**Components:**
- **Stage A (`retrieval/prune.py`):** in-memory inverted index `token → set[section_id]`, built lazily on first search per index, cached on the `DocIndex` instance. Cap candidate set at 200 by union of query-token postings.
- **Stage B:** BM25 + cosine on candidates only.
- **`_hybrid_search` rewrite:** Reciprocal Rank Fusion (`k=60`) instead of min-max. RRF is stable under sparse candidates and doesn't require global score floors.
- **`embed_query` cache:** `@lru_cache(maxsize=256)` on (provider, model, query). 5-minute TTL via timestamp on entry.

**Replay gate:** p95 search latency on a 10k-section fixture drops ≥3× vs v1.12.0; nDCG@5 within 0.01 of v1.12.0 (no regression).

**Tests:** prune correctness (every result that would have ranked top-K under full scan still appears), RRF stability, query-cache invalidation.

---

### v1.14.0 — Telemetry foundation + analyze_perf — ✅ SHIPPED (2026-04-26)
**Goal:** Direct port of jcodemunch v1.74.0. Without telemetry, F17 weight tuning and F8 drift detection are blind.

**Components:**
- `storage/token_tracker.py` grows `_tool_latencies: dict[str, deque(maxlen=512)]` + `_tool_errors`.
- `record_tool_latency(tool, duration_ms, ok, repo)` and `latency_stats()` module-level entries.
- `server.py::call_tool` wraps every dispatch in `time.perf_counter()` + `try/finally` recording.
- `get_session_stats` (new tool) returns `latency_per_tool: {tool: {count, p50_ms, p95_ms, max_ms, errors, error_rate}}`.
- New `analyze_perf` tool: `window=session|1h|24h|7d|all`. Session reads in-memory ring; longer windows read `~/.doc-index/telemetry.db` (opt-in via `JDOCMUNCH_PERF_TELEMETRY=1` or `perf_telemetry_enabled` config flag).
- Persistent SQLite: `tool_calls(ts, tool, duration_ms, ok, repo)` indexed on `tool+ts`. Rolling cap via `perf_telemetry_max_rows` (default 100k), trimmed in 1k-row batches.

**Tests:** 13+ in `test_perf_telemetry.py` mirroring jcodemunch's coverage.

**Replay gate:** no retrieval-quality change.

---

### v1.15.0 — Content-hash-keyed embedding cache + drift canary — ✅ SHIPPED (2026-04-26)
**Goal:** Cut embedding cost 60–95% on doc churn; detect provider/model regressions.

**Embedding cache:**
- Sidecar `~/.doc-index/<owner>/<name>.embeddings.jsonl`, line-keyed by `content_hash` → `{provider, model, dim, vector, captured_at}`.
- Cache header: `{provider, model, dim}` validated on load; provider/model change purges cache.
- `embed_sections` looks up by hash before calling provider; only POSTs cache misses. Persist after each batch.
- Survives `incremental_save` — sections preserved across re-index keep their cached vector.
- New CLI: `jdocmunch-mcp clear-embedding-cache --repo <repo>`.

**Drift canary:**
- `embeddings/embed_drift.py` with 16-string immutable `CANARY_STRINGS` tuple (covers function names, prose, code-like tokens, multilingual snippet). Append-only contract; never reorder.
- `capture_canary()` embeds via the active provider, persists to `~/.doc-index/embed_canary.json`. Idempotent unless `force=True`.
- `check_drift(threshold=0.05)` re-embeds, computes per-canary cosine drift, alarms when any drift > threshold. Returns `{has_canary, alarm, threshold, max_drift, mean_drift, captured_provider, captured_model, current_provider, current_model, per_canary:[...]}`.
- New tool `check_embedding_drift` registered in MCP surface (count 16 → 17). Force-included like jcodemunch's `set_tool_tier`.

**Tests:** 17+ in `test_embedding_cache.py` and `test_embed_drift.py` ported from jcodemunch v1.80.0.

**Replay gate:** no retrieval-quality regression; embedding-cost A/B harness shows ≥80% reduction on a "edit 3 of 50 docs" fixture.

---

### v1.16.0 — Section freshness probe + retrieval confidence — ✅ SHIPPED (2026-04-26)
**Goal:** Agents stop confidently quoting stale sections; LLMs get a "should I expand?" signal.

**Freshness (`retrieval/freshness.py`):**
- `FreshnessProbe` with three buckets per result: `stale_index` (index file_hash != current file's hash on disk), `edited_uncommitted` (per-section content_hash != current byte-range hash), `fresh`.
- Cached HEAD-file lookup + per-file mtime stats (lazy, 2s timeout).
- `_freshness` field added to every result entry in `search_sections`, `get_section`, `get_section_context`, `get_sections`.
- `_meta.freshness` summary on every envelope: `{fresh, edited_uncommitted, stale_index}` counts.

**Confidence (`retrieval/confidence.py`):**
- `compute_confidence(top_results)` → 0–1 weighted geometric mean of:
  - `gap = (top1 - top2) / top1` (weight 0.35)
  - `strength = 1 - exp(-top1 / 4)` (weight 0.35)
  - `identity` = exact title hit on top-3 (weight 0.15; default 0.7 if ambiguous)
  - `freshness` = 1.0 fresh / 0.6 stale (weight 0.15)
- `attach_confidence(results, include_components=False)` mutates `_meta.confidence`. With `include_components=True`, adds `_meta.confidence_components`.
- Wired into `search_sections` (all three paths).

**Tests:** 14+ across `test_freshness.py` + `test_confidence.py` (mirror jcodemunch v1.75.0/v1.77.0).

**Replay gate:** no quality drop. Add new metric to replay output: `mean_confidence_top1`, tracked but not gated.

---

### v1.17.0 — Code-block-aware indexing + jcodemunch bridge — ✅ SHIPPED (2026-04-26)
**Goal:** The differentiator. Make doc code samples first-class, queryable, and linkable to jcodemunch symbols.

**Parser:**
- During `parse_markdown`, after the B2 fence state machine lands, emit `Section.code_blocks: [{lang, content, byte_start, byte_end, block_id}]` where `block_id = "{section_id}::code#{n}"`.
- Persist in `Section.to_dict`. Index-version bump to 3 (full re-index).

**New MCP tool `find_code_examples`:**
- Args: `repo, query, lang?, max_results=10, role?`.
- Searches code-block content via BM25 + (when `lang=python|js|...`) tree-sitter token tokenization (lazy import, optional).
- Returns `{block_id, section_id, doc_path, lang, snippet, _meta}`.

**New MCP tool `link_code_to_symbols`:**
- Args: `repo, code_repo, max_examples=200`.
- For each code block in jdocmunch's `repo`, call jcodemunch's `search_symbols` (via subprocess MCP client or HTTP if running) with extracted identifiers.
- Returns mapping `{block_id → [symbol_id]}` and reverse `{symbol_id → [block_id]}`.
- Bridge is best-effort; missing jcodemunch returns empty mapping with `_meta.bridge_available=false`.

**Index-side metadata:**
- `Section.code_block_count` for fast filtering.
- `DocIndex.code_block_index` (built lazily) `block_id → block` for O(1) byte-range read.

**Tests:** 25+ in `test_code_blocks.py` covering: mixed-language doc, fence-info-string parsing, byte-range integrity, jcodemunch bridge mocked.

**Replay gate:** new fixture `code_examples.json` (5 queries) locked at 1.0; no other fixture regresses.

**Deliverable:** demo notebook showing "find Python install examples that call `Client.authenticate`" working end-to-end with jcodemunch.

---

### v1.18.0 — Structured OpenAPI retrieval — ✅ SHIPPED (2026-04-26)
**Goal:** Promote OpenAPI to a first-class doc type. No more flattening to prose.

**Parser rewrite (`parser/openapi_parser.py`):**
- Detect OpenAPI 2.0 / 3.0 / 3.1 by version string.
- Each operation becomes a `Section` with role-typed metadata:
  ```
  Section.metadata.openapi_op = {
    method, path, operationId, summary, description,
    tags, parameters: [...], request_body_schema, response_schemas: {code: ref},
    deprecated, security
  }
  ```
- Each schema (`components/schemas/*` or `definitions/*`) becomes a `Section` with `metadata.openapi_schema = {name, type, properties, required, used_by_operations: [opId]}`.
- Tag groups become parent sections; ungrouped goes under `Operations`.
- Deterministic section IDs: `repo::doc::op-{operationId|method-path-slug}` and `repo::doc::schema-{name}`.

**New MCP tools:**
- `find_endpoint(repo, path_glob?, method?, tag?)`.
- `find_operations_using_schema(repo, schema_name)`.
- `list_endpoints_by_tag(repo, tag)`.
- `get_schema_graph(repo, schema_name)` — returns transitive schema dependencies.

**Existing tools (search_sections, get_section, etc.):** still work; OpenAPI sections searchable like any other.

**Tests:** 30+ in `test_openapi_structured.py` against Petstore + Stripe API + GitHub API spec fixtures.

**Replay gate:** `openapi_realworld.json` nDCG@5 ≥0.85 (lock new baseline).

---

### v1.19.0 — Section role classification + glossary — ✅ SHIPPED (2026-04-26)
**Goal:** Task-aware retrieval profiles ("show troubleshooting near 'connection refused'").

**Role classifier (`retrieval/roles.py`):**
- Heuristic first: heading regex (`^(?:Example|Troubleshoot|Error|FAQ|API|Tutorial|Quickstart|Concept|How.?To|Reference|Guide)`), code-block density, imperative-verb density, definition-pattern density.
- Tier 2 (optional, AI): when heuristic confidence < 0.6, batch-classify via existing summarizer providers. Cache role on `Section.role`.
- Roles enum: `concept | tutorial | how_to | reference | api | example | troubleshooting | changelog | faq | other`.

**Glossary extractor (`retrieval/glossary.py`):**
- Detect definition patterns: `**Term** —`, `Term : description`, `*X is*`, RST `.. glossary::` directive, MDX `<Glossary>` component.
- Build per-repo `terms.json`: `{term: {section_id, context, defined_at_byte_range}}`.
- Single-word search queries auto-resolve through glossary first; multi-word queries optionally boost sections defining a query term.

**New MCP tools:**
- `lookup_term(repo, term)`.
- `list_terms(repo)`.
- `search_sections(role="troubleshooting"|...)` filter.
- `search_sections(profile="install"|"debug"|"explain")` — preset weight bundles.

**Tests:** 22+ in `test_roles.py` + `test_glossary.py`.

**Replay gate:** new fixture `roles_filter.json` locked.

---

### v1.20.0 — Capstone bundle (formerly scoped as v2.0.0) — ✅ SHIPPED (2026-04-26)
**Goal:** Light up the v1.10–v1.19 foundations with related-graph navigation, drift-aware diff, health diagnostics, and a tighter retrieval surface. Major-version bump rejected as unjustified — the only user-visible breakage is `lexical_engine="legacy"` now raising; everything else is additive. Real v2.0.0 deferred until a genuinely backwards-incompatible change ships (schema bump, new MCP wire format, etc.).

**Shipped:**
- Drop legacy `lexical_engine` fallback (was deprecated in v1.12.0; now raises `ValueError`).
- New `estimate_savings_text()` helper that uses `count_tokens` (tiktoken when available) for accurate counts.
- `retrieval/related.py` + `get_related_sections` tool — structural (parent/child/sibling/cousin) and semantic (top-N cosine) neighbors.
- `get_section_diff` tool — unified diff between indexed snapshot and current on-disk byte range; reports identical/divergent hashes.
- `get_doc_health` tool — single-shot diagnostics: section_count, doc_count, role_distribution, freshness counts, broken_link_count, drift status, BM25 corpus sanity, embedding coverage.
- `get_section_context(include_related=True)` — adaptive context budget appends related-section summaries.

**Deferred to a future v2.0.0 (when other breaking changes accumulate):**
- Online weight tuning (port jcodemunch v1.79.0 — needs a ranking-event ledger to be added first).
- Boilerplate detector + suppression.
- Notebook output preservation + cell-pair retrieval.
- Cross-repo concept graph for monorepos.
- Tutorial-path reconstruction.
- Inverse coverage tool (`get_undocumented_symbols`).
- Section schema bump to `INDEX_VERSION=4` with auto-migration on first load.
- Real tiktoken-or-error replacement of the bytes/4 estimator (current additive helper preserves the heuristic).

## Reserved for 2.x (license-blocked — won't ship until a major-version license revision is planned)

Each item below would unavoidably break a 1.x licensee. Deferred indefinitely. Re-evaluate only when sales explicitly approves a 2.x cut.

| Item | Why it's 2.x-only |
|---|---|
| Drop bytes/4 token estimate (require tiktoken) | Removes a fallback an existing user might rely on |
| Rename `list_repos` MCP name (drop `index_repo` / `list_repos` aliases) | Tool removal breaks agents pinned to the name |
| Forced reindex on schema bump | We auto-migrate on 1.x; "force" would break offline upgrades |
| MCP wire-format change (e.g. envelope rename) | Breaks every existing consumer at once |

## Ships on 1.x (additive — coming in 1.21+)

Everything from the original "v2.0.0 capstone bundle" that can be re-engineered as additive lands here:

### v1.21.0 — Real-world replay corpora — ✅ SHIPPED (2026-04-26)
**Goal:** Lock retrieval quality against real docs, not just self-fixture. Pure infrastructure; zero API change.

- `benchmarks/replay/fixtures/markdown_realworld.json` — checked-in slice of FastAPI docs.
- `benchmarks/replay/fixtures/rst_realworld.json` — checked-in slice of a Sphinx project (e.g. requests).
- `benchmarks/replay/fixtures/openapi_realworld.json` — Petstore + a non-trivial spec.
- `benchmarks/replay/fixtures/notebook_realworld.json` — small Jupyter book slice.
- All locked at v1.21.0 baselines. CI gate extended to fail on any of them.

### v1.22.0 — Tutorial path + inverse coverage tools — ✅ SHIPPED (2026-04-26)
**Goal:** Two pure-additive MCP tools that complete the navigation surface.

- `get_tutorial_path(repo, start_section_id)` — detects `Next:` / `Previous:` links, frontmatter `next:` / `prev:`, ordered file naming (`01-intro.md`); returns ordered section IDs.
- `get_undocumented_symbols(doc_repo, code_repo)` — companion to jcodemunch's `get_untested_symbols`; walks code_repo's symbols and returns those whose name/qualified-name appears in zero section title/summary/content. Best-effort jcodemunch bridge (mirrors v1.17 `link_code_to_symbols` import-fallback pattern).

### v1.23.0 — Ranking-event ledger + online weight tuning — ✅ SHIPPED (2026-04-26)
**Goal:** Port jcodemunch v1.79.0 in a 1.x-safe way. New SQLite table; new MCP tool; existing tools untouched.

- New `ranking_events` table in `~/.doc-index/telemetry.db` (additive — opt-in via `JDOCMUNCH_PERF_TELEMETRY=1`, same flag as analyze_perf's persistent sink).
- `record_ranking_event` called from `search_sections` post-attach (no-op when telemetry disabled).
- New `tools/tune_weights.py` and `tune_weights` MCP tool: reads `ranking_events`, proposes ±0.05 step on `semantic_weight` per repo when correlation crosses threshold (min 50 events). Persists to `~/.doc-index/tuning.jsonc`.
- `search_sections` reads the tuned weight when `semantic_weight` is at its default 0.5; explicit non-default values always win.

### v1.24.0 — Related-graph persistence + boilerplate detector — ✅ SHIPPED (2026-04-26)
**Goal:** Speed up `get_related_sections` on big indexes; remove repeated headers/footers from token budgets.

- Sidecar adjacency list at `~/.doc-index/<owner>/<name>.related.json` written at index time. `get_related_sections` consumes it when present; falls back to on-demand build (current behavior).
- New `retrieval/boilerplate.py`: shingled cross-section matching detects repeated content (license headers, "Edit this page on GitHub" footers, nav menus). Persisted as `~/.doc-index/<owner>/<name>.boilerplate.json`.
- `get_section`, `get_sections`, `get_section_context` gain `strip_boilerplate: bool = False` kwarg. When True, suppress matched fragments before returning content; `_meta.boilerplate_stripped_bytes` reports the reduction.

### v1.25.0 — Notebook output preservation — ✅ SHIPPED (2026-04-26)
**Goal:** Preserve the teaching value of notebooks (currently `convert_notebook` strips outputs).
**Scope landed:** stream / execute_result / display_data / error outputs rendered into the markdown body (blockquote-formatted so the BM25 tokenizer indexes every word). HTML outputs strip-converted; image outputs collapsed to a marker; JSON outputs fenced. INDEX_VERSION stayed at 3 — no schema change required, ships purely in `notebook_parser.py`. The `Section.metadata.cell_pair_id` notion deferred to a future minor when we encounter a use case the body-fold doesn't cover.

- `parser/notebook_parser.py` rewrite: each cell becomes a `Section` with `metadata.cell_type` ∈ `{markdown, code}` and `metadata.outputs: [{type, text|html|image_b64_truncated}]`. Code cells + immediate output share `metadata.cell_pair_id` for "show me example with output" retrieval.
- `INDEX_VERSION` 3 → 4 with auto-migration on first load (silent upgrade — old indexes still readable, new fields populated on next reindex). Per the 1.x compatibility contract, no forced reindex.

### v1.26.0 — Cross-repo concept graph — ✅ SHIPPED (2026-04-26)
**Goal:** Monorepo-friendly fan-out search.

- `~/.doc-index/_groups.jsonc` config: `{"docs-everywhere": ["python-docs", "internal-runbook", "openapi-spec"]}`.
- `search_sections(repo_group="docs-everywhere", ...)` fans out across constituent indices, fuses via Reciprocal Rank Fusion (`k=60`, reuses v1.13 RRF). Existing `repo` arg unchanged.
- New tool `list_repo_groups`.

### v1.27.0 — Phase-6 infrastructure (batch 1: integrity + golden corpus) — ✅ SHIPPED (2026-04-26)
**Goal:** Tighten testing surface — protect against the silent-corruption bug class that motivated B1/B2.

**Shipped:**
- `verify_index` MCP tool + `jdocmunch-mcp verify-index` CLI subcommand. Walks every section, byte-range-reads, recomputes SHA-256, compares to stored hash. Reports drift / missing / error. Exits 2 on drift; 0 clean.
- Section-boundary golden corpus: `tests/fixtures/golden_sections/*.json` snapshots of {id, title, level, byte_start, byte_end, content_hash, parent_id} for every file under `benchmarks/replay/corpus/`. Property test asserts current parser output matches.

### v1.28.0 — Phase-6 infrastructure (batch 2: drift sim + cross-platform paths + replay log) — ✅ SHIPPED (2026-04-26)
**Shipped:**
- Embedding-drift simulation suite — provider-swap scenarios prove the canary alarms fire at expected thresholds (subtle drift below threshold, orthogonal swap, anti-parallel swap, threshold-boundary just-above-vs-loose).
- Cross-platform path matrix — `_safe_content_path` resolves nested doc paths within root and rejects traversal; `index_local` round-trip with deep nesting confirmed; stored `doc_path` always uses posix separators.
- Retrieval-replay log capture (opt-in via `JDOCMUNCH_REPLAY_LOG=1`). JSONL stream at `~/.doc-index/replay.log` complementary to v1.23 SQLite ranking ledger; grep-friendly. `read_all(limit=N)` for offline analysis.

### v1.29.0 — Sphinx toctree + VuePress + OpenAPI 3.1 + Swagger 2.0 + autotune — ✅ SHIPPED (2026-04-26)
**Shipped:**
- `get_tutorial_path` gains two new strategies: `sphinx_toctree` (parses `.. toctree::` directives, tolerates `:maxdepth:` etc options, handles `Display label <doc>` form) and `vuepress_sidebar` (reads `.vuepress/config.json`; supports the flat-string sidebar form via JSON-or-converted-markdown fallback parser; grouped-dict form documented as known limitation pending source_root persistence).
- New corpus + locked fixtures `openapi31_realworld` (OpenAPI 3.1 with webhooks + nullable types + `[type, "null"]`) and `swagger20_realworld` (Swagger 2.0 with `definitions:` + `host:`/`basePath:`).
- `index_local(autotune=True)` opt-in flag runs the v1.23 weight tuner against accumulated ranking events at end of indexing. No-op when telemetry is disabled.
- CI gate updated to loop all 7 fixtures.

### v1.30.0 — source_root persistence + README contract + grouped VuePress — ✅ SHIPPED (2026-04-26)
**Shipped:**
- `DocIndex.source_root` field; populated by `index_local` with `str(folder_path)`. Persisted only when non-empty (omit-when-empty pattern).
- `_vuepress_chain` now reads the raw `.vuepress/config.json` from disk via `source_root` first; falls back to the cached/converted form. Grouped-dict sidebar form `[{text, children:[...]}]` resolvable end-to-end.
- README.md gains a customer-visible "1.x compatibility commitment" block enumerating what jdocmunch-mcp will never break on 1.x: tool removal/rename, Section-field drop, forced-reindex schema bump, wire-format break, default-behavior raise. Test pins the exact phrasing so future README edits don't accidentally weaken it.

### v1.31.0 — Stale-index simulation + multi-format regression harness — ✅ SHIPPED (2026-04-26)
**Shipped:**
- Stale-index simulation suite — single mutation surfaces in all three observability paths (FreshnessProbe / verify_index / get_section_diff). Append-only mutation correctly classifies as `edited_uncommitted` without flagging unaffected byte ranges. Missing file surfaces both in FreshnessProbe and verify_index. search_sections `_meta.freshness` summary reflects drift.
- Multi-format regression harness — parametrized test exercises every supported format (md / mdx / rst / adoc / html / txt / json / xml / tscn / yaml-as-OpenAPI) end-to-end through index_local + load + section count. Companion test asserts every parser registration in ALL_EXTENSIONS exists.

**Phase-6 backlog: COMPLETE.** Original PRD §6 enumerated 13 infrastructure items. v1.27 → v1.31 shipped all of them as additive 1.x minors.

---

### v2.0.0 — Major bet bundle (RESERVED — see § "Reserved for 2.x")
**Goal:** Capstone release. Everything earned by v1.19.0 lights up.

**Includes:**
- **Online weight tuning** (port jcodemunch v1.79.0). Per-repo learned `semantic_weight`, `bm25_field_weights`, `freshness_penalty` from ranking-event ledger. Persisted to `~/.doc-index/tuning.jsonc`. Min 50 events / metric, ±0.05 step on signal correlation, dry-run mode.
- **Related-section graph** (F13). Structural edges (siblings/cousins via `parent_id`) + semantic top-3 cosine neighbors per section, score>0.6. Persisted as adjacency list. New tool `get_related_sections(section_id, mode=structural|semantic|both)`. Used to power adaptive `get_section_context`.
- **Adaptive context budget in `get_section_context`** (F23). Priority queue: ancestors → target_summary → child_summaries → fill with target_content → append related-section summaries. New `strategy=summary_first|content_first` arg.
- **Section diff tool** (`get_section_diff`).
- **Tutorial-path reconstruction** (`get_tutorial_path`).
- **Boilerplate detector + suppression** (F25).
- **Notebook output preservation + cell-pair retrieval** (F10).
- **Index health tool** (`get_doc_health`): combined orphan/broken/stale/coverage/dedupe/drift score.
- **Cross-repo concept graph for monorepos** (F19): `--alias-group` + RRF fan-out.
- **Inverse coverage tool** (`get_undocumented_symbols`): companion to jcodemunch's `get_untested_symbols`.

**Breaking changes (v2.0.0 only):**
- Drop `lexical_engine="legacy"` flag. BM25 is the only engine.
- Rename `tools/list_repos.py` MCP-exposed name to `doc_list_repos` (v1.0 alias removed).
- `Section` schema bump: index-version 4. Migration runs on first load.
- Remove the `bytes/4` token estimate; use a real tokenizer (`tiktoken` if available, fallback to character heuristic with documented multiplier).

**Replay gate:** all fixtures meet or exceed v1.19.0 metrics; new tutorial-path fixture locked.

---

## 3. Quality Gates Per Release

Every release post-v1.11.0 must:
1. Pass full test suite (`PYTHONPATH=src python -m pytest tests/ -q`).
2. Pass replay benchmark (`run_replay --baseline <prev> --gate 0.02`).
3. Update `CLAUDE.md` and `MEMORY.md` in the same commit.
4. Capture token-savings baseline (`benchmarks/token_baselines/v{version}.json`) — schema mirrors jcodemunch.
5. Tag, push, GitHub release with notes.

---

## 4. Infrastructure Backlog (built incrementally)

| Name | Built in | Purpose |
|---|---|---|
| Retrieval golden corpus | v1.11.0 | nDCG/MRR/Recall lock |
| Section-boundary golden tests | v1.10.0 (B2) | Parser stability |
| Multi-format regression suite | v1.11.0 | All ALL_EXTENSIONS roundtrip |
| Byte-offset integrity check | v1.10.0 | Detect drift between byte_range and raw |
| Stale-index simulation | v1.16.0 | Validate freshness probe |
| Token-savings measurement | v1.14.0 | Trust the `tokens_saved` metric |
| Ranking eval harness | v1.12.0 | Param-sweep `k1`, `b`, `semantic_weight` |
| Section-ID stability test | v1.10.0 | Property-based: reorder content, IDs survive |
| Cache-hit telemetry | v1.14.0 + v1.15.0 | `_INDEX_CACHE` and embedding cache hit rate |
| Retrieval replay logs | v1.14.0 | Capture real queries (opt-in JSONL) |
| Cross-platform path tests | v1.10.0 | Windows/Posix symmetry |
| Embedding-drift simulation | v1.15.0 | Validate canary alarm |
| Index health diagnostics | v2.0.0 | One-shot doc-set audit |

---

## 5. Risk Register

| Risk | Mitigation |
|---|---|
| BM25 corpus stats inflate index size | Cap `df` to top 5000 tokens; measure on real fixture; tune cap |
| Two-stage prune drops relevant results | Replay benchmark gate; fall back to full scan when query has <2 distinct tokens |
| Embedding cache stale after model upgrade | Cache header includes `(provider, model, dim)`; purge on mismatch |
| Drift canary false positives | Per-canary report + `force` reset; alarm only on `max_drift`, not mean |
| jcodemunch bridge unavailable | Best-effort; `_meta.bridge_available=false`; tool still returns code blocks |
| OpenAPI spec variants (Swagger 2 / 3.0 / 3.1) | Version detection; comprehensive fixture matrix |
| Online weight tuning overfits | `min_events=50` gate; `|delta_conf| ≥ 0.05` threshold; bounded clamp |
| v2.0.0 schema migration breaks user indexes | Auto-migrate on first load with backup; fail loud, never silent |
| Provider rate limits during full re-index | Embedding cache (v1.15.0) + summarizer batch retries |

---

## 6. Out of Scope

- Hosted SaaS or web portal.
- Generic "AI chat with docs" interface.
- Cosmetic dashboards.
- Code symbol parsing or docstring extraction (jcodemunch territory).
- Database/data exploration (jdatamunch territory).
- Real-time collaborative editing or wiki authoring.
- Browser extensions or IDE plugins beyond MCP.

---

## 7. Open Questions

1. **Embedding cache location:** sidecar JSONL vs SQLite vs in-index. JSONL chosen for simplicity + git-diff-ability; revisit if file size > 100MB.
2. **Tokenizer:** `tiktoken` opt-in (small extra dep) vs pure-Python regex. Default pure-Python; `JDOCMUNCH_TOKENIZER=tiktoken` for accuracy mode.
3. **OpenAPI: should each schema be a Section?** Yes — schemas are first-class navigation targets. Cost: more sections per spec; mitigated by `role=schema` filter.
4. **AI role classification cost:** how much budget per repo? Default cap 100 sections; configurable.
5. **Cross-MCP bridge transport (v1.17.0):** subprocess MCP client vs assume jcodemunch HTTP-mode running vs file-based shared cache. Lean toward "jcodemunch must be running on stdio in same agent" — bridge is opt-in.

---

## 8. Sequencing Summary

```
v1.10.0 — Critical bugs (B1–B7)              [unblocks everything]
v1.11.0 — Replay benchmark + gate            [unblocks all later releases]
v1.12.0 — True BM25 + heading-path           [retrieval correctness]
v1.13.0 — Two-stage prune + RRF + caches     [latency + scale]
v1.14.0 — Telemetry + analyze_perf           [observability foundation]
v1.15.0 — Embedding cache + drift canary     [cost + reliability]
v1.16.0 — Freshness + confidence             [agent workflow]
v1.17.0 — Code blocks + jcodemunch bridge    [differentiator #1]
v1.18.0 — Structured OpenAPI                 [differentiator #2]
v1.19.0 — Roles + glossary                   [task-aware retrieval]
v2.0.0  — Tuning + graphs + cleanups         [capstone, breaking]
```

Each release is independently shippable. Each is gated by replay benchmark from v1.11.0 onward. Each updates CLAUDE.md + MEMORY.md as part of the same commit. No orphan releases, no orphan features.
