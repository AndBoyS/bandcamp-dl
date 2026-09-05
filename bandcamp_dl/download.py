from __future__ import annotations

import contextlib
import logging
import math
import time
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from requests import Response

from bandcamp_dl.config import Config, TrackInfo
from bandcamp_dl.utils import print_progress

if TYPE_CHECKING:
    from bandcamp_dl.bandcamp_downloader import AlbumDownloadProgress

logger = logging.getLogger(__name__)

TRANSIENT_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
_RETRY_AFTER_CAP = 30.0


class RetriesExhaustedError(RuntimeError):
    def __init__(self, title: str, attempts: int) -> None:
        super().__init__(f"Track '{title}' failed after {attempts} download attempts")


class TrackOutcome(IntEnum):
    """Result of a single track download sequence."""

    COMPLETED = 1
    SKIPPED = 2


def retry_delay_amount(e: Exception, attempt: int) -> float | None:
    """Return the seconds to wait before retrying a failed attempt, or None when it is permanent

    Retryable failures are transient connection issues and retryable HTTP statuses, honoring the
    server's Retry-After header where present.

    :param e: exception raised by the failed attempt
    :param attempt: 1-based attempt number, used for the default exponential backoff
    :return: seconds to wait before the next attempt, or None when the failure is permanent
    """
    default_delay = min(2**attempt, 5)
    if isinstance(e, requests.HTTPError):
        response = e.response
        status = response.status_code if isinstance(response, Response) else None
        if status is None or status not in RETRYABLE_STATUSES:
            return None
        retry_after = response.headers.get("Retry-After") if isinstance(response, Response) else None
        if retry_after is not None:
            with contextlib.suppress(ValueError):
                retry_after = float(retry_after)
                if math.isfinite(retry_after):
                    return min(max(retry_after, 0.0), _RETRY_AFTER_CAP)
        return default_delay
    if isinstance(e, TRANSIENT_ERRORS):
        return default_delay
    return None


class TrackFileDownloader:
    """Streams track files to disk with retry/backoff and progress display"""

    def __init__(self, config: Config, *, session: requests.Session) -> None:
        self.config = config
        self.session = session

    def download_track(
        self, tmp_path: Path, output_path: Path, *, track: TrackInfo, progress: AlbumDownloadProgress
    ) -> TrackOutcome:
        """Download a single track into its tmp file, retrying transient failures

        :param tmp_path: temporary path to stream into
        :param output_path: final output path
        :param track: track metadata
        :param progress: album progress for display
        :return: COMPLETED when fully downloaded, SKIPPED when the finished file already exists
        """
        last_error: Exception | None = None
        attempts_amt = self.config.max_retries + 1
        for attempt in range(1, attempts_amt + 1):
            tmp_path.unlink(missing_ok=True)
            if output_path.exists() and self.config.overwrite is not True:
                print(f"File: {output_path.name} already exists and is complete, skipping..")
                return TrackOutcome.SKIPPED
            delay = min(2**attempt, 5)
            try:
                with self.session.get(track.download_url, stream=True) as r:
                    r.raise_for_status()
                    file_length = r.headers.get("content-length")
                    file_length = int(file_length) if (file_length is not None and file_length.isdecimal()) else None
                    self._stream_response(
                        r=r, tmp_path=tmp_path, output_path=output_path, file_length=file_length, progress=progress
                    )
                local_size = tmp_path.stat().st_size
                if local_size > 0 and (file_length is None or local_size == file_length):
                    return TrackOutcome.COMPLETED
                if attempt < attempts_amt:
                    print(f"{output_path.name} is incomplete, retrying..")
            except Exception as e:
                last_error = e
                delay = retry_delay_amount(e, attempt)
                if delay is None:
                    raise
                logger.debug(f"Retrying '{track.title}' after failure: {e}")
            if attempt < attempts_amt:
                logger.debug(f"Retrying in {delay:.0f}s..")
                time.sleep(delay)
        raise RetriesExhaustedError(track.title, attempts_amt) from last_error

    def _stream_response(
        self,
        *,
        r: requests.Response,
        tmp_path: Path,
        output_path: Path,
        file_length: int | None,
        progress: AlbumDownloadProgress,
    ) -> None:
        """Stream the response body to tmp_path while printing progress

        :param r: streaming response of the track file
        :param tmp_path: temporary path to write to
        :param output_path: final path, used for progress display
        :param file_length: remote file size in bytes or None when unknown
        :param progress: album progress for display
        """
        chunk_size = max(file_length // 100, 8192) if bool(file_length) else 8192
        with tmp_path.open("wb") as f:
            dl = 0
            for data in r.iter_content(chunk_size=chunk_size):
                dl += len(data)
                _ = f.write(data)
                if not self.config.debug and bool(file_length):
                    print_progress(
                        track_num=progress.track_num,
                        num_tracks=progress.num_tracks,
                        label=f"Downloading: {output_path.stem}",
                        done=dl,
                        total=file_length,
                    )
