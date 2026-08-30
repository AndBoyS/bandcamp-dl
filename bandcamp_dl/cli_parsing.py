from __future__ import annotations

import argparse
from pathlib import Path
from typing import Literal

import typed_argparse as tap

from bandcamp_dl.config import ArtMode, CaseType, Config


class ConfigurableArgs(tap.TypedArgs):
    # Stuff that can be taken from user config
    debug: bool | None
    ignore_errors: bool | None
    template: str | None
    base_dir: Path | None
    overwrite: bool | None
    art_mode: ArtMode | None
    embed_lyrics: bool | None
    group: bool | None
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
    max_retries: int | None


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
    _ = parser.add_argument(
        "--max-retries", type=int, help="Maximum retries per failed track download; 0 for a single attempt"
    )
    add_boolean_argument(
        parser,
        "ignore_errors",
        pos_flags=("--ignore-errors",),
        neg_flags=("--no-ignore-errors",),
        help="Continue downloading when an parsing/downloading error occurs",
    )
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
    _ = parser.add_argument(
        "--art-mode",
        dest="art_mode",
        type=ArtMode,
        default=None,
        help="Album art handling: 'none' skips art, 'file' downloads cover.jpg (default), 'embed' embeds it in tags and"
        " removes the file, 'file-embed' combines both",
    )
    _ = parser.add_argument(
        "-n", "--no-art", dest="art_mode", action="store_const", const=ArtMode.NONE, help="Alias for --art-mode none"
    )
    _ = parser.add_argument(
        "-r",
        "--embed-art",
        dest="art_mode",
        action="store_const",
        const=ArtMode.EMBED,
        help="Alias for --art-mode embed",
    )
    _ = parser.add_argument(
        "--art-as-file", dest="art_mode", action="store_const", const=ArtMode.FILE, help="Alias for --art-mode file"
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
