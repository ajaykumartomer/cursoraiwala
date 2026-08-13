#!/usr/bin/env python3
r"""
AKT VIDEO PROCESSOR
Effect: Flipped Moving Repeat (Series 2 - BG2)

Matches AKT_Video_Processor.bat:
  copy source -> ASCII temp names
  ffmpeg -i temp -ss 4 -i temp [-stream_loop -1 -i bg]
  -filter_complex_script (not an inline graph, not amovie=)
  encode libx264/aac and copy the result to Output Folder\<stem>.mp4
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
AUDIO_BG_NAME = "bg2.mp4"
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
    *,
    audio_name: str | None,
    filter_script: str,
) -> list[str]:
    cmd = [ffmpeg, "-y", "-i", video_name, "-ss", OVERLAY_START_SS, "-i", video_name]
    if audio_name:
        cmd.extend(["-stream_loop", "-1", "-i", audio_name])
    cmd.extend(["-filter_complex_script", filter_script])
    cmd.extend(
        [
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
    )
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
        audio_name = None
        if bg is not None:
            safe_bg = tmp / "bg.mp4"
            link_or_copy(bg, safe_bg)
            audio_name = safe_bg.name
        cmd = build_ffmpeg_cmd(
            ffmpeg,
            safe_in.name,
            safe_out.name,
            audio_name=audio_name,
            filter_script=str(script),
        )
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


def folder_layout(base: Path) -> tuple[Path, Path, Path]:
    return (
        base / "Input Folder",
        base / "Output Folder",
        base / "Audio to Add",
    )


def list_inputs(input_folder: Path) -> list[Path]:
    files = []
    for path in sorted(input_folder.iterdir(), key=lambda p: p.name.lower()):
        if path.is_file():
            files.append(path)
    return files


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
    input_folder, output_folder, audio_folder = folder_layout(base)
    info("Checking folders...")
    print()
    for folder, label in (
        (input_folder, "Input Folder"),
        (output_folder, "Output Folder"),
        (audio_folder, "Audio to Add"),
    ):
        if not folder.is_dir():
            folder.mkdir(parents=True, exist_ok=True)
            ok(f"Created: {label}")
        else:
            ok(f"{label} exists")
    print()

    bg_path = audio_folder / AUDIO_BG_NAME
    bg = bg_path if bg_path.is_file() else None
    if bg:
        ok(f"Audio: {AUDIO_BG_NAME}")
    else:
        print(f" [WARN] Audio not found: {bg_path}")
        print("         Processing WITHOUT background audio.")
    print()

    videos = list_inputs(input_folder)
    if not videos:
        fail("No files in: Input Folder")
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
    print(f" Audio       : {bg_path}")
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
