from __future__ import annotations

import shutil


def print_clean(msg: str) -> None:
    terminal_size = shutil.get_terminal_size()
    padding = max(0, terminal_size[0] - len(msg))
    print(f"{msg}{' ' * padding}", end="")
