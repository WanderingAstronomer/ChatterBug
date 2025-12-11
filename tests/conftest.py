"""Pytest configuration for integration-heavy CLI tests.

This file ensures the project root is on ``PYTHONPATH`` so that
``python -m vociferous.cli.main`` works when running from the source
tree without an editable install. The environment modification is
process-wide and inherited by subprocess-based CLI invocations used
throughout the test suite.
"""

from __future__ import annotations

import os
from pathlib import Path


def _ensure_repo_on_path() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    existing = os.environ.get("PYTHONPATH")
    paths = [str(repo_root)]
    if existing:
        paths.append(existing)
    os.environ["PYTHONPATH"] = ":".join(paths)


_ensure_repo_on_path()

