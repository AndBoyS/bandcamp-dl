from __future__ import annotations

import html
import logging
import re
from typing import Any

import orjson

logger = logging.getLogger(__name__)

_SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.DOTALL)
_DATA_TRALBUM_RE = re.compile(r'\bdata-tralbum="([^"]*)"')
_PAGEDATA_TAG_RE = re.compile(r"<div\b[^>]*\bid=\"pagedata\"[^>]*>")


def extract_page_json(raw_html: str) -> list[dict[str, Any]]:
    """Grab the needed JSON data from the page."""
    json_data = [_get_pagedata(raw_html)]
    json_data.extend(_get_embedded_json(raw_html))
    return json_data


def _get_pagedata(raw_html: str) -> dict[str, Any]:
    logger.debug("Grab pagedata JSON..")
    tag_match = _PAGEDATA_TAG_RE.search(raw_html)
    if tag_match is None:
        raise ValueError("Could not find pagedata div on Bandcamp page")
    blob_match = re.compile(r'\bdata-blob="([^"]*)"').search(tag_match.group(0))
    if blob_match is None:
        raise ValueError("Could not find data-blob attribute on pagedata div")
    pagedata = html.unescape(blob_match.group(1))
    return parse_page_json(pagedata)


def _get_embedded_json(raw_html: str) -> list[dict[str, Any]]:
    """Get script elements containing the data we need."""
    logger.debug("Grabbing embedded scripts..")
    parsed: list[dict[str, Any]] = []
    ld_json_found = False
    for attrs, content in _SCRIPT_TAG_RE.findall(raw_html):
        if "application/ld+json" in attrs:
            if ld_json_found:
                continue
            if content.strip() != "":
                ld_json_found = True
            blob = content
        else:
            album_info_match = _DATA_TRALBUM_RE.search(attrs)
            if album_info_match is None:
                continue
            blob = html.unescape(album_info_match.group(1))
        if blob.strip() == "":
            logger.warning("Skipping empty JSON blob on page")
            continue
        parsed.append(parse_page_json(blob))
    if not ld_json_found:
        raise ValueError("Could not find application/ld+json script on Bandcamp page")
    return parsed


def parse_page_json(js_data: str) -> dict[str, Any]:
    """Parse a Bandcamp page JSON blob."""
    logger.debug("Parsing page JSON..")
    data = orjson.loads(js_data)
    assert isinstance(data, dict)
    return data
