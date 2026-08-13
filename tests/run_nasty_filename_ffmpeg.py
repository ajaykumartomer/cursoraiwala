#!/usr/bin/env python3
"""Create a tiny clip whose name contains @ and #, then run the processor."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import akt_video_processor as vp  # noqa: E402

NASTY_NAME = (
    "My Suggestions To @bjp4india   #ugcguidelines #narendramodi "
    "#mohanbhagwat #ajeetbharti #ajeetbhartireels.mp4"
)


def ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise SystemExit("ffmpeg required for integration test")
    return found


def make_clip(ffmpeg: str, dest: Path, seconds: float = 1.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size=320x240:rate=25:duration={seconds}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={seconds}",
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    ffmpeg = ffmpeg_bin()
    with tempfile.TemporaryDirectory(prefix="akt_vp_it_") as raw:
        base = Path(raw)
        input_folder = base / "Input Folder"
        output_folder = base / "Output Folder"
        audio_folder = base / "Audio to Add"
        input_folder.mkdir()
        output_folder.mkdir()
        audio_folder.mkdir()

        src = input_folder / NASTY_NAME
        bg = audio_folder / "bg2.mp4"
        make_clip(ffmpeg, src, 1.0)
        make_clip(ffmpeg, bg, 1.0)
        assert src.is_file(), src

        ok = vp.process_file(ffmpeg, src, bg, output_folder)
        out = output_folder / NASTY_NAME
        if not ok or not out.is_file() or out.stat().st_size == 0:
            print("INTEGRATION FAIL: output missing", file=sys.stderr)
            return 1
        print(f"INTEGRATION OK: {out.name} ({out.stat().st_size} bytes)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
