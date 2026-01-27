from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import toml

REPO_DIR = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode().strip())

metadata: dict[str, Any] = toml.load(REPO_DIR / "pyproject.toml")
VERSION: str = metadata["project"]["version"]
