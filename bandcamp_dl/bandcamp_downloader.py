from __future__ import annotations

import logging
import os
import re
import shutil

import requests
import slugify
from mutagen import id3, mp3

from bandcamp_dl.config import AlbumInfo, CaseType, Config, TemplateTokens, TrackInfo
from bandcamp_dl.const import VERSION

logger = logging.getLogger(__name__)


def print_clean(msg: str) -> None:
    terminal_size = shutil.get_terminal_size()
    print(f"{msg}{' ' * (terminal_size[0] - len(msg))}", end="")


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
        self.album_art: str | None = None
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
                return self.download_album(album)
            print("Cancelling download process.")
            return False
        return self.download_album(album)

    def template_to_path(
        self,
        track: TrackInfo,
        album: AlbumInfo,
        ascii_only: bool,
        ok_chars: str,
        space_char: str,
        keep_space: bool,
        case_mode: CaseType,
    ) -> str:
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

        output = f"{self.config.base_dir}/{template}.mp3" if self.config.base_dir is not None else f"{template}.mp3"

        logger.debug(f" filepath/trackname generated for '{track.title}'..")
        logger.debug(f"\n\tPath: {output}")
        return output

    def create_directory(self, filename: str) -> str:
        """Create directory based on filename if it doesn't exist

        :param filename: full filename
        :return: directory path
        """
        directory = os.path.dirname(filename)
        logger.debug(f" Directory:\n\t{directory}")
        logger.debug(f" Directory doesn't exist for {filename}, creating..")
        if not os.path.exists(directory):
            os.makedirs(directory)

        return directory

    def download_album(self, album: AlbumInfo) -> bool:
        """Download all MP3 files in the album

        :param album: album info
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
            filepath = filepath + ".tmp"
            filename = filepath.rsplit("/", 1)[1]
            dirname = self.create_directory(filepath)

            logger.debug(f" Current file for track '{track.title}' on album '{album.title}':\n\t{filepath}")

            if album.art is not None and not os.path.exists(dirname + "/cover.jpg"):
                try:
                    with open(dirname + "/cover.jpg", "wb") as f:
                        r = self.session.get(album.art, headers=self.headers)
                        _ = f.write(r.content)
                    self.album_art = dirname + "/cover.jpg"
                except Exception:
                    logger.exception(f"Couldn't download album art for track '{track.title}' on album '{album.title}'")
                    print("Couldn't download album art.")

            attempts = 0
            skip = False

            while True:
                try:
                    if track.download_url is None:
                        raise ValueError(f"download_url is None for {track.title}")
                    r = self.session.get(track.download_url, headers=self.headers, stream=True)
                    file_length = int(r.headers.get("content-length", 0))
                    total = int(file_length / 100)
                    # If file exists and is still a tmp file skip downloading and encode
                    if os.path.exists(filepath):
                        self.write_id3_tags(filepath, track=track, album=album)
                        # Set skip to True so that we don't try encoding again
                        skip = True
                        # break out of the try/except and move on to the next file
                        break
                    if os.path.exists(filepath[:-4]) and self.config.overwrite is not True:
                        print(f"File: {filename[:-4]} already exists and is complete, skipping..")
                        skip = True
                        break
                    with open(filepath, "wb") as f:
                        if file_length is None:
                            _ = f.write(r.content)
                        else:
                            dl = 0
                            for data in r.iter_content(chunk_size=total):
                                dl += len(data)
                                _ = f.write(data)
                                if not self.config.debug:
                                    done = int(50 * dl / file_length)
                                    print_clean(
                                        f"\r({self.track_num}/{self.num_tracks}) "
                                        f"[{'=' * done}{' ' * (50 - done)}] :: "
                                        f"Downloading: {filename[:-8]}"
                                    )
                    local_size = os.path.getsize(filepath)
                    # if the local filesize before encoding doesn't match the remote filesize
                    # redownload
                    # TODO max retries in config
                    if local_size != file_length and attempts != 3:  # noqa: PLR2004
                        print(f"{filename} is incomplete, retrying..")
                        continue
                    # if the maximum number of retry attempts is reached give up and move on
                    if attempts == 3:  # noqa: PLR2004
                        print("Maximum retries reached.. skipping.")
                        # Clean up incomplete file
                        os.remove(filepath)
                        break
                    # if all is well continue the download process for the rest of the tracks
                    break
                except Exception:
                    logger.exception(f"Downloading failed for track '{track.title}' on album '{album.title}'")
                    print("Downloading failed..")
                    return False
            if skip is False:
                try:
                    self.write_id3_tags(filepath, track=track, album=album)
                except Exception:
                    logger.exception(f"Failed writing tags to '{track.title}' on album '{album.title}'")
                    return False

        if os.path.isfile(f"{self.config.base_dir}/{VERSION}.not.finished"):
            os.remove(f"{self.config.base_dir}/{VERSION}.not.finished")

        # Remove album art image as it is embedded
        if self.config.embed_art and self.album_art is not None:
            os.remove(self.album_art)

        return True

    def write_id3_tags(self, filepath: str, track: TrackInfo, album: AlbumInfo) -> None:
        """Write metadata to the MP3 file

        :param filepath: name of mp3 file
        :param track: track metadata
        :param album: album metadata
        """
        title = track.title
        logger.debug(f" Encoding process starting for '{title}'..")

        filename = filepath.rsplit("/", 1)[1][:-8]

        if not self.config.debug:
            print_clean(f"\r({self.track_num}/{self.num_tracks}) [{'=' * 50}] :: Encoding: {filename}")

        audio = mp3.MP3(filepath)
        _ = audio.delete()
        audio["TIT2"] = id3._frames.TIT2(encoding=3, text=["title"])
        audio["WOAF"] = id3._frames.WOAF(url=album.url)
        _ = audio.save(filename=None, v1=2)

        audio = mp3.MP3(filepath)
        if self.config.group:
            label = album.label if album.label is not None else ""
            audio["TIT1"] = id3._frames.TIT1(encoding=3, text=label)

        if self.config.embed_lyrics:
            lyrics = track.lyrics if track.lyrics is not None else ""
            audio["USLT"] = id3._frames.USLT(encoding=3, lang="eng", desc="", text=lyrics)

        if self.config.embed_art and self.album_art is not None:
            with open(self.album_art, "rb") as cover_img:
                cover_bytes = cover_img.read()
                audio["APIC"] = id3._frames.APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes)
        if self.config.embed_genres:
            genres = album.genres if album.genres is not None else ""
            audio["TCON"] = id3._frames.TCON(encoding=3, text=genres)
        _ = audio.save()

        audio = mp3.EasyMP3(filepath)

        track_num = track.track_num
        if track_num is None:
            track_num = "1"
        audio["tracknumber"] = track_num

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
        logger.debug(f" Renaming:\n\t{filepath} -to-> {filepath[:-4]}")

        try:
            os.rename(filepath, filepath[:-4])
        except OSError:
            logger.warning(f"Output file already exists, replacing it: {filepath[:-4]}")
            os.remove(filepath[:-4])
            os.rename(filepath, filepath[:-4])

        if self.config.debug:
            return

        print_clean(f"\r({self.track_num}/{self.num_tracks}) [{'=' * 50}] :: Finished: {filename}")


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
