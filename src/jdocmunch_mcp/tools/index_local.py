"""Index local folder tool — walk, parse, summarize, save."""

import os
import time
from pathlib import Path
from typing import Optional

import pathspec

from ..parser import parse_file, preprocess_content, ALL_EXTENSIONS
from ..retrieval.roles import annotate_sections as _annotate_roles
from ..retrieval.glossary import extract_glossary, write_terms
from ..security import (
    validate_path,
    is_symlink_escape,
    is_secret_file,
    should_exclude_file,
    DEFAULT_MAX_FILE_SIZE,
)
from ..storage import DocStore
from ..summarizer import summarize_sections
from ..embeddings import embed_sections, get_provider_name, should_embed
from ._constants import SKIP_PATTERNS


def _load_gitignore(folder_path: Path) -> Optional[pathspec.PathSpec]:
    gitignore_path = folder_path / ".gitignore"
    if gitignore_path.is_file():
        try:
            content = gitignore_path.read_text(encoding="utf-8", errors="replace")
            return pathspec.PathSpec.from_lines("gitignore", content.splitlines())
        except Exception:
            pass
    return None


def _should_skip(rel_path: str) -> bool:
    normalized = "/" + rel_path.replace("\\", "/")
    for pat in SKIP_PATTERNS:
        if ("/" + pat) in normalized:
            return True
    return False


def discover_doc_files(
    folder_path: Path,
    max_files: int = 500,
    max_size: int = DEFAULT_MAX_FILE_SIZE,
    extra_ignore_patterns: Optional[list] = None,
    follow_symlinks: bool = False,
) -> tuple:
    """Discover doc files (.md, .txt, .rst) with security filtering."""
    files = []
    warnings = []
    root = folder_path.resolve()

    gitignore_spec = _load_gitignore(root)
    extra_spec = None
    if extra_ignore_patterns:
        try:
            extra_spec = pathspec.PathSpec.from_lines("gitignore", extra_ignore_patterns)
        except Exception:
            pass

    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        dir_path = Path(dirpath)
        try:
            dir_rel = dir_path.relative_to(root).as_posix()
        except ValueError:
            dirnames.clear()
            continue

        # Prune skipped directories in-place so os.walk won't descend into them
        dirnames[:] = [
            d for d in dirnames
            if not _should_skip(f"{dir_rel}/{d}/".lstrip("./"))
            and not (gitignore_spec and gitignore_spec.match_file(f"{dir_rel}/{d}/".lstrip("./")))
            and not (extra_spec and extra_spec.match_file(f"{dir_rel}/{d}/".lstrip("./")))
        ]

        for filename in filenames:
            file_path = dir_path / filename

            if not follow_symlinks and file_path.is_symlink():
                continue
            if file_path.is_symlink() and is_symlink_escape(root, file_path):
                warnings.append(f"Skipped symlink escape: {file_path}")
                continue

            if not validate_path(root, file_path):
                warnings.append(f"Skipped path traversal: {file_path}")
                continue

            rel_path = f"{dir_rel}/{filename}".lstrip("./") if dir_rel != "." else filename

            if _should_skip(rel_path):
                continue

            if gitignore_spec and gitignore_spec.match_file(rel_path):
                continue

            if extra_spec and extra_spec.match_file(rel_path):
                continue

            if is_secret_file(rel_path):
                warnings.append(f"Skipped secret file: {rel_path}")
                continue

            ext = file_path.suffix.lower()
            if ext not in ALL_EXTENSIONS:
                continue

            try:
                if file_path.stat().st_size > max_size:
                    continue
            except OSError:
                continue

            files.append(file_path)

        if len(files) >= max_files:
            break

    return files[:max_files], warnings


def index_local(
    path: str,
    name: Optional[str] = None,
    use_ai_summaries: bool = True,
    use_embeddings="auto",
    storage_path: Optional[str] = None,
    extra_ignore_patterns: Optional[list] = None,
    follow_symlinks: bool = False,
    incremental: bool = True,
    max_files: int = 500,
    autotune: bool = False,
) -> dict:
    """Index a local folder containing documentation files.

    Args:
        path: Path to local folder.
        name: Optional repo identifier override. Use when two folders share the same
              name (e.g. two libraries both with a 'docs' folder). Defaults to the
              folder name.
        use_ai_summaries: Whether to use AI for section summaries.
        use_embeddings: True/False/"auto". "auto" (default) enables embeddings when
                        an embedding provider is configured (GOOGLE_API_KEY,
                        OPENAI_API_KEY, or sentence-transformers installed).
        storage_path: Custom storage path (default: ~/.doc-index/).
        extra_ignore_patterns: Additional gitignore-style patterns to exclude.
        follow_symlinks: Whether to follow symlinks.
        incremental: When True and an existing index exists, only re-index changed files.
        max_files: Maximum number of doc files to index. Default 500.

    Returns:
        Dict with indexing results.
    """
    t0 = time.perf_counter()
    folder_path = Path(path).expanduser().resolve()

    if not folder_path.exists():
        return {"success": False, "error": f"Folder not found: {path}"}
    if not folder_path.is_dir():
        return {"success": False, "error": f"Path is not a directory: {path}"}

    use_embeddings = should_embed(use_embeddings)
    warnings = []

    try:
        doc_files, discover_warnings = discover_doc_files(
            folder_path,
            max_files=max_files,
            extra_ignore_patterns=extra_ignore_patterns,
            follow_symlinks=follow_symlinks,
        )
        warnings.extend(discover_warnings)

        if not doc_files:
            return {"success": False, "error": "No documentation files found"}

        repo_name = name if name else folder_path.name
        owner = "local"
        repo_id = f"{owner}/{repo_name}"
        store = DocStore(base_path=storage_path)

        # Read all discovered files
        current_files: dict = {}
        for file_path in doc_files:
            if not validate_path(folder_path, file_path):
                continue
            try:
                rel_path = file_path.relative_to(folder_path).as_posix()
            except ValueError:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                parsed_content = preprocess_content(content, rel_path)
                current_files[rel_path] = parsed_content
            except Exception as e:
                warnings.append(f"Failed to read {file_path}: {e}")

        # --- Incremental path ---
        if incremental and store.load_index(owner, repo_name) is not None:
            changed, new, deleted = store.detect_changes(owner, repo_name, current_files)

            if not changed and not new and not deleted:
                latency_ms = int((time.perf_counter() - t0) * 1000)
                return {
                    "success": True,
                    "message": "No changes detected",
                    "repo": f"{owner}/{repo_name}",
                    "folder_path": str(folder_path),
                    "incremental": True,
                    "changed": 0, "new": 0, "deleted": 0,
                    "_meta": {"latency_ms": latency_ms},
                }

            files_to_parse = set(changed) | set(new)
            new_sections = []
            raw_subset: dict = {}
            doc_types: dict = {}

            for rel_path in files_to_parse:
                content = current_files[rel_path]
                raw_subset[rel_path] = content
                ext = rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
                try:
                    sections = parse_file(content, rel_path, repo_id)
                    if sections:
                        new_sections.extend(sections)
                        doc_types[f".{ext}"] = doc_types.get(f".{ext}", 0) + 1
                except Exception as e:
                    warnings.append(f"Failed to parse {rel_path}: {e}")

            new_sections = summarize_sections(new_sections, use_ai=use_ai_summaries)
            _annotate_roles(new_sections)
            if use_embeddings:
                new_sections = embed_sections(
                    new_sections,
                    owner=owner, name=repo_name, storage_path=storage_path,
                )

            updated = store.incremental_save(
                owner=owner, name=repo_name,
                changed_files=changed, new_files=new, deleted_files=deleted,
                new_sections=new_sections, raw_files=raw_subset, doc_types=doc_types,
            )

            latency_ms = int((time.perf_counter() - t0) * 1000)
            result = {
                "success": True,
                "repo": f"{owner}/{repo_name}",
                "folder_path": str(folder_path),
                "incremental": True,
                "changed": len(changed), "new": len(new), "deleted": len(deleted),
                "section_count": len(updated.sections) if updated else 0,
                "indexed_at": updated.indexed_at if updated else "",
                "semantic_search": use_embeddings and get_provider_name() is not None,
                "_meta": {"latency_ms": latency_ms},
            }
            if warnings:
                result["warnings"] = warnings
            return result

        # --- Full index path ---
        all_sections = []
        doc_types = {}
        raw_files: dict = {}
        parsed_files = []

        for rel_path, content in current_files.items():
            ext = f".{rel_path.rsplit('.', 1)[-1].lower()}" if "." in rel_path else ""
            try:
                sections = parse_file(content, rel_path, repo_id)
                if sections:
                    all_sections.extend(sections)
                    doc_types[ext] = doc_types.get(ext, 0) + 1
                    raw_files[rel_path] = content
                    parsed_files.append(rel_path)
            except Exception as e:
                warnings.append(f"Failed to parse {rel_path}: {e}")

        if not all_sections:
            return {"success": False, "error": "No sections extracted from files"}

        all_sections = summarize_sections(all_sections, use_ai=use_ai_summaries)
        _annotate_roles(all_sections)
        if use_embeddings:
            all_sections = embed_sections(
                all_sections,
                owner=owner, name=repo_name, storage_path=storage_path,
            )

        # v1.19.0: glossary sidecar built from final section content.
        try:
            entries = extract_glossary(all_sections)
            write_terms(storage_path, owner, repo_name, entries)
        except Exception:
            pass  # glossary is best-effort; never fail indexing

        # v1.24.0: related-graph adjacency list sidecar.
        try:
            from ..retrieval.related_persist import write as _write_related
            _write_related(storage_path, owner, repo_name, all_sections)
        except Exception:
            pass

        # v1.24.0: boilerplate detector sidecar.
        try:
            from ..retrieval.boilerplate import write as _write_boilerplate
            _write_boilerplate(storage_path, owner, repo_name, all_sections)
        except Exception:
            pass

        # v1.29.0: opt-in autotune. Runs the v1.23 weight tuner on this
        # repo's accumulated ranking events; no-op when telemetry isn't
        # enabled. Failures swallowed.
        autotune_result = None
        if autotune:
            try:
                from .tune_weights import tune_weights as _tune_weights
                autotune_result = _tune_weights(
                    repo=f"{owner}/{repo_name}",
                    storage_path=storage_path,
                )
            except Exception:
                autotune_result = None

        saved = store.save_index(
            owner=owner,
            name=repo_name,
            sections=all_sections,
            raw_files=raw_files,
            doc_types=doc_types,
            source_root=str(folder_path),
        )

        latency_ms = int((time.perf_counter() - t0) * 1000)
        result = {
            "success": True,
            "repo": f"{owner}/{repo_name}",
            "folder_path": str(folder_path),
            "indexed_at": saved.indexed_at,
            "file_count": len(parsed_files),
            "section_count": len(all_sections),
            "doc_types": doc_types,
            "files": parsed_files[:20],
            "semantic_search": use_embeddings and get_provider_name() is not None,
            "_meta": {"latency_ms": latency_ms},
        }
        if autotune_result is not None:
            result["autotune"] = autotune_result

        if warnings:
            result["warnings"] = warnings
        if len(doc_files) >= max_files:
            result["note"] = f"Folder has many files; indexed first {max_files}"

        return result

    except Exception as e:
        return {"success": False, "error": f"Indexing failed: {str(e)}"}
