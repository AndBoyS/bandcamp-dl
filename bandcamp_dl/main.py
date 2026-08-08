from __future__ import annotations

import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from bandcamp_dl.bandcamp_downloader import BandcampDownloader
from bandcamp_dl.bandcamp_parser import BandcampParser
from bandcamp_dl.cli_parsing import parse_args, resolve_config
from bandcamp_dl.config import Album, get_user_config
from bandcamp_dl.const import VERSION


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
    logging_handle = "bandcamp-dl"
    logger = logging.getLogger(logging_handle)

    # TODO: Its possible to break bandcamp-dl temporarily by simply erasing a line in the config, catch this and warn.
    logger.debug("Config/Args: %s", actual_config)
    if not bool(arguments.URL) and not bool(arguments.artist):
        parser.print_usage()
        _ = sys.stderr.write(
            f"{Path(sys.argv[0]).name}: error: the following arguments are required: URL or --artist\n"
        )
        sys.exit(2)

    bandcamp_parser = BandcampParser()

    urls: list[str]
    if arguments.artist is not None and arguments.album is not None:
        urls = [BandcampParser.generate_album_url(artist=arguments.artist, slug=arguments.album, page_type="album")]
    elif arguments.artist is not None and arguments.track is not None:
        urls = [BandcampParser.generate_album_url(artist=arguments.artist, slug=arguments.track, page_type="track")]
    elif arguments.artist is not None:
        urls = bandcamp_parser.get_full_discography(artist=arguments.artist, page_type="music")
    else:
        urls = []
        for url in arguments.URL:
            assert isinstance(url, str)
            parsed_url = urlparse(url)
            if parsed_url.netloc.endswith(".bandcamp.com") and (parsed_url.path in {"/music", "/", ""}):
                artist = parsed_url.netloc.split(".")[0]
                print(f"Found artist page, fetching full discography for: {artist}")
                urls.extend(bandcamp_parser.get_full_discography(artist, page_type="music"))
            else:
                urls.append(url)

    album_list: list[Album] = []

    for url in urls:
        if "/album/" not in url and "/track/" not in url:
            continue
        logger.debug("\n\tURL: %s", url)
        album = bandcamp_parser.parse(
            url,
            add_art=not actual_config.no_art,
            add_lyrics=actual_config.embed_lyrics,
            add_genres=actual_config.embed_genres,
            cover_quality=actual_config.cover_quality,
        )
        if album is not None:
            logger.debug(f" Album data:\n\t{album}")

            if arguments.full_album and not album.all_tracks_have_url:
                print(f"Full album not available. Skipping {album.title} ...")
            else:
                album_list.append(album)

    if bool(arguments.URL) or arguments.artist is not None:
        logger.debug("Preparing download process..")
        for album in album_list:
            bandcamp_downloader = BandcampDownloader(actual_config, [album.url])
            logger.debug("Initiating download process..")
            bandcamp_downloader.start(album)
            # Add a newline to stop prompt mangling
            print()
    else:
        logger.debug(r" /!\ Something went horribly wrong /!\ ")


if __name__ == "__main__":
    main()
