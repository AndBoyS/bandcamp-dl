from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from pathlib import Path

import requests

from bandcamp_dl.config import AlbumInfo, ArtMode, Config
from bandcamp_dl.const import VERSION
from bandcamp_dl.download import TrackFileDownloader, TrackOutcome, retry_delay_amount
from bandcamp_dl.paths import template_to_path
from bandcamp_dl.tagging import write_id3_tags
from bandcamp_dl.utils import print_clean

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlbumDownloadProgress:
    album: AlbumInfo
    num_tracks: int
    track_num: int = 0
    art_path: Path | None = None


class BandcampDownloader:
    """Orchestrates path resolution, downloading and tagging for an album download run"""

    def __init__(self, config: Config) -> None:
        # TODO: update version
        self.headers = {"User-Agent": f"bandcamp-dl/{VERSION} (https://github.com/evolution0/bandcamp-dl)"}
        self.session = requests.Session()
        self.config = config
        self._downloader = TrackFileDownloader(config, session=self.session, headers=self.headers)

    def download_album(self, album: AlbumInfo) -> bool:
        """Start album download process

        :param album: album info
        :return: True if successful
        """
        progress = AlbumDownloadProgress(album=album, num_tracks=len(album.tracks))
        for track_index, track in enumerate(album.tracks, start=1):
            progress = replace(progress, track_num=track_index)

            filepath = template_to_path(track=track, album=album, config=self.config)
            tmp_path = filepath.with_name(f"{filepath.name}.tmp")
            output_path = tmp_path.with_suffix("")
            folder = output_path.parent
            if not folder.exists():
                logger.debug(f"Directory doesn't exist for {output_path}, creating..")
            folder.mkdir(parents=True, exist_ok=True)

            logger.debug(f"Current file for track '{track.title}' on album '{album.title}':\n\t{tmp_path}")

            fetched_art = self._ensure_cover_art(progress=progress, dirname=folder, track_title=track.title)
            if fetched_art is not None:
                progress = replace(progress, art_path=fetched_art)

            try:
                outcome = self._downloader.download_track(tmp_path, output_path, track=track, progress=progress)

                if outcome is not TrackOutcome.COMPLETED:
                    continue

                if not self.config.debug:
                    print_clean(
                        f"\r({progress.track_num}/{progress.num_tracks}) [{'=' * 50}] :: Encoding: {output_path.stem}"
                    )
                write_id3_tags(
                    tmp_path,
                    track=track,
                    album=album,
                    art_path=progress.art_path,
                    config=self.config,
                )
                self._finalize_track(tmp_path, output_path)
                if not self.config.debug:
                    print_clean(
                        f"\r({progress.track_num}/{progress.num_tracks}) [{'=' * 50}] :: Finished: {output_path.stem}"
                    )
            except Exception:
                logger.exception(f"Failed processing '{track.title}' on album '{album.title}'")
                if not self.config.ignore_errors:
                    return False
                print("Skipping track..")
            finally:
                tmp_path.unlink(missing_ok=True)

        not_finished = self.config.base_dir / f"{VERSION}.not.finished"
        if not_finished.is_file():
            not_finished.unlink()

        # Remove album art image as it is embedded
        if self.config.art_mode is ArtMode.EMBED and progress.art_path is not None:
            progress.art_path.unlink()

        return True

    def _ensure_cover_art(self, *, progress: AlbumDownloadProgress, dirname: Path, track_title: str) -> Path | None:
        """Fetch the album cover into the track's directory once and report its path

        :param progress: per-album download progress, only read
        :param dirname: directory of the current track
        :param track_title: title of the current track, used for error messages
        :return: path of the available cover image, or None when there is none
        """
        cover_path = dirname / "cover.jpg"
        if progress.album.art is None:
            return None
        if cover_path.exists() and cover_path.stat().st_size > 0:
            return cover_path
        attempts_amt = self.config.max_retries + 1
        for attempt in range(1, attempts_amt + 1):
            delay = min(2**attempt, 5)
            try:
                r = self.session.get(progress.album.art, headers=self.headers)
                r.raise_for_status()
                if len(r.content) == 0:
                    logger.debug(f"Empty album art response for '{track_title}' on '{progress.album.title}'")
                else:
                    with cover_path.open("wb") as f:
                        _ = f.write(r.content)
                    return cover_path
            except Exception as e:
                delay = retry_delay_amount(e, attempt)
                if delay is None:
                    cover_path.unlink(missing_ok=True)
                    logger.warning(f"Couldn't download album art for '{track_title}' on '{progress.album.title}'")
                    return None
                logger.debug(f"Transient failure downloading album art for '{track_title}': {e}")
            if attempt < attempts_amt:
                logger.debug(f"Retrying in {delay:.0f}s..")
                time.sleep(delay)
        logger.warning(f"Couldn't download album art for '{track_title}' on '{progress.album.title}'")
        cover_path.unlink(missing_ok=True)
        return None

    def _finalize_track(self, tmp_path: Path, output_path: Path) -> None:
        """Rename the completed tmp file to its final output path

        :param tmp_path: temporary path of the tmp mp3 file
        :param output_path: final path
        """
        logger.debug(f"Renaming:\n\t{tmp_path} -to-> {output_path}")

        if output_path.exists():
            logger.warning(f"Output file already exists, replacing it: {output_path}")

        _ = tmp_path.replace(output_path)
