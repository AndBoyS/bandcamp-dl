from __future__ import annotations

import shutil


def print_clean(msg: str) -> None:
    terminal_size = shutil.get_terminal_size()
    padding = max(0, terminal_size[0] - len(msg))
    print(f"{msg}{' ' * padding}", end="")


def print_progress(*, track_num: int, num_tracks: int, label: str, done: int, total: int) -> None:
    """Print a single-line progress bar for the current album download

    :param track_num: 1-based index of the current track
    :param num_tracks: total number of tracks in the album
    :param label: text shown after the bar (e.g. the file being downloaded)
    :param done: number of bytes (or items) completed so far
    :param total: total number of bytes (or items), when known
    """
    filled = min(int(50 * done / total), 50) if total > 0 else 0
    print_clean(f"\r({track_num}/{num_tracks}) [{'=' * filled}{' ' * (50 - filled)}] :: {label}")
