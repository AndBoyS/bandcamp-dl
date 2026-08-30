from __future__ import annotations

import logging
from pathlib import Path

from mutagen import id3, mp3

from bandcamp_dl.config import AlbumInfo, Config, TrackInfo

logger = logging.getLogger(__name__)


def write_id3_tags(
    tmp_path: Path,
    *,
    track: TrackInfo,
    album: AlbumInfo,
    art_path: Path | None,
    config: Config,
) -> None:
    """Write metadata to the MP3 file

    :param tmp_path: name of mp3 file
    :param track: track metadata
    :param album: album metadata
    :param art_path: path of the downloaded cover art, if any
    :param config: user config/args
    """
    title = track.title
    logger.debug(f" Encoding process starting for '{title}'..")

    audio = mp3.MP3(tmp_path)
    _ = audio.delete()
    if audio.tags is None:
        audio.add_tags()
    tags = audio.tags
    assert tags is not None

    artist = track.track_artist
    if artist is None:
        artist = album.artist

    track_num = track.track_num
    if track_num is None:
        track_num = "1"

    tags.add(id3.TIT2(encoding=3, text=[title]))
    tags.add(id3.TPE1(encoding=3, text=[artist]))
    tags.add(id3.TPE2(encoding=3, text=[album.artist]))
    tags.add(id3.TALB(encoding=3, text=[album.title]))
    tags.add(id3.TDRC(encoding=3, text=album.date))
    tags.add(id3.TDOR(encoding=3, text=album.date))
    tags.add(id3.TRCK(encoding=3, text=str(track_num)))
    tags.add(id3.WOAF(url=album.url))

    if config.group:
        label = album.label if album.label is not None else ""
        tags.add(id3.TIT1(encoding=3, text=label))

    if config.embed_lyrics:
        lyrics = track.lyrics if track.lyrics is not None else ""
        tags.add(id3.USLT(encoding=3, lang="eng", desc="", text=lyrics))

    if config.embed_art and art_path is not None:
        with art_path.open("rb") as cover_img:
            cover_bytes = cover_img.read()
            tags.add(id3.APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes))

    if config.embed_genres:
        genres = album.genres if album.genres is not None else ""
        tags.add(id3.TCON(encoding=3, text=genres))

    _ = audio.save(v1=2)

    logger.debug(f" Encoding process finished for '{title}'..")
