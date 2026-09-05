from __future__ import annotations

import json
import logging
import sys
from urllib.parse import urlparse

from bandcamp_dl.bandcamp_downloader import BandcampDownloader
from bandcamp_dl.bandcamp_parser import BandcampParser
from bandcamp_dl.cli_parsing import parse_args, resolve_config
from bandcamp_dl.config import AlbumInfo, ArtMode, get_user_config
from bandcamp_dl.const import VERSION, is_error

logger = logging.getLogger(__name__)


def confirm_incomplete_download() -> bool:
    while True:
        try:
            choice = input("Track list incomplete, some tracks may be private, download anyway? (yes/no): ")
        except EOFError:
            print("\nCancelling download process.")
            return False
        choice = choice.strip().lower()
        if choice in ("yes", "y"):
            print("Starting download process.")
            return True
        if choice in ("no", "n"):
            print("Cancelling download process.")
            return False
        print("Please answer yes or no.")


def main() -> None:
    parser, arguments = parse_args()
    user_conf = get_user_config()

    if arguments.version:
        _ = sys.stdout.write(f"bandcamp-dl {VERSION}\n")
        return

    actual_config = resolve_config(user_conf, arguments)

    if actual_config.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig()
    logger.debug(f"Config/args: {json.dumps(vars(arguments), indent=4, default=str)}")
    logger.debug(f"Config after merging with user's config: {actual_config.model_dump_json(indent=4)}")
    if not bool(arguments.URL) and not bool(arguments.artist):
        parser.error("the following arguments are required: URL or --artist")

    bandcamp_parser = BandcampParser()
    bandcamp_downloader = BandcampDownloader(actual_config, session=bandcamp_parser.session)

    bandcamp_downloader.preconnect("f4.bcbits.com", "t4.bcbits.com")

    urls: list[str]
    if arguments.artist is not None and arguments.album is not None:
        urls = [BandcampParser.generate_album_url(artist=arguments.artist, slug=arguments.album, page_type="album")]
    elif arguments.artist is not None and arguments.track is not None:
        urls = [BandcampParser.generate_album_url(artist=arguments.artist, slug=arguments.track, page_type="track")]
    elif arguments.artist is not None:
        urls, error_status = bandcamp_parser.get_full_discography(artist=arguments.artist, page_type="music")
        if is_error(error_status) and not actual_config.ignore_errors:
            sys.exit(1)
    else:
        urls = []
        for url in arguments.URL:
            parsed_url = urlparse(url)
            if parsed_url.netloc.endswith(".bandcamp.com") and (parsed_url.path in {"/music", "/", ""}):
                artist = parsed_url.netloc.split(".")[0]
                print(f"Found artist page, fetching full discography for: {artist}")
                cur_urls, error_status = bandcamp_parser.get_full_discography(artist, page_type="music")
                if is_error(error_status) and not actual_config.ignore_errors:
                    sys.exit(1)
                urls.extend(cur_urls)
            else:
                urls.append(url)

    album_list: list[AlbumInfo] = []

    for url in urls:
        if "/album/" not in url and "/track/" not in url:
            continue
        logger.debug(f"\n\tURL: {url}")
        try:
            album = bandcamp_parser.parse(
                url,
                add_art=actual_config.art_mode is not ArtMode.NONE,
                add_lyrics=actual_config.embed_lyrics,
                add_genres=actual_config.embed_genres,
                cover_quality=actual_config.cover_quality,
            )
        except Exception:
            logger.exception(f"Failed parsing album at {url}")
            if not actual_config.ignore_errors:
                sys.exit(1)
            else:
                continue

        logger.debug(f"Album data:\n\t{album}")

        if arguments.full_album and not album.all_tracks_have_url:
            if actual_config.ignore_errors:
                print(f"Full album not available. Skipping {album.title} ..")
            else:
                logger.error(f"Full album not available for {album.title}")
                sys.exit(1)
        else:
            album_list.append(album)

    logger.debug(f"Preparing download process for {len(album_list)} album(s)..")
    for album in album_list:
        success = True
        if not album.all_tracks_have_url and not actual_config.no_confirm:
            success = confirm_incomplete_download()
        if success:
            logger.debug(f"Initiating download process for album '{album.title}'..")
            success = bandcamp_downloader.download_album(album)
        if not success and not actual_config.ignore_errors:
            sys.exit(1)
        # Add a newline to stop prompt mangling
        print()


if __name__ == "__main__":
    main()
