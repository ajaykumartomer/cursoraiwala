#!/usr/bin/env python3
"""Split MergedScripts.txt back into original .bat files.

Never modifies MergedScripts.txt. Writes into extracted_bats/ only.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADER_RE = re.compile(r"^Script\s+\d+\s+\{(.+)\}\s*$")
INPUT_NAME = "MergedScripts.txt"
OUTPUT_DIR_NAME = "extracted_bats"
PROTECTED_NAMES = {
    INPUT_NAME.lower(),
    "mergeallbats.bat",
    "splitmergedscripts.bat",
    "splitmergedscripts.py",
}


def is_blank(line: str) -> bool:
    return line.strip() == ""


def safe_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name.strip()
    if not base or base in {".", ".."}:
        raise ValueError(f"unsafe filename: {name!r}")
    if base.lower() in PROTECTED_NAMES:
        raise ValueError(f"refusing to write protected file: {base}")
    if not base.lower().endswith(".bat"):
        raise ValueError(f"refusing non-.bat output: {base}")
    return base


def save_script(folder: Path, filename: str, body: list[str]) -> Path:
    while body and is_blank(body[-1]):
        body.pop()
    path = folder / filename
    path.write_bytes(("\r\n".join(body) + ("\r\n" if body else "")).encode("utf-8"))
    return path


def split_merged_scripts(
    folder: Path,
    input_name: str = INPUT_NAME,
    output_dir_name: str = OUTPUT_DIR_NAME,
) -> list[str]:
    input_path = folder / input_name
    if not input_path.is_file():
        raise FileNotFoundError(input_name)

    source_before = input_path.read_bytes()
    text = source_before.decode("utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    out_dir = folder / output_dir_name
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    current_name: str | None = None
    body: list[str] = []
    skip_blanks = 0

    def flush() -> None:
        nonlocal current_name, body
        if not current_name:
            return
        filename = safe_filename(current_name)
        save_script(out_dir, filename, body)
        created.append(filename)
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

    source_after = input_path.read_bytes()
    if source_after != source_before:
        raise RuntimeError("MergedScripts.txt was changed; aborting")
    return created


def main() -> int:
    folder = Path(__file__).resolve().parent
    try:
        created = split_merged_scripts(folder)
    except FileNotFoundError:
        print()
        print(f'[ERROR] "{INPUT_NAME}" was not found in this folder.')
        print("This script never deletes that file. Copy it here and run again.")
        return 1
    except Exception as exc:
        print()
        print(f"[ERROR] {exc}")
        return 1

    print()
    print("============================================")
    print("       DISINTEGRATING SCRIPTS")
    print("============================================")
    print()
    for name in created:
        print(f"[+] Created: {OUTPUT_DIR_NAME}/{name}")
    print()
    print("============================================")
    print("    COMPLETED!")
    print("============================================")
    print()
    print(f"Total Scripts Extracted: {len(created)}")
    print(f'Input left untouched: "{INPUT_NAME}"')
    print(f'Output folder: "{OUTPUT_DIR_NAME}"')
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
