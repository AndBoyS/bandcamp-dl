from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path

import toml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self

logger = logging.getLogger(__name__)


class CaseType(Enum):
    LOWER = "lower"
    UPPER = "upper"
    CAMEL = "camel"
    NONE = "none"

    # On python3.11 can move to StrEnum
    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return repr(self)


class ArtMode(Enum):
    NONE = "none"
    FILE = "file"
    EMBED = "embed"
    FILE_EMBED = "file-embed"

    # On python3.11 can move to StrEnum
    def __repr__(self) -> str:
        return str(self.value)

    def __str__(self) -> str:
        return repr(self)


USER_HOME = Path.home()


def _user_config_dirs() -> list[Path]:
    """Candidate user config directories in priority order

    On Windows %APPDATA% comes first, with $XDG_CONFIG_HOME and $HOME/.config as fallbacks.
    On Linux and macOS uses $XDG_CONFIG_HOME or $HOME/.config.
    """
    dirs: list[Path] = []
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata is not None and appdata != "":
            dirs.append(Path(appdata))
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home is not None and xdg_config_home != "":
        dirs.append(Path(xdg_config_home))
    if os.name == "nt":
        dirs.append(USER_HOME / "AppData" / "Roaming")
    else:
        dirs.append(USER_HOME / ".config")
    return dirs


class GoodBaseModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
    )


def as_placeholder(value: str) -> str:
    return f"%{{{value}}}"


class TemplateTokens:
    trackartist = as_placeholder("trackartist")
    artist = as_placeholder("artist")
    album = as_placeholder("album")
    title = as_placeholder("title")
    date = as_placeholder("date")
    label = as_placeholder("label")
    track = as_placeholder("track")
    album_id = as_placeholder("album_id")
    track_id = as_placeholder("track_id")


_TTokens = TemplateTokens

# in 3.14 would be a template string
TEMPLATE = f"{_TTokens.artist}/{_TTokens.album}/{_TTokens.track} - {_TTokens.title}"
OK_CHARS = "-_~"
SPACE_CHAR = "-"


class Config(GoodBaseModel):
    base_dir: Path = Path(".")
    template: str = TEMPLATE
    overwrite: bool = False
    art_mode: ArtMode = ArtMode.FILE
    embed_lyrics: bool = False
    group: bool = False
    no_slugify: bool = False
    ok_chars: str = OK_CHARS
    space_char: str = SPACE_CHAR
    case_mode: CaseType = CaseType.LOWER
    ascii_only: bool = False
    keep_spaces: bool = False
    no_confirm: bool = False
    debug: bool = False
    embed_genres: bool = False
    untitled_path_from_slug: bool = False
    cover_quality: int = 0
    truncate_album: int = 0
    truncate_track: int = 0
    ignore_errors: bool = False
    # Number of retries after the initial download attempt (total attempts = max_retries + 1)
    max_retries: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def validate_template(self) -> Self:
        stripped = self.template.strip("/")
        if stripped != self.template:
            logger.warning(f"Template contains leading/trailing '/'; stripping: '{self.template}' -> '{stripped}'")
            self.template = stripped
        if stripped == "":
            raise ValueError("Template is empty after stripping path separators")
        return self


class TrackInfo(GoodBaseModel):
    title: str
    duration: float
    track_num: int | None = None
    download_url: str
    track_id: int | None = None
    track_url: str | None = None
    track_artist: str | None = None
    lyrics: str | None = None


class AlbumInfo(GoodBaseModel):
    tracks: list[TrackInfo]
    title: str
    artist: str
    label: str | None = None
    all_tracks_have_url: bool
    art: str | None = None
    date: str
    url: str
    genres: str | None = None
    album_id: int | None = None


def get_user_config() -> Config:
    config_dirs = list(dict.fromkeys(_user_config_dirs()))
    for config_dir in config_dirs:
        path = config_dir / "bandcamp-dl" / "bandcamp-dl.toml"
        if not path.exists():
            continue
        logger.debug(f"Reading user config from: {path}")
        try:
            with path.open() as f:
                toml_config = toml.load(f)
        except OSError:
            logger.debug(f"Cannot access user config at: {path}", exc_info=True)
            continue
        return Config(**toml_config)
    return Config()
