from __future__ import annotations

import importlib.metadata
from enum import Enum
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

# TODO: update metadata
PROG = "bandcamp-dl"
USER_AGENT = f"{PROG}/{VERSION} (https://github.com/evolution0/bandcamp-dl)"


class ErrorStatus(Enum):
    ERROR = 1
    NO_ERROR = 2


def is_error(err_status: ErrorStatus) -> bool:
    return err_status == ErrorStatus.ERROR
