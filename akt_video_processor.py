#!/usr/bin/env python3
r"""
AKT VIDEO PROCESSOR
Effect: Flipped Moving Repeat (Series 2 - BG2)

FFmpeg treats '@' as "read extra options from this file" and '#' as a
comment when the command is built as one shell string. Filenames such as
"My Suggestions To @bjp4india   #ugcguidelines.mp4" then get split, the
filter graph is glued onto the path, and processing fails with
"No such file or directory".

This script never passes original filenames to FFmpeg. Each job copies
(or hard-links) the video and background audio to simple temp names and
runs FFmpeg with a subprocess argument list (no shell).
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
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".mpeg", ".mpg"}
AUDIO_BG_NAME = "bg2.mp4"

FILTER_COMPLEX = (
    "[0:v]scale=iw:ih[v2];"
    "[1:v]crop=in_w/1.5:in_h/1.5:"
    "(in_w-out_w)/1.5+((in_w-out_w)/1.5)*sin(t*0.5):"
    "(in_h-out_h)/1.5+((in_h-out_h)/1.5)*sin(t*0.2),"
    "boxblur=1:1,scale=iw*1.5:ih*1.5,hflip[v1];"
    "[v2][v1]overlay=enable='gte(mod(t,5),3)':x=0:y=0[vout];"
    "[0:a]atempo=1,bass=frequency=200:gain=-90,volume=+20dB,"
    "aecho=1:0.6:2:0.4,"
    "bass=g=3:f=110:w=20,bass=g=10:f=500:w=20,bass=g=3:f=300:w=30,"
    "bass=g=10:f=110:w=20,bass=g=20:f=110:w=40,"
    "firequalizer=gain_entry='entry(0,-23);entry(250,-11.5);entry(6000,0);"
    "entry(12000,8);entry(16000,16)',"
    "compand=attacks=7:decays=1:points=-90/-90|-70/-60|-15/-15|0/-10:"
    "soft-knee=1:volume=-70:gain=3,"
    "pan=stereo|FL<FL+0.5*FC+0.6*BL+0.6*SL|FR<FR+2*FC+1*BR+2*SR,"
    "highpass=f=300,lowpass=f=700,volume=6[a1];"
    "[2:a]volume=1[a2];"
    "[a1][a2]amix=duration=shortest:dropout_transition=0[aout]"
)


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def ok(msg: str) -> None:
    print(f" [OK] {msg}")


def fail(msg: str) -> None:
    print(f" [FAIL] {msg}")


def info(msg: str) -> None:
    print(f" [~] {msg}")


def banner() -> None:
    print()
    print("=" * 60)
    print("  AKT VIDEO PROCESSOR")
    print("  Effect: Flipped Moving Repeat (Series 2 - BG2)")
    print("=" * 60)
    print()


def find_python_label() -> str:
    return Path(sys.executable).name


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
            Path("ffmpeg.exe"),
            Path("ffmpeg"),
        ]
    )
    for path in candidates:
        if path.is_file():
            return str(path)
    found = shutil.which("ffmpeg")
    return found


def ensure_lib_folder() -> None:
    try:
        LIB_ROOT.mkdir(parents=True, exist_ok=True)
        probe = LIB_ROOT / "Lib" / "site-packages"
        probe.mkdir(parents=True, exist_ok=True)
        test = probe / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        ok(f"Library folder writable: {probe}")
    except OSError as exc:
        fail(f"Library folder not writable: {exc}")


def check_optional_imports() -> None:
    info("Checking libraries...")
    print()
    for name in ("PIL", "google.genai"):
        label = "Pillow" if name == "PIL" else "google-genai"
        try:
            __import__(name)
            ok(f"{label} (already installed)")
        except Exception:
            ok(f"{label} (not required for this effect)")


def folder_layout(base: Path) -> tuple[Path, Path, Path]:
    return (
        base / "Input Folder",
        base / "Output Folder",
        base / "Audio to Add",
    )


def list_videos(input_folder: Path) -> list[Path]:
    files = []
    for path in sorted(input_folder.iterdir(), key=lambda p: p.name.lower()):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTS:
            files.append(path)
    return files


def pick_background(audio_folder: Path) -> Path | None:
    preferred = audio_folder / AUDIO_BG_NAME
    if preferred.is_file():
        return preferred
    for path in sorted(audio_folder.iterdir()):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTS | {".mp3", ".wav", ".m4a", ".aac"}:
            return path
    return None


def link_or_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


def has_audio_stream(ffmpeg: str, media: Path) -> bool:
    ffprobe = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    probe_bin = str(ffprobe) if ffprobe.is_file() else shutil.which("ffprobe")
    if not probe_bin:
        return True
    proc = subprocess.run(
        [
            probe_bin,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(media),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(proc.stdout.strip())


def build_ffmpeg_cmd(
    ffmpeg: str,
    video_name: str,
    audio_name: str,
    output_name: str,
) -> list[str]:
    """Build argv using only safe temp filenames (no original path, no shell)."""
    return [
        ffmpeg,
        "-y",
        "-i",
        video_name,
        "-i",
        video_name,
        "-stream_loop",
        "-1",
        "-i",
        audio_name,
        "-filter_complex",
        FILTER_COMPLEX,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        output_name,
    ]


def process_file(
    ffmpeg: str,
    src: Path,
    bg: Path,
    output_folder: Path,
) -> bool:
    print(" --------------------------------------------------------")
    info(f"Processing: {src.name}")
    print(" --------------------------------------------------------")

    if not has_audio_stream(ffmpeg, src):
        fail(f"No audio stream (required for this effect): {src.name}")
        return False

    out_path = output_folder / src.name
    with tempfile.TemporaryDirectory(prefix="akt_vp_") as raw_tmp:
        tmp = Path(raw_tmp)
        safe_in = tmp / f"input{src.suffix.lower() or '.mp4'}"
        safe_bg = tmp / f"bg{bg.suffix.lower() or '.mp4'}"
        safe_out = tmp / "output.mp4"
        link_or_copy(src, safe_in)
        link_or_copy(bg, safe_bg)
        cmd = build_ffmpeg_cmd(ffmpeg, safe_in.name, safe_bg.name, safe_out.name)
        proc = subprocess.run(cmd, cwd=tmp, check=False)
        if proc.returncode != 0 or not safe_out.is_file() or safe_out.stat().st_size == 0:
            fail(f"Failed: {src.name}")
            return False
        output_folder.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()
        shutil.move(str(safe_out), str(out_path))

    ok(f"Saved: {out_path.name}")
    return True


def main() -> int:
    banner()
    ensure_lib_folder()
    print()
    ok(f"Python: {find_python_label()}")
    print(sys.version.split()[0])
    print()
    check_optional_imports()
    print()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        fail("FFmpeg not found. Put ffmpeg.exe on PATH or in C:\\AKT Media Tools\\Tools")
        return 1
    ok("FFmpeg found")
    print()

    info("Checking folders...")
    print()
    base = script_dir()
    input_folder, output_folder, audio_folder = folder_layout(base)
    for folder, label in (
        (input_folder, "Input Folder"),
        (output_folder, "Output Folder"),
        (audio_folder, "Audio to Add"),
    ):
        if folder.is_dir():
            ok(f"{label} exists")
        else:
            folder.mkdir(parents=True, exist_ok=True)
            ok(f"{label} created")
    print()

    bg = pick_background(audio_folder)
    if not bg:
        fail(f"No background audio in: {audio_folder} (expected {AUDIO_BG_NAME})")
        return 1
    ok(f"Audio: {bg.name}")
    print()

    videos = list_videos(input_folder)
    ok(f"Found {len(videos)} file(s) to process")
    print()
    print("=" * 60)
    print("  STARTING VIDEO PROCESSING")
    print("=" * 60)
    print()

    started = time.strftime("%H:%M:%S")
    processed = 0
    failed = 0
    for src in videos:
        if process_file(ffmpeg, src, bg, output_folder):
            processed += 1
        else:
            failed += 1
        print()

    ended = time.strftime("%H:%M:%S")
    print("=" * 60)
    print("  PROCESSING COMPLETE")
    print("=" * 60)
    print()
    print(f" Start Time  : {started}")
    print(f" End Time    : {ended}")
    print(f" Processed   : {processed}")
    print(f" Failed      : {failed}")
    print(f" Input       : {input_folder}")
    print(f" Output      : {output_folder}")
    print(f" Audio       : {bg}")
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
    if os.name == "nt":
        try:
            input("Press any key to continue . . .")
        except EOFError:
            pass
    sys.exit(code)
