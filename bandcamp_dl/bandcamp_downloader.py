from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests

from bandcamp_dl.config import AlbumInfo, ArtMode, Config
from bandcamp_dl.const import VERSION
from bandcamp_dl.download import TrackFileDownloader, TrackOutcome
from bandcamp_dl.paths import template_to_path
from bandcamp_dl.tagging import write_id3_tags
from bandcamp_dl.utils import print_clean

logger = logging.getLogger(__name__)


@dataclass
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
        # TODO: move the incomplete-tracklist confirm decision to the caller
        if not album.all_tracks_have_url and not self.config.no_confirm:
            while True:
                try:
                    choice = input("Track list incomplete, some tracks may be private, download anyway? (yes/no): ")
                except EOFError:
                    print("\nCancelling download process.")
                    return False
                choice = choice.strip().lower()
                if choice in ("yes", "y"):
                    print("Starting download process.")
                    return self._download_album(album, ignore_errors=self.config.ignore_errors)
                if choice in ("no", "n"):
                    print("Cancelling download process.")
                    return False
                print("Please answer yes or no.")
        return self._download_album(album, ignore_errors=self.config.ignore_errors)

    def _download_album(self, album: AlbumInfo, ignore_errors: bool = False) -> bool:
        progress = AlbumDownloadProgress(album=album, num_tracks=len(album.tracks))
        for track_index, track in enumerate(album.tracks, start=1):
            progress.track_num = track_index

            filepath = template_to_path(track=track, album=album, config=self.config)
            tmp_path = filepath.with_name(f"{filepath.name}.tmp")
            output_path = tmp_path.with_suffix("")
            folder = output_path.parent
            if not folder.exists():
                logger.debug(f" Directory doesn't exist for {output_path}, creating..")
            folder.mkdir(parents=True, exist_ok=True)

            logger.debug(f" Current file for track '{track.title}' on album '{album.title}':\n\t{tmp_path}")

            self._ensure_cover_art(progress=progress, dirname=folder, track_title=track.title)

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
                if not ignore_errors:
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

    def _ensure_cover_art(self, *, progress: AlbumDownloadProgress, dirname: Path, track_title: str) -> None:
        """Fetch the album cover into the track's directory once and track it on the per-album state

        :param progress: mutable per-album download progress
        :param dirname: directory of the current track
        :param track_title: title of the current track, used for error messages
        """
        cover_path = dirname / "cover.jpg"
        # TODO: failed art GET leaves zero-byte cover.jpg behind, blocking future art attempts
        if progress.album.art is not None and not cover_path.exists():
            try:
                with cover_path.open("wb") as f:
                    r = self.session.get(progress.album.art, headers=self.headers)
                    _ = f.write(r.content)
                progress.art_path = cover_path
            except Exception:
                logger.exception(
                    f"Couldn't download album art for track '{track_title}' on album '{progress.album.title}'"
                )
                print("Couldn't download album art.")

    def _finalize_track(self, tmp_path: Path, output_path: Path) -> None:
        """Rename the completed tmp file to its final output path

        :param tmp_path: temporary path of the tmp mp3 file
        :param output_path: final path
        """
        logger.debug(f" Renaming:\n\t{tmp_path} -to-> {output_path}")

        if output_path.exists():
            logger.warning(f"Output file already exists, replacing it: {output_path}")

        _ = tmp_path.replace(output_path)
