from __future__ import annotations

from pathlib import Path
from typing import Any

import toml

REPO_DIR = Path(__file__).parents[1]

metadata: dict[str, Any] = toml.load(REPO_DIR / "pyproject.toml")
VERSION: str = metadata["project"]["version"]
