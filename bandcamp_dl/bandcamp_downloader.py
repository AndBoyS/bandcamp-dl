from __future__ import annotations

import contextlib
import logging
import math
import re
import shutil
import time
from enum import IntEnum
from pathlib import Path

import requests
import slugify
from mutagen import id3, mp3
from requests import Response

from bandcamp_dl.config import AlbumInfo, CaseType, Config, TemplateTokens, TrackInfo
from bandcamp_dl.const import VERSION

logger = logging.getLogger(__name__)


def print_clean(msg: str) -> None:
    terminal_size = shutil.get_terminal_size()
    print(f"{msg}{' ' * (terminal_size[0] - len(msg))}", end="")


# TODO: max retries in config
_MAX_ATTEMPTS = 3
_TRANSIENT_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
# TODO examine
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_RETRY_AFTER_CAP = 30.0


class _RetriesExhaustedError(RuntimeError):
    """Raised when a track download could not be completed within the retry budget."""


class TrackOutcome(IntEnum):
    """Result of a single track download sequence."""

    COMPLETED = 1
    SKIPPED = 2


def _is_transient(exc: Exception) -> bool:
    return isinstance(exc, _TRANSIENT_ERRORS)


def _retry_delay_amount(e: requests.HTTPError, attempt: int) -> float:
    """Get delay amount before retrying a retryable HTTP error, honoring the server's Retry-After header

    :param e: HTTP error carrying the failed response
    :param attempt: 1-based attempt number, used for the default exponential backoff
    :return: seconds to wait before the next attempt
    """
    response = e.response
    if isinstance(response, Response):
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            with contextlib.suppress(ValueError):
                retry_after = float(retry_after)
                if math.isfinite(retry_after):
                    return min(max(retry_after, 0.0), _RETRY_AFTER_CAP)
    return min(2**attempt, 5)


class BandcampDownloader:
    def __init__(self, config: Config, urls: list[str] | None = None) -> None:
        """Initialize variables we will need throughout the Class

        :param config: user config/args
        :param urls: list of urls
        """
        self.headers = {"User-Agent": f"bandcamp-dl/{VERSION} (https://github.com/evolution0/bandcamp-dl)"}
        self.session = requests.Session()
        self.config = config
        self.urls = urls
        self.album_art: Path | None = None
        self.num_tracks: int = 0
        # TODO: don't like this
        self.track_num: int = 0

    def start(self, album: AlbumInfo) -> bool:
        """Start album download process

        :param album: album info
        """

        if not album.all_tracks_have_url and not self.config.no_confirm:
            # TODO: reprompt
            choice = input("Track list incomplete, some tracks may be private, download anyway? (yes/no): ").lower()
            if choice in {"yes", "y"}:
                print("Starting download process.")
                return self.download_album(album, ignore_errors=self.config.ignore_errors)
            print("Cancelling download process.")
            return False
        return self.download_album(album, ignore_errors=self.config.ignore_errors)

    def template_to_path(
        self,
        track: TrackInfo,
        album: AlbumInfo,
        ascii_only: bool,
        ok_chars: str,
        space_char: str,
        keep_space: bool,
        case_mode: CaseType,
    ) -> Path:
        """Create valid filepath based on template

        :param track: track metadata
        :param album: track metadata
        :param ok_chars: optional chars to allow
        :param ascii_only: allow only ascii chars in filename
        :param keep_space: retain whitespace in filename
        :param case_mode: char case conversion logic (or none / retain)
        :param space_char: char to use in place of spaces
        :return: filepath
        """
        logger.debug(f" Generating filepath/trackname for '{track.title}'..")
        template = self.config.template
        logger.debug(f"\n\tTemplate: {template}")

        album_title = album.title
        album_title = _maybe_truncate(album_title, trunc_len=self.config.truncate_album)
        if self.config.untitled_path_from_slug and album_title.lower() == "untitled":
            album_title = album.url.split("/")[-1].replace("-", " ")

        track_title = track.title
        track_title = _maybe_truncate(track_title, trunc_len=self.config.truncate_track)

        track_artist = track.track_artist if track.track_artist is not None else album.artist
        label = album.label if album.label is not None else ""

        template_values: dict[str, str] = {
            TemplateTokens.trackartist: track_artist,
            TemplateTokens.artist: album.artist,
            TemplateTokens.album: album_title,
            TemplateTokens.title: track_title,
            TemplateTokens.date: album.date,
            TemplateTokens.label: label,
            TemplateTokens.track: str(track.track_num).zfill(2) if bool(track.track_num) else "Single",
            TemplateTokens.album_id: "" if album.album_id is None else str(album.album_id),
            TemplateTokens.track_id: "" if track.track_id is None else str(track.track_id),
        }
        for token, value in template_values.items():
            replacement = (
                value
                if self.config.no_slugify
                else _slugify(
                    value,
                    ascii_only=ascii_only,
                    ok_chars=ok_chars,
                    space_char=space_char,
                    keep_space=keep_space,
                    case_mode=case_mode,
                )
            )
            template = template.replace(token, replacement)

        output = self.config.base_dir / f"{template}.mp3"

        logger.debug(f" filepath/trackname generated for '{track.title}'..")
        logger.debug(f"\n\tPath: {output}")
        return output

    def create_directory(self, filename: Path) -> Path:
        """Create directory based on filename if it doesn't exist

        :param filename: full filename
        :return: directory path
        """
        directory = filename.parent
        logger.debug(f" Directory:\n\t{directory}")
        logger.debug(f" Directory doesn't exist for {filename}, creating..")
        directory.mkdir(parents=True, exist_ok=True)

        return directory

    def download_album(self, album: AlbumInfo, ignore_errors: bool = False) -> bool:
        """Download all MP3 files in the album

        :param album: album info
        :param ignore_errors: skip failed tracks instead of aborting the album
        :return: True if successful
        """
        for track_index, track in enumerate(album.tracks):
            self.num_tracks = len(album.tracks)
            self.track_num = track_index + 1

            filepath = self.template_to_path(
                track=track,
                album=album,
                ascii_only=self.config.ascii_only,
                ok_chars=self.config.ok_chars,
                space_char=self.config.space_char,
                keep_space=self.config.keep_spaces,
                case_mode=self.config.case_mode,
            )
            tmp_path = filepath.with_name(f"{filepath.name}.tmp")
            output_path = tmp_path.with_suffix("")
            dirname = self.create_directory(tmp_path)

            logger.debug(f" Current file for track '{track.title}' on album '{album.title}':\n\t{tmp_path}")

            cover_path = dirname / "cover.jpg"
            # TODO: failed art GET leaves zero-byte cover.jpg behind, blocking future art attempts
            if album.art is not None and not cover_path.exists():
                try:
                    with cover_path.open("wb") as f:
                        r = self.session.get(album.art, headers=self.headers)
                        _ = f.write(r.content)
                    self.album_art = cover_path
                except Exception:
                    logger.exception(f"Couldn't download album art for track '{track.title}' on album '{album.title}'")
                    print("Couldn't download album art.")

            try:
                outcome = self._download_track(tmp_path, output_path, track=track)
                if outcome is TrackOutcome.COMPLETED:
                    self.write_id3_tags(tmp_path, track=track, album=album)
                    self._finalize_track(tmp_path, output_path)
            except Exception:
                logger.exception(f"Failed processing '{track.title}' on album '{album.title}'")
                if not ignore_errors:
                    return False
                print("Skipping track..")
            finally:
                tmp_path.unlink(missing_ok=True)

        not_finished = self.config.base_dir / f"{VERSION}.not.finished"
        if not_finished.is_file():
            not_finished.unlink()

        # Remove album art image as it is embedded
        # TODO: album_art persists across albums; album without art after one with art -> FileNotFoundError here
        if self.config.embed_art and self.album_art is not None:
            self.album_art.unlink()

        return True

    def _download_track(self, tmp_path: Path, output_path: Path, track: TrackInfo) -> TrackOutcome:
        """Download a single track into its tmp file, retrying transient failures

        :param tmp_path: temporary path to stream into
        :param output_path: final output path
        :param track: track metadata
        :return: COMPLETED when fully downloaded, SKIPPED when the finished file already exists
        """
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            tmp_path.unlink(missing_ok=True)
            if output_path.exists() and self.config.overwrite is not True:
                print(f"File: {output_path.name} already exists and is complete, skipping..")
                return TrackOutcome.SKIPPED
            delay = min(2**attempt, 5)
            try:
                with self.session.get(track.download_url, headers=self.headers, stream=True) as r:
                    r.raise_for_status()
                    file_length = r.headers.get("content-length")
                    file_length = int(file_length) if (file_length is not None and file_length.isdecimal()) else None
                    self._stream_response(r, tmp_path, output_path, file_length)
                local_size = tmp_path.stat().st_size
                if local_size > 0 and (file_length is None or local_size == file_length):
                    return TrackOutcome.COMPLETED
                if attempt < _MAX_ATTEMPTS:
                    print(f"{output_path.name} is incomplete, retrying..")
            except requests.HTTPError as e:
                last_error = e
                response = e.response
                status = response.status_code if isinstance(response, Response) else None
                if status is not None and status in _RETRYABLE_STATUSES:
                    delay = _retry_delay_amount(e, attempt)
                    logger.debug(f"HTTP {status} downloading '{track.title}'")
                else:
                    print("Downloading failed..")
                    raise
            except Exception as e:
                last_error = e
                if not _is_transient(e):
                    print("Downloading failed..")
                    raise
                logger.debug(f"Transient failure downloading '{track.title}': {e}")
            if attempt < _MAX_ATTEMPTS:
                logger.debug(f"retrying in {delay:.0f}s..")
                time.sleep(delay)
        print("Maximum retries reached..")

        raise _RetriesExhaustedError(
            f"Track '{track.title}' failed after {_MAX_ATTEMPTS} download attempts"
        ) from last_error

    def _stream_response(
        self, r: requests.Response, tmp_path: Path, output_path: Path, file_length: int | None
    ) -> None:
        """Stream the response body to tmp_path while printing progress

        :param r: streaming response of the track file
        :param tmp_path: temporary path to write to
        :param output_path: final path, used for progress display
        :param file_length: remote file size in bytes or None when unknown
        """
        chunk_size = max(file_length // 100, 8192) if bool(file_length) else 8192
        with tmp_path.open("wb") as f:
            dl = 0
            for data in r.iter_content(chunk_size=chunk_size):
                dl += len(data)
                _ = f.write(data)
                if not self.config.debug and bool(file_length):
                    done = int(50 * dl / file_length)
                    done = min(done, 50)
                    print_clean(
                        f"\r({self.track_num}/{self.num_tracks}) "
                        f"[{'=' * done}{' ' * (50 - done)}] :: "
                        f"Downloading: {output_path.stem}"
                    )

    def write_id3_tags(self, tmp_path: Path, track: TrackInfo, album: AlbumInfo) -> None:
        """Write metadata to the MP3 file

        :param tmp_path: name of mp3 file
        :param track: track metadata
        :param album: album metadata
        """
        title = track.title
        logger.debug(f" Encoding process starting for '{title}'..")

        filename = tmp_path.name[:-8]

        if not self.config.debug:
            print_clean(f"\r({self.track_num}/{self.num_tracks}) [{'=' * 50}] :: Encoding: {filename}")

        audio = mp3.MP3(tmp_path)
        _ = audio.delete()
        audio["TIT2"] = id3._frames.TIT2(encoding=3, text=["title"])
        audio["WOAF"] = id3._frames.WOAF(url=album.url)
        _ = audio.save(filename=None, v1=2)

        audio = mp3.MP3(tmp_path)
        if self.config.group:
            label = album.label if album.label is not None else ""
            audio["TIT1"] = id3._frames.TIT1(encoding=3, text=label)

        if self.config.embed_lyrics:
            lyrics = track.lyrics if track.lyrics is not None else ""
            audio["USLT"] = id3._frames.USLT(encoding=3, lang="eng", desc="", text=lyrics)

        if self.config.embed_art and self.album_art is not None:
            with self.album_art.open("rb") as cover_img:
                cover_bytes = cover_img.read()
                audio["APIC"] = id3._frames.APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes)
        if self.config.embed_genres:
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

    def _finalize_track(self, tmp_path: Path, output_path: Path) -> None:
        """Rename the completed tmp file to its final output path

        :param tmp_path: temporary path of the tmp mp3 file
        :param output_path: final path
        """
        logger.debug(f" Renaming:\n\t{tmp_path} -to-> {output_path}")

        if output_path.exists():
            logger.warning(f"Output file already exists, replacing it: {output_path}")

        _ = tmp_path.replace(output_path)

        if self.config.debug:
            return

        print_clean(f"\r({self.track_num}/{self.num_tracks}) [{'=' * 50}] :: Finished: {output_path.stem}")


def _maybe_truncate(s: str, trunc_len: int) -> str:
    if trunc_len > 0 and len(s) > trunc_len:
        s = s[:trunc_len]
    return s


def _slugify(
    content: str,
    ascii_only: bool,
    ok_chars: str,
    space_char: str,
    keep_space: bool,
    case_mode: CaseType,
) -> str:
    retain_case = case_mode != CaseType.LOWER
    if case_mode == CaseType.UPPER:
        content = content.upper()
    if case_mode == CaseType.CAMEL:
        # pyrefly: ignore [implicit-any-lambda]
        content = re.sub(r"(((?<=\s)|^|-)[a-z])", lambda x: x.group().upper(), content.lower())
    return slugify.slugify(
        content,
        ok=ok_chars,
        only_ascii=ascii_only,
        spaces=keep_space,
        lower=not retain_case,
        space_replacement=space_char,
    )
