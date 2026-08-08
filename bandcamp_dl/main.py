from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import typed_argparse as tap

from bandcamp_dl.bandcamp import Bandcamp
from bandcamp_dl.bandcampdownloader import BandcampDownloader
from bandcamp_dl.config import Album, CaseType, Config, get_user_config
from bandcamp_dl.const import VERSION


class ConfigurableArgs(tap.TypedArgs):
    # Stuff that can be taken from user config
    debug: bool | None
    template: str | None
    base_dir: Path | None
    overwrite: bool | None
    no_art: bool | None
    embed_lyrics: bool | None
    group: bool | None
    embed_art: bool | None
    cover_quality: Literal[0, 10, 16] | None
    untitled_path_from_slug: bool | None
    no_slugify: bool | None
    ok_chars: str | None
    space_char: str | None
    ascii_only: bool | None
    keep_spaces: bool | None
    case_mode: CaseType | None
    no_confirm: bool | None
    embed_genres: bool | None
    truncate_album: int | None
    truncate_track: int | None


class CliOnlyArgs(tap.TypedArgs):
    URL: list[str]
    version: bool
    full_album: bool
    artist: str | None
    track: str | None
    album: str | None


class AllCliArgs(ConfigurableArgs, CliOnlyArgs):
    pass


def add_boolean_argument(
    parser: argparse.ArgumentParser,
    dest: str,
    *,
    pos_flags: tuple[str, ...],
    neg_flags: tuple[str, ...],
    help: str,
) -> None:
    """In cli user can pass positive flag to enable or negative to disable a field (dest)"""
    _ = parser.add_argument(*pos_flags, dest=dest, action="store_const", const=True, default=None, help=help)
    _ = parser.add_argument(
        *neg_flags, dest=dest, action="store_const", const=False, default=None, help=argparse.SUPPRESS
    )


def parse_args(raw_args: list[str] | None = None) -> tuple[argparse.ArgumentParser, AllCliArgs]:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("URL", nargs="*", help="Bandcamp album/track URL")
    _ = parser.add_argument("-v", "--version", action="store_true", help="Show version")
    _ = parser.add_argument("--artist", help="Specify an artist's slug to download their full discography.")
    _ = parser.add_argument(
        "--track", help="Specify a track's slug to download a single track. Must be used with --artist."
    )
    _ = parser.add_argument(
        "--album", help="Specify an album's slug to download a single album. Must be used with --artist."
    )
    _ = parser.add_argument("--template", help="Output filename template")
    _ = parser.add_argument("--base-dir", type=Path, help="Base location of which all files are downloaded")
    _ = parser.add_argument("-f", "--full-album", action="store_true", help="Download only if all tracks are available")
    _ = parser.add_argument("--cover-quality", type=int, choices=(0, 10, 16), help="Set the cover art quality")
    _ = parser.add_argument("-c", "--ok-chars", help="Specify allowed chars in slugify")
    _ = parser.add_argument("-s", "--space-char", help="Specify the char to use in place of spaces")
    _ = parser.add_argument(
        "-x", "--case-convert", dest="case_mode", type=CaseType, help="Specify the char case conversion logic"
    )
    _ = parser.add_argument("--truncate-album", type=int, metavar="LENGTH", help="Truncate album title; 0 for no limit")
    _ = parser.add_argument("--truncate-track", type=int, metavar="LENGTH", help="Truncate track title; 0 for no limit")
    add_boolean_argument(
        parser, "debug", pos_flags=("-d", "--debug"), neg_flags=("--no-debug",), help="Verbose logging"
    )
    add_boolean_argument(
        parser,
        "overwrite",
        pos_flags=("-o", "--overwrite"),
        neg_flags=("--no-overwrite",),
        help="Overwrite tracks that already exist",
    )
    add_boolean_argument(
        parser, "no_art", pos_flags=("-n", "--no-art"), neg_flags=("--art",), help="Skip grabbing album art"
    )
    add_boolean_argument(
        parser,
        "embed_lyrics",
        pos_flags=("-e", "--embed-lyrics"),
        neg_flags=("--no-embed-lyrics",),
        help="Embed track lyrics (If available)",
    )
    add_boolean_argument(
        parser,
        "group",
        pos_flags=("-g", "--group"),
        neg_flags=("--no-group",),
        help="Use album/track Label as iTunes grouping",
    )
    add_boolean_argument(
        parser,
        "embed_art",
        pos_flags=("-r", "--embed-art"),
        neg_flags=("--no-embed-art",),
        help="Embed album art (If available)",
    )
    add_boolean_argument(
        parser,
        "untitled_path_from_slug",
        pos_flags=("--untitled-path-from-slug",),
        neg_flags=("--no-untitled-path-from-slug",),
        help="Use the URL slug for untitled album paths",
    )
    add_boolean_argument(
        parser,
        "no_slugify",
        pos_flags=("-y", "--no-slugify"),
        neg_flags=("--slugify",),
        help="Disable slugification of track, album, and artist names",
    )
    add_boolean_argument(
        parser,
        "ascii_only",
        pos_flags=("-a", "--ascii-only"),
        neg_flags=("--no-ascii-only",),
        help="Only allow ASCII chars",
    )
    add_boolean_argument(
        parser,
        "keep_spaces",
        pos_flags=("-k", "--keep-spaces"),
        neg_flags=("--no-keep-spaces",),
        help="Retain whitespace in filenames",
    )
    add_boolean_argument(
        parser,
        "no_confirm",
        pos_flags=("--no-confirm",),
        neg_flags=("--confirm",),
        help="Override confirmation prompts. Use with caution",
    )
    add_boolean_argument(
        parser,
        "embed_genres",
        pos_flags=("--embed-genres",),
        neg_flags=("--no-embed-genres",),
        help="Embed album/track genres",
    )
    return parser, AllCliArgs.from_argparse(parser.parse_args(raw_args), disallow_extra_args=True)


def resolve_config(user_config: Config, args: ConfigurableArgs) -> Config:
    attrs = Config().model_dump()
    cfg_set_attrs = {k: getattr(user_config, k) for k in user_config.model_fields_set}
    cli_set_attrs = {k: getattr(args, k) for k in ConfigurableArgs.__annotations__ if getattr(args, k) is not None}
    attrs.update(cfg_set_attrs)
    attrs.update(cli_set_attrs)
    return Config.model_validate(attrs)


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

    bandcamp = Bandcamp()

    urls: list[str]
    if arguments.artist is not None and arguments.album is not None:
        urls = [Bandcamp.generate_album_url(arguments.artist, arguments.album, "album")]
    elif arguments.artist is not None and arguments.track is not None:
        urls = [Bandcamp.generate_album_url(arguments.artist, arguments.track, "track")]
    elif arguments.artist is not None:
        urls = Bandcamp.get_full_discography(bandcamp, arguments.artist, "music")
    else:
        urls = []
        for url in arguments.URL:
            assert isinstance(url, str)
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
            add_art=not actual_config.no_art,
            add_lyrics=actual_config.embed_lyrics,
            add_genres=actual_config.embed_genres,
            cover_quality=actual_config.cover_quality,
        )
        if album is not None:
            logger.debug(f" Album data:\n\t{album}")

            if arguments.full_album and not album.all_tracks_have_url:
                print("Full album not available. Skipping ", album.title, " ...")
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
