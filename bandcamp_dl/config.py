from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

import toml
from pydantic import BaseModel, ConfigDict, model_validator

TEMPLATE = "%{artist}/%{album}/%{track} - %{title}"
OK_CHARS = "-_~"
SPACE_CHAR = "-"


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
CONFIG_PATH = USER_HOME / (".config" if os.name == "posix" else ".bandcamp-dl") / "bandcamp-dl.toml"


class GoodBaseModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
    )


class Config(GoodBaseModel):
    base_dir: Path = USER_HOME
    template: str = TEMPLATE
    overwrite: bool = False
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

    @model_validator(mode="after")
    def validate_art_options(self) -> Config:
        if self.no_art and self.embed_art:
            raise ValueError("no_art and embed_art cannot both be enabled")
        return self


class Track(GoodBaseModel):
    title: str
    duration: float
    track_id: int | None
    track_num: int | None = None
    partial_url: str | None = None
    download_url: str | None = None
    artist: str | None = None
    artist_url: str | None = None
    lyrics: str | None = None
    file: dict[str, str] | None = None

    @property
    def full_track_url(self) -> str:
        return f"{self.artist_url}{self.partial_url}"


class Album(GoodBaseModel):
    tracks: list[Track]
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
