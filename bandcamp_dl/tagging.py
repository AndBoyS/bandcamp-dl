from __future__ import annotations

import logging
from pathlib import Path

from mutagen import id3, mp3

from bandcamp_dl.config import AlbumInfo, Config, TrackInfo

logger = logging.getLogger(__name__)


def write_id3_tags(
    tmp_path: Path,
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

    # TODO: consolidate the three save passes into one
    audio = mp3.MP3(tmp_path)
    _ = audio.delete()
    audio["TIT2"] = id3._frames.TIT2(encoding=3, text=["title"])
    audio["WOAF"] = id3._frames.WOAF(url=album.url)
    _ = audio.save(filename=None, v1=2)

    audio = mp3.MP3(tmp_path)
    if config.group:
        label = album.label if album.label is not None else ""
        audio["TIT1"] = id3._frames.TIT1(encoding=3, text=label)

    if config.embed_lyrics:
        lyrics = track.lyrics if track.lyrics is not None else ""
        audio["USLT"] = id3._frames.USLT(encoding=3, lang="eng", desc="", text=lyrics)

    if config.embed_art and art_path is not None:
        with art_path.open("rb") as cover_img:
            cover_bytes = cover_img.read()
            audio["APIC"] = id3._frames.APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes)
    if config.embed_genres:
        genres = album.genres if album.genres is not None else ""
        audio["TCON"] = id3._frames.TCON(encoding=3, text=genres)
    _ = audio.save()

    audio = mp3.EasyMP3(tmp_path)

    track_num = track.track_num
    if track_num is None:
        track_num = "1"
    audio["tracknumber"] = str(track_num)

    artist = track.track_artist
    if artist is None:
        artist = album.artist
    audio["artist"] = artist

    audio["title"] = title
    audio["albumartist"] = album.artist
    audio["album"] = album.title
    audio["date"] = album.date
    _ = audio.save()

    logger.debug(f" Encoding process finished for '{title}'..")
