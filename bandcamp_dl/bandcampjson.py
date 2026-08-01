from __future__ import annotations

import logging

import demjson3
from bs4 import BeautifulSoup


class BandcampJSON:
    def __init__(self, body: BeautifulSoup) -> None:
        self.body = body
        self.json_data: list[str] = []
        self.logger = logging.getLogger("bandcamp-dl").getChild("JSON")

    def generate(self) -> list[str]:
        """Grabbing needed data from the page"""
        self.get_pagedata()
        self.get_js()
        return self.json_data

    def get_pagedata(self) -> None:
        self.logger.debug(" Grab pagedata JSON..")
        pagedata_tag = self.body.find("div", {"id": "pagedata"})
        if pagedata_tag is None:
            raise ValueError("Could not find pagedata div on Bandcamp page")
        pagedata = pagedata_tag["data-blob"]
        assert isinstance(pagedata, str)
        self.json_data.append(pagedata)

    def get_js(self) -> None:
        """Get <script> element containing the data we need and return the raw JS"""
        self.logger.debug(" Grabbing embedded scripts..")
        ld_json_script = self.body.find("script", {"type": "application/ld+json"})
        if ld_json_script is None:
            raise ValueError("Could not find application/ld+json script on Bandcamp page")
        embedded_scripts_raw: list[str | None] = [ld_json_script.string]
        for script in self.body.find_all("script"):
            album_info = script.get("data-tralbum")
            if album_info is not None:
                assert isinstance(album_info, str)
                embedded_scripts_raw.append(album_info)
        for script in embedded_scripts_raw:
            if script is None:
                continue
            js_data = self.js_to_json(script)
            self.json_data.append(js_data)

    def js_to_json(self, js_data: str) -> str:
        """Convert JavaScript dictionary to JSON"""
        self.logger.debug(" Converting JS to JSON..")
        # Decode with demjson first to reformat keys and lists
        decoded_js = demjson3.decode(js_data)
        result = demjson3.encode(decoded_js)
        assert isinstance(result, str)
        return result
