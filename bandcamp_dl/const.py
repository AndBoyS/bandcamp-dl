from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any

import toml

REPO_DIR = Path(__file__).parents[1]

pyproject_path = REPO_DIR / "pyproject.toml"
if pyproject_path.exists():
    metadata: dict[str, Any] = toml.load(pyproject_path)
    VERSION: str = metadata["project"]["version"]
else:
    VERSION = importlib.metadata.version("bandcamp-downloader")
