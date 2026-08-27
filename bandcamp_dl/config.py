from __future__ import annotations

import logging
import os
from enum import Enum
from pathlib import Path

import toml
from pydantic import BaseModel, ConfigDict, model_validator
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


USER_HOME = Path.home()
# For Linux/BSD https://www.freedesktop.org/wiki/Software/xdg-user-dirs/
# For Windows ans MacOS .appname is fine
# TODO: check if can be better
CONFIG_PATH = USER_HOME / (".config" if os.name == "posix" else ".bandcamp-dl") / "bandcamp-dl.toml"


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
    base_dir: Path = USER_HOME
    template: str = TEMPLATE
    overwrite: bool = False
    # TODO: change to art modes
    no_art: bool = False
    embed_art: bool = False
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

    @model_validator(mode="after")
    def validate_art_options(self) -> Self:
        if self.no_art and self.embed_art:
            raise ValueError("no_art and embed_art cannot both be enabled")
        return self

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
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open() as f:
            toml_config = toml.load(f)
        return Config(**toml_config)
    return Config()
