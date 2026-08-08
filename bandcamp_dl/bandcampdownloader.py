from __future__ import annotations

import logging
import os
import re
import shutil
from typing import Any

import requests
import slugify
from mutagen import id3, mp3

from bandcamp_dl.config import Album, CaseType, Config
from bandcamp_dl.const import VERSION


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
        self.logger = logging.getLogger("bandcamp-dl").getChild("Downloader")
        self.config = config
        self.urls = urls
        self.album_art: str | None = None
        self.num_tracks: int = 0
        self.track_num: int = 0

    def start(self, album: Album) -> None:
        """Start album download process

        :param album: album dict
        """

        if not album.all_tracks_have_url and not self.config.no_confirm:
            choice = input("Track list incomplete, some tracks may be private, download anyway? (yes/no): ").lower()
            if choice in {"yes", "y"}:
                print("Starting download process.")
                _ = self.download_album(album)
            else:
                print("Cancelling download process.")
                return
        else:
            _ = self.download_album(album)

    def template_to_path(
        self,
        track: dict[str, Any],
        ascii_only: bool,
        ok_chars: str,
        space_char: str,
        keep_space: bool,
        case_mode: CaseType,
    ) -> str:
        """Create valid filepath based on template

        :param track: track metadata
        :param ok_chars: optional chars to allow
        :param ascii_only: allow only ascii chars in filename
        :param keep_space: retain whitespace in filename
        :param case_mode: char case conversion logic (or none / retain)
        :param space_char: char to use in place of spaces
        :return: filepath
        """
        self.logger.debug(" Generating filepath/trackname..")
        template: str = self.config.template
        self.logger.debug(f"\n\tTemplate: {template}")

        def slugify_preset(content: str) -> str:
            retain_case = case_mode != CaseType.LOWER
            if case_mode == CaseType.UPPER:
                content = content.upper()
            if case_mode == CaseType.CAMEL:
                # pyrefly: ignore [implicit-any-lambda]
                content = re.sub(r"(((?<=\s)|^|-)[a-z])", lambda x: x.group().upper(), content.lower())
            result = slugify.slugify(
                content,
                ok=ok_chars,
                only_ascii=ascii_only,
                spaces=keep_space,
                lower=not retain_case,
                space_replacement=space_char,
            )
            assert isinstance(result, str)
            return result

        template_tokens = ["trackartist", "artist", "album", "title", "date", "label", "track", "album_id", "track_id"]
        for token in template_tokens:
            key = token
            if token == "trackartist":
                key = "artist"
            elif token == "artist":
                key = "albumartist"

            if key == "artist" and track.get("artist") is None:
                self.logger.debug("Track artist is None, replacing with album artist")
                track["artist"] = track.get("albumartist")

            if self.config.untitled_path_from_slug and token == "album" and track["album"].lower() == "untitled":
                url = track["url"]
                assert isinstance(url, str)
                track["album"] = url.split("/")[-1].replace("-", " ")

            if token == "track" and track["track"] == "None":
                track["track"] = "Single"
            else:
                track["track"] = str(track["track"]).zfill(2)

            replacement = str(track.get(key, "")) if self.config.no_slugify else slugify_preset(track.get(key, ""))

            template = template.replace(f"%{{{token}}}", replacement)

        output = f"{self.config.base_dir}/{template}.mp3" if self.config.base_dir is not None else f"{template}.mp3"

        self.logger.debug(" filepath/trackname generated..")
        self.logger.debug(f"\n\tPath: {output}")
        return output

    def create_directory(self, filename: str) -> str:
        """Create directory based on filename if it doesn't exist

        :param filename: full filename
        :return: directory path
        """
        directory = os.path.dirname(filename)
        self.logger.debug(f" Directory:\n\t{directory}")
        self.logger.debug(" Directory doesn't exist, creating..")
        if not os.path.exists(directory):
            os.makedirs(directory)

        return directory

    def download_album(self, album: Album) -> bool:
        """Download all MP3 files in the album

        :param album: album dict
        :return: True if successful
        """
        for track_index, track in enumerate(album.tracks):
            track_meta: dict[str, Any] = {
                "artist": track.artist,
                "albumartist": album.artist,
                "label": album.label,
                "album": album.title,
                "title": track.title.replace(f"{track.artist} - ", "", 1),
                "track": str(track.track_num),
                "track_id": track.track_id,
                "album_id": album.album_id,
                # TODO: Find out why the 'lyrics' key seems to vanish.
                "lyrics": track.lyrics,
                "date": album.date,
                "url": album.url,
                "genres": album.genres,
            }

            path_meta = track_meta.copy()

            truncate_album: int = self.config.truncate_album
            if truncate_album > 0 and len(path_meta["album"]) > truncate_album:
                album_value = path_meta["album"]
                assert isinstance(album_value, str)
                path_meta["album"] = album_value[:truncate_album]

            truncate_track = self.config.truncate_track
            assert isinstance(truncate_track, int)
            if truncate_track > 0 and len(path_meta["title"]) > truncate_track:
                title_value = path_meta["title"]
                assert isinstance(title_value, str)
                path_meta["title"] = title_value[:truncate_track]

            self.num_tracks = len(album.tracks)
            self.track_num = track_index + 1

            filepath = self.template_to_path(
                path_meta,
                self.config.ascii_only,
                self.config.ok_chars,
                self.config.space_char,
                self.config.keep_spaces,
                self.config.case_mode,
            )
            filepath = filepath + ".tmp"
            filename = filepath.rsplit("/", 1)[1]
            dirname = self.create_directory(filepath)

            self.logger.debug(" Current file:\n\t%s", filepath)

            if album.art is not None and not os.path.exists(dirname + "/cover.jpg"):
                try:
                    with open(dirname + "/cover.jpg", "wb") as f:
                        r = self.session.get(album.art, headers=self.headers)
                        _ = f.write(r.content)
                    self.album_art = dirname + "/cover.jpg"
                except Exception as e:
                    print(e)
                    print("Couldn't download album art.")

            attempts = 0
            skip = False

            while True:
                try:
                    download_url = track.download_url
                    if download_url is None:
                        raise ValueError(f"download_url is None for {track.title}")
                    r = self.session.get(download_url, headers=self.headers, stream=True)
                    file_length = int(r.headers.get("content-length", 0))
                    total = int(file_length / 100)
                    # If file exists and is still a tmp file skip downloading and encode
                    if os.path.exists(filepath):
                        self.write_id3_tags(filepath, track_meta)
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
                except Exception as e:
                    print(e)
                    print("Downloading failed..")
                    return False
            if skip is False:
                self.write_id3_tags(filepath, track_meta)

        if os.path.isfile(f"{self.config.base_dir}/{VERSION}.not.finished"):
            os.remove(f"{self.config.base_dir}/{VERSION}.not.finished")

        # Remove album art image as it is embedded
        if self.config.embed_art and self.album_art is not None:
            os.remove(self.album_art)

        return True

    def write_id3_tags(self, filepath: str, meta: dict[str, Any]) -> None:
        """Write metadata to the MP3 file

        :param filepath: name of mp3 file
        :param meta: dict of track metadata
        """
        self.logger.debug(" Encoding process starting..")

        filename = filepath.rsplit("/", 1)[1][:-8]

        if not self.config.debug:
            print_clean(f"\r({self.track_num}/{self.num_tracks}) [{'=' * 50}] :: Encoding: {filename}")

        audio = mp3.MP3(filepath)
        _ = audio.delete()
        audio["TIT2"] = id3._frames.TIT2(encoding=3, text=["title"])
        url = meta["url"]
        assert isinstance(url, str)
        audio["WOAF"] = id3._frames.WOAF(url=url)
        _ = audio.save(filename=None, v1=2)

        audio = mp3.MP3(filepath)
        if self.config.group and "label" in meta:
            label: str = meta["label"] or ""
            audio["TIT1"] = id3._frames.TIT1(encoding=3, text=label)

        if self.config.embed_lyrics:
            lyrics: str = meta["lyrics"] or ""
            audio["USLT"] = id3._frames.USLT(encoding=3, lang="eng", desc="", text=lyrics)

        if self.config.embed_art and self.album_art is not None:
            with open(self.album_art, "rb") as cover_img:
                cover_bytes = cover_img.read()
                audio["APIC"] = id3._frames.APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes)
        if self.config.embed_genres:
            genres: str = meta["genres"] or ""
            audio["TCON"] = id3._frames.TCON(encoding=3, text=genres)
        _ = audio.save()

        audio = mp3.EasyMP3(filepath)

        track = meta["track"]
        assert isinstance(track, str)
        if track.isdigit():
            audio["tracknumber"] = track
        else:
            audio["tracknumber"] = "1"

        artist = meta["artist"]
        if artist is not None:
            assert isinstance(artist, str)
            audio["artist"] = artist
        else:
            albumartist = meta["albumartist"]
            assert isinstance(albumartist, str)
            audio["artist"] = albumartist
        title = meta["title"]
        assert isinstance(title, str)
        audio["title"] = title
        albumartist = meta["albumartist"]
        assert isinstance(albumartist, str)
        audio["albumartist"] = albumartist
        album = meta["album"]
        assert isinstance(album, str)
        audio["album"] = album
        date = meta["date"]
        assert isinstance(date, str)
        audio["date"] = date
        _ = audio.save()

        self.logger.debug(" Encoding process finished..")
        self.logger.debug(f" Renaming:\n\t{filepath} -to-> {filepath[:-4]}")

        try:
            os.rename(filepath, filepath[:-4])
        except OSError:
            os.remove(filepath[:-4])
            os.rename(filepath, filepath[:-4])

        if self.config.debug:
            return

        print_clean(f"\r({self.track_num}/{self.num_tracks}) [{'=' * 50}] :: Finished: {filename}")
