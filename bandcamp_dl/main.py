from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from urllib.parse import urlparse

from bandcamp_dl import config
from bandcamp_dl.bandcamp import Bandcamp
from bandcamp_dl.bandcampdownloader import BandcampDownloader
from bandcamp_dl.config import Album
from bandcamp_dl.const import VERSION


def main() -> None:
    default_conf = config.Config()

    parser = argparse.ArgumentParser()
    parser.add_argument("URL", help="Bandcamp album/track URL", nargs="*")
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    parser.add_argument("-d", "--debug", action="store_true", help="Verbose logging", default=default_conf.debug)
    parser.add_argument("--artist", help="Specify an artist's slug to download their full discography.")
    parser.add_argument(
        "--track", help="Specify a track's slug to download a single track. Must be used with --artist."
    )
    parser.add_argument(
        "--album", help="Specify an album's slug to download a single album. Must be used with --artist."
    )
    parser.add_argument(
        "--template",
        help=f"Output filename template, default: {default_conf.template.replace('%', '%%')}",
        default=default_conf.template,
    )
    parser.add_argument(
        "--base-dir", help="Base location of which all files are downloaded", default=default_conf.base_dir
    )
    parser.add_argument("-f", "--full-album", help="Download only if all tracks are available", action="store_true")
    parser.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help=f"Overwrite tracks that already exist. Default is {default_conf.overwrite}.",
        default=default_conf.overwrite,
    )
    parser.add_argument(
        "-n", "--no-art", help="Skip grabbing album art", action="store_true", default=default_conf.no_art
    )
    parser.add_argument(
        "-e",
        "--embed-lyrics",
        help="Embed track lyrics (If available)",
        action="store_true",
        default=default_conf.embed_lyrics,
    )
    parser.add_argument(
        "-g",
        "--group",
        help="Use album/track Label as iTunes grouping",
        action="store_true",
        default=default_conf.group,
    )
    parser.add_argument(
        "-r", "--embed-art", help="Embed album art (If available)", action="store_true", default=default_conf.embed_art
    )
    parser.add_argument(
        "--cover-quality",
        help="Set the cover art quality. 0 is source, 10 is album page (1200x1200), 16 is default embed (700x700).",
        default=default_conf.cover_quality,
        type=int,
        choices=[0, 10, 16],
    )
    parser.add_argument(
        "--untitled-path-from-slug",
        help="For albums titled untitled, use the URL slug to generate the folder path.",
        action="store_true",
        default=default_conf.untitled_path_from_slug,
    )
    parser.add_argument(
        "-y",
        "--no-slugify",
        action="store_true",
        default=default_conf.no_slugify,
        help="Disable slugification of track, album, and artist names",
    )
    parser.add_argument(
        "-c",
        "--ok-chars",
        default=default_conf.ok_chars,
        help=f"Specify allowed chars in slugify, default: {default_conf.ok_chars}",
    )
    parser.add_argument(
        "-s",
        "--space-char",
        help=f"Specify the char to use in place of spaces, default: {default_conf.space_char}",
        default=default_conf.space_char,
    )
    parser.add_argument(
        "-a",
        "--ascii-only",
        help="Only allow ASCII chars (北京 (capital of china) -> bei-jing-capital-of-china)",
        action="store_true",
        default=default_conf.ascii_only,
    )
    parser.add_argument(
        "-k",
        "--keep-spaces",
        help="Retain whitespace in filenames",
        action="store_true",
        default=default_conf.keep_spaces,
    )
    parser.add_argument(
        "-x",
        "--case-convert",
        help=f"Specify the char case conversion logic, default: {default_conf.case_mode}",
        default=default_conf.case_mode,
        dest="case_mode",
        choices=[config.CASE_LOWER, config.CASE_UPPER, config.CASE_CAMEL, config.CASE_NONE],
    )
    parser.add_argument(
        "--no-confirm",
        help="Override confirmation prompts. Use with caution",
        action="store_true",
        default=default_conf.no_confirm,
    )
    parser.add_argument(
        "--embed-genres", help="Embed album/track genres", action="store_true", default=default_conf.embed_genres
    )
    parser.add_argument(
        "--truncate-album",
        metavar="LENGTH",
        type=int,
        default=0,
        help="Truncate album title to a maximum length. 0 for no limit.",
    )
    parser.add_argument(
        "--truncate-track",
        metavar="LENGTH",
        type=int,
        default=0,
        help="Truncate track title to a maximum length. 0 for no limit.",
    )

    arguments = parser.parse_args()
    if arguments.version:
        sys.stdout.write(f"bandcamp-dl {VERSION}\n")
        return

    if arguments.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig()
    logging_handle = "bandcamp-dl"
    logger = logging.getLogger(logging_handle)

    # TODO: Its possible to break bandcamp-dl temporarily by simply erasing a line in the config, catch this and warn.
    logger.debug(f"Config/Args: {arguments}")
    if not arguments.URL and not arguments.artist:
        parser.print_usage()
        sys.stderr.write(
            f"{pathlib.Path(sys.argv[0]).name}: error: the following arguments are required: URL or --artist\n"
        )
        sys.exit(2)

    for arg, val in [
        ("base_dir", config.USER_HOME),
        ("template", config.TEMPLATE),
        ("ok_chars", config.OK_CHARS),
        ("space_char", config.SPACE_CHAR),
    ]:
        if not getattr(arguments, arg):
            setattr(arguments, arg, val)
    bandcamp = Bandcamp()

    urls: list[str]
    if arguments.artist and arguments.album:
        urls = [Bandcamp.generate_album_url(arguments.artist, arguments.album, "album")]
    elif arguments.artist and arguments.track:
        urls = [Bandcamp.generate_album_url(arguments.artist, arguments.track, "track")]
    elif arguments.artist:
        urls = Bandcamp.get_full_discography(bandcamp, arguments.artist, "music")
    else:
        urls = []
        for url in arguments.URL:
            parsed_url = urlparse(url)
            if parsed_url.netloc.endswith(".bandcamp.com") and (parsed_url.path in {"/music", "/", ""}):
                artist = parsed_url.netloc.split(".")[0]
                print(f"Found artist page, fetching full discography for: {artist}")
                urls.extend(bandcamp.get_full_discography(artist, "music"))
            else:
                urls.append(url)

    album_list: list[Album] = []

    for url in urls:
        if "/album/" not in url and "/track/" not in url:
            continue
        logger.debug("\n\tURL: %s", url)
        album = bandcamp.parse(
            url,
            add_art=not arguments.no_art,
            add_lyrics=arguments.embed_lyrics,
            add_genres=arguments.embed_genres,
            cover_quality=arguments.cover_quality,
        )
        if album:
            logger.debug(f" Album data:\n\t{album}")

            if arguments.full_album and not album.all_tracks_have_url:
                print("Full album not available. Skipping ", album.title, " ...")
            else:
                album_list.append(album)

    if arguments.URL or arguments.artist:
        logger.debug("Preparing download process..")
        for album in album_list:
            bandcamp_downloader = BandcampDownloader(arguments, [album.url])
            logger.debug("Initiating download process..")
            bandcamp_downloader.start(album)
            # Add a newline to stop prompt mangling
            print()
    else:
        logger.debug(r" /!\ Something went horribly wrong /!\ ")


if __name__ == "__main__":
    main()
