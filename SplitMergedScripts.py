#!/usr/bin/env python3
"""Split MergedScripts.txt back into original .bat files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADER_RE = re.compile(r"^Script\s+\d+\s+\{(.+)\}\s*$")
INPUT_NAME = "MergedScripts.txt"


def is_blank(line: str) -> bool:
    return line.strip() == ""


def save_script(folder: Path, filename: str, body: list[str]) -> None:
    while body and is_blank(body[-1]):
        body.pop()
    path = folder / filename
    path.write_bytes(("\r\n".join(body) + ("\r\n" if body else "")).encode("utf-8"))


def split_merged_scripts(folder: Path, input_name: str = INPUT_NAME) -> list[str]:
    input_path = folder / input_name
    if not input_path.is_file():
        raise FileNotFoundError(input_name)

    raw = input_path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    # Keep a possible trailing empty from final newline as a real last line only if needed
    if lines and lines[-1] == "":
        lines.pop()

    created: list[str] = []
    current_name: str | None = None
    body: list[str] = []
    skip_blanks = 0

    def flush() -> None:
        nonlocal current_name, body
        if not current_name:
            return
        save_script(folder, current_name, body)
        created.append(current_name)
        current_name = None
        body = []

    for line in lines:
        match = HEADER_RE.match(line)
        if match:
            flush()
            current_name = match.group(1)
            skip_blanks = 3
            body = []
            continue
        if current_name is None:
            continue
        if skip_blanks > 0:
            if is_blank(line):
                skip_blanks -= 1
                continue
            skip_blanks = 0
        body.append(line)

    flush()
    return created


def main() -> int:
    folder = Path(__file__).resolve().parent
    try:
        created = split_merged_scripts(folder)
    except FileNotFoundError:
        print()
        print(f'[ERROR] "{INPUT_NAME}" was not found in this folder.')
        return 1

    print()
    print("============================================")
    print("       DISINTEGRATING SCRIPTS")
    print("============================================")
    print()
    for name in created:
        print(f"[+] Created: {name}")
    print()
    print("============================================")
    print("    COMPLETED!")
    print("============================================")
    print()
    print(f"Total Scripts Extracted: {len(created)}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
