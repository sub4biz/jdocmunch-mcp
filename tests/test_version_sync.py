"""Guard against pyproject.toml / __init__.py version drift.

Both pins must move in lockstep on every release. v1.63.0 shipped with
`src/jdocmunch_mcp/__init__.py` stuck at 1.60.0 (three minors behind
pyproject.toml) because nothing failed when they diverged. This test
fails the build the moment they disagree.
"""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml has no top-level version line"
    return m.group(1)


def _init_version() -> str:
    text = (REPO_ROOT / "src" / "jdocmunch_mcp" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "src/jdocmunch_mcp/__init__.py has no __version__ assignment"
    return m.group(1)


def test_pyproject_and_init_versions_match():
    py = _pyproject_version()
    init = _init_version()
    assert py == init, (
        f"version drift: pyproject.toml={py!r} vs "
        f"src/jdocmunch_mcp/__init__.py={init!r}. "
        f"Bump both in the same commit."
    )
