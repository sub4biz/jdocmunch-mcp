# jDocMunch PRD — v1.10.0 → v2.0.0 Roadmap

**Owner:** jgravelle
**Drafted:** 2026-04-26
**Status:** Draft — pending sequencing review
**Scope:** 10 sequential releases (v1.10.0 → v1.18.0 → v2.0.0). Each release is independently shippable, gated by replay benchmark from v1.11.0 onward.

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

### v2.0.0 — Major bet bundle + breaking-change cleanups
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
