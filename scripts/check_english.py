#!/usr/bin/env python3
"""Reject localized text and filenames from the public English repository."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALIZED_CODEPOINTS = {
    0x00C7,
    0x00D6,
    0x00DC,
    0x00E7,
    0x00F6,
    0x00FC,
    0x011E,
    0x011F,
    0x0130,
    0x0131,
    0x015E,
    0x015F,
}
FORBIDDEN_PATH_MARKERS = ("_TR.", "_TR/", "DURUM-RAPORU")
FORBIDDEN_ASCII_SNIPPETS = (
    'lang="' + "tr" + '"',
    "tr" + "-TR",
    "birle" + "sik",
    "calis" + "tir",
    "dogru" + "la",
    "fizik" + "sel",
    "gore" + "v",
    "henu" + "z",
    "kamera" + "li",
    "kamera" + "siz",
    "kayi" + "t",
    "konus" + "ma",
    "olust" + "ur",
    "simu" + "lasyon",
    "varsayi" + "lan",
)


def tracked_files() -> list[Path]:
    payload = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode()
    return [ROOT / item for item in payload.split("\0") if item]


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            continue
        if any(marker.casefold() in relative.casefold() for marker in FORBIDDEN_PATH_MARKERS):
            problems.append(f"localized filename: {relative}")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        localized = sorted(
            {character for character in text if ord(character) in LOCALIZED_CODEPOINTS}
        )
        if localized:
            codepoints = ", ".join(f"U+{ord(character):04X}" for character in localized)
            problems.append(f"localized characters in {relative}: {codepoints}")
        folded = text.casefold()
        for snippet in FORBIDDEN_ASCII_SNIPPETS:
            if snippet.casefold() in folded:
                problems.append(f"localized text marker in {relative}: {snippet}")

    if problems:
        print("English-only repository check failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("English-only repository check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
