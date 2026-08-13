#!/usr/bin/env python3
r"""
AKT VIDEO PROCESSOR — same encode as the original one-liner:

  ffmpeg -y -i INPUT -ss 4 -i INPUT -filter_complex "...;amovie=aud/bg2.mp4:loop=9999,volume=1[a2];[a1][a2]amix=duration=shortest" ... OUTPUT

Input is copied to a temp name first so @ and # in YouTube titles cannot
split FFmpeg. amovie stays aud/bg2.mp4 (relative, no C:\\ path).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

LIB_ROOT = Path(r"C:\AKT Media Tools") if os.name == "nt" else Path.home() / "AKT Media Tools"
OVERLAY_START_SS = "4"

METADATA_CLEAR = [
    "title",
    "artist",
    "album_artist",
    "album",
    "date",
    "track",
    "genre",
    "publisher",
    "encoded_by",
    "copyright",
    "composer",
    "performer",
    "TIT1",
    "TIT3",
    "disc",
    "TKEY",
    "TBPM",
    "encoder",
]


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def filter_file(with_audio: bool) -> Path:
    name = "akt_filter_bg2.txt" if with_audio else "akt_filter_bg2_noaudio.txt"
    return script_dir() / name


def ok(msg: str) -> None:
    print(f" [OK] {msg}")


def fail(msg: str) -> None:
    print(f" [FAIL] {msg}")


def info(msg: str) -> None:
    print(f" [~] {msg}")


def find_ffmpeg() -> str | None:
    env = os.environ.get("FFMPEG_PATH")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.extend(
        [
            LIB_ROOT / "Tools" / "ffmpeg.exe",
            LIB_ROOT / "ffmpeg.exe",
            script_dir() / "ffmpeg.exe",
        ]
    )
    for path in candidates:
        if path.is_file():
            return str(path)
    return shutil.which("ffmpeg")


def link_or_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def build_ffmpeg_cmd(
    ffmpeg: str,
    video_name: str,
    output_name: str,
    filter_script: str,
) -> list[str]:
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        video_name,
        "-ss",
        OVERLAY_START_SS,
        "-i",
        video_name,
        "-filter_complex_script",
        filter_script,
        "-vcodec",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-g",
        "60",
        "-b:v",
        "1550k",
        "-shortest",
        "-acodec",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
    ]
    for key in METADATA_CLEAR:
        cmd.extend(["-metadata", f"{key}="])
    cmd.extend(
        [
            "-metadata",
            "language=eng",
            "-threads",
            "0",
            "-preset",
            "ultrafast",
            "-crf",
            "30",
            output_name,
        ]
    )
    return cmd


def resolve_folders(base: Path) -> tuple[Path, Path, Path]:
    input_folder = base / "_input" if (base / "_input").is_dir() else base / "Input Folder"
    output_folder = base / "_output" if (base / "_output").is_dir() else base / "Output Folder"
    aud = base / "aud"
    return input_folder, output_folder, aud


def resolve_bg(base: Path, aud: Path) -> Path | None:
    dest = aud / "bg2.mp4"
    if dest.is_file():
        return dest
    alt = base / "Audio to Add" / "bg2.mp4"
    if alt.is_file():
        aud.mkdir(parents=True, exist_ok=True)
        shutil.copy2(alt, dest)
        return dest
    return dest if dest.is_file() else None


def process_file(
    ffmpeg: str,
    src: Path,
    bg: Path | None,
    output_folder: Path,
    log_file: Path | None = None,
) -> bool:
    print(" --------------------------------------------------------")
    info(f"Processing: {src.name}")
    print(" --------------------------------------------------------")

    with_audio = bg is not None
    script = filter_file(with_audio)
    if not script.is_file():
        fail(f"Missing filter file: {script}")
        return False

    out_path = output_folder / f"{src.stem}.mp4"
    with tempfile.TemporaryDirectory(prefix="akt_vp_") as raw_tmp:
        tmp = Path(raw_tmp)
        safe_in = tmp / "input.mp4"
        safe_out = tmp / "output.mp4"
        link_or_copy(src, safe_in)
        if bg is not None:
            link_or_copy(bg, tmp / "aud" / "bg2.mp4")
        cmd = build_ffmpeg_cmd(ffmpeg, safe_in.name, safe_out.name, str(script))
        log_handle = None
        try:
            if log_file is not None:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                log_handle = open(log_file, "a", encoding="utf-8", errors="replace")
            proc = subprocess.run(
                cmd,
                cwd=tmp,
                check=False,
                stdout=log_handle,
                stderr=log_handle,
            )
        finally:
            if log_handle is not None:
                log_handle.close()
        if proc.returncode != 0 or not safe_out.is_file() or safe_out.stat().st_size == 0:
            fail(f"Failed: {src.name}")
            if log_file is not None:
                print(f"         See: {log_file.name}")
            return False
        output_folder.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()
        shutil.copy2(safe_out, out_path)

    ok(f"Done: {out_path.name}")
    return True


def main() -> int:
    print()
    print("=" * 60)
    print("  AKT VIDEO PROCESSOR")
    print("  Effect: Flipped Moving Repeat (Series 2 - BG2)")
    print("=" * 60)
    print()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        fail("FFmpeg not found in PATH.")
        return 1
    ok("FFmpeg found")
    print()

    base = script_dir()
    os.chdir(base)
    input_folder, output_folder, aud = resolve_folders(base)
    input_folder.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(parents=True, exist_ok=True)
    aud.mkdir(parents=True, exist_ok=True)
    ok(f"Input: {input_folder}")
    ok(f"Output: {output_folder}")

    bg = resolve_bg(base, aud)
    if bg:
        ok("Audio: aud/bg2.mp4")
    else:
        print(" [WARN] aud/bg2.mp4 not found. Processing WITHOUT background audio.")
    print()

    videos = [p for p in sorted(input_folder.iterdir(), key=lambda x: x.name.lower()) if p.is_file()]
    if not videos:
        fail(f"No files in: {input_folder}")
        return 1
    ok(f"Found {len(videos)} file(s) to process")
    print()
    print("=" * 60)
    print("  STARTING VIDEO PROCESSING")
    print("=" * 60)
    print()

    log_file = base / "ffmpeg_log.txt"
    if log_file.exists():
        log_file.unlink()

    started = time.strftime("%H:%M:%S")
    processed = 0
    failed = 0
    for src in videos:
        if process_file(ffmpeg, src, bg, output_folder, log_file=log_file):
            processed += 1
        else:
            failed += 1
        print()

    print("=" * 60)
    print("  PROCESSING COMPLETE")
    print("=" * 60)
    print()
    print(f" Start Time  : {started}")
    print(f" End Time    : {time.strftime('%H:%M:%S')}")
    print(f" Processed   : {processed}")
    print(f" Failed      : {failed}")
    print(f" Input       : {input_folder}")
    print(f" Output      : {output_folder}")
    print(f" Audio       : {aud / 'bg2.mp4'}")
    if failed:
        print()
        print(f" [!] FFmpeg errors saved to: {log_file.name}")
    print()
    print("=" * 60)
    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        fail(str(exc))
        code = 1
    sys.exit(code)
