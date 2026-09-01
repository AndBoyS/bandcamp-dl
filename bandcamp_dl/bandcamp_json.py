from __future__ import annotations

import logging
from typing import Any

import orjson
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_page_json(body: BeautifulSoup) -> list[dict[str, Any]]:
    """Grab the needed JSON data from the page."""
    json_data = [_get_pagedata(body)]
    json_data.extend(_get_embedded_json(body))
    return json_data


def _get_pagedata(body: BeautifulSoup) -> dict[str, Any]:
    logger.debug("Grab pagedata JSON..")
    pagedata_tag = body.find("div", {"id": "pagedata"})
    if pagedata_tag is None:
        raise ValueError("Could not find pagedata div on Bandcamp page")
    pagedata = pagedata_tag["data-blob"]
    assert isinstance(pagedata, str)
    return parse_page_json(pagedata)


def _get_embedded_json(body: BeautifulSoup) -> list[dict[str, Any]]:
    """Get script elements containing the data we need."""
    logger.debug("Grabbing embedded scripts..")
    parsed: list[dict[str, Any]] = []
    ld_json_found = False
    for script in body.find_all("script"):
        if script.get("type") == "application/ld+json":
            if ld_json_found:
                continue
            blob = script.get_text()
            if blob.strip() != "":
                ld_json_found = True
        else:
            album_info = script.get("data-tralbum")
            if album_info is None:
                continue
            assert isinstance(album_info, str)
            blob = album_info
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
