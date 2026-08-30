from __future__ import annotations

import logging
import re
from pathlib import Path

import slugify

from bandcamp_dl.config import AlbumInfo, CaseType, Config, TemplateTokens, TrackInfo

logger = logging.getLogger(__name__)


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


def template_to_path(track: TrackInfo, album: AlbumInfo, config: Config) -> Path:
    """Create valid filepath based on template

    :param track: track metadata
    :param album: album metadata
    :param config: user config/args
    :return: filepath
    """
    logger.debug(f" Generating filepath/trackname for '{track.title}'..")
    template = config.template
    logger.debug(f"\n\tTemplate: {template}")

    album_title = album.title
    album_title = _maybe_truncate(album_title, trunc_len=config.truncate_album)
    if config.untitled_path_from_slug and album_title.lower() == "untitled":
        album_title = album.url.split("/")[-1].replace("-", " ")

    track_title = track.title
    track_title = _maybe_truncate(track_title, trunc_len=config.truncate_track)

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
            if config.no_slugify
            else _slugify(
                value,
                ascii_only=config.ascii_only,
                ok_chars=config.ok_chars,
                space_char=config.space_char,
                keep_space=config.keep_spaces,
                case_mode=config.case_mode,
            )
        )
        template = template.replace(token, replacement)

    output = config.base_dir / f"{template}.mp3"

    logger.debug(f" filepath/trackname generated for '{track.title}'..")
    logger.debug(f"\n\tPath: {output}")
    return output
