#!/usr/bin/env python3
"""Repair of the broken bash mastering pipeline.

Stages:
  1. Decode + even-dimension scale + ProRes 422 HQ intermediate
  2. HEVC (NVENC when available, else libx265) to a delivery file
  3. EBU R128 / ITU-R BS.1770 loudness (two-pass loudnorm) with AAC audio

This is a local transcode/mastering tool. It does not change perceptual
fingerprints and will not bypass Content ID or similar systems.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO_SUFFIXES = {
    ".mov",
    ".mp4",
    ".mkv",
    ".avi",
    ".m4v",
    ".webm",
    ".mpg",
    ".mpeg",
    ".wmv",
}

# Even-grid scale: odd widths/heights cause chroma subsample bleed.
EVEN_SCALE = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

# Streaming-safe loudness (YouTube-ish -16 LUFS, true peak -1.5 dBTP).
LOUDNORM_I = -16.0
LOUDNORM_LRA = 11.0
LOUDNORM_TP = -1.5


class PipelineError(RuntimeError):
    pass


def require_binaries() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise PipelineError(f"Required tools not on PATH: {', '.join(missing)}")


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    try:
        return subprocess.run(
            cmd,
            check=True,
            text=True,
            capture_output=capture,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise PipelineError(
            f"Command failed ({exc.returncode}): {' '.join(cmd)}\n{stderr}"
        ) from exc


def probe_json(path: Path) -> dict:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        capture=True,
    )
    return json.loads(proc.stdout)


def has_audio(path: Path) -> bool:
    data = probe_json(path)
    return any(s.get("codec_type") == "audio" for s in data.get("streams", []))


def ffmpeg_encoder_list() -> str:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout


def encoder_exists(name: str, listing: str | None = None) -> bool:
    blob = listing if listing is not None else ffmpeg_encoder_list()
    return name in blob


def nvidia_gpu_present() -> bool:
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        subprocess.run(
            ["nvidia-smi", "-L"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return True


def nvenc_available() -> bool:
    return nvidia_gpu_present() and encoder_exists("hevc_nvenc")


def pick_simple_video_encoder(prefer: str) -> tuple[str, list[str]]:
    """Return (label, ffmpeg args after -c:v) for a widely playable MP4."""
    listing = ffmpeg_encoder_list()
    want_gpu = prefer in ("auto", "nvenc")
    if want_gpu and nvidia_gpu_present() and encoder_exists("h264_nvenc", listing):
        return "h264_nvenc", [
            "h264_nvenc",
            "-preset",
            "p4",
            "-rc",
            "vbr",
            "-cq",
            "23",
            "-b:v",
            "0",
            "-pix_fmt",
            "yuv420p",
        ]
    if prefer == "nvenc":
        raise PipelineError("h264_nvenc requested but not available in this FFmpeg build")
    if encoder_exists("libx264", listing):
        return "libx264", [
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
        ]
    if encoder_exists("libx265", listing):
        return "libx265", [
            "libx265",
            "-preset",
            "medium",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-tag:v",
            "hvc1",
        ]
    raise PipelineError("No usable H.264/HEVC encoder in this FFmpeg build")


def stage1_prores(src: Path, dest: Path) -> None:
    """Native-resolution decode -> even grid -> ProRes 422 HQ."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vf",
            EVEN_SCALE,
            "-c:v",
            "prores_ks",
            "-profile:v",
            "3",  # 422 HQ
            "-pix_fmt",
            "yuv422p10le",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )


def stage2_hevc(src: Path, dest: Path, preset: str, use_nvenc: bool) -> None:
    """Encode delivery HEVC. youtube vs twitch only changes rate control."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if preset == "youtube":
        cq, x265_crf, gop = 23, 20, 60
    else:  # twitch: slightly higher quality / less aggressive
        cq, x265_crf, gop = 21, 18, 120

    common_out = [
        "-pix_fmt",
        "yuv420p10le",
        "-tag:v",
        "hvc1",
        "-movflags",
        "+faststart",
        "-c:a",
        "copy",
        str(dest),
    ]

    if use_nvenc:
        # Real NVENC flags. There is no hevc_vcn_encoder; AMD is hevc_amf.
        # -scenecut is libx264/x265 only — omitted here on purpose.
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-c:v",
            "hevc_nvenc",
            "-preset",
            "p4",
            "-rc",
            "vbr",
            "-cq",
            str(cq),
            "-b:v",
            "0",
            "-maxrate",
            "40M",
            "-bufsize",
            "80M",
            "-bf",
            "3",
            "-g",
            str(gop),
            "-profile:v",
            "main10",
        ] + common_out
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-c:v",
            "libx265",
            "-preset",
            "medium",
            "-crf",
            str(x265_crf),
            "-pix_fmt",
            "yuv420p10le",
            "-tag:v",
            "hvc1",
            "-x265-params",
            f"keyint={gop}:min-keyint={gop // 2}:scenecut=50:bframes=3",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(dest),
        ]

    run(cmd)


def parse_loudnorm_json(stderr: str) -> dict:
    start = stderr.rfind("{")
    end = stderr.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise PipelineError(f"loudnorm did not print measured stats:\n{stderr[-2000:]}")
    return json.loads(stderr[start : end + 1])


def stage3_loudnorm(src: Path, dest: Path) -> None:
    """Two-pass loudnorm. Audio must be re-encoded; -c:a copy cannot apply -af."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not has_audio(src):
        print("No audio stream; copying video only.", flush=True)
        run(["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(dest)])
        return

    measure = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-af",
        f"loudnorm=I={LOUDNORM_I}:LRA={LOUDNORM_LRA}:TP={LOUDNORM_TP}:print_format=json",
        "-f",
        "null",
        "-",
    ]
    print("+", " ".join(measure), flush=True)
    proc = subprocess.run(measure, check=True, text=True, capture_output=True)
    stats = parse_loudnorm_json(proc.stderr)

    loudnorm = (
        f"loudnorm=I={LOUDNORM_I}:LRA={LOUDNORM_LRA}:TP={LOUDNORM_TP}"
        f":measured_I={stats['input_i']}"
        f":measured_LRA={stats['input_lra']}"
        f":measured_TP={stats['input_tp']}"
        f":measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}"
        f":linear=true:print_format=summary"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-map",
            "0",
            "-c:v",
            "copy",
            "-af",
            loudnorm,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-map_metadata",
            "0",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )


def loudnorm_filter_from_src(src: Path) -> str | None:
    if not has_audio(src):
        return None
    measure = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vn",
        "-af",
        f"loudnorm=I={LOUDNORM_I}:LRA={LOUDNORM_LRA}:TP={LOUDNORM_TP}:print_format=json",
        "-f",
        "null",
        "-",
    ]
    print("+", " ".join(measure), flush=True)
    proc = subprocess.run(measure, check=True, text=True, capture_output=True)
    stats = parse_loudnorm_json(proc.stderr)
    return (
        f"loudnorm=I={LOUDNORM_I}:LRA={LOUDNORM_LRA}:TP={LOUDNORM_TP}"
        f":measured_I={stats['input_i']}"
        f":measured_LRA={stats['input_lra']}"
        f":measured_TP={stats['input_tp']}"
        f":measured_thresh={stats['input_thresh']}"
        f":offset={stats['target_offset']}"
        f":linear=true"
    )


def simple_encode(src: Path, dest: Path, encoder: str) -> None:
    """One-pass delivery encode: even scale + H.264 + AAC + loudnorm."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    label, vargs = pick_simple_video_encoder(encoder)
    print(f"Simple encode using {label}", flush=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vf",
        EVEN_SCALE,
        "-c:v",
        *vargs,
        "-movflags",
        "+faststart",
        "-map_metadata",
        "0",
    ]
    af = loudnorm_filter_from_src(src)
    if af:
        cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        print("No audio stream; video only.", flush=True)
    cmd.append(str(dest))
    run(cmd)


def process_one(
    src: Path, out_dir: Path, preset: str, encoder: str, pipeline: str
) -> Path:
    if not src.is_file():
        raise PipelineError(f"Input file not found: {src}")

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem

    if pipeline == "simple":
        final = out_dir / f"{stem}_{preset}.mp4"
        print(f"Simple pipeline for {src.name}", flush=True)
        simple_encode(src, final, encoder)
        print(f"Finalized: {final}", flush=True)
        return final

    final = out_dir / f"{stem}_{preset}_hevc.mp4"
    use_nvenc = encoder == "nvenc" or (encoder == "auto" and nvenc_available())
    print(f"GPU path: {'hevc_nvenc' if use_nvenc else 'libx265'}", flush=True)

    with tempfile.TemporaryDirectory(prefix="master_pipeline_") as tmp:
        tmp_path = Path(tmp)
        prores = tmp_path / f"{stem}.stage_prores.mov"
        hevc = tmp_path / f"{stem}_hevc.mp4"

        print(f"Stage 1: ProRes intermediate for {src.name}", flush=True)
        stage1_prores(src, prores)

        print("Stage 2: HEVC encode", flush=True)
        stage2_hevc(prores, hevc, preset, use_nvenc)

        print("Stage 3: loudness normalization", flush=True)
        stage3_loudnorm(hevc, final)

    print(f"Finalized: {final}", flush=True)
    return final


def collect_inputs(input_dir: Path, single: Path | None) -> list[Path]:
    if single is not None:
        return [single]
    if not input_dir.is_dir():
        raise PipelineError(f"Input folder does not exist: {input_dir}")
    files = sorted(
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES
    )
    if not files:
        raise PipelineError(
            f"No video files in {input_dir}. "
            "Put a .mp4 / .mov / .mkv there, then run: python3 process_video.py"
        )
    return files


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decode → ProRes → HEVC → loudnorm mastering pipeline."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("Input Folder"),
        help="Folder of source videos (default: Input Folder)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Output Folder"),
        help="Destination folder (default: Output Folder)",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=None,
        help="Process a single file instead of the whole input folder",
    )
    parser.add_argument(
        "--preset",
        choices=("youtube", "twitch"),
        default="youtube",
        help="Rate-control preset (default: youtube)",
    )
    parser.add_argument(
        "--encoder",
        choices=("auto", "nvenc", "cpu"),
        default="auto",
        help="Prefer GPU if present; simple mode uses H.264, full mode uses HEVC",
    )
    parser.add_argument(
        "--pipeline",
        choices=("simple", "full"),
        default="simple",
        help="simple = one FFmpeg encode (default); full = ProRes then HEVC",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        require_binaries()
        args.input_dir.mkdir(parents=True, exist_ok=True)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        sources = collect_inputs(args.input_dir, args.src)
        for src in sources:
            process_one(
                src, args.output_dir, args.preset, args.encoder, args.pipeline
            )
    except PipelineError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Task complete. Check your Output Folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
