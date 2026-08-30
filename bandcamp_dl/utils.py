from __future__ import annotations

import shutil


def print_clean(msg: str) -> None:
    terminal_size = shutil.get_terminal_size()
    print(f"{msg}{' ' * (terminal_size[0] - len(msg))}", end="")
