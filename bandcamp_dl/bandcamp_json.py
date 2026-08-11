from __future__ import annotations

import logging

import demjson3
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_page_json(body: BeautifulSoup) -> list[str]:
    """Grab the needed JSON data from the page."""
    json_data = [_get_pagedata(body)]
    json_data.extend(_get_embedded_json(body))
    return json_data


def _get_pagedata(body: BeautifulSoup) -> str:
    logger.debug(" Grab pagedata JSON..")
    pagedata_tag = body.find("div", {"id": "pagedata"})
    if pagedata_tag is None:
        raise ValueError("Could not find pagedata div on Bandcamp page")
    pagedata = pagedata_tag["data-blob"]
    assert isinstance(pagedata, str)
    return pagedata


def _get_embedded_json(body: BeautifulSoup) -> list[str]:
    """Get script elements containing the data we need."""
    logger.debug(" Grabbing embedded scripts..")
    ld_json_script = body.find("script", {"type": "application/ld+json"})
    if ld_json_script is None:
        raise ValueError("Could not find application/ld+json script on Bandcamp page")
    embedded_scripts_raw: list[str | None] = [ld_json_script.string]
    for script in body.find_all("script"):
        album_info = script.get("data-tralbum")
        if album_info is not None:
            assert isinstance(album_info, str)
            embedded_scripts_raw.append(album_info)
    return [_js_to_json(script) for script in embedded_scripts_raw if script is not None]


def _js_to_json(js_data: str) -> str:
    """Convert a JavaScript dictionary to JSON."""
    logger.debug(" Converting JS to JSON..")
    # Decode with demjson first to reformat keys and lists.
    decoded_js = demjson3.decode(js_data)
    result = demjson3.encode(decoded_js)
    return result
