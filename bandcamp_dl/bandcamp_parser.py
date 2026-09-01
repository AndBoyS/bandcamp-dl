from __future__ import annotations

import datetime
import json
import logging
from collections import defaultdict
from typing import Any, NamedTuple, TypedDict
from urllib.parse import urljoin, urlsplit

import bs4
import requests
from bs4.element import Tag

from bandcamp_dl.bandcamp_json import extract_page_json
from bandcamp_dl.config import AlbumInfo, TrackInfo
from bandcamp_dl.const import VERSION, ErrorStatus
from bandcamp_dl.custom_ssl import CUSTOM_SSL_CTX, SSLAdapter

logger = logging.getLogger(__name__)


class TrackRaw(TypedDict, total=False):
    title: str
    duration: float
    track_num: int
    artist: str
    track_id: int
    title_link: str
    full_link: str
    file: dict[str, str]
    has_lyrics: bool
    lyrics: str


class BandcampParser:
    def __init__(self) -> None:
        # TODO: update version
        self.headers = {"User-Agent": f"bandcamp-dl/{VERSION} (https://github.com/evolution0/bandcamp-dl)"}

        # Mount the adapter with the custom SSL context to the session
        self.session = requests.Session()
        self.adapter = SSLAdapter(ssl_context=CUSTOM_SSL_CTX)
        self.session.mount("https://", self.adapter)

    def parse(
        self,
        url: str,
        *,
        add_art: bool = True,
        add_lyrics: bool = False,
        add_genres: bool = False,
        cover_quality: int = 0,
    ) -> AlbumInfo:
        """Requests the page, cherry-picks album info

        :param url: album/track url
        :param add_art: if True download album art
        :param add_lyrics: if True fetch track lyrics
        :param add_genres: if True fetch track tags
        :param cover_quality: The quality of the album art to retrieve
        :return: album metadata
        """

        logger.debug(f"Starting to parse {url}")
        try:
            response = self.session.get(url, headers=self.headers)
        except requests.exceptions.MissingSchema:
            logger.warning(f"Invalid URL schema: {url}")
            raise

        if not response.ok:
            logger.error(
                f"The Album/Track requested does not exist at: {url};"
                f" status code: {response.status_code} ({response.reason})"
            )
            raise ValueError()

        soup = bs4.BeautifulSoup(response.text, "lxml")

        logger.debug("Generating BandcampJSON..")
        try:
            bandcamp_json = extract_page_json(soup)
        except Exception:
            logger.exception("Error parsing web page")
            raise

        page_json: dict[str, Any] = {}
        for entry in bandcamp_json:
            page_json = {**page_json, **json.loads(entry)}
        logger.debug("BandcampJSON generated..")

        logger.debug("Generating Album..")
        tracks_raw: list[TrackRaw] = page_json["trackinfo"]

        artist_url: str
        if "/track/" in page_json["url"]:
            artist_url = page_json["url"].rpartition("/track/")[0]
        else:
            artist_url = page_json["url"].rpartition("/album/")[0]

        for t in tracks_raw:
            partial_link = t.get("title_link")
            if bool(partial_link):
                t["full_link"] = urljoin(artist_url, partial_link)

        link_to_track = {normalized_url_key(t.get("full_link")): t for t in tracks_raw if bool(t.get("full_link"))}
        if "track" in page_json and "itemListElement" in page_json["track"]:
            for item in page_json["track"]["itemListElement"]:
                track_url = item["item"]["@id"]
                assert isinstance(track_url, str)
                for prop in item["item"].get("additionalProperty", []):
                    if prop.get("name") == "track_id":
                        value = prop["value"]
                        assert isinstance(value, int)
                        track_url = normalized_url_key(track_url)
                        track = link_to_track.get(track_url)
                        if track is not None:
                            track["track_id"] = value
                        break

        track_nums = {t.get("track_num") for t in tracks_raw}
        amt_tracks = len(tracks_raw)

        if amt_tracks != len(track_nums) or any(t is None for t in track_nums):
            logger.debug("Duplicate/incomplete track numbers found, re-numbering based on position..")
            track_nums_by_page: dict[UrlKey, int] = {}
            if "track" in page_json and "itemListElement" in page_json["track"]:
                for item in page_json["track"]["itemListElement"]:
                    full_track_url = item["item"]["@id"]
                    assert isinstance(full_track_url, str)
                    position = item.get("position")
                    if isinstance(position, int):
                        track_nums_by_page[normalized_url_key(full_track_url)] = position

            for track in tracks_raw:
                link = track.get("full_link")
                if link is None:
                    continue
                num_candidate = track_nums_by_page.get(normalized_url_key(link))
                if num_candidate is not None:
                    track["track_num"] = num_candidate

            num_to_tracks = defaultdict[int, list[int]](list)

            for t_i, t in enumerate(tracks_raw):
                num = t.get("track_num")
                if num is not None:
                    num_to_tracks[num].append(t_i)

            for cur_tracks in num_to_tracks.values():
                if len(cur_tracks) > 1:
                    for i in cur_tracks:
                        _ = tracks_raw[i].pop("track_num")

            used_nums = {track["track_num"] for track in tracks_raw if track.get("track_num") is not None}

            next_number = 1
            for track in tracks_raw:
                if track.get("track_num") is not None:
                    continue

                while next_number in used_nums:
                    next_number += 1

                track["track_num"] = next_number
                used_nums.add(next_number)
                next_number += 1

        album_date: str | None = page_json.get("album_release_date")
        if album_date is None:
            album_date = page_json["current"].get("release_date")
        if album_date is None:
            album_date = page_json["embed_info"]["item_public"]

        try:
            album_title: str = page_json["current"]["title"]
        except KeyError:
            album_title = page_json["trackinfo"][0]["title"]
            logger.debug(f"Album title missing from current metadata, using track title ({album_title})")

        try:
            label: str | None = page_json["item_sellers"][f"{page_json['current']['selling_band_id']}"]["name"]
        except KeyError:
            logger.debug(f"Label missing from page metadata ({url})")
            label = None

        album_id: int | None = None
        track_id_from_music_recording: int | None = None

        if page_json.get("@type") == "MusicRecording":
            if "additionalProperty" in page_json:
                for prop in page_json["additionalProperty"]:
                    if prop.get("name") == "track_id":
                        track_id_from_music_recording = prop.get("value")
                        assert isinstance(track_id_from_music_recording, int) or track_id_from_music_recording is None
                        album_id = track_id_from_music_recording
                        logger.debug(f"Single track page, found track_id: {track_id_from_music_recording}")
                        break
        elif page_json.get("@type") == "MusicAlbum" and "albumRelease" in page_json:
            for release in page_json["albumRelease"]:
                if "additionalProperty" in release:
                    for prop in release["additionalProperty"]:
                        if prop.get("name") == "item_id":
                            album_id = prop.get("value")
                            assert isinstance(album_id, int) or album_id is None
                            logger.debug(f"Album page, found album_id: {album_id}")
                            break
                if album_id is not None:
                    break

        tracks = [
            self.parse_track_finalize(
                t,
                track_id_from_music_recording=track_id_from_music_recording,
                add_lyrics=add_lyrics,
                album_title=album_title,
            )
            for t in tracks_raw
        ]

        album = AlbumInfo(
            tracks=[t for t in tracks if t is not None],
            title=album_title,
            artist=page_json["artist"],
            label=label,
            all_tracks_have_url=all(t is not None for t in tracks),
            art=self.get_album_art(soup=soup, quality=cover_quality) if add_art else None,
            date=str(datetime.datetime.strptime(album_date, "%d %b %Y %H:%M:%S GMT").year),
            url=url,
            genres="; ".join(page_json["keywords"]) if add_genres else None,
            album_id=album_id,
        )
        if add_art and album.art is None:
            logger.exception(f"Could not find album art for {album_title}")

        logger.debug(f"Album generated: '{album.title}' ({album.url})..")
        return album

    def get_track_lyrics(self, track_url: str) -> str:
        lyrics_url = f"{track_url}#lyrics"

        logger.debug(f"Fetching track lyrics for {track_url}..")
        track_page = self.session.get(lyrics_url, headers=self.headers)
        track_soup = bs4.BeautifulSoup(track_page.text, "lxml")
        track_lyrics = track_soup.find("div", {"class": "lyricsText"})
        if track_lyrics is not None:
            logger.debug("Lyrics retrieved..")
            return track_lyrics.text
        logger.debug("Lyrics not found..")
        return ""

    def parse_track_finalize(
        self, track_raw: TrackRaw, *, track_id_from_music_recording: int | None, add_lyrics: bool, album_title: str
    ) -> TrackInfo | None:

        title = track_raw.get("title")
        if title is None:
            logger.debug(f"Title not found for track {album_title}")
            title = "No title"
        track_artist = track_raw.get("artist")

        if track_artist is not None:
            title = title.replace(f"{track_artist} - ", "", 1)

        logger.debug(f"Finalizing track metadata for '{title}'..")

        file: dict[str, str] | None = track_raw.get("file")
        if file is None:
            file = {}

        download_url: str | None = None
        if "mp3-128" in file:
            download_url = file["mp3-128"] if "https" in file["mp3-128"] else "http:" + file["mp3-128"]

        if not bool(download_url):
            logger.debug(f"download_url not found for '{title}'")
            return None

        track = TrackInfo(
            duration=track_raw.get("duration", 0),
            track_num=track_raw.get("track_num"),
            title=title,
            track_artist=track_artist,
            track_id=track_raw.get("track_id"),
            track_url=track_raw.get("full_link"),
            download_url=download_url,
        )

        if track_raw.get("has_lyrics") is not False and track_raw.get("lyrics") is not None:
            track.lyrics = track_raw["lyrics"].replace("\\r\\n", "\n")

        if track_id_from_music_recording is not None:
            track.track_id = track_id_from_music_recording

        if add_lyrics and bool(track.track_url):
            track.lyrics = self.get_track_lyrics(track.track_url)

        logger.debug(f"Track metadata generated for '{track.title}'..")
        return track

    @staticmethod
    def generate_album_url(*, artist: str, slug: str, page_type: str) -> str:
        """Generate an album url based on the artist and album name

        :param artist: artist name
        :param slug: Slug of album/track
        :param page_type: Type of page album/track
        :return: url as str
        """
        return f"http://{artist}.bandcamp.com/{page_type}/{slug}"

    def get_album_art(self, soup: bs4.BeautifulSoup, quality: int = 0) -> str | None:
        try:
            tralbum = soup.find(id="tralbumArt")
            assert isinstance(tralbum, Tag)
            url = tralbum.find_all("a")[0]["href"]
            return f"{url[:-6]}{quality}{url[-4:]}"
        except Exception:
            return None

    def get_full_discography(self, artist: str, page_type: str) -> tuple[list[str], ErrorStatus]:
        """Generate a list of album and track urls based on the artist name

        :param artist: artist name
        :param page_type: Type of page, it should be music but it's a parameter so it's not
                          hardcoded
        :return: urls as list of strs, ErrorStatus
        """

        # We have ErrorStatus instead of raising for case
        # when some errors have occured, but there is still result
        error_status: ErrorStatus = ErrorStatus.NO_ERROR
        album_urls: set[str] = set()

        music_page_url = f"https://{artist}.bandcamp.com/{page_type}"
        logger.info(f"Scraping discography from: {music_page_url}")

        try:
            response = self.session.get(music_page_url, headers=self.headers)
        except requests.exceptions.RequestException:
            logger.exception(f"Could not fetch artist page {music_page_url}")
            return ([], ErrorStatus.ERROR)

        soup = bs4.BeautifulSoup(response.text, "lxml")

        music_grid = soup.find("ol", {"id": "music-grid"})
        if music_grid is None:
            logger.exception(f"Could not find music grid on {music_page_url}. No albums found.")
            return ([], ErrorStatus.ERROR)

        if "data-client-items" in music_grid.attrs:
            logger.debug("Found data-client-items attribute. Parsing for album URLs.")
            try:
                data_client_items = music_grid["data-client-items"]
                assert isinstance(data_client_items, str)
                json_string = bs4.BeautifulSoup(data_client_items, "html.parser").text
                items: list[dict[str, Any]] = json.loads(json_string)
            except (json.JSONDecodeError, TypeError):
                logger.exception(f"Failed to parse data-client-items JSON from {music_page_url}")
                error_status = ErrorStatus.ERROR
            else:
                for item in items:
                    if "page_url" in item:
                        page_url = item.get("page_url")
                        if isinstance(page_url, str):
                            full_url = urljoin(music_page_url, page_url)
                            album_urls.add(full_url)
                        else:
                            logger.exception("Failed to extract url")
                            error_status = ErrorStatus.ERROR

        logger.debug(f"Scraping all <li> elements in the music grid for links ({artist}).")
        for a in music_grid.select("li.music-grid-item a"):
            href = a.get("href")
            if href is not None:
                assert isinstance(href, str)
                full_url = urljoin(music_page_url, href)
                album_urls.add(full_url)

        logger.info(f"Found a total of {len(album_urls)} unique album/track links.")
        return list(album_urls), error_status


class UrlKey(NamedTuple):
    host: str
    path: str


def normalized_url_key(url: str) -> UrlKey:
    parsed = urlsplit(url)
    host = parsed.hostname.lower() if parsed.hostname is not None else ""
    # pyrefly: ignore [implicit-bool]
    path = parsed.path.rstrip("/") or "/"
    return UrlKey(host=host, path=path)
