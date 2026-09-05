"""Regenerate the Options section of README.md from the CLI parser's own help output.

Usage:
    uv run python devscripts/make_readme.py           # rewrite README.md
    uv run python devscripts/make_readme.py --check   # exit 1 if README.md is out of date
"""

from __future__ import annotations

import os
import sys

from bandcamp_dl.cli_parsing import parse_args
from bandcamp_dl.const import PROG, REPO_DIR

README_FILE = REPO_DIR / "README.md"
OPTIONS_HEADING = "## Options"
NEXT_HEADING = "## Filename Template"
HELP_WIDTH = 100


def build_help() -> str:
    os.environ["COLUMNS"] = str(HELP_WIDTH)
    parser, _ = parse_args([], prog=PROG)
    return parser.format_help().rstrip()


def generate_readme(readme: str) -> str:
    start = readme.index(OPTIONS_HEADING)
    end = readme.index(NEXT_HEADING)
    section = f"{OPTIONS_HEADING}\n\n```text\n{build_help()}\n```\n\n"
    return readme[:start] + section + readme[end:]


def main() -> None:
    readme = README_FILE.read_text()
    generated = generate_readme(readme)
    if "--check" in sys.argv[1:]:
        if generated != readme:
            print(
                "README.md options are out of date; run: uv run python devscripts/make_readme.py",
                file=sys.stderr,
            )
            sys.exit(1)
        return
    _ = README_FILE.write_text(generated)


if __name__ == "__main__":
    main()
