from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

TEMPLATE = "%{artist}/%{album}/%{track} - %{title}"
OK_CHARS = "-_~"
SPACE_CHAR = "-"
CASE_LOWER = "lower"
CASE_UPPER = "upper"
CASE_CAMEL = "camel"
CASE_NONE = "none"
USER_HOME = Path.home()
# For Linux/BSD https://www.freedesktop.org/wiki/Software/xdg-user-dirs/
# For Windows ans MacOS .appname is fine
CONFIG_PATH = USER_HOME / (".config" if os.name == "posix" else ".bandcamp-dl") / "bandcamp-dl.json"
OPTION_MIGRATION_FORWARD = "forward"
OPTION_MIGRATION_REVERSE = "reverse"


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
    case_mode: str = CASE_LOWER
    ascii_only: bool = False
    keep_spaces: bool = False
    no_confirm: bool = False
    debug: bool = False
    embed_genres: bool = False
    untitled_path_from_slug: bool = False
    cover_quality: int = 0
    truncate_album: int = 0
    truncate_track: int = 0


class Track(GoodBaseModel):
    title: str
    duration: float
    track_id: int | None
    track_num: int
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
            json_config = json.load(f)
        return Config(**json_config)
    return Config()
