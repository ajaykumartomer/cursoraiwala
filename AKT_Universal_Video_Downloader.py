#!/usr/bin/env python3
"""
AKT Complete All-In-One Script
==============================
Single .py file — no other project files required.

Includes:
  • Social Media Snapshotter (S24 Ultra screenshots for X/Instagram + others)
  • Universal Video Downloader (any http(s) URL → .mp4 when available)
  • Cookie/browser-independent yt-dlp ladder: API → CLI → gallery-dl → streamlink/direct
  • YouTube player-client ladder works without browser cookies

Usage:
  python AKT_Universal_Video_Downloader.py
  python AKT_Universal_Video_Downloader.py "https://..."

Outputs (next to this script):
  Social Media Screenshots/
  Social Media Videos/

Windows tools: C:\\AKT Media Tools
Other OS: .akt_media_tools/ next to this script
"""

import sys
import os
import ctypes
import subprocess
import importlib
import asyncio
import re
import warnings
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import shutil
import tempfile
import zipfile
import urllib.request
from typing import Iterable, List, Optional

# Suppress harmless third-party syntax warnings from the WMI library
warnings.filterwarnings("ignore", category=SyntaxWarning, module="wmi")

# ============================================================================
# 1. PATHS & BOOTSTRAP CONFIGURATION
# ============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Windows keeps the original AKT Tools root; other OSes use a local folder
# so video/ffmpeg/deno installs still work for development and testing.
if os.name == "nt":
    LIB_ROOT = r"C:\AKT Media Tools"
else:
    LIB_ROOT = os.path.join(SCRIPT_DIR, ".akt_media_tools")
SITE_PACKAGES = os.path.join(LIB_ROOT, "Lib", "site-packages")
TOOLS_DIR = os.path.join(LIB_ROOT, "Tools")
PW_BROWSERS = os.path.join(TOOLS_DIR, "pw-browsers")
VIDEO_DIR = os.path.join(SCRIPT_DIR, "Social Media Videos")

# Force Playwright to use the same private browser directory that
# prepare_environment() checks/installs into. This prevents it from falling
# back to %LOCALAPPDATA%\\ms-playwright and reporting a missing Firefox.
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PW_BROWSERS

S24_VIEWPORT = {"width": 720, "height": 1560}
# Galaxy S24 Ultra style physical-pixel density for screenshots.
S24_DEVICE_SCALE_FACTOR = 3.5

S24_CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36"
)

S24_FIREFOX_UA = "Mozilla/5.0 (Android 14; Mobile; rv:125.0) Gecko/125.0 Firefox/125.0"

S24_UA = S24_CHROME_UA

# ============================================================================
# EMBEDDED UNIVERSAL VIDEO DOWNLOAD ENGINE (all-in-one — no separate module)
# ============================================================================


# ---------------------------------------------------------------------------
# Shared constants (mirrors the snapshotter mobile UA)
# ---------------------------------------------------------------------------

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".ts"}

PLATFORM_DOMAIN_MAP = {
    "x": "x.com",
    "instagram": "instagram.com",
    "youtube": "youtube.com",
    "facebook": "facebook.com",
    "reddit": "reddit.com",
    "tiktok": "tiktok.com",
    "pinterest": "pinterest.com",
    "linkedin": "linkedin.com",
    "threads": "threads.net",
    "snapchat": "snapchat.com",
    "telegram": "telegram.com",
    "twitch": "twitch.tv",
    "sharechat": "sharechat.com",
    "bluesky": "bsky.app",
    "truth": "truthsocial.com",
    "discord": "discord.com",
    "whatsapp": "whatsapp.com",
    "quora": "quora.com",
    "moj": "mojapp.in",
    "josh": "joshapp.com",
    "nextdoor": "nextdoor.com",
    "shaadi": "shaadi.com",
    "generic": "video",
}

UNIVERSAL_PLATFORM_PATTERNS = {
    "facebook": ("facebook.com", "fb.watch", "m.facebook.com"),
    "instagram": ("instagram.com", "instagr.am"),
    "youtube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "whatsapp": ("whatsapp.com", "wa.me"),
    "linkedin": ("linkedin.com",),
    "x": ("twitter.com", "x.com"),
    "reddit": ("reddit.com", "redd.it", "redditmedia.com"),
    "snapchat": ("snapchat.com",),
    "pinterest": ("pinterest.com", "pin.it"),
    "telegram": ("t.me", "telegram.me", "telegram.org"),
    "threads": ("threads.net",),
    "discord": ("discord.com", "discordapp.com"),
    "tiktok": ("tiktok.com",),
    "moj": ("mojapp.in", "moj.in"),
    "josh": ("myjosh.in", "joshapp.com"),
    "sharechat": ("sharechat.com",),
    "quora": ("quora.com",),
    "shaadi": ("shaadi.com",),
    "bluesky": ("bsky.app", "bsky.social"),
    "nextdoor": ("nextdoor.com",),
    "twitch": ("twitch.tv",),
    "truth": ("truthsocial.com",),
}


def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for platform, domains in UNIVERSAL_PLATFORM_PATTERNS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return platform
    return "generic"


def is_downloadable_url(url: str) -> bool:
    try:
        parsed = urlparse((url or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def safe_filename(value: str, fallback: str = "social_media") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value or "")
    value = re.sub(r"\s+", " ", value).strip().strip(".")
    return value[:180] or fallback


def platform_username_from_url(url: str, platform: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if platform == "x" and len(parts) >= 2 and parts[1] == "status":
        return parts[0]
    if platform == "youtube":
        if parts and parts[0].startswith("@"):
            return parts[0][1:]
        if parts and parts[0] in {"watch", "shorts", "live", "embed"}:
            return "youtube"
    if platform in {"instagram", "tiktok", "threads", "bluesky", "pinterest"} and parts:
        if parts[0] not in {"p", "reel", "reels", "pin", "video", "post", "tv"}:
            return parts[0].lstrip("@")
    if platform in {
        "facebook", "linkedin", "reddit", "telegram", "twitch",
        "truth", "sharechat",
    } and parts:
        return parts[0].lstrip("@")
    if platform == "generic" and parts:
        return safe_filename(parts[0], "unknown")[:40]
    return "unknown"


def _tools_dir() -> str:
    """Prefer the snapshotter's TOOLS_DIR when already configured."""
    return globals().get("TOOLS_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".akt_tools"
    )


def _sanitize_header_value(value) -> str:
    if value is None:
        return ""
    value = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value).strip()


def _cookie_header(cookies) -> str:
    if not cookies:
        return ""
    pairs = []
    seen = set()
    for c in cookies:
        try:
            name = _sanitize_header_value(c.get("name", ""))
            value = _sanitize_header_value(c.get("value", ""))
            if not name or name in seen:
                continue
            seen.add(name)
            pairs.append(f"{name}={value}")
        except Exception:
            continue
    return "; ".join(pairs)


def _media_headers(referer: str = "", cookies=None) -> str:
    lines = [
        f"User-Agent: {S24_CHROME_UA}",
        "Accept: */*",
        "Accept-Language: en-US,en;q=0.9",
    ]
    if referer:
        referer = _sanitize_header_value(referer)
        parsed = urlparse(referer)
        lines.append(f"Referer: {referer}")
        if parsed.scheme and parsed.netloc:
            lines.append(f"Origin: {parsed.scheme}://{parsed.netloc}")
    cookie = _cookie_header(cookies)
    if cookie:
        lines.append(f"Cookie: {cookie}")
    return "\r\n".join(lines) + "\r\n"


def _netscape_cookie_line(c) -> str:
    domain = _sanitize_header_value(c.get("domain", "")).strip()
    name = _sanitize_header_value(c.get("name", "")).strip()
    value = _sanitize_header_value(c.get("value", ""))
    path = _sanitize_header_value(c.get("path", "/")) or "/"
    if not domain or not name:
        return ""
    include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
    secure = "TRUE" if c.get("secure") else "FALSE"
    try:
        expires = int(float(c.get("expires", 0) or 0))
        if expires < 0:
            expires = 0
    except Exception:
        expires = 0
    return "\t".join([
        domain, include_subdomains, path, secure, str(expires), name, value,
    ])


def write_temp_netscape_cookies(cookies) -> Optional[str]:
    """Write a Netscape cookie file with real newlines (not literal \\n)."""
    if not cookies:
        return None
    fd, path = tempfile.mkstemp(prefix="akt_social_", suffix=".txt")
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            try:
                line = _netscape_cookie_line(c)
                if line:
                    f.write(line + "\n")
            except Exception:
                pass
    return path


def _cookie_to_playwright(c):
    domain = c.domain or ""
    if not domain:
        return None
    out = {
        "name": c.name,
        "value": c.value,
        "domain": domain,
        "path": c.path or "/",
        "secure": bool(c.secure),
        "httpOnly": bool(getattr(c, "rest", {}).get("HttpOnly", False)),
        "sameSite": "Lax",
    }
    try:
        exp = int(c.expires)
        if exp > 0:
            out["expires"] = exp
    except Exception:
        pass
    return out


def get_browser_cookies_for_domain(domain: str):
    try:
        import browser_cookie3
    except Exception:
        return []

    domain = (domain or "").lower().lstrip(".")
    browser_funcs = [
        ("Firefox", browser_cookie3.firefox),
        ("Brave", browser_cookie3.brave),
        ("Chrome", browser_cookie3.chrome),
        ("Edge", browser_cookie3.edge),
    ]
    for name, func in browser_funcs:
        try:
            jar = func(domain_name=domain)
            cookies = []
            for c in jar:
                pc = _cookie_to_playwright(c)
                if pc:
                    cookies.append(pc)
            if cookies:
                print(f"[+] Reused {len(cookies)} {name} cookie(s) for {domain}.")
                return cookies
        except Exception:
            continue
    return []


def find_js_runtime():
    tools = _tools_dir()
    candidates = []

    if os.name == "nt":
        candidates.append(("deno", os.path.join(tools, "deno", "deno.exe")))
    else:
        candidates.append(("deno", os.path.join(tools, "deno", "deno")))

    for name in ("deno", "node", "bun"):
        exe = shutil.which(name)
        if exe:
            candidates.append((name, exe))

    if os.name == "nt":
        candidates.extend([
            ("node", r"C:\Program Files\nodejs\node.exe"),
            ("node", r"C:\Program Files (x86)\nodejs\node.exe"),
        ])

    for runtime, path in candidates:
        if path and os.path.isfile(path):
            return runtime, path
    return None, None


def ensure_deno_runtime():
    runtime, path = find_js_runtime()
    if runtime:
        return runtime, path

    deno_dir = os.path.join(_tools_dir(), "deno")
    os.makedirs(deno_dir, exist_ok=True)

    if os.name == "nt":
        deno_exe = os.path.join(deno_dir, "deno.exe")
        asset = "deno-x86_64-pc-windows-msvc.zip"
        expected = "deno.exe"
    else:
        deno_exe = os.path.join(deno_dir, "deno")
        machine = os.uname().machine.lower() if hasattr(os, "uname") else "x86_64"
        if "aarch64" in machine or "arm64" in machine:
            asset = "deno-aarch64-unknown-linux-gnu.zip"
        else:
            asset = "deno-x86_64-unknown-linux-gnu.zip"
        expected = "deno"

    if os.path.isfile(deno_exe):
        return "deno", deno_exe

    url = f"https://github.com/denoland/deno/releases/latest/download/{asset}"
    temp_zip = os.path.join(tempfile.gettempdir(), "akt_deno_latest.zip")
    temp_extract = os.path.join(tempfile.gettempdir(), "akt_deno_extract")

    print("[+] No supported yt-dlp JavaScript runtime found.")
    print("[+] Downloading official stable Deno runtime for video extraction...")

    try:
        if os.path.exists(temp_zip):
            os.remove(temp_zip)
        if os.path.isdir(temp_extract):
            shutil.rmtree(temp_extract, ignore_errors=True)

        urllib.request.urlretrieve(url, temp_zip)
        with zipfile.ZipFile(temp_zip, "r") as zf:
            zf.extractall(temp_extract)

        extracted = os.path.join(temp_extract, expected)
        if not os.path.isfile(extracted):
            for root, _, files in os.walk(temp_extract):
                if expected in files:
                    extracted = os.path.join(root, expected)
                    break

        if not os.path.isfile(extracted):
            raise RuntimeError("Deno executable was not found in the official archive.")

        shutil.copy2(extracted, deno_exe)
        try:
            os.chmod(deno_exe, 0o755)
        except Exception:
            pass
        print(f"[OK] Deno installed: {deno_exe}")
        return "deno", deno_exe
    except Exception as e:
        print(f"[!] Could not install Deno automatically: {e}")
        return None, None
    finally:
        for p in (temp_zip, temp_extract):
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass


def get_ffmpeg_executable():
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        return exe if os.path.isfile(exe) else None
    except Exception:
        pass
    return shutil.which("ffmpeg")


def _valid_video_file(path: str) -> bool:
    try:
        return os.path.isfile(path) and os.path.getsize(path) >= 32 * 1024
    except Exception:
        return False


def _video_download_temp_root() -> str:
    """Scratch files live under AKT Tools, never in Social Media Videos/."""
    root = os.path.join(_tools_dir(), "VideoDownloadTemp")
    os.makedirs(root, exist_ok=True)
    return root


def _robust_rmtree(path: str, attempts: int = 6, delay: float = 0.5) -> bool:
    import stat
    import time

    if not os.path.isdir(path):
        return True

    def _on_error(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    for _ in range(attempts):
        try:
            shutil.rmtree(path, onerror=_on_error)
            if not os.path.isdir(path):
                return True
        except Exception:
            pass
        time.sleep(delay)
    return not os.path.isdir(path)


def cleanup_stale_video_temp_dirs(max_age_hours: float = 2.0) -> None:
    root = _video_download_temp_root()
    try:
        now = datetime.now().timestamp()
        for entry in os.listdir(root):
            full = os.path.join(root, entry)
            try:
                if not os.path.isdir(full):
                    continue
                age_hours = (now - os.path.getmtime(full)) / 3600
                if age_hours >= max_age_hours:
                    _robust_rmtree(full)
            except Exception:
                continue
    except Exception:
        pass


def _find_video_files(directory: str) -> List[Path]:
    if not os.path.isdir(directory):
        return []
    files = []
    for p in Path(directory).rglob("*"):
        try:
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS and _valid_video_file(str(p)):
                files.append(p)
        except Exception:
            pass
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _rename_downloaded_video(
    path: str,
    output_dir: str,
    platform: str,
    username: str,
    timestamp_str: str,
    index: int = 1,
) -> str:
    ext = Path(path).suffix.lower()
    if ext not in VIDEO_EXTS:
        return path

    domain = PLATFORM_DOMAIN_MAP.get(platform, f"{platform}.com")
    user = safe_filename(username or "unknown", "unknown")
    suffix = "" if index == 1 else str(index)
    target = os.path.join(
        output_dir,
        f"{domain}_@{user}_{timestamp_str}_Video{suffix}.mp4",
    )

    if ext != ".mp4":
        ffmpeg = get_ffmpeg_executable()
        if ffmpeg:
            temp_mp4 = target + ".tmp.mp4"
            remuxed = False
            for args in (
                ["-c", "copy", "-movflags", "+faststart"],
                [
                    "-c:v", "libx264", "-preset", "veryfast",
                    "-c:a", "aac", "-movflags", "+faststart",
                ],
            ):
                try:
                    subprocess.run(
                        [ffmpeg, "-y", "-i", path, *args, temp_mp4],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                        timeout=600,
                    )
                    if _valid_video_file(temp_mp4):
                        os.replace(temp_mp4, target)
                        if os.path.abspath(path) != os.path.abspath(target):
                            try:
                                os.remove(path)
                            except Exception:
                                pass
                        remuxed = True
                        break
                except Exception:
                    try:
                        if os.path.exists(temp_mp4):
                            os.remove(temp_mp4)
                    except Exception:
                        pass
            if remuxed:
                return target
            # Fall through: rename original container if remux is impossible.

    if os.path.abspath(path) != os.path.abspath(target):
        try:
            if os.path.exists(target):
                os.remove(target)
            os.replace(path, target)
        except Exception:
            return path
    return target


def _ytdlp_format_selector() -> str:
    """
    Quality rule (resolution FIRST, container second):
      1) Best video <= 1080p + best audio (any container; remux to mp4 later).
      2) Else best single-file stream <= 1080p.
      3) Else same ladder at 720p.
      4) Else best available.

    IMPORTANT: do NOT prefer [ext=mp4] before resolution — that used to lock
    onto a 360p progressive MP4 while a 1080p webm/avc adaptive stream existed.
    """
    return (
        "bestvideo*[height<=1080]+bestaudio/"
        "bestvideo[height<=1080]+bestaudio/"
        "best[height<=1080]/"
        "bestvideo*[height<=720]+bestaudio/"
        "best[height<=720]/"
        "bestvideo*+bestaudio/best"
    )


def _ytdlp_format_sort() -> list:
    """Force yt-dlp to rank by resolution near 1080p, not by codec/container quirks."""
    return ["res:1080", "res", "br", "fps", "hdr:sdr", "codec:h264:aac", "size", "proto"]


# ---------------------------------------------------------------------------
# YouTube player-client ladder — COOKIE / BROWSER INDEPENDENT.
#
# Clients that typically expose 1080p adaptive formats are tried first.
# Android-only clients often only advertise 360p/720p progressive streams,
# which previously caused 640x360 downloads even when 1080p existed.
# ---------------------------------------------------------------------------
YOUTUBE_PLAYER_CLIENT_LADDER = [
    "web_embedded,mweb",
    "mweb,android",
    "default,-tv,-tv_downgraded",
    "tv_embedded",
    "android,ios",
    "android_vr,ios",
    "android_creator",
    "mediaconnect",
]


def _youtube_extractor_args_dict(player_client: str) -> dict:
    clients = [c.strip() for c in player_client.split(",") if c.strip()]
    return {"youtube": {"player_client": clients}}


def _base_ytdlp_cmd(
    outtmpl: str,
    player_client: Optional[str] = None,
) -> list:
    """Build a yt-dlp CLI command with NO cookies / NO browser cookie flags."""
    ffmpeg = get_ffmpeg_executable()
    runtime, runtime_path = ensure_deno_runtime()

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "--retries", "10",
        "--fragment-retries", "10",
        "--file-access-retries", "5",
        "--extractor-retries", "5",
        "--retry-sleep", "1",
        "--sleep-requests", "1",
        "--concurrent-fragments", "4",
        "--newline",
        "--no-mtime",
        "--ignore-errors",
        "--ignore-no-formats-error",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--output", outtmpl,
        "--format", _ytdlp_format_selector(),
        "--format-sort", ",".join(_ytdlp_format_sort()),
        "--format-sort-force",
        "--add-header", f"User-Agent: {S24_CHROME_UA}",
        "--add-header", "Accept-Language: en-US,en;q=0.9",
        "--remote-components", "ejs:github",
    ]
    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]
    if runtime and runtime_path:
        cmd += ["--js-runtimes", f"{runtime}:{runtime_path}"]
    if player_client:
        cmd += ["--extractor-args", f"youtube:player_client={player_client}"]
    return cmd


def _collect_renamed(
    temp_dir: str,
    output_dir: str,
    platform: str,
    username: str,
    timestamp_str: str,
    before: Optional[Iterable[str]] = None,
) -> list:
    before = set(before or [])
    candidates = [p for p in _find_video_files(temp_dir) if str(p) not in before]
    results = []
    for idx, p in enumerate(candidates, start=1):
        results.append(
            _rename_downloaded_video(
                str(p), output_dir, platform, username, timestamp_str, idx
            )
        )
    return results


def _run_yt_dlp_cli(
    url: str,
    output_dir: str,
    platform: str,
    username: str,
    timestamp_str: str,
    temp_dir: str,
) -> list:
    os.makedirs(temp_dir, exist_ok=True)
    client_ladder = YOUTUBE_PLAYER_CLIENT_LADDER if platform == "youtube" else [None]

    for player_client in client_ladder:
        try:
            before = set(str(p) for p in _find_video_files(temp_dir))
            outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
            cmd = _base_ytdlp_cmd(outtmpl, player_client=player_client) + [url]

            label = f" (player_client={player_client})" if player_client else ""
            print(f"[+] VIDEO ENGINE B: yt-dlp CLI{label} [no cookies]")
            r = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                timeout=1800,
                cwd=temp_dir,
            )
            out = r.stdout or ""

            if r.returncode != 0 and "unrecognized argument" in out.lower():
                print("[i] Installed yt-dlp is older than expected; retrying without newer flags...")
                stripped_cmd = []
                skip_next = False
                for token in cmd:
                    if skip_next:
                        skip_next = False
                        continue
                    if token in ("--remote-components", "--js-runtimes", "--extractor-args"):
                        skip_next = True
                        continue
                    stripped_cmd.append(token)
                r = subprocess.run(
                    stripped_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    errors="replace",
                    timeout=1800,
                    cwd=temp_dir,
                )
                out = r.stdout or ""

            if r.returncode != 0:
                lines = [x.strip() for x in out.splitlines() if x.strip()]
                for line in lines[-8:]:
                    print(f"    {line}")

            results = _collect_renamed(
                temp_dir, output_dir, platform, username, timestamp_str, before
            )
            if results:
                return results
        except subprocess.TimeoutExpired:
            print("[!] yt-dlp CLI timed out; moving to the next fallback.")
        except Exception as e:
            print(f"[i] yt-dlp CLI fallback failed: {type(e).__name__}: {e}")

    return []


def _run_gallery_dl_get_urls(url: str) -> list:
    """Extract direct media URLs without cookies."""
    try:
        cmd = [sys.executable, "-m", "gallery_dl", "-g", "--no-color", url]
        print("[+] gallery-dl fallback: extracting direct media URLs (no cookies)...")
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=90,
        )
        urls = []
        for line in (r.stdout or "").splitlines():
            candidate = line.strip()
            if not re.match(r"^https?://", candidate, re.I):
                continue
            low = candidate.lower().split("?", 1)[0]
            if any(x in low for x in (".mp4", ".m4v", ".mov", ".webm", ".m3u8", ".mpd")) or (
                "video" in low or "media" in low
            ):
                urls.append(candidate)
        return list(dict.fromkeys(urls))
    except Exception as e:
        print(f"[i] gallery-dl fallback unavailable/failed: {e}")
        return []


def _download_direct_media_url(
    media_url: str,
    output_dir: str,
    base_name: str,
    referer: str = "",
) -> list:
    """Download a direct media URL with UA/Referer only — no cookies."""
    if not media_url or not re.match(r"^https?://", media_url, re.I):
        return []

    os.makedirs(output_dir, exist_ok=True)
    lower = media_url.lower().split("?", 1)[0]
    target = os.path.join(output_dir, base_name + "_Video.mp4")
    ffmpeg = get_ffmpeg_executable()
    headers_text = _media_headers(referer, cookies=None)

    try:
        if (".m3u8" in lower or ".mpd" in lower) and ffmpeg:
            cmd = [
                ffmpeg, "-y",
                "-headers", headers_text,
                "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
                "-i", media_url,
                "-c", "copy",
                "-movflags", "+faststart",
                target,
            ]
            r = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800
            )
            if r.returncode == 0 and _valid_video_file(target):
                return [target]

        if any(x in lower for x in (".mp4", ".m4v", ".mov", ".webm", ".mkv")):
            req_headers = {
                "User-Agent": _sanitize_header_value(S24_CHROME_UA),
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            }
            if referer:
                req_headers["Referer"] = _sanitize_header_value(referer)

            req = urllib.request.Request(media_url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=120) as response, open(target, "wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)

            if _valid_video_file(target):
                if not lower.endswith(".mp4") and ffmpeg:
                    normalized = target + ".normalized.mp4"
                    remuxed = False
                    for args in (
                        ["-c", "copy", "-movflags", "+faststart"],
                        [
                            "-c:v", "libx264", "-preset", "veryfast",
                            "-c:a", "aac", "-movflags", "+faststart",
                        ],
                    ):
                        try:
                            subprocess.run(
                                [ffmpeg, "-y", "-i", target, *args, normalized],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                timeout=600,
                                check=True,
                            )
                            if _valid_video_file(normalized):
                                os.replace(normalized, target)
                                remuxed = True
                                break
                        except Exception:
                            try:
                                if os.path.exists(normalized):
                                    os.remove(normalized)
                            except Exception:
                                pass
                    if not remuxed:
                        print("[i] Kept downloaded media without remux (ffmpeg remux failed).")
                return [target]
    except Exception as e:
        print(f"[i] Direct media fallback failed: {type(e).__name__}: {e}")
        try:
            if os.path.exists(target) and not _valid_video_file(target):
                os.remove(target)
        except Exception:
            pass
    return []


def _run_streamlink_fallback(
    media_url: str,
    output_dir: str,
    base_name: str,
    referer: str = "",
) -> list:
    """HLS/DASH via streamlink — UA/Referer only, no cookies."""
    try:
        if not re.match(r"^https?://", media_url, re.I):
            return []
        lower = media_url.lower()
        if ".m3u8" not in lower and ".mpd" not in lower:
            return []

        temp = Path(output_dir) / ".akt_streamlink_tmp.mp4"
        if temp.exists():
            temp.unlink()

        cmd = [
            sys.executable, "-m", "streamlink",
            "--force",
            "--output", str(temp),
            media_url,
            "best",
            "--http-header", f"User-Agent={S24_CHROME_UA}",
        ]
        if referer:
            cmd += ["--http-header", f"Referer={referer}"]

        print("[+] Streamlink fallback: attempting HLS/DASH stream (no cookies)...")
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=1800,
        )
        if r.returncode == 0 and _valid_video_file(str(temp)):
            target = Path(output_dir) / f"{base_name}_Video.mp4"
            if target.exists():
                target.unlink()
            temp.replace(target)
            return [str(target)]
        return []
    except Exception as e:
        print(f"[i] Streamlink fallback failed: {e}")
        return []


def _ytdlp_progress_hook(d: dict) -> None:
    try:
        if d.get("status") == "downloading":
            pct = (d.get("_percent_str") or "").strip()
            speed = (d.get("_speed_str") or "").strip()
            eta = (d.get("_eta_str") or "").strip()
            print(f"\r    ↳ {pct} at {speed}, ETA {eta}   ", end="", flush=True)
        elif d.get("status") == "finished":
            print("\r    ↳ 100% — merging/finalizing...          ")
    except Exception:
        pass


def run_yt_dlp_download(
    url: str,
    output_dir: str,
    platform: str,
    cookies=None,  # ignored — kept for call-site compatibility
    username: str = "unknown",
    timestamp_str: str = "",
) -> list:
    """
    Cookie/browser-independent multi-engine video ladder for any http(s) URL:
      A. yt-dlp Python API  (YouTube: player-client ladder, no cookies)
      B. yt-dlp CLI         (same ladder)
      C. gallery-dl → direct / streamlink
      D. yt-dlp URL extract → direct / streamlink

    Browser cookies and --cookies-from-browser are never used for downloads.
    """
    if not is_downloadable_url(url):
        print("[!] Not a downloadable http(s) URL.")
        return []

    # Explicitly ignore any cookies passed by callers.
    if cookies:
        print("[i] Ignoring browser cookies for video download (cookie-independent mode).")
    cookies = None

    os.makedirs(output_dir, exist_ok=True)
    platform = platform or detect_platform(url)
    username = username or platform_username_from_url(url, platform)

    temp_dir = os.path.join(
        _video_download_temp_root(),
        re.sub(r"[^A-Za-z0-9_-]+", "_", str(abs(hash(url + timestamp_str))))[:48],
    )
    os.makedirs(temp_dir, exist_ok=True)

    base_name = safe_filename(
        f"{PLATFORM_DOMAIN_MAP.get(platform, platform + '.com')}_@"
        f"{username or 'unknown'}_{timestamp_str}"
    )

    try:
        ffmpeg = get_ffmpeg_executable()
        runtime, runtime_path = ensure_deno_runtime()
        client_ladder = YOUTUBE_PLAYER_CLIENT_LADDER if platform == "youtube" else [None]

        # ---------------------------------------------------------------
        # 0) Direct media URL fast-path (no cookies, no browser)
        # ---------------------------------------------------------------
        url_path = (url or "").lower().split("?", 1)[0]
        if any(url_path.endswith(ext) for ext in (
            ".mp4", ".m4v", ".mov", ".webm", ".mkv", ".m3u8", ".mpd", ".ts"
        )):
            print("[+] VIDEO FAST-PATH: URL looks like direct media — downloading without cookies...")
            results = _download_direct_media_url(url, output_dir, base_name, referer=url)
            if results:
                return results
            results = _run_streamlink_fallback(url, output_dir, base_name, referer=url)
            if results:
                return results

        # ---------------------------------------------------------------
        # A) yt-dlp Python API — no cookiefile, no cookiesfrombrowser
        # ---------------------------------------------------------------
        for attempt_idx, player_client in enumerate(client_ladder, start=1):
            try:
                import yt_dlp

                outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
                ydl_opts = {
                    "outtmpl": outtmpl,
                    "format": _ytdlp_format_selector(),
                    "format_sort": _ytdlp_format_sort(),
                    "format_sort_force": True,
                    "merge_output_format": "mp4",
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                    "noprogress": False,
                    "progress_hooks": [_ytdlp_progress_hook],
                    "retries": 10,
                    "fragment_retries": 10,
                    "file_access_retries": 5,
                    "extractor_retries": 5,
                    "sleep_interval_requests": 1,
                    "continuedl": True,
                    "overwrites": True,
                    "windowsfilenames": True,
                    "concurrent_fragment_downloads": 4,
                    "http_chunk_size": 10 * 1024 * 1024,
                    "http_headers": {
                        "User-Agent": _sanitize_header_value(S24_CHROME_UA),
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    "remote_components": ["ejs:github"],
                }
                if ffmpeg:
                    ydl_opts["ffmpeg_location"] = ffmpeg
                if runtime and runtime_path:
                    ydl_opts["js_runtimes"] = {runtime: {"path": runtime_path}}
                if player_client:
                    ydl_opts["extractor_args"] = _youtube_extractor_args_dict(player_client)

                label = f" (player_client={player_client})" if player_client else ""
                print(
                    f"[+] VIDEO ENGINE A: yt-dlp API — {platform} "
                    f"({urlparse(url).hostname or 'site'}){label} [no cookies]"
                )
                if attempt_idx == 1:
                    print("[+] Quality ladder: 1080p → 720p → best available")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                infos = []
                if isinstance(info, dict) and info.get("entries"):
                    infos = [x for x in info["entries"] if x]
                elif info:
                    infos = [info]

                results = []
                for idx, item in enumerate(infos, start=1):
                    candidate = item.get("filepath") or item.get("_filename")
                    if not candidate:
                        try:
                            candidate = ydl.prepare_filename(item)
                        except Exception:
                            candidate = None

                    candidates = []
                    if candidate:
                        candidates.append(candidate)
                        stem = os.path.splitext(candidate)[0]
                        for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi"):
                            candidates.append(stem + ext)

                    actual = next((p for p in candidates if _valid_video_file(p)), None)
                    if actual:
                        actual_user = (
                            username if username and username != "unknown"
                            else item.get("uploader") or item.get("channel") or "unknown"
                        )
                        results.append(
                            _rename_downloaded_video(
                                actual, output_dir, platform,
                                actual_user, timestamp_str, idx,
                            )
                        )

                if results:
                    return results

                scanned = _collect_renamed(
                    temp_dir, output_dir, platform, username, timestamp_str
                )
                if scanned:
                    return scanned
            except Exception as e:
                client_note = f" (player_client={player_client})" if player_client else ""
                print(f"[i] VIDEO ENGINE A failed{client_note}: {type(e).__name__}: {e}")
                continue

        # ---------------------------------------------------------------
        # B) yt-dlp CLI — no cookies
        # ---------------------------------------------------------------
        results = _run_yt_dlp_cli(
            url, output_dir, platform, username, timestamp_str, temp_dir,
        )
        if results:
            return results

        # ---------------------------------------------------------------
        # C) gallery-dl → direct / streamlink (no cookies)
        # ---------------------------------------------------------------
        for media_url in _run_gallery_dl_get_urls(url):
            results = _download_direct_media_url(
                media_url, output_dir, base_name, referer=url
            )
            if results:
                return results
            results = _run_streamlink_fallback(
                media_url, output_dir, base_name, referer=url
            )
            if results:
                return results

        # ---------------------------------------------------------------
        # D) Extract formats without downloading, then fetch media URLs
        # ---------------------------------------------------------------
        try:
            import yt_dlp

            extract_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
                "remote_components": ["ejs:github"],
                "http_headers": {"User-Agent": S24_CHROME_UA},
            }
            if runtime and runtime_path:
                extract_opts["js_runtimes"] = {runtime: {"path": runtime_path}}
            if platform == "youtube":
                extract_opts["extractor_args"] = _youtube_extractor_args_dict(
                    YOUTUBE_PLAYER_CLIENT_LADDER[0]
                )

            with yt_dlp.YoutubeDL(extract_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            formats = []
            if isinstance(info, dict):
                formats.extend(info.get("formats") or [])
                if info.get("url"):
                    formats.append(info)

            formats.sort(
                key=lambda f: (
                    min(int(f.get("height") or 0), 1080),
                    int(f.get("tbr") or 0),
                ),
                reverse=True,
            )

            seen = set()
            for fmt in formats:
                media_url = fmt.get("url")
                if not media_url or media_url in seen:
                    continue
                seen.add(media_url)

                results = _download_direct_media_url(
                    media_url, output_dir, base_name, referer=url
                )
                if results:
                    return results
                results = _run_streamlink_fallback(
                    media_url, output_dir, base_name, referer=url
                )
                if results:
                    return results
        except Exception as e:
            print(f"[i] Direct yt-dlp URL extraction failed: {type(e).__name__}: {e}")

        return []
    finally:
        if not _robust_rmtree(temp_dir):
            print(
                f"[!] Could not fully remove temp folder (a file may still be "
                f"locked): {temp_dir}"
            )
            print("    It will be cleaned up automatically on the next run.")


def ensure_video_dependencies(site_packages: str) -> None:
    """
    Install/refresh the yt-dlp stack into the AKT site-packages target.
    Always-upgrade packages are re-checked at most every 12 hours.
    """
    always_upgrade = {
        "yt_dlp": "yt-dlp",
        "yt_dlp_ejs": "yt-dlp-ejs",
    }
    install_if_missing = {
        "imageio_ffmpeg": "imageio-ffmpeg",
        "gallery_dl": "gallery-dl",
        "streamlink": "streamlink",
    }

    UPDATE_CHECK_INTERVAL_HOURS = 12
    marker_path = os.path.join(site_packages, ".akt_last_ytdlp_check")
    should_check = True
    try:
        if os.path.isfile(marker_path):
            age_hours = (datetime.now().timestamp() - os.path.getmtime(marker_path)) / 3600
            if age_hours < UPDATE_CHECK_INTERVAL_HOURS:
                should_check = False
    except Exception:
        pass

    if should_check:
        print("[+] Checking for yt-dlp / yt-dlp-ejs updates (keeps every site working)...")
        try:
            subprocess.check_call(
                [
                    sys.executable, "-m", "pip", "install", "--upgrade",
                    "--target", site_packages,
                    "--disable-pip-version-check", "--no-input", "--quiet",
                ] + list(always_upgrade.values()),
                stdout=subprocess.DEVNULL,
            )
            print("[OK] yt-dlp extractor engine is up to date.")
            try:
                os.makedirs(site_packages, exist_ok=True)
                with open(marker_path, "w") as f:
                    f.write(str(datetime.now().timestamp()))
            except Exception:
                pass
        except Exception as e:
            print(f"[!] Could not check/upgrade yt-dlp automatically: {e}")
            print("[!] If downloads keep failing, manually run:")
            print(f"    \"{sys.executable}\" -m pip install --upgrade yt-dlp yt-dlp-ejs")
    else:
        print(
            f"[OK] yt-dlp was already checked within the last "
            f"{UPDATE_CHECK_INTERVAL_HOURS}h — skipping network check."
        )

    missing = []
    for module, pip_name in install_if_missing.items():
        if not os.path.isdir(os.path.join(site_packages, module)):
            try:
                __import__(module)
            except Exception:
                missing.append(pip_name)

    if missing:
        print(f"[-] Installing video libraries {missing}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", "--target", site_packages]
                + missing
            )
        except Exception as e:
            print(f"[!] Could not install {missing}: {e}")

    if site_packages not in sys.path:
        sys.path.insert(0, site_packages)
    import importlib
    importlib.invalidate_caches()

    try:
        import yt_dlp
        try:
            from yt_dlp.version import __version__ as ytdlp_version
        except Exception:
            ytdlp_version = getattr(yt_dlp, "__version__", "unknown")
        print(f"[OK] Using yt-dlp version {ytdlp_version}")
    except Exception as e:
        print(f"[!] yt-dlp still not importable after install attempt: {e}")


# ============================================================================
# SNAPSHOTTER CONTINUES
# ============================================================================



IG_SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
# ============================================================================
# SOCIAL MEDIA SNAPSHOTTER URL PICKER
# ============================================================================
URL_PICKER_FILE = Path(SCRIPT_DIR) / "Social Media SnapShottter URL Picker.txt"
DONE_URL_LOG_FILE = Path(SCRIPT_DIR) / "Completed Social Media SnapShottter URL.txt"
ERROR_LOG_FILE = Path(SCRIPT_DIR) / "Error Social Media SnapShottter URL.txt"


def ensure_url_picker_file() -> Path:
    try:
        if not URL_PICKER_FILE.exists():
            URL_PICKER_FILE.write_text("", encoding="utf-8")
            print(f"[+] Created URL picker: {URL_PICKER_FILE.name}")
        else:
            print(f"[+] URL picker present: {URL_PICKER_FILE.name}")
    except Exception as e:
        print(f"[!] Could not ensure URL picker file: {e}")
    return URL_PICKER_FILE


def load_urls_from_picker():
    urls, seen = [], set()
    try:
        if not URL_PICKER_FILE.exists():
            return []
        text = URL_PICKER_FILE.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"[!] load_urls_from_picker: {e}")
        return []

    for m in re.finditer(r"https?://[^\s<>\"'\])\}]+", text, re.IGNORECASE):
        u = m.group(0).rstrip(".,;:)")
        if not u or u.lower() in seen:
            continue
        seen.add(u.lower())
        urls.append(u)
    return urls


def remove_url_from_picker(url: str) -> bool:
    if not url or not URL_PICKER_FILE.exists():
        return False
    try:
        text = URL_PICKER_FILE.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        new_lines, removed = [], False
        url_norm = url.strip()

        for line in lines:
            if not removed and url_norm in line:
                stripped = line.strip()
                if stripped == url_norm or stripped.rstrip(".,;:)") == url_norm:
                    removed = True
                    continue
                new_line = line.replace(url_norm, "", 1)
                if new_line.strip():
                    new_lines.append(new_line)
                removed = True
            else:
                new_lines.append(line)

        if removed:
            URL_PICKER_FILE.write_text("".join(new_lines), encoding="utf-8")
            remaining = load_urls_from_picker()
            print(
                f"[+] Completed URL removed from {URL_PICKER_FILE.name} "
                f"(remaining: {len(remaining)} URL(s))"
            )
            return True
    except Exception as e:
        print(f"[!] Could not remove URL from picker: {e}")
    return False


def record_completed_url(url: str) -> None:
    """Record a successfully completed URL at the top with newest entry as #1."""
    if not url:
        return

    try:
        existing_urls = []
        if DONE_URL_LOG_FILE.exists():
            text = DONE_URL_LOG_FILE.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                m = re.search(r"https?://[^\s<>\"'\])\}]+", line, re.IGNORECASE)
                if m:
                    saved_url = m.group(0).rstrip(".,;:)")
                    if saved_url and saved_url.lower() not in {u.lower() for u in existing_urls}:
                        existing_urls.append(saved_url)

        ordered_urls = [url.strip()]
        ordered_urls.extend(
            u for u in existing_urls if u.strip().lower() != url.strip().lower()
        )

        # Keep newest URL at the TOP, but assign serial numbers in chronological
        # order: the oldest completed URL is always #1, and the newest is the
        # highest serial number.
        total = len(ordered_urls)
        DONE_URL_LOG_FILE.write_text(
            "\n".join(
                f"{total - i}. {u}" for i, u in enumerate(ordered_urls)
            ) + "\n",
            encoding="utf-8",
        )
        print(f"[+] Completed URL recorded: {DONE_URL_LOG_FILE.name}")
    except Exception as e:
        print(f"[!] Could not update completed URL log: {e}")


def record_error(url: str, error: object, context: str = "") -> None:
    """Append a failed URL/error to the error log. This file is created only on failure."""
    try:
        from traceback import format_exc

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_text = str(error)
        trace = format_exc()
        if trace.strip() == "NoneType: None":
            trace = ""

        with ERROR_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"Time: {timestamp}\n")
            f.write(f"URL: {url or '[unknown]'}\n")
            if context:
                f.write(f"Context: {context}\n")
            f.write(f"Error: {error_text}\n")
            if trace.strip():
                f.write("Traceback:\n")
                f.write(trace.rstrip() + "\n")
            f.write("\n")
        print(f"[+] Error recorded: {ERROR_LOG_FILE.name}")
    except Exception as log_error:
        print(f"[!] Could not write error log: {log_error}")


def get_url_with_timeout():
    """
    Picker is checked first. This fallback is intentionally an immediate
    manual URL prompt — there is NO timeout / auto-skip logic.
    """
    print()
    print(f"[+] No URLs in {URL_PICKER_FILE.name}")
    print("    Enter any video / social-media URL (http/https):")

    try:
        raw = input("    URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if not raw:
        return None

    m = re.search(r"https?://[^\s<>\"\'\])\}]+", raw.strip(), re.IGNORECASE)
    if not m:
        print("[!] No valid URL found.")
        return None

    return m.group(0).rstrip(".,;:)")


# ============================================================================
# EMBEDDED TIMESTAMP FONT — Courier Bold Prime
# Stored directly in this Python file as Base64.
# No external .ttf file or Windows font installation is required.
# ============================================================================
TIMESTAMP_FONT_FAMILY = "Courier Bold Prime"
TIMESTAMP_FONT_DATA_URI = "data:font/ttf;base64,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AAAACgG6AZgBmAFUATQA+ACwAGYAOAAWAAEAAAABAAgAAgAOAAQAawB5AGsAeQABAAQAJAAyAEQAUgAEAAAAAQAIAAEAHgACABQACgABAAQBaAACAHYAAQAEAVkAAgB2AAEAAgAvAE8AAQAAAAEACAACACIADgGKAYgBjAGCAYYBhwGFAYMBiQGOAY0BjwGLAYEAAQAOAEMAaQBuAHMAdwEqASsBLAEtAS4BLwEwATEBgAAGAAAAAgAkAAoAAwABADQAAQASAAAAAQAAAAkAAQACADIAUgADAAEAGgABABIAAAABAAAACQABAAIAJABEAAIAAQATABwAAAAEAAAAAQAIAAEALAACABYACgABAAQAfAADABIAFwACAA4ABgB6AAMAEgAXAHsAAwASABUAAQACABQAFgABAAAAAQAIAAIADgAEAHgAcQByAXMAAgABABQAFwAAAAYAAAACACQACgADAAAAAgAUAC4AAQAUAAEAAAAIAAEAAQAvAAMAAAACABoAFAABABoAAQAAAAgAAQABAHYAAQABAE8AAQAAAAEACAACAA4ABAEnASgBEQESAAEABAENAQ4BVAFVAAEAAAABAAgAAgA6ABoAeABxAHIBcwBrAHkBigBrAHkBiAGMAYIBhgEnASgBhwGFAYMBiQGOAY0BjwGLAREBEgGBAAEAGgAUABUAFgAXACQAMgBDAEQAUgBpAG4AcwB3AQ0BDgEqASsBLAEtAS4BLwEwATEBVAFVAYAAAAAAAA0AogADAAEECQAAAMgC3gADAAEECQABABoCxAADAAEECQACAAgCvAADAAEECQADADgChAADAAEECQAEACQCYAADAAEECQAFABoCRgADAAEECQAGACICJAADAAEECQAIACQCAAADAAEECQAJAEoBtgADAAEECQALADYBgAADAAEECQAMACwBVAADAAEECQANASAANAADAAEECQAOADQAAABoAHQAdABwADoALwAvAHMAYwByAGkAcAB0AHMALgBzAGkAbAAuAG8AcgBnAC8ATwBGAEwAVABoAGkAcwAgAEYAbwBuAHQAIABTAG8AZgB0AHcAYQByAGUAIABpAHMAIABsAGkAYwBlAG4AcwBlAGQAIAB1AG4AZABlAHIAIAB0AGgAZQAgAFMASQBMACAATwBwAGUAbgAgAEYAbwBuAHQAIABMAGkAYwBlAG4AcwBlACwAIABWAGUAcgBzAGkAbwBuACAAMQAuADEALgAgAFQAaABpAHMAIABsAGkAYwBlAG4AcwBlACAAaQBzACAAYQB2AGEAaQBsAGEAYgBsAGUAIAB3AGkAdABoACAAYQAgAEYAQQBRACAAYQB0ADoAIABoAHQAdABwADoALwAvAHMAYwByAGkAcAB0AHMALgBzAGkAbAAuAG8AcgBnAC8ATwBGAEwAaAB0AHQAcAA6AC8ALwBiAGEAcwBpAGMAcgBlAGMAaQBwAGUALgBjAG8AbQBoAHQAdABwADoALwAvAHEAdQBvAHQAZQB1AG4AcQB1AG8AdABlAGEAcABwAHMALgBjAG8AbQBBAGwAYQBuACAARABhAGcAdQBlAC0ARwByAGUAZQBuAGUALAAgAFEAdQBvAHQAZQAtAFUAbgBxAHUAbwB0AGUAIABBAHAAcABzAFEAdQBvAHQAZQAtAFUAbgBxAHUAbwB0AGUAIABBAHAAcABzAEMAbwB1AHIAaQBlAHIAUAByAGkAbQBlAC0AQgBvAGwAZABWAGUAcgBzAGkAbwBuACAAMwAuADAAMQA4AEMAbwB1AHIAaQBlAHIAIABQAHIAaQBtAGUAIABCAG8AbABkADMALgAwADEAOAA7AFEAVQBRAEEAOwBDAG8AdQByAGkAZQByAFAAcgBpAG0AZQAtAEIAbwBsAGQAQgBvAGwAZABDAG8AdQByAGkAZQByACAAUAByAGkAbQBlAEMAbwBwAHkAcgBpAGcAaAB0ACAAMgAwADEANQAgAFQAaABlACAAQwBvAHUAcgBpAGUAcgAgAFAAcgBpAG0AZQAgAFAAcgBvAGoAZQBjAHQAIABBAHUAdABoAG8AcgBzACAAKABoAHQAdABwAHMAOgAvAC8AZwBpAHQAaAB1AGIALgBjAG8AbQAvAHEAdQBvAHQAZQB1AG4AcQB1AG8AdABlAGEAcABwAHMALwBDAG8AdQByAGkAZQByAFAAcgBpAG0AZQApAC4EzACVBMwAAATMAAAEzAAABMwByATMALEEzAAyBMwApATMADIEzABrBMwBvwTMAQEEzAEtBMwAvQTMAKoEzAFhBMwAqgTMAcEEzACfBMwAhQTMALoEzACeBMwAtwTMAHgEzACwBMwAoATMALwEzACrBMwAlgTMAcEEzAF1BMwAeATMAKoEzACSBMwA0ATMACEEzP/2BMwARgTMAGcEzAA8BMwAPATMADwEzABJBMwAMgTMAKoEzABjBMwAMgTMADwEzAAKBMwAMgTMAD8EzAA8BMwAPwTMADwEzACVBMwAYgTMADIEzP/2BMz/7ATMAB4EzAAoBMwAigTMASIEzACfBMwBLgTMAMEEzP/aBMwBFATMAG4EzAAbBMwAfwTMAGEEzACDBMwApwTMAGEEzAAvBMwApwTMAJ8EzAA5BMwAnQTM//IEzAA5BMwAbwTMACUEzABhBMwAfwTMAKQEzABhBMwAMgTMACgEzP/sBMwARgTMACgEzACKBMwApQTMAekEzADmBMwAgQTMAcgEzAB/BMwAlgTMAGYEzAAoBMwB6QTMAJ8EzAENBMwAHATMAOUEzAB4BMwAfQTMARgEzADcBMwAqgTMARcEzAEYBMwBmATMALgEzABlBMwBwQTMAV8EzAElBMwA4ATM/+wEzP/sBMz/9gTMAOYEzP/2BMz/9gTM//YEzP/2BMz/9gTM//YEzP/iBMwAZwTMADwEzAA8BMwAPATMADwEzACqBMwAqgTMAKoEzACqBMwAKATMADIEzAA/BMwAPwTMAD8EzAA/BMwAPwTMANYEzAA/BMwAMgTMADIEzAAyBMwAMgTMACgEzAB4BMwAFgTMAG4EzABuBMwAbgTMAG4EzABuBMwAbgTMACAEzAB/BMwAgwTMAIMEzACDBMwAgwTMAKcEzACnBMwApwTMAKcEzAB6BMwAOQTMAG8EzABvBMwAbwTMAG8EzABvBMwAqgTMAFMEzAAyBMwAMgTMADIEzAAyBMwAKATMACUEzAAoBMz/9gTMAG4EzP/2BMwAbgTM//YEzABuBMwAZwTMAH8EzABnBMwAfwTMAGcEzAB/BMwAZwTMAH8EzAA8BMwATQTMADwEzAB7BMwAPATMAIMEzAA8BMwAgwTMADwEzACDBMwAPATMAIMEzABJBMwAYQTMAEkEzABhBMwASQTMAGEEzABJBMwAYQTMADIEzAAlBMwAHgTMAB4EzACqBMwApwTMAKoEzACnBMwAqgTM/+IEzAAlBMwAYwTMAJ8EzAAyBMwAOQTMADwEzACdBMwAPATMAJ0EzAA8BMwAdQTMAAMEzACdBMwAMgTMADkEzAAyBMwAOQTMADIEzAA5BMwAPwTMAG8EzAA/BMwAbwTMAD8EzAAbBMwAPATMAH8EzAA8BMwAfwTMADwEzAB/BMwAlQTMAKQEzACVBMwApATMAJUEzACkBMwAlQTMAKQEzABiBMwAYQTMAGIEzABhBMwAMgTMADIEzAAyBMwAMgTMADIEzAAyBMwAMgTMADIEzAAyBMwAMgTMACgEzACKBMwAigTMAIoEzACKBMwAigTMAIoEzAADBMwAlQTMAKQEzACfBMwBAATMAQAEzAEFBMwB6QTMAWAEzAFdBMwA4wTMARkEzABGBMwAqgTM/+IEzAF7BMwBmwTMAZsEzABjBMwAgwTMAIMEzAD6BMwA+gTMAWcEzABZBMwAMgTMAWIEzAGFBMwAVQTMADIEzAAsBMwAkwTMAJEEzACgBMwAqgTMAKoEzABkBMwAEgTMAAUEzACBBMwAqgTMAKoEzACkBMwArwTM/+wEzAAFBMwAYgTMAGEEzAA8BMwAqgTMAKoEzAA8BMwAMgTMAD8EzABiBMwAMgTM/+wEzP/sBMz/7ATM/+wEzAAoBMwAKATMAIMEzACnBMwApwTMAKcEzAB1BMwAVwTMAG8EzABhBMwAMgTM/+wEzP/sBMz/7ATM/+wEzAAoBMwAKATMAOYEzADIBMwAqgTMAF4EzACBBMwAAATMADwEzAAeBMz/4gTMAJAEzAC4BMwBggTMAKYAAPznAAD85wTMAZgBBQDZAQABXwEAAQ0B6QEUARkBGAFdAWAA4wAAAAIAAAAAAAD/ZQCCAAAAAQAAAAAAAAAAAAAAAAAAAAABkAAAAQIAAgADAAQABQAGAAcACAAJAAoACwAMAA0ADgAPABAAEQASABMAFAAVABYAFwAYABkAGgAbABwAHQAeAB8AIAAhACIAIwAkACUAJgAnACgAKQAqACsALAAtAC4ALwAwADEAMgAzADQANQA2ADcAOAA5ADoAOwA8AD0APgA/AEAAQQBCAEMARABFAEYARwBIAEkASgBLAEwATQBOAE8AUABRAFIAUwBUAFUAVgBXAFgAWQBaAFsAXABdAF4AXwBgAGEAowCEAIUAvQCWAOgAhgCOAIsAnQCkAIoA2gCDAJMBAwEEAI0BBQCIAMMA3gEGAJ4A9QD0APYAogCtAMkAxwCuAGIAYwCQAGQAywBlAMgAygDPAMwAzQDOAOkAZgDTANAA0QCvAGcA8ACRANYA1ADVAGgA6wDtAIkAagBpAGsAbQBsAG4AoABvAHEAcAByAHMAdQB0AHYAdwDqAHgAegB5AHsAfQB8ALgAoQB/AH4AgACBAOwA7gC6AQcBCAEJAQoBCwEMAP0A/gENAQ4BDwEQAP8BAAERARIBEwEBARQBFQEWARcBGAEZARoBGwEcAR0A+AD5AR4BHwEgASEBIgEjASQBJQEmAScBKAEpAPoBKgErASwBLQEuAS8BMAExATIBMwE0ATUA4gDjATYBNwE4ATkBOgE7ATwBPQE+AT8AsACxAUABQQFCAUMBRAFFAUYBRwFIAUkA+wD8AOQA5QFKAUsBTAFNAU4BTwFQAVEBUgFTAVQBVQFWAVcAuwFYAVkBWgFbAOYA5wCmAVwBXQFeANgA4QDbANwA3QDgANkA3wCbALIAswC2ALcAxAC0ALUAxQCCAMIAhwCrAMYAvgC/ALwAjAFfAJgBYACaAJkA7wClAJIAnACnAI8AlACVALkAwADBAWEBYgFjAWQBZQFmAWcBaAFpAWoBawFsAW0BbgFvAXABcQDXAXIBcwF0AXUBdgF3AXgBeQF6AXsBfAF9AX4BfwGAAYEAqQCqAYIBgwD3AYQBhQGGAYcBiAGJAYoBiwGMAY0BjgGPAZABkQGSAZMBlAGVAZYBlwGYBE5VTEwHdW5pMDBCMgd1bmkwMEIzB3VuaTAzQkMHdW5pMDBCOQdBbWFjcm9uB2FtYWNyb24GQWJyZXZlBmFicmV2ZQdBb2dvbmVrB2FvZ29uZWsLQ2NpcmN1bWZsZXgLY2NpcmN1bWZsZXgKQ2RvdGFjY2VudApjZG90YWNjZW50BkRjYXJvbgZkY2Fyb24GRGNyb2F0B0VtYWNyb24HZW1hY3JvbgpFZG90YWNjZW50CmVkb3RhY2NlbnQHRW9nb25lawdlb2dvbmVrBkVjYXJvbgZlY2Fyb24LR2NpcmN1bWZsZXgLZ2NpcmN1bWZsZXgKR2RvdGFjY2VudApnZG90YWNjZW50B3VuaTAxMjIHdW5pMDEyMwtIY2lyY3VtZmxleAtoY2lyY3VtZmxleARIYmFyBGhiYXIHSW1hY3JvbgdpbWFjcm9uB0lvZ29uZWsHaW9nb25lawJJSgJpagtKY2lyY3VtZmxleAtqY2lyY3VtZmxleAd1bmkwMTM2B3VuaTAxMzcGTGFjdXRlBmxhY3V0ZQd1bmkwMTNCB3VuaTAxM0MGTGNhcm9uBmxjYXJvbgZOYWN1dGUGbmFjdXRlB3VuaTAxNDUHdW5pMDE0NgZOY2Fyb24GbmNhcm9uB09tYWNyb24Hb21hY3Jvbg1PaHVuZ2FydW1sYXV0DW9odW5nYXJ1bWxhdXQGUmFjdXRlBnJhY3V0ZQd1bmkwMTU2B3VuaTAxNTcGUmNhcm9uBnJjYXJvbgZTYWN1dGUGc2FjdXRlC1NjaXJjdW1mbGV4C3NjaXJjdW1mbGV4B3VuaTAyMUEHdW5pMDIxQgZUY2Fyb24GdGNhcm9uB1VtYWNyb24HdW1hY3JvbgZVYnJldmUGdWJyZXZlBVVyaW5nBXVyaW5nDVVodW5nYXJ1bWxhdXQNdWh1bmdhcnVtbGF1dAdVb2dvbmVrB3VvZ29uZWsGWmFjdXRlBnphY3V0ZQpaZG90YWNjZW50Cnpkb3RhY2NlbnQHdW5pMDIxOAd1bmkwMjE5B3VuaTAyMzcHdW5pMDNBOQd1bmkwMzk0B3VuaTAxNjIHdW5pMDE2MwZFYnJldmUGSWJyZXZlBkl0aWxkZQRMZG90A0VuZwZPYnJldmUEVGJhcgZVdGlsZGUGV2FjdXRlC1djaXJjdW1mbGV4CVdkaWVyZXNpcwZXZ3JhdmULWWNpcmN1bWZsZXgGWWdyYXZlBmVicmV2ZQZpYnJldmUGaXRpbGRlBGxkb3QDZW5nBm9icmV2ZQR0YmFyBnV0aWxkZQZ3YWN1dGULd2NpcmN1bWZsZXgJd2RpZXJlc2lzBndncmF2ZQt5Y2lyY3VtZmxleAZ5Z3JhdmUHdW5pMjA3NAd1bmkwMEFEB3VuaTIwMTEHdW5pMDBBMARFdXJvB3VuaTIwQTkHdW5pMjIxNQd1bmkwMEI1Bm1pbnV0ZQZzZWNvbmQHdW5pMDMyNgx1bmkwMzI2LmNhc2UKYWN1dGUuY2FzZQpicmV2ZS5jYXNlCWNhcm9uLmFsdApjYXJvbi5jYXNlDGNlZGlsbGEuY2FzZQ9jaXJjdW1mbGV4LmNhc2UNZGllcmVzaXMuY2FzZQ5kb3RhY2NlbnQuY2FzZQpncmF2ZS5jYXNlEWh1bmdhcnVtbGF1dC5jYXNlC21hY3Jvbi5jYXNlC29nb25lay5jYXNlCXJpbmcuY2FzZQp0aWxkZS5jYXNlALAALCCwAFVYRVkgIEu4AA5RS7AGU1pYsDQbsChZYGYg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YFmwAyWwAmIgsABQWLBAYFlmsAFjYbACJUZhOCMgPCM4GyEgIEYjR7ABKyNhOCFZsTABFCstsEcssQA6Ky6xMAEUKy2wSCyxADsrISMgIDywBiNCIzixMAEUK7AGQy6wMCstsEkssAAVIEewACNCsgABARUUEy6wNiotsEossAAVIEewACNCsgABARUUEy6wNiotsEsssQABFBOwNyotsEwssDkqLbBNLLAAFkUjIC4gRoojYTixMAEUKy2wTiywCiNCsE0rLbBPLLIAAEYrLbBQLLIAAUYrLbBRLLIBAEYrLbBSLLIBAUYrLbBTLLIAAEcrLbBULLIAAUcrLbBVLLIBAEcrLbBWLLIBAUcrLbBXLLMAAABDKy2wWCyzAAEAQystsFksswEAAEMrLbBaLLMBAQBDKy2wWyyzAAABQystsFwsswABAUMrLbBdLLMBAAFDKy2wXiyzAQEBQystsF8ssgAARSstsGAssgABRSstsGEssgEARSstsGIssgEBRSstsGMssgAASCstsGQssgABSCstsGUssgEASCstsGYssgEBSCstsGcsswAAAEQrLbBoLLMAAQBEKy2waSyzAQAARCstsGosswEBAEQrLbBrLLMAAAFEKy2wbCyzAAEBRCstsG0sswEAAUQrLbBuLLMBAQFEKy2wbyyxADwrLrEwARQrLbBwLLEAPCuwQCstsHEssQA8K7BBKy2wciywABaxADwrsEIrLbBzLLEBPCuwQCstsHQssQE8K7BBKy2wdSywABaxATwrsEIrLbB2LLEAPSsusTABFCstsHcssQA9K7BAKy2weCyxAD0rsEErLbB5LLEAPSuwQistsHossQE9K7BAKy2weyyxAT0rsEErLbB8LLEBPSuwQistsH0ssQA+Ky6xMAEUKy2wfiyxAD4rsEArLbB/LLEAPiuwQSstsIAssQA+K7BCKy2wgSyxAT4rsEArLbCCLLEBPiuwQSstsIMssQE+K7BCKy2whCyxAD8rLrEwARQrLbCFLLEAPyuwQCstsIYssQA/K7BBKy2whyyxAD8rsEIrLbCILLEBPyuwQCstsIkssQE/K7BBKy2wiiyxAT8rsEIrLbCLLLILAANFUFiwBhuyBAIDRVgjIRshWVlCK7AIZbADJFB4sQUBFUVYMFktAAAAAAMAlf7lBEsFKgAPABMAOQBXQFQ2LSMZBAYEAUwFAQQCBgIEBoAKBwIGAwIGA34IAQEAAgQBAmcJAQMAAANXCQEDAwBfAAADAE8UFBAQAAAUORQ4NDIoJh8eEBMQExIRAA8ADTULBhcrABYVAxQGIyEiJjUTNDYzIQMTIQM2JjU0NxMDJjU0NjMyFhcTEzY2MzIWFRQHAxMWFRQGIyInAwMGIwQuHQMdIvzLIh0DHSIDNS0C/SACkyQD1tYCIhUSGQWiogUZEhUiAtbWAyQVJgmiogkmBSofJfpDJR8fJQW9JR/6IQV5+of2EQ0EBgGaAZgDBw4SCwr+swFNCgsSDgcD/mj+ZgYEDRETAU3+sxMAAgHI//YDBAT1AAwAGgBMS7AXUFhAFwAAAAFfBAEBASRNBQEDAwJhAAICIwJOG0AVBAEBAAADAQBpBQEDAwJhAAICIwJOWUASDQ0AAA0aDRkUEgAMAAokBggXKwAWBwMGIyInAyY2MzMCFhUVFAYjIiY1NTQ2MwLwFAI5BV5eBTkCFBfmIUlJUlJJSVIE9Rga/W86OgKRGhj8VR0i1iIdHSLWIh0A//8AsQKfBCEE9QAjAAr+8gAAAAMACgEOAAAAAAACADL/6gSaBLkAUwBXAFpAV09EAgkKJRoCAwICTBEPBwMBBgQCAgMBAmcMAQoKKE0OCAIAAAlfEA0LAwkJJU0FAQMDKQNOVFQAAFRXVFdWVQBTAFJNS0hHQkA9OyEmJSMVIyYhJhIIHysAFhYVFAYGIyMHMzIWFhUUBgYjIwcGBiMiJjU0NzcjBwYGIyImNTQ3NyMiJiY1NDY2MzM3IyImJjU0NjYzMzc2NjMyFhUUBwczNzY2MzIWFRQHBzMBNyMHBHMaDQ0aGJw9fxgaDQ0aGLlABCseLUkBN91ABCseLUkBN2QYGg0NGhifPIEYGg0NGhi8PQQrHi1JATXePQQrHi1JATVi/l083T0DrBIwLy8wEekSMC8vMBH2EBEgGgYD1PYQESAaBgPUETAvLzAS6REwLy8wEuwQESAaBgPK7BARIBoGA8r+NunpAAMApP+DBC4FIABFAE0AVAB5QBdNFAUDBAEAU0w4FQQFAVQ3KCYEAgUDTEuwIFBYQB4GAQAAAQUAAWkABQQBAgMFAmkAAwMHYQgBBwckA04bQCQIAQcAAwdZBgEAAAEFAAFpAAUEAQIDBQJpCAEHBwNhAAMHA1FZQBAAAABFAEQcJSgjHCUoCQgdKwAWFRUWFzU0NjMyFhUVFAYjIicmJxUWFxYWFRQGBgcVFAYjIiY1NSYnFRQGIyImNTU0NjMyFxYXNSYmJyY1NDY2NzU0NjMCBhUUFxYXNQA1NCcmJxUClyYxLDE/QDYrMTUUQF56TVBaVqZ1Jjc3JjQxOkBANi8xPRY7Z0FpK4pbn2UmN4kxJBUkASkqHCkFIBwjvxIbCiIdHSLTIh0VRB2SDiAhdmFbiE4EtCMcHCPMER4IIh0dIt8hHhxLHaEKHhhMpFaARgKjIxz+TigdIBMLBY792EUhFQwGmQAFADL/6gSaBLkADwAjAC8APwBLAGxAaRYBBAUgAQgJAkwAAgEFAQIFgAADCAYIAwaAAAQAAAcEAGkMAQcNAQkIBwlpCwEFBQFhCgEBAShNAAgIBmEABgYpBk5AQDAwJCQAAEBLQEpGRDA/MD44NiQvJC4qKBwaEhAADwAOJg4IFysAFhYVFAYGIyImJjU0NjYzBDMyFhcWFRQHAQYjIiYnJjU0NwEEBhUUFjMyNjU0JiMAFhYVFAYGIyImJjU0NjYzBgYVFBYzMjY1NCYjAY5+Skp+Skp+Skp+SgKpEw4jGSwW/JMXEQ4jGC0XA239RzMzJCQzMyQCjn5KSn5KSn5KSn5KJDMzJCQzMyQEuUp+Skp+Skp+Skp+SmoXGi0cExb8vhUXGjAbERcDQj0zJCQzMyQkM/4QSn5KSn5KSn5KSn5KuzMkJDMzJCQzAAIAa//qBHsEuQBDAEwAkUAVDAEAAUw9FQMDAksmAgQDNAEFBARMS7AXUFhAKAAAAQIBAAKAAAIAAwQCA2kAAQEHYQkBBwcoTQgBBAQFYQYBBQUjBU4bQDIAAAECAQACgAACAAMEAgNpAAEBB2EJAQcHKE0IAQQEBV8ABQUjTQgBBAQGYQAGBikGTllAEgAASkgAQwBCIzYjJjokJwoIHSsAFxYWFRUUBiMiJjU1JiMiBhUUFhcXNjc2NjMzMhYWFRQGBiMjBgcXMzIWFhUUBgYjIyInJwYjIiYmNTQ2NyY1NDY2MwIGFRQWMzI3JwLirhYVOkA+LkhHOEY4NLUbFAcYFdwYGg0NGhhbGx5bTRgaDQ0aGKsoIEGBv2meVlpaVVysdcMhQjdOP8MEuWAMHRXFIh0cI2YkSDswXTa9QT0UFhAsKiosEU1AXhEsKiosECFDelebZF+TPHh8Y5xY/P1DKTlEPcsAAAEBvwKfAxME9QAOAD21CQEAAQFMS7AXUFhADAAAAAFfAgEBASQAThtAEgIBAQAAAVcCAQEBAGEAAAEAUVlACgAAAA4ADCQDCBcrAAcDBgYjIiYnAyY1NDMzAxMHSQUqLi4qBUkBKvoE9TL+ICEjIyEB4AQIJgABAQH+pwOfBWcAHwBCS7AXUFhACwAAACpNAAEBJwFOG0uwIFBYQAsAAQEAYQAAACoBThtAEAAAAQEAWQAAAAFhAAEAAVFZWbUVFCACCBcrADMyFhcWFRQHBgIVFBIXFhUUBwYGIyInJiYCNTQSNjcDEQ4XMRQkEsjMzMgSJBQxFw4Oi+eQkOeLBWclHzYpGwx9/r3W1v69fQwbKTYfJQhP7gFOzc0BTu5PAAEBLf6nA8sFZwAfAEJLsBdQWEALAAEBKk0AAAAnAE4bS7AgUFhACwAAAAFhAAEBKgBOG0AQAAEAAAFZAAEBAGEAAAEAUVlZtR0cKAIIFysAFhIVFAIGBwYjIiYnJjU0NzYSNTQCJyY1NDc2NjMyFwJU55CQ54sODhcxFCQSyMzMyBIkFDEXDg4FEO7+ss3N/rLuTwglHzYpGwx9AUPW1gFDfQwbKTYfJQgAAQC9AYMEDwS5ADsAVEAPOAICAAQ1KR0RBQUBAAJMS7AVUFhAEwIBAQABhgUBBAQoTQMBAAArAE4bQBUDAQAEAQQAAYACAQEBhAUBBAQoBE5ZQA0AAAA7ADovJi8nBggaKwAWFRQHBzc2MzIWFxYVFAYHBxcWFhUUBwYjIiYnJwcGBiMiJyY1NDY3NycmJjU0NzY2MzIXFycmNTQ2MwKfPwQvsyAiIjcOCDov0J4VFzcmJyA1DlNTDjUgJyY3FxWe0C86CA43IiIgsy8EPzkEuT0vEQ/MbBQsKxsULTgFE4kTLRc2KRwnIsHBIiccKTYXLROJEwU4LRQbKywUbMwPES89AAABAKoAigQiBAIAJwAtQCoGAQUAAgVZBAEAAwEBAgABZwYBBQUCYQACBQJRAAAAJwAmJiQkJiQHCBsrABYWFREhMhYWFRQGBiMhERQGBiMiJiY1ESEiJiY1NDY2MyERNDY2MwKVMBEBDRgaDQ0aGP7zETAvLzAS/vQYGg0NGhgBDBIwLwQCDRoY/vQSMC8vMBH+8xgaDQ0aGAENETAvLzASAQwYGg0AAQFh/toDEAFiABEAHkAbCgEAAQFMAAEAAAFXAAEBAGEAAAEAUScmAggYKwAWFRQHAwYjIiY1NDcTNjYzMwL+EgftFFYmKwFkBBsV8wFiEg8PD/3nMBwZCQQCHhMVAAEAqgHWBCICtwARAB9AHAIBAQAAAVcCAQEBAF8AAAEATwAAABEADzYDCBcrABYWFRQGBiMhIiYmNTQ2NjMhA/saDQ0aGP0GGBoNDRoYAvoCtxIwLy8wEREwLy8wEgABAcH/9gMLAXIADQAZQBYCAQEBAGEAAAAjAE4AAAANAAwlAwgXKwAWFRUUBiMiJjU1NDYzAr1OTldXTk5XAXIdIv4iHR0i/iIdAAEAn/6YBC0FdwAPAEu2CgICAAEBTEuwG1BYQAwCAQEBKk0AAAAnAE4bS7AkUFhADAIBAQABhQAAACcAThtACgIBAQABhQAAAHZZWUAKAAAADwAOJgMIFysAFhUUBwEGIyImNTQ3ATYzA9JbBP1mEkBDWwQCmhJABXcsIgsJ+a4rLCILCQZSKwACAIX/6gRHBLkADwAbACxAKQUBAwMBYQQBAQEoTQACAgBhAAAAKQBOEBAAABAbEBoWFAAPAA4mBggXKwAWEhUUAgYjIiYCNTQSNjMGBhUUFjMyNjU0JiMC+dp0dNqTk9p0dNqTaG1taGhtbWgEuZ3+6bS0/umcnAEXtLQBF53jxcDAxMTAwMUAAQC6AAAELAS8ACUAMEAtEgECAwFMAAIDAQMCAYAAAwMoTQUEAgEBAGAAAAAjAE4AAAAlACQpIyY2BggaKyQWFhUUBgYjISImJjU0NjYzMxEHBiMiJicmNTQ2NyU2MzIWFREzBAUaDQ0aGP0kGBoNDRoY9tESDhMjEhQTFAGmHB0dJOzNESwqKiwQECwqKiwRAqJ3CiQnLB0VHAvuECAg/FEAAQCeAAAEJAS5ADEAbLUkAQQDAUxLsBBQWEAkAAQDAQMEAYAAAQAAAXAAAwMFYQYBBQUoTQAAAAJgAAICIwJOG0AlAAQDAQMEAYAAAQADAQB+AAMDBWEGAQUFKE0AAAACYAACAiMCTllADgAAADEAMCQsNSMXBwgbKwAWFhUUBgcBITU0NjMyFhUVFAYjISImJjU0NjcBNjY1NCYjIgcVFAYjIiY1NTQ3NjYzAtu5X1tj/u8BGi4+QDoeI/z6GBoNCg4BrVM/UExXVi4+QDorWbhWBLlbpG5lql/++VwjHB0i8iIfESwqKCgNAZ1QYjRFVCqMIxwdIu0pFzExAAABALf/6gQWBLkAOgBLQEgtAQYFBAEDBAJMAAYFBAUGBIAAAQMCAwECgAAEAAMBBANpAAUFB2EIAQcHKE0AAgIAYQAAACkATgAAADoAOSQkNDQkFikJCB0rABYVFAcWFhUUBiMiJyY1NDc2MzIXFhYzMjY1NCYjIyImNTQ2MzMyNjU0JiMiBxUUBiMiJjU1NDc2NjMDGNuNU13+5MaRJhEiKggMQYpBamxWVGcjHBwjTFlXVFJLTi4+QDoxT6tTBLmvpatKJodfu79NEy0bLVQFHyJPSkhJLT4+LkJGREYXTyMcHSK7LRMgJAACAHgAAARKBLkALQAwADZAMzABAAYBTAcBAAUBAQIAAWcIAQYGKE0EAQICA2AAAwMjA04AAC8uAC0ALCEmNiEmIwkIHCsAFhURMzIWFhUUBgYjIxUzMhYWFRQGBiMhIiYmNTQ2NjMzNSEiJiY1NDcBNjYzATMTAzAvrBgaDQ0aGKyOGBoNDRoY/c4YGg0NGhiq/lIYGg0TAdYbRzP+ndsQBLkuLP3gESwqKiwQpREsKiosEBAsKiosEaUQLCpBGAJDIiP9hgEkAAEAsP/qBBYEowAvAEZAQwcBBQEBTAAGBQMFBgOAAAMEBQMEfgABAAUGAQVpAAAAB18IAQcHIk0ABAQCYQACAikCTgAAAC8ALSIkIxclIiQJCB0rABYVFAYjIQc2MzIWFhUUBiMiJicmNTQ3NjMyFxYzMjY1NCYjIgcGIyImNxM2NjMhA7wcHCP+Rg5gYHyvWvvdX7tOJhEiKggMmoNccFtTXmIqKEA1AiECHSICYASjLj4+Ld8lZbV2yc8vKhUrGy1UBU1gVVFcJBAeIwImIx4AAAIAoP/qBDYEugAfAC0AQEA9AgEAAwoBBQECTAABBwEFBAEFaQAAAANhBgEDAyhNAAQEAmEAAgIpAk4gIAAAIC0gLCgmAB8AHiYlFggIGSsAFhcWFRQHDgIHNjYzMhYWFRQGBiMiJicmJjU0EiQlAAYGFRQWFjMyNjU0JiMD6x0FAim48YUUNoZXb65ic8yAfsJBKS27AW4BCP5zWjItVzpWaGFVBLo0OBEcVwMJTJByPDlfqm5wsWNmYD2uZdMBMasK/VgoSC4uTi5ZS01XAAABALz/6gQ4BKMAHgBStQ4BAAIBTEuwClBYQBgAAgEAAQJyAAEBA18EAQMDIk0AAAApAE4bQBkAAgEAAQIAgAABAQNfBAEDAyJNAAAAKQBOWUAMAAAAHgAcIxcoBQgZKwAWFhUUBwEGBiMiJyYmNTQ3ASEVFAYjIiY1ETQ2MyEEERoNCf5fCjEiHRwtOQYBeP6SLj5AOh8iAvwEoxEsKjEX/CQXFwcKLR4MDwNrwCMcHSIBViMeAAMAq//qBCEEuQAbACcAMwBEQEEUBgIFAgFMAAIIAQUEAgVpBwEDAwFhBgEBAShNAAQEAGEAAAApAE4oKBwcAAAoMygyLiwcJxwmIiAAGwAaLAkIFysAFhYVFAYHFhYVFAYGIyImJjU0NjcmJjU0NjYzBgYVFBYzMjY1NCYjAgYVFBYzMjY1NCYjAuC4YlZNX2tvyISEyG9qYE1WYrh6R1RSSUlSVEdWXFxWVlxcVgS5WptdXH0jI45rbqFWVqFubI0jIn5cXZta2k0/P0xMPz9N/idYSkpWVkpKWAACAJb/6QQsBLkAHgAsAEBAPRMBAgQLAQABAkwABAACAQQCaQcBBQUDYQYBAwMoTQABAQBhAAAAKQBOHx8AAB8sHyslIwAeAB0lFicICBkrABYXFhYVEAAFBiYnJjU0Nz4CNwYGIyImJjU0NjYzBgYVFBYzMjY2NTQmJiMC08JBKS3+kf56Gh0FAim212oPNoZXb65ic8yAVWhhVTpaMi1XOgS5ZmA9rmX+uv6cDwE0OBEcVwMJS451PDlfqm5wsWPfWUtNVyhILi5OLgACAcH/9gMLA6YADQAbACxAKQQBAQEAYQAAACVNAAICA2EFAQMDIwNODg4AAA4bDhoVEwANAAwlBggXKwAmNTU0NjMyFhUVFAYjAiY1NTQ2MzIWFRUUBiMCD05OV1dOTldXTk5XV05OVwJSHSLWIh0dItYiHf2kHSLWIh0dItYiHQAAAgF1/toDJAOmAA0AHwAqQCcYAQIDAUwAAwACAwJlBAEBAQBhAAAAJQFOAAAfHRYUAA0ADCUFCBcrACY1NTQ2MzIWFRUUBiMWFhUUBwMGIyImNTQ3EzY2MzMCD05OV1dOTlesEgftFFYmKwFkBBsV8wJSHSLWIh0dItYiHfASDw8P/ecwHBkJBAIeExUAAAEAeABNBDoEQQAbAB5AGwkBAQABTAAAAQEAWQAAAAFhAAEAAVEeIAIIGCsAMzIWFxYVFAcBARYVFAcGBiMiJwEmJjU0NjcBA8YNFCQVGiT9twJJJBoVJBQNFPz0GRUVGQMMBEEkKjQfIhP+3P7cEyIfNCokCgGSDSgpKSgNAZIAAgCqAPEEIgOcABEAIwApQCYFAQMAAgMCYwAAAAFfBAEBASUAThISAAASIxIhGxgAEQAPNgYIFysAFhYVFAYGIyEiJiY1NDY2MyESFhYVFAYGIyEiJiY1NDY2MyED+xoNDRoY/QYYGg0NGhgC+hgaDQ0aGP0GGBoNDRoYAvoDnBIwLy8wEREwLy8wEv42EjAvLzARETAvLzASAAEAkgBNBFQEQQAbAB5AGxABAAEBTAABAAABWQABAQBhAAABAFEeJwIIGCsAFhUUBgcBBiMiJicmNTQ3AQEmNTQ3NjYzMhcBBD8VFRn89BQNFCQVGiQCSf23JBoVJBQNFAMMApgoKSkoDf5uCiQqNB8iEwEkASQTIh80KiQK/m4AAgDQ//YD5gT1ACQAMgB6QAwYAQIBDAYFAwACAkxLsBdQWEAmAAIBAAECAIAAAAUBAAV+AAEBA2EGAQMDJE0HAQUFBGEABAQjBE4bQCQAAgEAAQIAgAAABQEABX4GAQMAAQIDAWkHAQUFBGEABAQjBE5ZQBQlJQAAJTIlMSwqACQAIyQrKAgIGSsAFhUUBgcHBgYjIiYnJyY3NzY2NTQmIyIHFRQGIyImNTU0NzYzEhYVFRQGIyImNTU0NjMDGc2XnAYCLDc3LAIMAiFnSEZPTUtOLj5AOim6pT1ERE1NRERNBPW8p4ufK1YZFxcZ0SwHFA5HPkRGHlwjHB0ivikUWPwtHSKuIh0dIq4iHQAAAgAh/2cEowQ2AEoAVwBSQE8YFQIJAgoBAAMCTAoBBwAEAgcEaQACCwEJAwIJaQgBAwEBAAUDAGkABQYGBVkABQUGYQAGBQZRS0sAAEtXS1ZSUABKAEktJiYuJSMmDAgdKwAWFhUUBgYjIiYnBiMiJjU0NjYzMhc3NjMyFxYWBwMGFRQWMzI2NjU0JiYjIgYGFRQWFjMyNzYzMhYXFhUUBgcGBiMiJiY1NBIkMwIGBhUUFjMyNjY1NCMDMe+DT4tYRVsRTXhUZliSU1slIQUYExUaHgRICCAZJjwjWqpzhdF1VaRziHoIBg4UCQcMDDWhUqPvf6MBH7EvRi8kHiJFLUIENoz5nn+5YUw/kH5yZ8+Fc0UJBgcVDf7IIBUkJT5zTHayYo/2k3SwYSgDGyEbERESBRcdhfSlwAE7tv5NT3s+LzNZfS5mAAL/9gAABNYEowA3ADsAOEA1AAkAAwAJA2cABwcIXwoBCAgiTQYEAgMAAAFfBQEBASMBTgAAOjkANwA1ISY2IREmNiMLCB4rABYXATMyFhYVFAYGIyEiJiY1NDY2MzMnIQczMhYWFRQGBiMhIiYmNTQ2NjMzEyMiJiY1NDY2MyEHAzMDAuEyCwEiVxgaDQ0aGP5YGBoNDRoYVi3+lC1KGBoNDRoY/mwYGg0NGhhU/acYGg0NGhgB2lh7+XgEox8i/GsQLCoqLBERLCoqLBCRkRAsKiosEREsKiosEAMJESwqKiwQzf5VAasAAAMARgAABHMEowAfACgAMAB1tQUBBwQBTEuwMVBYQCAABAAHAQQHZwUBAgIDXwgBAwMiTQYBAQEAXwAAACMAThtALAACAwUFAnIAAQYABgFyAAQABwYEB2cABQUDYAgBAwMiTQAGBgBfAAAAIwBOWUAUAAAwLispKCYiIAAfAB0hJjkJCBkrABYVFAYHFhUUBiMhIiYmNTQ2NjMzESMiJiY1NDY2MyEDMzI2NTQmIyMRMzI1NCYjIwNfyVFJ5d7P/b8YGg0NGhhraxgaDQ0aGAIJpI5aWFVdjsDCX2PABKOrmFJ1Iz7gqa8QLCoqLBEDCRAsKiosEf4nQEJDPf0Li0pHAAEAZ//qBGcEuQAuAENAQCoBAQUBTAADAAIAAwKAAAEBBWEHBgIFBShNAAAABWEHBgIFBShNAAICBGEABAQpBE4AAAAuAC0mJiMkJSUICBwrABYVERQGIyImJjU0JiMiBhUUFjMyNjc2MzIXFhUUBwYjIiYCNTQSNjMyFzU0NjMELC49Ry8zFG1li5CZjFegXhAOLx8OLtbVpPqJhu2Wr1U6QAS5HCP+gCIdDRoYZHjIvLrLLzAIUyYeMxZqlgEXu7oBF5Z+PyIdAAACADwAAASDBKMAHAAlAFpLsDFQWEAYBQECAgNfBgEDAyJNBAEBAQBfAAAAIwBOG0AkAAIDBQUCcgABBAAEAXIABQUDYAYBAwMiTQAEBABfAAAAIwBOWUAQAAAlIx8dABwAGiEmNgcIGSsAFhIVFAIGIyEiJiY1NDY2MzMRIyImJjU0NjYzIQMzMjY1NCYjIwMB/IaG/K/+KRgaDQ0aGGFhGBoNDRoYAdd8aJuenptoBKOK/vW8vP71ixAsKiosEQMJECwqKiwR/DTBurrAAAEAPAAABGAEowA2APtLsApQWEAuAAABAgEAcgAFAwQEBXIAAgADBQIDZwgBAQEJXwoBCQkiTQcBBAQGYAAGBiMGThtLsAxQWEAvAAABAgEAcgAFAwQDBQSAAAIAAwUCA2cIAQEBCV8KAQkJIk0HAQQEBmAABgYjBk4bS7AxUFhAMAAAAQIBAAKAAAUDBAMFBIAAAgADBQIDZwgBAQEJXwoBCQkiTQcBBAQGYAAGBiMGThtAPAAICQEBCHIAAAECAQACgAAFAwQDBQSAAAcEBgQHcgACAAMFAgNnAAEBCWAKAQkJIk0ABAQGYAAGBiMGTllZWUASAAAANgA0ISY1IxEkIRMlCwgfKwAWFREUBiMiJjU1IRUzMhYVFAYjIxEhNTQ2MzIWFREUBiMhIiYmNTQ2NjMzESMiJiY1NDY2MyEELh46QD4u/nD0IxwcI/QBmjtDQjAeI/xcGBoNDRoYYWEYGg0NGhgDkASjHiP+0iIdHCOY/S4+Pi3+38oiHRwj/qAiHxAsKiosEQMJECwqKiwRAAEAPAAABGAEowAzAKVLsAxQWEAnAAABAgEAcgACAAMEAgNnBwEBAQhfCQEICCJNBgEEBAVfAAUFIwVOG0uwMVBYQCgAAAECAQACgAACAAMEAgNnBwEBAQhfCQEICCJNBgEEBAVfAAUFIwVOG0AuAAcIAQEHcgAAAQIBAAKAAAIAAwQCA2cAAQEIYAkBCAgiTQYBBAQFXwAFBSMFTllZQBEAAAAzADEhJjYhJCETJQoIHisAFhURFAYjIiY1NSERITIWFRQGIyEVMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMhBEIeOkA+Lv56ATAjHBwj/tDZGBoNDRoY/a4YGg0NGhh/fxgaDQ0aGAOkBKMeI/7SIh0cI5j+zy4+Pi33ESwqKiwQECwqKiwRAwkQLCoqLBEAAAEASf/qBKQEuQA+AEpARzoBAQcVAQIDAkwABAUBAwIEA2kAAQEHYQkIAgcHKE0AAAAHYQkIAgcHKE0AAgIGYQAGBikGTgAAAD4APSYmJjYiJCUlCggeKwAWFREUBiMiJiY1NCYjIgYVFBYzMjc1IyImJjU0NjYzITIWFhUUBgYjIxEUBgcGBiMiJgI1NBI2MzIXNTQ2MwQOLj1HLzMUaGqLkJmMb2PBGBoNDRoYAdoYGg0NGhgfExFd3nek+omG7ZawVDpABLkcI/6oIh0NGhhWXsi8ussepxAsKiosEREsKiosEP79GCQJMDCWARe7ugEXlnY3Ih0AAQAyAAAEmgSjAFMAQ0BAAAsABAELBGcMCggDAAAJXw4NAgkJIk0HBQMDAQECXwYBAgIjAk4AAABTAFFLSUhHRkQ+OyEmNiERJjYhJg8IHysAFhYVFAYGIyMRMzIWFhUUBgYjISImJjU0NjYzMxEhETMyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzITIWFhUUBgYjIxEhESMiJiY1NDY2MyEEcxoNDRoYOTkYGg0NGhj+ihgaDQ0aGEP+fEMYGg0NGhj+ihgaDQ0aGDk5GBoNDRoYAXYYGg0NGhhDAYRDGBoNDRoYAXYEoxEsKiosEPz3ESwqKiwQECwqKiwRASv+1REsKiosEBAsKiosEQMJECwqKiwRESwqKiwQ/vkBBxAsKiosEQABAKoAAAQiBKMAJwApQCYEAQAABV8GAQUFIk0DAQEBAl8AAgIjAk4AAAAnACUhJjYhJgcIGysAFhYVFAYGIyMRITIWFhUUBgYjISImJjU0NjYzIREjIiYmNTQ2NjMhA+caDQ0aGOwBABgaDQ0aGP0GGBoNDRoYAQDsGBoNDRoYAtIEoxEsKiosEPz3ESwqKiwQECwqKiwRAwkQLCoqLBEAAQBj/+oEmgSjACkANkAzGQEDAgFMAAIAAwACA4AEAQAABV8GAQUFIk0AAwMBYgABASkBTgAAACkAJyMlJiMmBwgbKwAWFhUUBgYjIxEUBiMiJyY1ETQ2MzIWFhURFjMyNjURISImJjU0NjYzIQRzGg0NGhi62NHqmxA9Ry8zFEVhUlL+zhgaDQ0aGALmBKMRLCoqLBD9lcDBkxAiAUQiHQ0aGP78IldbAlcQLCoqLBEAAAEAMgAABMwEowBgAFFATlUBAQAsAQIEAkwAAQAEAAEEgAAEAgAEAn4LCggDAAAJXw0MAgkJIk0HBQICAgNhBgEDAyMDTgAAAGAAXlhWVFJMSSEmNiMpNjkRJg4IHysAFhYVFAYGIyMBFhYXFhYXFhcWFjMzMhYWFRQGBiMjIiYnJicmJicmJiMiBwcVMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMhMhYWFRQGBiMjEQEjIiYmNTQ2NjMhBIIaDQ0aGCv+ojhcIhcmGCQOFjAfChgaDQ0aGIs9VSQXGRImEBpAIiwjM3MYGg0NGhj+KBgaDQ0aGGtrGBoNDRoYAZQYGg0NGhgvAUQ1GBoNDRoYAYUEoxEsKiosEP6rAzcwIUczShglKBEsKiosEEtDKzkmTBknLSIysBEsKiosEBAsKiosEQMJECwqKiwRESwqKiwQ/sABQBAsKiosEQABADwAAARgBKMAKwBjS7AxUFhAIAACAAEAAgGABQEAAAZfBwEGBiJNBAEBAQNgAAMDIwNOG0AmAAIAAQACAYAABAEDAQRyBQEAAAZfBwEGBiJNAAEBA2AAAwMjA05ZQA8AAAArACkhJjYjESYICBwrABYWFRQGBiMjESERNDYzMhYWFREUBiMhIiYmNTQ2NjMzESMiJiY1NDY2MyEC+RoNDRoY2gFfPUcvMxQeI/xcGBoNDRoYkpIYGg0NGhgCZgSjESwqKiwQ/QEBOCIdDRoY/jIiHxAsKiosEQMJECwqKiwRAAABAAoAAATCBKMATQBDQEBIJR0DBAABTAAEAAEABAGACAEAAAlfCwoCCQkiTQcFAwMBAQJfBgECAiMCTgAAAE0AS0VCISY2JCQmNiEmDAgfKwAWFhUUBgYjIxMzMhYWFRQGBiMhIiYmNTQ2NjMzAwMGBiMiJicDAzMyFhYVFAYGIyEiJiY1NDY2MzMTIyImJjU0NjYzITIWFxMTNjYzIQSHGg0NGhg2DjwYGg0NGhj+ihgaDQ0aGFwGlw0uKisuDpgGXRgaDQ0aGP6KGBoNDRoYOw82GBoNDRoYARwVGwa3tgYbFQEdBKMRLCoqLBD89xEsKiosEBAsKiosEQJQ/mgjHR0jAZX9sxEsKiosEBAsKiosEQMJECwqKiwRDhH+FQHrEQ4AAQAy/+oErgSjAD8AYbYzEAICAAFMS7AXUFhAGwcFAgAABl8JCAIGBiJNBAECAgFhAwEBASkBThtAHwcFAgAABl8JCAIGBiJNBAECAgNfAAMDI00AAQEpAU5ZQBEAAAA/AD0kNiEmNiUjJgoIHisAFhYVFAYGIyMRFAYjIiYnASMRMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMhMhcBMxEjIiYmNTQ2NjMhBIcaDQ0aGDkyPC4tEf4+BG8YGg0NGhj+bBgaDQ0aGENDGBoNDRoYAQgoEAGfBFwYGg0NGhgBdwSjESwqKiwQ/FYhIRkcAun9xREsKiosEBAsKiosEQMJECwqKiwRG/1RAf0QLCoqLBEAAAIAP//qBI0EuQAPABsALEApBQEDAwFhBAEBAShNAAICAGEAAAApAE4QEAAAEBsQGhYUAA8ADiYGCBcrABYSFRQCBiMiJgI1NBI2MwYGFRQWMzI2NTQmIwMK+omJ+qSk+omJ+qSLkJCLi5CQiwS5lf7pu7v+6ZaWARe7uwEXlePIvLzJyby8yAACADwAAARxBKMAJQAuAGZLsDFQWEAgAAYAAAEGAGcHAQQEBV8IAQUFIk0DAQEBAl8AAgIjAk4bQCYABAUHBwRyAAYAAAEGAGcABwcFYAgBBQUiTQMBAQECXwACAiMCTllAEgAALiwoJgAlACMhJjYhJAkIGysAFhUUBiMjFTMyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzIQMzMjY1NCYjIwOE7e3mltkYGg0NGhj9mhgaDQ0aGJOTGBoNDRoYAiOWd3d5eXd3BKPPw8PQsREsKiosEBAsKiosEQMJECwqKiwR/bJcYGBbAAIAP/7hBI0EuQA5AEUAw0uwE1BYQAoyAQAHCgEFAQJMG0ALMgEABwFMCgECAUtZS7ATUFhAJAAHAAABBwBpAAUEAQVZAwICAQAEAQRlCgEICAZhCQEGBigIThtLsB1QWEAlAAcAAAEHAGkDAQEABQQBBWkAAgAEAgRlCgEICAZhCQEGBigIThtALAADAAEAAwGAAAcAAAMHAGkAAQAFBAEFaQACAAQCBGUKAQgIBmEJAQYGKAhOWVlAFzo6AAA6RTpEQD4AOQA4JCgTJCMmCwgcKwAWEhUUAgYjIicHNjMyFhcWFjMyNzYzMhYXFhUUBwYGIyImJyYmIyIHBiMiJicmNTQ3NyYCNTQSNjMGBhUUFjMyNjU0JiMDCvqJifqkGRRqTk4fRR8cOxpOSwwNFisPEyM5bTkkSzNBUy52bwYIEyoPFhG8ma6J+qSKkZGKipGRigS5jv78ra3++44Cah0JBgUJKAYkHyYfKhoqIwsKDAsvAyQcJyMeEcg9ARjDrQEEjuO2pqa3t6amtgAAAgA8AAAEuASjAEMATABztQQBAggBTEuwMVBYQCIACAACAAgCaQkBBgYHXwoBBwciTQUDAgAAAWEEAQEBIwFOG0AoAAYHCQkGcgAIAAIACAJpAAkJB2AKAQcHIk0FAwIAAAFhBAEBASMBTllAFAAATEpGRABDAEEhJjYhKTY9CwgdKwAWFRQHFhcWFhcWFxYWMzMyFhYVFAYGIyMiJicmJyYmJyYmIyMRMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMhAzMyNjU0JiMjA13i+DYgFSMXGA0UKBkTGBoNDRoYYU9iKRQcFCQWH0w1QGEYGg0NGhj+OhgaDQ0aGGtrGBoNDRoYAg+qlWZiYmaVBKO6sec8FSkbOy0wFSEhESwqKiwQQEsjPS5DICsm/wARLCoqLBAQLCoqLBEDCRAsKiosEf4BSUtLSQABAJX/6gQ/BLkASgBNQEpGAQEGHwECBQJMAAEBBmEIBwIGBihNAAAABmEIBwIGBihNAAQEAmEDAQICKU0ABQUCYQMBAgIpAk4AAABKAElEQiQlJC8kJQkIHCsAFhURFAYjIiYnJiYjIgYVFBYXFhcWFhcWFRQGBiMiJxUUBiMiJjURNDYzMhYXFhYzMjY1NCYnJiYnJiYnJiY1NDY2MzIWFzU0NjMD1DYrMSEmCy+UYUlTJCIsa2iEOqBduoindDE/QDYrMSMpCzaWZFhcKScgTUtWcDFMVmKxclCIMjE/BLkdIv7uIh0QEEpRSjsdJQ4REhQjJGHYbqRcZSYiHR0iAU4iHRIWZ2hIQCg3ExAUEBIeGiiFamqlXDQwJSIdAAABAGIAAARqBKMALQA0QDEGAQABAgEAAoAFAQEBB18IAQcHIk0EAQICA18AAwMjA04AAAAtACsjESY2IRMlCQgdKwAWFREUBiMiJjURIxEzMhYWFRQGBiMhIiYmNTQ2NjMzESMRFAYjIiY1ETQ2MyEETB43OTcrtdgYGg0NGhj9VhgaDQ0aGNi1Nzk3Kx8iA4YEox4j/lohHh0iARD9AREsKiosEBAsKiosEQL//vAhHh0iAaYjHgAAAQAy/+oEmgSjADcALUAqBgQCAwAAA18IBwIDAyJNAAUFAWEAAQEpAU4AAAA3ADUjIyY2JCQmCQgdKwAWFhUUBgYjIxEUBgYjIiYmNREjIiYmNTQ2NjMhMhYWFRQGBiMjERQWMzI2NREjIiYmNTQ2NjMhBHMaDQ0aGC9uzIyMzG4vGBoNDRoYAXYYGg0NGhhNbl5ebk0YGg0NGhgBdgSjESwqKiwQ/ceKxGVlxIoCORAsKiosEREsKiosEP3bc3FxcwIlECwqKiwRAAH/9v/qBNYEowAvAC1AKiQBAQABTAUEAgMAAANfBwYCAwMiTQABASkBTgAAAC8ALSImNiMjJggIHCsAFhYVFAYGIyMBBgYjIiYnASMiJiY1NDY2MyEyFhYVFAYGIyMTEyMiJiY1NDY2MyEErxoNDRoYRP6VDjo9PTkN/qJNGBoNDRoYAbIYGg0NGhhZ1+VHGBoNDRoYAZQEoxEsKiosEPxVJB0eIwOrECwqKiwRESwqKiwQ/ZsCZRAsKiosEQAB/+z/6gTgBKMAQQA6QDc2LhEDAQYBTAAGAAEABgGABwUDAwAABF8JCAIEBCJNAgEBASkBTgAAAEEAPyQkJjYkJiQmCggeKwAWFhUUBgYjIwMOAiMiJicDAwYGIyImJicDIyImJjU0NjYzITIWFhUUBgYjIxMTNjYzMhYXExMjIiYmNTQ2NjMhBLkaDQ0aGDhlAxYyLkI7DKCiDDxDLjEVA2EyGBoNDRoYAYoYGg0NGhh1NZIHKC8yLAaTNmcYGg0NGhgBdgSjESwqKiwQ/FUZHAweIwHX/ikjHgwcGQOrECwqKiwRESwqKiwQ/bgBrBcYExX+TQJIECwqKiwRAAEAHgAABK4EowBTAEBAPUgzHgkEAQABTAoJBwMAAAhfDAsCCAgiTQYEAwMBAQJfBQECAiMCTgAAAFMAUUtJR0U2IiY2IiY2IiYNCB8rABYWFRQGBiMjAQEzMhYWFRQGBiMhIiYmNTQ2NjMzJwczMhYWFRQGBiMhIiYmNTQ2NjMzAQEjIiYmNTQ2NjMhMhYWFRQGBiMjFzcjIiYmNTQ2NjMhBGkaDQ0aGDj+9gEjPRgaDQ0aGP5sGBoNDRoYNK2rJhgaDQ0aGP6AGBoNDRoYPgEj/vk8GBoNDRoYAYoYGg0NGhgrkpEYGBoNDRoYAWwEoxEsKiosEP6G/nERLCoqLBAQLCoqLBH09BEsKiosEBAsKiosEQGaAW8QLCoqLBERLCoqLBDR0RAsKiosEQAAAQAoAAAEpASjAD4AN0A0Mx4JAwEAAUwHBgQDAAAFXwkIAgUFIk0DAQEBAl8AAgIjAk4AAAA+ADwiJjYiJjYiJgoIHisAFhYVFAYGIyMBFTMyFhYVFAYGIyEiJiY1NDY2MzM1ASMiJiY1NDY2MyEyFhYVFAYGIyMTEyMiJiY1NDY2MyEEfRoNDRoYLP6qxBgaDQ0aGP1+GBoNDRoYxP6sLhgaDQ0aGAGKGBoNDRoYQ7q8NRgaDQ0aGAF2BKMRLCoqLBD99f4RLCoqLBAQLCoqLBH/AgoQLCoqLBERLCoqLBD+3AEkECwqKiwRAAABAIoAAAQ4BKMAJwBkS7AKUFhAIwAEAwEDBHIAAQAAAXAAAwMFXwYBBQUiTQAAAAJgAAICIwJOG0AlAAQDAQMEAYAAAQADAQB+AAMDBV8GAQUFIk0AAAACYAACAiMCTllADgAAACcAJSMWNSMWBwgbKwAWFhUUBwEhNTQ2MzIWFREUBiMhIiYmNTQ3ASEVFAYjIiY1ETQ2MyEEERoNF/3CAW86QD4uHiP80hgaDRQCPv6yOkA+Lh8iAxAEoxEsKj0f/PfeIh0cI/6MIh8QLCpCGwMJyiIdHCMBYCMeAAABASL+swOeBVwAFwApQCYAAQACAwECZwQBAwAAA1cEAQMDAF8AAAMATwAAABcAFiQ1NAUIGSsEFhUUBiMhIiY1ETQ2MyEyFhUUBiMhESEDghwcI/4CIh0dIgH+IxwcI/69AUNsL0JCLh0iBisiHS9CQi77GQAAAQCf/pgELQV3AA8AS7YMBAIAAQFMS7AbUFhADAIBAQEqTQAAACcAThtLsCRQWEAMAgEBAAGFAAAAJwBOG0AKAgEBAAGFAAAAdllZQAoAAAAPAA4mAwgXKwAXARYVFAYjIicBJjU0NjMBfRICmgRbQ0AS/WYEW0MFdyv5rgkLIiwrBlIJCyIsAAEBLv6zA6oFXAAXAChAJQQBAwACAQMCZwABAAABVwABAQBfAAABAE8AAAAXABUhJDUFCBkrABYVERQGIyEiJjU0NjMhESEiJjU0NjMhA40dHSL+AiMcHCMBQ/69IxwcIwH+BVwdIvnVIh0uQkIvBOcuQkIvAAABAMEB1AQLBLkAHQApsQZkREAeFw4FAwACAUwDAQIAAoUBAQAAdgAAAB0AHCYpBAgYK7EGAEQAFhcBFhUUBgcGIyImJwMDBgYjIicmJjU0NwE2NjMCkC8JAT4FNikiHB0pB7u7BykdHCIpNgUBPgkuKwS5EhP9ngoIFyMKCA8OAYb+eg4PCAojFwgKAmITEgAB/9r9/wTy/uAAEQAgsQZkREAVAAEAAAFXAAEBAF8AAAEATycmAggYK7EGAEQAFhYVFAYGIyEiJiY1NDY2MyEE3g4GBg4N+yoNDgYGDg0E1v7gETAwMC8RES8wMDARAAABARQD/QM0BaQAEQAZsQZkREAOAAEAAYUAAAB2GBQCCBgrsQYARAAVFAcGIyInJSY1NDc2MzIXBQM0FiAkDAv+aRgoOS4REAFbBIscHCMzBs0MICc2Swv/AAACAG7/6gSbA7IAMgA+AORLsCBQWEAPHwEIAzw7AgAIEwEBAANMG0APHwEIAzw7AgAIEwEBBwNMWUuwF1BYQCkABQQDBAUDgAADCgEIAAMIaQAEBAZhCQEGBitNBwEAAAFhAgEBASMBThtLsCBQWEAzAAUEAwQFA4AAAwoBCAADCGkABAQGYQkBBgYrTQcBAAABYQABASNNBwEAAAJhAAICKQJOG0AxAAUEAwQFA4AAAwoBCAADCGkABAQGYQkBBgYrTQAAAAFhAAEBI00ABwcCYQACAikCTllZQBczMwAAMz4zPTk3ADIAMSMkJSQ2NQsIHCsAFhURFBYzMzIWFhUUBgYjIyImJwYGIyImJjU0NjMyFzU0JiMiBgcGIyImJyY1NDc2NjMCBhUUFjMyNjc1JiMDN8QiIB8YGg0NGhhwPl8ZT7BdcaRXxrKFllRqO5FHEQwZJxAPLlnIWKJJR0NFhzuEfgOyvrH+3ygtESwqKiwQMzc9Q02PYYyaHh1DQB0YBSUsLBwzESAg/c0yMC8xNzBAGwAAAgAb/+oEawUgACoAOgDHS7AXUFhACgMBBwARAQEDAkwbQAoDAQcAEQECAwJMWUuwF1BYQCMABAQFXwgBBQUkTQkBBwcAYQAAACtNBgEDAwFhAgEBASkBThtLsCBQWEAtAAQEBV8IAQUFJE0JAQcHAGEAAAArTQYBAwMCXwACAiNNBgEDAwFhAAEBKQFOG0ArCAEFAAQABQRpCQEHBwBhAAAAK00GAQMDAl8AAgIjTQYBAwMBYQABASkBTllZQBYrKwAAKzorOTMxACoAKCEmNSYlCggbKwAWFRE2NjMyFhYVFAYGIyImJxUUBiMjIiYmNTQ2NjMzESMiJiY1NDY2MyESBgYVFBYWMzI2NjU0JiYjAZgdM4ZOg8RoaMSDX5w0HSLgGBoNDRoYTWEYGg0NGhgBHN5oPj5oQD5cMTFcPgUgHSL+Wzk9gNyIiNyAWVBUIh0RLCoqLBADhhAsKiosEf2vPHVQUHU8P3ROTnQ/AAABAH//6gQ2A7IAMgBDQEAuAQEFAUwAAwACAAMCgAABAQVhBwYCBQUrTQAAAAVhBwYCBQUrTQACAgRhAAQEKQROAAAAMgAxJicjJiYlCAgcKwAWFREUBiMiJiY1NCYmIyIGBhUUFhYzMjY3NjMyFxYVFAcGBiMiJiY1NDY2MzIXNTQ2MwP5Lj1HLzMUKVE5SGw7O2xITaFMEg8tIhIrXc1nmOZ9ftmGokM6QAOyHCP+vyIdDRoYKkgrP3VNTXU/MiwKTyseLRg0OnzcjIzde3U2Ih0AAAIAYf/qBKcFIAAqADoAtEAKHwEHAxEBAQACTEuwF1BYQCMABAQFXwgBBQUkTQkBBwcDYQADAytNBgEAAAFhAgEBASMBThtLsCBQWEAtAAQEBV8IAQUFJE0JAQcHA2EAAwMrTQYBAAABXwABASNNBgEAAAJhAAICKQJOG0ArCAEFAAQDBQRnCQEHBwNhAAMDK00GAQAAAV8AAQEjTQYBAAACYQACAikCTllZQBYrKwAAKzorOTMxACoAKCMmJTYjCggbKwAWFREzMhYWFRQGBiMjIiY1NQYGIyImJjU0NjYzMhYXESMiJiY1NDY2MyEABgYVFBYWMzI2NjU0JiYjA/QdVxgaDQ0aGOoiHTScX4PEaGjEg06GM5MYGg0NGhgBTv4oXDExXD5AaD4+aEAFIB0i++wQLCoqLBEdIlRQWYDciIjcgD05ARcQLCoqLBH9rz90Tk50Pzx1UFB1PAAAAgCD/+oETwOyACEAJwA/QDwAAgABAAIBgAAFAAACBQBnCAEGBgRhBwEEBCtNAAEBA2EAAwMpA04iIgAAIiciJiQjACEAICkTIiUJCBorABYWFRQGIyEWFjMyNzYzMhYXFhUUBgcGBiMiJiY1NDY2MwYHISYmIwMM1m0dIv1+E31gm7UMDBYgDQoXGmTQZJjcc3jil7crAbgRb1YDsoPpliIcUFU3BCgwJRoaHQkhJnzbjYzcfOOaSVEAAQCnAAAEZAUlADkAcEuwIFBYQCkAAAECAQACgAgBAgcBAwQCA2cAAQEJYQoBCQkkTQYBBAQFXwAFBSMFThtAJwAAAQIBAAKACgEJAAEACQFpCAECBwEDBAIDZwYBBAQFXwAFBSMFTllAEgAAADkAOCQhJjYhJCIjGAsIHysAFxYWFRQHBgYjIicmIyIVFSEyFhUUBiMhESEyFhYVFAYGIyEiJiY1NDY2MzMRIyImNTQ2MzM1NDYzA5qYGRkKDCMYDBF/X4EBNyMcHCP+yQEZGBoNDRoY/TYYGg0NGhi3tyMcHCO3t64FJTkJIRwaJCwmBSemPC4+Pi3+RBEsKiosEBAsKiosEQG8LT4+Lkm6wgACAGH+ZgSnA7IAMQA/AJJACgIBAQAmAQUHAkxLsBdQWEArAAMFBAUDBIAKCAIBAQBhCQYCAAAlTQAHBwVhAAUFI00ABAQCYQACAi0CThtANgADBQQFAwSACggCAQEGYQkBBgYrTQoIAgEBAF8AAAAlTQAHBwVhAAUFI00ABAQCYQACAi0CTllAFzIyAAAyPzI+ODYAMQAwJSMYIyY1CwgcKwAWFzU0NjMzMhYWFRQGBiMjERQGIyImJyY1NDc2NjMyFxYzMjY1NQYGIyImJjU0NjYzBgYVFBYzMjY2NTQmJiMCb5w0HSLqGBoNDRoYV+vqVsxdMA0PJRkNC790eWwzhk6BxGpqxIE1bm5dQGk9PWlAA7JQS0YiHREsKiosEP0yxNchHQ82GC4vKgQ7ZWdmNzx51YeH1Xnjf3NzfzdtTk5tNwABAC8AAASlBSAARABttQMBBAABTEuwIFBYQCQACAgJXwoBCQkkTQAEBABhAAAAK00HBQMDAQECXwYBAgIjAk4bQCIKAQkACAAJCGkABAQAYQAAACtNBwUDAwEBAl8GAQICIwJOWUASAAAARABCISY2JCMmNiQkCwgfKwAWFRE2MzIWFhURMzIWFhUUBgYjISImJjU0NjYzMxE0JiMiBgYVFTMyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzIQGsHXiqW4lKTRgaDQ0aGP6KGBoNDRoYLzY/Omg/LxgaDQ0aGP6KGBoNDRoYTWEYGg0NGhgBHAUgHSL+GrdQk2P+YREsKiosEBAsKiosEQFkTlBholyjESwqKiwQECwqKiwRA4YQLCoqLBH//wCnAAAESQVTACIBZQAAAAIBLQ4AAAD//wCf/mYDmwVTACIBKQAAAAMBLQC4AAAAAQA5AAAEkQUgAEEAcUAJPy4LCgQBBgFMS7AgUFhAJAAEBAVfAAUFJE0IAQYGB18ABwclTQoJAwMBAQBfAgEAACMAThtAIgAFAAQHBQRpCAEGBgdfAAcHJU0KCQMDAQEAXwIBAAAjAE5ZQBIAAABBAEAkNCQ2ISY2JDULCB8rJBYVFAYGIyMiJwMHFTMyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzITIWFRElIyImNTQ2MyEyFhUUBiMjBxMzBHUcDRoYqzIc/IpXGBoNDRoY/mIYGg0NGhhNYRgaDQ0aGAEcIh0BBDIjHBwjAZ4jHBwjKPnzPc0qPSosECgBXmlQESwqKiwQECwqKiwRA4YQLCoqLBEdIv0u1CY2NyYmNzYmyf6zAAABAJ0AAAQ/BSAAIQBHS7AgUFhAFwADAwRfBQEEBCRNAgEAAAFfAAEBIwFOG0AVBQEEAAMABANnAgEAAAFfAAEBIwFOWUANAAAAIQAfISY2IwYIGisAFhURITIWFhUUBgYjISImJjU0NjYzIREjIiYmNTQ2NjMhAsodARkYGg0NGhj83BgaDQ0aGAER6RgaDQ0aGAGkBSAdIvvsESwqKiwQECwqKiwRA4YQLCoqLBEAAAH/8gAABIwDsgA/AJxLsBBQWLY8NwIBBgFMG0AKPAEFBjcBAQUCTFlLsBBQWEAXBQMCAQEGYQkIBwMGBiVNBAICAAAjAE4bS7AXUFhAIwAFBQZhCQgHAwYGJU0DAQEBBmEJCAcDBgYlTQQCAgAAIwBOG0AfAAUFBl8ABgYlTQMBAQEHYQkIAgcHK00EAgIAACMATllZQBEAAAA/AD4lNiM1JTUlNQoIHisAFhURFAYjIyImNRE0JiMiBhURFAYjIyImNRE0JiMiBhURFAYjIyImNREjIiYmNTQ2NjMzMhYVFTY2MzIXNjYzBCJqHSJ8Ih0ZGy83HSJ8Ih0ZGy83HSJ8Ih05GBoNDRoYriIdL39MlCsuekcDspaZ/bwiHR0iAgs1MpKM/qwiHR0iAgs1MpKM/qwiHR0iApAQLCoqLBEdIpBxdMtkZwABADkAAASvA7IARABptUIBAAMBTEuwF1BYQBwHAQMDCGEKCQIICCVNBgQCAwAAAV8FAQEBIwFOG0AmBwEDAwlhCgEJCStNBwEDAwhfAAgIJU0GBAIDAAABXwUBAQEjAU5ZQBIAAABEAEM2ISY2JCMmNiQLCB8rABYWFREzMhYWFRQGBiMhIiYmNTQ2NjMzETQmIyIGBhUVMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMzMhYVFTYzA1CJSk0YGg0NGhj+ihgaDQ0aGC82PzpoPy8YGg0NGhj+ihgaDQ0aGE1hGBoNDRoY9CIdhMYDslCTY/5hESwqKiwQECwqKiwRAWROUGGiXKMRLCoqLBAQLCoqLBECAhAsKiosER0ikeYAAgBv/+oEXQOyAA8AHwAsQCkFAQMDAWEEAQEBK00AAgIAYQAAACkAThAQAAAQHxAeGBYADwAOJgYIFysAFhYVFAYGIyImJjU0NjYzDgIVFBYWMzI2NjU0JiYjAv7ke3vkmJjke3vkmEhqOTlqSEhqOTlqSAOyfNyMjNx8fNyMjNx84z90Tk50Pz90Tk50PwAAAgAl/nwEawOyADAAQACEQAotAQQFCgEABwJMS7AXUFhAJAoIAgQEBWEJBgIFBSVNAAcHAGEAAAApTQMBAQECXwACAicCThtALwoIAgQEBmEJAQYGK00KCAIEBAVfAAUFJU0ABwcAYQAAAClNAwEBAQJfAAICJwJOWUAXMTEAADFAMT85NwAwAC82ISY2IyYLCBwrABYWFRQGBiMiJicRMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMzMhYVFTY2Mw4CFRQWFjMyNjY1NCYmIwM/xGhoxINOhjOnGBoNDRoY/ggYGg0NGhhXVxgaDQ0aGOoiHTScX2hoPj5oQD5cMTFcPgOygNyIiNyAPTn+6RAsKiosERAsKiosEQOGECwqKiwRHSJUUFnjPHVQUHU8P3ROTnQ/AAACAGH+fASnA7IAMABAAIRACgIBAQAlAQUHAkxLsBdQWEAkCggCAQEAYQkGAgAAJU0ABwcFYQAFBSlNBAECAgNfAAMDJwNOG0AvCggCAQEGYQkBBgYrTQoIAgEBAF8AAAAlTQAHBwVhAAUFKU0EAQICA18AAwMnA05ZQBcxMQAAMUAxPzk3ADAALyMmNiEmNQsIHCsAFhc1NDYzMzIWFhUUBgYjIxEzMhYWFRQGBiMhIiYmNTQ2NjMzEQYGIyImJjU0NjYzDgIVFBYWMzI2NjU0JiYjAm+cNB0i6hgaDQ0aGFdXGBoNDRoY/ggYGg0NGhinM4ZOg8RoaMSDFlwxMVw+QGg+PmhAA7JZUFQiHREsKiosEPx6ESwqKiwQESwqKiwQARc5PYDciIjcgOM/dE5OdD88dVBQdTwAAAEAfwAABGsDsgA2ALZLsAxQWLUzAQAFAUwbtTMBAAEBTFlLsAxQWEAlAAUFBmEIBwIGBiVNAQEAAAZhCAcCBgYlTQQBAgIDXwADAyMDThtLsBdQWEAsAAABAgEAAoAABQUGYQgHAgYGJU0AAQEGYQgHAgYGJU0EAQICA18AAwMjA04bQCkAAAECAQACgAAFBQZfAAYGJU0AAQEHYQgBBwcrTQQBAgIDXwADAyMDTllZQBAAAAA2ADU2ISY2JCMXCQgdKwAXFhUUBwYGIyInJiMiBgYVFSEyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzITIWFRU2NjMD9EssEhItGQ4QODxNhlEBHxgaDQ0aGP1UGBoNDRoYk3UYGg0NGhgBEiIdS8NkA7I4IDQhLS0uCB9irGpfESwqKiwQECwqKiwRAgIQLCoqLBEdItmRnQAAAQCk/+oELgOyAEQATEBJQAEBBh4BAgUCTAABAQZhCAcCBgYrTQAAAAZhCAcCBgYrTQAEBAJhAwECAilNAAUFAmEDAQICKQJOAAAARABDLiMlJC8jJQkIHSsAFhUVFAYjIicmJiMiBhUUFxYXFhYXFhYVFAYGIyInFRQGIyImNTU0NjMyFxYWMzI1NCYnJicmJicmNTQ2NjMyFzU0NjMDyjYrMTUUO5hkO0NKJ15dezdQWl2zfot3OkBANi8xPRYynF2gLSwZW2WRO4pepWeXdTE/A7IdItMiHRU/NSojKhIKCQsWFiF2YV+LS0cIIh0dIt8hHhw/OlMZHgoFDQwfIUykV4JFSQoiHQABAGH/6gRVBLkALgA2QDMAAwECAQMCgAYBAAUBAQMAAWcIAQcHKE0AAgIEYQAEBCkETgAAAC4ALSQjKCMiJCQJCB0rABYWFREhMhYVFAYjIREUMzI2NzYzMhYXFhUUBgcGIyImNREjIiY1NDYzMxE0NjMCFDMUAXMjHBwj/o2BLntSFg0VJBASFRXOl663wSMcHCPBPUcEuQ0aGP7mLj4+Lf7qpiklCSMoLRwWHQtowroBIy0+Pi4BGiIdAAEAMv/qBJQDnAA4AGO1EQEAAwFMS7AXUFhAGgYBAwMEXwgHAgQEJU0FAQAAAWECAQEBIwFOG0AkBgEDAwRfCAcCBAQlTQUBAAABXwABASNNBQEAAAJhAAICKQJOWUAQAAAAOAA2JCU2JCQ2IwkIHSsAFhURMzIWFhUUBgYjIyImNTUGIyImJjURIyImJjU0NjYzITIWFREUFjMyNjY1NSMiJiY1NDY2MyED6x1NGBoNDRoY4CIdhMZbiUpNGBoNDRoYAQgiHTY/Omg/axgaDQ0aGAEmA5wdIv1wECwqKiwRHSKR5lCTYwGfESwqKiwQHSL+Dk5QYaJcoxEsKiosEAABACj/6gSkA5wALwAtQCokAQEAAUwFBAIDAAADXwcGAgMDJU0AAQEpAU4AAAAvAC0iJjYjIyYICBwrABYWFRQGBiMjAQYGIyImJwEjIiYmNTQ2NjMhMhYWFRQGBiMjExMjIiYmNTQ2NjMhBH0aDQ0aGET+2w9ERkZCD/7dQhgaDQ0aGAGUGBoNDRoYQ7GzNxgaDQ0aGAGAA5wRLCoqLBD9XCMeHiMCpBAsKiosEREsKiosEP5HAbkQLCoqLBEAAf/s/+oE4AOcAD8AOkA3NCwQAwEAAUwABgQABAYAgAcFAwMAAARfCQgCBAQlTQIBAQEpAU4AAAA/AD0kJCY2IyYjJgoIHisAFhYVFAYGIyMDBgYjIiYnAwMGBiMiJicDIyImJjU0NjYzITIWFhUUBgYjIxMTNjYzMhYXExMjIiYmNTQ2NjMhBLkaDQ0aGCmSCDU8OjgNjI4OODs8MwiPIhgaDQ0aGAFYGBoNDRoYVUuKCywpKysLiU5IGBoNDRoYAU4DnBEsKiosEP1cJB0eIwFj/p0jHh0kAqQQLCoqLBERLCoqLBD+fAFTHB0YGv6mAYQQLCoqLBEAAAEARgAABIYDnABTAEBAPUgzHgkEAQABTAoJBwMAAAhfDAsCCAglTQYEAwMBAQJfBQECAiMCTgAAAFMAUUtJRkU2IiY2IxY2IiYNCB8rABYWFRQGBiMjBwEzMhYWFRQGBiMhIiYmNTQ2NjMzJwczMhYWFRQGBiMhIiYmNTQ2NjMzEycjIiYmNTQ2NjMhMhYWFRQGBiMjFzcjIiYmNTQ2NjMhBFUaDQ0aGDvxAQMzGBoNDRoY/oAYGg0NGhgOg3wRGBoNDRoY/p4YGg0NGhg2/vY0GBoNDRoYAXYYGg0NGhgNgHkWGBoNDRoYAWIDnBEsKiosEPv++REsKiosEBAsKiosEYaGESwqKiwQECwqKiwRAQj6ECwqKiwRESwqKiwQg4MQLCoqLBEAAQAo/mUEpAOcADcANEAxLBcCAgABTAYFAwMAAARfCAcCBAQlTQACAgFhAAEBLQFOAAAANwA1IiY2JBUkJgkIHSsAFhYVFAYGIyMBDgIHBiY1NDY3PgI3ASMiJiY1NDY2MyEyFhYVFAYGIyMTEyMiJiY1NDY2MyEEfRoNDRoYQP6BRn+jgSQlGxlPY1E5/s5LGBoNDRoYAZQYGg0NGhg8rq42GBoNDRoYAYADnBEsKiosEPz4jZM9BAE4SjMsAgUybW4CdRAsKiosEREsKiosEP6EAXwQLCoqLBEAAAEAigAABDgDnAArAGRLsA5QWEAjAAQDAQMEcgABAAABcAADAwVfBgEFBSVNAAAAAmAAAgIjAk4bQCUABAMBAwQBgAABAAMBAH4AAwMFXwYBBQUlTQAAAAJgAAICIwJOWUAOAAAAKwApIxc2IxcHCBsrABYWFRQGBwEhNTQ2MzIWFhURFAYjISImJjU0NjcBIRUUBiMiJiY1NTQ2MyEEERoNDhL99QFFNEYvLg8eI/zSGBoNDhICC/7PNEYvLg8fIgMaA5wQLCobJBP96XwjHAwaGf74Ih8QLCobJBMCF3IjHAwaGf4jHgABAKX+swPmBVwAQQBsQA47AQQADwEDBCkBAQMDTEuwIFBYQBsABAADAQQDaQABAAIBAmUAAAAFYQYBBQUqAE4bQCEGAQUAAAQFAGkABAADAQQDaQABAgIBWQABAQJhAAIBAlFZQBIAAABBAEA3NS8tJCIdGyUHCBcrABYVFAYGIyIGBh8CFAYHFRYWFRQHBwYVFBYWMzIWFhUUBiMiJjU0Nzc2NTQmIyImJjU0NjYzMjY1NCcnJjU0NjMDyhwMGxhiaycEBQFse3tvAQkBLmpaGBsMHCP78gMNAXdwGBoNDRoYcHMBCgPy/AVcKz4uLhArW05hGmmJIwoiimYUCoMMGENQJw8uLj4ssbodH48IEFVdES4sLC0RXFUQCW0eHLWuAAEB6f6dAuMFcgANADZLsCBQWEAMAgEBASpNAAAAJwBOG0ASAgEBAAABWQIBAQEAYQAAAQBRWUAKAAAADQAMJQMIFysAFhURFAYjIiY1ETQ2MwKtNkJCQDZCQgVyHSL5qSEeHSIGVyEeAAABAOb+swQnBVwAQgBpQA4FAQAEMAEBABcBAwEDTEuwIFBYQBsAAAABAwABaQADAAIDAmUABAQFYQYBBQUqBE4bQCEGAQUABAAFBGkAAAABAwABaQADAgIDWQADAwJhAAIDAlFZQA8AAABCAEE8OiUpJikHCBorABYVFAcHBhUUFjMyFhYVFAYGIyIGFRQXFxYVFAYjIiY1NDY2MzI2NjU0JycmNTQ2NzUmJjc3NjU0JiYjIiYmNTQ2MwIh8gMKAXNwGBoNDRoYcHcBDQPy+yMcDBsYWmouAQkBb3uDaQYFAS1oXBgbDBwjBVyutRwebQkQVVwRLSwsLhFdVRAIjx8durEsPi4uDydQQxgMgwoUZooiCiWWdGEKEkNPJhAuLj4rAAEAgQGMBEsC/QAnAHCxBmREtiIOAgMAAUxLsAxQWEAbAAADAgBZBgUCAQADAgEDaQAAAAJhBAECAAJRG0ApAAEFAAUBAIAABAMCAwQCgAAAAwIAWQYBBQADBAUDaQAAAAJhAAIAAlFZQA4AAAAnACYjJCcjJAcIGyuxBgBEABYXFhYzMjY3NjMyFxYVFAcGBiMiJicmJiMiBgcGIyInJjU0NzY2MwHjXkI1SiQnPSASFiEpLw07i1o2YUA2SCMnPSASFiEpLw07i1oC/SMiHB0gIhMlKSURFVdYJCIcHCAiEyUpJREVV1gAAAIByP6nAwQDpgANABoAS0uwF1BYQBcEAQEBAGEAAAAlTQACAgNfBQEDAycDThtAFAACBQEDAgNjBAEBAQBhAAAAJQFOWUASDg4AAA4aDhgUEgANAAwlBggXKwAmNTU0NjMyFhUVFAYjAiY3EzYzMhcTFgYjIwIUSUlSUklJUooUAjkFXl4FOQIUF+YCUh0i1iIdHSLWIh38VRgaApE6Ov1vGhgAAgB//4MENgUgADgAPwBjQBE8MR8dFQUDAjsyDQUEAAQCTEuwIFBYQBsABAMAAwQAgAACAAMEAgNpAAAAAWEAAQEkAE4bQCAABAMAAwQAgAABAgABWQACAAMEAgNpAAEBAGEAAAEAUVm3KiUoLigFCBsrABUUBwYHFRQGIyImNTUuAjU0NjY3NTQ2MzIWFRUWFzU0NjMyFhURFAYjIiYmNTQmJxE2NzYzMhckFhcRBgYVBDYrnKgmNzcmerNhZrVzJjc3Jk8rOkA+Lj1HLzMUNTF2dxIPLSL9Z0U9PUUBRx4tGFcTuCMcHCO9FYPJen7NghGpIxwcI7MbSjYiHRwj/r8iHQ0aGDBPEf4RE0UKT5V6HQHUHXpTAAEAlv/cBCUEuQBcAYRLsA5QWEAKCwEAASMBBwQCTBtLsB1QWEAKCwEAASMBCAQCTBtACgsBAAEjAQgFAkxZWUuwDlBYQCwAAAECAQACgAsBAgoBAwQCA2cAAQEMYQ0BDAwoTQYFAgQEB2EJCAIHBykHThtLsBlQWEAwAAABAgEAAoALAQIKAQMEAgNnAAEBDGENAQwMKE0ACAgjTQYFAgQEB2EJAQcHKQdOG0uwHVBYQDcAAAECAQACgAAGAwQDBgSACwECCgEDBgIDZwABAQxhDQEMDChNAAgII00FAQQEB2EJAQcHKQdOG0uwLVBYQD0AAAECAQACgAAGAwQDBgSAAAQFAwQFfgsBAgoBAwYCA2cAAQEMYQ0BDAwoTQAICCNNAAUFB2EJAQcHKQdOG0BBAAABAgEAAoAABgMEAwYEgAAEBQMEBX4LAQIKAQMGAgNnAAEBDGENAQwMKE0ACAgjTQAFBQdhAAcHKU0ACQkpCU5ZWVlZQBgAAABcAFtVU01LQj8kKBMiJCY3JCYOCB8rABcWFRUUBiMiJjU1JiMiBhUUFhcWFhchMhYWFRQGBiMjBgYHNjMyFxYzMjc2MzIWFxYVFAcGBiMiJicmJiMiBwYjIiYnJjU0NzY2NyMiJiY1NDY2MzMmJjU0NjYzAw6tLjpAPi5ATz5HHh4EDAYBIBgaDQ0aGPEIOjFLQicxNhpCQwcJFCkOExU7bDcfPiszSylycgQIEykQFRVZUwSiGBoNDRoYXyAjWqt2BLlZGCfPIh0cI28fST0rSTQIEw0SMC8vMBE7ajUcCQghBCgfKCUlDiwkCQgKCi8CKB4sISMPRnROETAvLzASPWI6YptZAAIAZgBbBGYEWgA/AE8ARkBDOi4qHgQHBD4aDgoEAQYCTAUBAwQAA1kABAAHBgQHaQAGAAEABgFpBQEDAwBhAgEAAwBRTEpEQjIwLSsoJiMjJggIGSskFRQGBwYGIyInJwYjIicHBiMiJicmJjU0NzcmNTQ3JyY1NDY3NjYzMhcXNjMyFzc2MzIWFxYWFRQHBxYVFAcXABYWMzI2NjU0JiYjIgYGFQRmGx4dKA8SFYVbbGxbhRUSDygdHhsVgzIyghUaHh4oDxIVhVltbVmFFRIPKB4eGhWCMjKD/VkvVjc3Vi8vVjc3Vi/6Eg8oHh4aFYUvL4UVGh4eKA8SFYNbbW5cghUSDygdHhsVhS4uhRUbHh0oDxIVglxubVuDARVWMDBWNjZWMDBWNgABACgAAASkBKMAYABYQFVVAQIBAUwLAQEKAQIDAQJnCQEDCAEEBQMEZw8ODAMAAA1fERACDQ0iTQcBBQUGXwAGBiMGTgAAAGAAXlhWVFJMSUNBQD46ODc1ISY2ISQhJCEmEggfKwAWFhUUBgYjIwczMhYVFAYjIwczMhYVFAYjIRUzMhYWFRQGBiMhIiYmNTQ2NjMzNSEiJjU0NjMzJyMiJjU0NjMzJyMiJiY1NDY2MyEyFhYVFAYGIyMTEyMiJiY1NDY2MyEEfRoNDRoYLF05IxwcI7Je/CMcHCP+4sQYGg0NGhj9fhgaDQ0aGMT+4iMcHCP8XbMjHBwjOlwuGBoNDRoYAYoYGg0NGhhDurw1GBoNDRoYAXYEoxEsKiosEI4mNzYmjyY3NiZ6ESwqKiwQECwqKiwReiY2NyaPJjY3Jo4QLCoqLBERLCoqLBD+3AEkECwqKiwRAAIB6f6dAuMFcgANABsAUkuwIFBYQBcAAAABYQQBAQEqTQUBAwMCYQACAicCThtAGwQBAQAAAwEAaQUBAwICA1kFAQMDAmEAAgMCUVlAEg4OAAAOGw4aFRMADQAMJQYIFysAFhURFAYjIiY1ETQ2MxIWFREUBiMiJjURNDYzAq02QkJANkJCQDZCQkA2QkIFch0i/ZEhHh0iAm8hHvwYHSL9kSEeHSICbyEeAAACAJ//GgQtBKMAOwBLAG9ADzQBAAFLQwIDABYBBAMDTEuwDlBYQCAAAAEDAQByAAMEBANwAAQAAgQCZAABAQVfBgEFBSIBThtAIgAAAQMBAAOAAAMEAQMEfgAEAAIEAmQAAQEFXwYBBQUiAU5ZQA4AAAA7ADkjJT8jJQcIGysAFhURFAYjIiY1NSMiBhUUFwUWFhUUBxYVFAYGIyEiJjURNDYzMhYVFTMyNjU0JyUmJjU0NyY1NDY2MyEAFRQWFwUWFzY1NCYnJSYnA9weOkA+LsErLlYBI1pgcg9Gh2D+diIfOkA+LsErLlb+3VpgcQ5Gh2ABiv3eMDQBCRUPDTA0/vcNGASjHiP++iIdHCOEJSNFKpEtlGGLXy02UXpEHiMBBiIdHCOEJSNFKpEtlGGMXTA0UXpE/ckcJzwahAsJFhwnPBqEBg4AAgENBDEDvwVTAA0AGwA0sQZkREApBQMEAwEAAAFZBQMEAwEBAGECAQABAFEODgAADhsOGhUTAA0ADCUGCBcrsQYARAAWFRUUBiMiJjU1NDYzIBYVFRQGIyImNTU0NjMBzjk1RkY5NEYB/zk1RkY5NEYFUx0ipCIdHSKkIxwdIqQiHR0ipCMcAAMAHP/qBK4EuQAPAB8ASwChsQZkREAKOAEGBD0BBwYCTEuwEFBYQCwJAQEKAQMIAQNpCwEIBQEEBggEaQAGAAcCBgdpAAIAAAJZAAICAGEAAAIAURtAMwAEBQYFBAaACQEBCgEDCAEDaQsBCAAFBAgFaQAGAAcCBgdpAAIAAAJZAAICAGEAAAIAUVlAICAgEBAAACBLIEpEQjUzLy0rKRAfEB4YFgAPAA4mDAgXK7EGAEQABBIVFAIEIyIkAjU0EiQzDgIVFBYWMzI2NjU0JiYjFhYXFhYVFAcGBiMiJyYjIgYVFBYzMjc2MzIWFxYVFAYHBgYjIiYmNTQ2NjMDDAELl5f+9aen/vWXlwELp4HEa2vEgYHEa2vEgUlhKhIRDAwXEQoJUDpHU1NHOlAJChEXDAwREiphL2CXVVWXYAS5of7nra3+5qGhARqtrQEZoZl404OD03l504OD03h3FhUJGBEVIB8cBBxaUVFaHAQcHx8WERgJFRZTm2pqm1MAAAIA5QHRBBsEuQAtADkAWEBVGwEIAzc2AgAIEAEBBwNMAAUEAwQFA4AJAQYABAUGBGkAAwoBCAADCGkAAAABYQABATNNAAcHAmEAAgI1Ak4uLgAALjkuODQyAC0ALBMkJCM0NQsJHCsAFhUVFBYzMzIWFRQGIyMiJwYGIyImNTQ2MzIXNTQmIyIHBiMiJicmNTQ3NjYzAgYVFBYzMjY3NSYjAwmXGhgYGxYVHFZmJj2IR4OUmIljdkRRU30LCxUeDAojRptBfTg3MzVoLWVhBLmSiN4fIiAwLx9RLzODcWt3FxYyMykEIiQcEyQNGhv+TyckJCYrJDIUAAABAHgA9QRKA00AFQAlQCIAAAEAhgMBAgEBAlcDAQICAV8AAQIBTwAAABUAEyQlBAgYKwAWFREUBiMiJiY1ESEiJiY1NDY2MyEELB49Ry8zFP1nGBoNDRoYA1IDTR4j/igiHQ0aGAFCES4tLS0RAAQAfQE0BE0FNgAPAB8APQBGAGexBmREQFwmAQUIAUwGAQQFAgUEAoAKAQELAQMHAQNpDAEHAAkIBwlpAAgABQQIBWcAAgAAAlkAAgIAYQAAAgBRICAQEAAARkRAPiA9IDs2NDEwLiwQHxAeGBYADwAOJg0IFyuxBgBEABYWFRQGBiMiJiY1NDY2Mw4CFRQWFjMyNjY1NCYmIx4CFRQGBxcWFRQHBiMiJycjFRQGIyImNRE0NjMzAzMyNjU0JiMjAvDffn7fi4vffn7fi2ukWVmka2ukWVmka2dcMjQxQBElIhMUEmM+HCsrHBkcxGtSJSomIVoFNobqkJDrh4frkJDqhoBkr21usGRksG5tr2RzN102OFUXSRQQFhoXF4BaHxcXHwGwHRj+9iIeHSMAAQEYBC4DtAT7ABEAJ7EGZERAHAIBAQAAAVcCAQEBAF8AAAEATwAAABEADzYDCBcrsQYARAAWFhUUBgYjISImJjU0NjYzIQONGg0NGhj94hgaDQ0aGAIeBPsRLCoqLBAQLCoqLBEAAgDcAjUDYAS5AA8AGwA3sQZkREAsBAEBBQEDAgEDaQACAAACWQACAgBhAAACAFEQEAAAEBsQGhYUAA8ADiYGCBcrsQYARAAWFhUUBgYjIiYmNTQ2NjMGBhUUFjMyNjU0JiMCdZRXV5RXV5RXV5RXLkFBLi5BQS4EuVeUV1eUV1eUV1eUV9NBLi5BQS4uQQAAAgCqAAAEIgRmACcAOQA4QDUEAQADAQECAAFnCAEFAAIHBQJpCQEHBwZfAAYGIwZOKCgAACg5KDcxLgAnACYmJCQmJAoIGysAFhYVFSEyFhYVFAYGIyEVFAYGIyImJjU1ISImJjU0NjYzITU0NjYzABYWFRQGBiMhIiYmNTQ2NjMhApUwEQENGBoNDRoY/vMRMC8vMBL+9BgaDQ0aGAEMEjAvAZUaDQ0aGP0GGBoNDRoYAvoEZg0aGNoSMC8vMBHbGBoNDRoY2xEwLy8wEtoYGg38exIwLy8wEREwLy8wEgABARcB4wPXBTYAMABstSMBBAMBTEuwHFBYQCQABAMBAwQBgAABAAABcAADAwVhBgEFBTJNAAAAAmAAAgIzAk4bQCUABAMBAwQBgAABAAMBAH4AAwMFYQYBBQUyTQAAAAJgAAICMwJOWUAOAAAAMAAvJSo1IxcHCRsrABYWFRQGBwczNTQ2MzIWFRUUBiMhIiY1NDclNjY1NCYjIgYHFRQGIyImNTU0NzY2MwLiiEZeXMbuJDI0LxUZ/aMZHBwBRzg0PjciRR0kMjQvH0ChTQU2Q3hQTn9Cjy4ZFxgYqhkVMTM3Ff0qQyUwNw0NWBkXGBitHBEiIwABARgB0QO6BTYAOwBLQEguAQYFBAEDBAJMAAYFBAUGBIAAAQMCAwECgAAEAAMBBANpAAUFB2EIAQcHMk0AAgIAYQAAADUATgAAADsAOiQkNDMjKCkJCR0rABYVFAcWFhUUBiMiJicmNTQ3NjYzMhcWFjMyNTQmIyMiJjU0NjMzMjY1NCYjIgcVFAYjIiY1NTQ3NjYzAwimekBGt6hKnjkiCgwgEAgEN3s2lDY1XRgYGBhKPj5EQUJGJDI0Lx9AoFEFNoR2djsYYEV9gB4YDigXGyIjAhcdVissKC4uKC4tKS4aOhkXGBiZIA0cHwAAAQGYA/0DuAWkABEAGbEGZERADgAAAQCFAAEBdhggAggYK7EGAEQAMzIXFhUUBwUGIyInJjU0NyUDGBEuOSgY/mkKDSQgFhUBWwWkSzYnIAzNBjMjHBwP/wAAAQC4/nwEIAOcACwAXkAKCwEABBABAQACTEuwLlBYQBwGBQIDAxZNAAAAFU0ABAQBYQABARVNAAICGAJOG0AaAAQAAQIEAWkGBQIDAxZNAAAAFU0AAgIYAk5ZQA4AAAAsACokNTQlNQcHGysAFhURFAYjIyImNTUGBiMiJxEUBiMjIiY1ETQ2MzMyFhURFDMyNjY1ETQ2MzMEAx0dIlQiHUKuZCImHSJ8Ih0dInwiHYk5bUUdInwDnB0i/OIiHR0ic15qCv7HIh0dIgSiIh0dIv4YnlCHTAFjIh0AAAEAZf5mBHIEowAiAClAJhkBAQABTAIBAAAEXwUBBAQiTQMBAQEtAU4AAAAiACAjEyMmBggaKwAWFhUUBgYjIxEUBiMiJjURIxEUBiMiJjURLgI1NDY2MyEESxoNDRoYQjc5NyugNzk3K2OUUWq9ewIsBKMRLCoqLBD6zyEeHSIFMfrPIR4dIgMTD2GcZXWrWgD//wHBAYYDCwMCAQcAEQAAAZAACbEAAbgBkLA1KwAAAAABAV/+KAOOABwAHwCwsQZkREuwEFBYtQkBAAEBTBu1CQEAAgFMWUuwDFBYQCIGAQUEAwEFcgAEAAMBBANpAgEBAAABWQIBAQEAYgAAAQBSG0uwEFBYQCMGAQUEAwQFA4AABAADAQQDaQIBAQAAAVkCAQEBAGIAAAEAUhtAKQYBBQQDBAUDgAABAwIDAQKAAAQAAwEEA2kAAgAAAlkAAgIAYgAAAgBSWVlADgAAAB8AHxJUIxYkBwgbK7EGAEQEFhUUBiMiJyY1NDc2MzIXFjMyNjU0JiMHBiMiNTUzFQMhbY+Ik20YChgeBAhSTzEvMCsXCBAluVNpVWBnKgodExpAAh0ZGhoVAQEpzG8AAQElAeMDygU2AB8AMEAtDgECAwFMAAIDAQMCAYAAAwMyTQUEAgEBAF8AAAAzAE4AAAAfAB4nIyQ0BgkaKwAWFRQGIyEiJjU0NjMzEQcGIyInJjU0NyU2MzIWFREzA7IYGBz9zBwXGBu8ixEOJBsQIQE0EhMbJ7UCjSgtLSgnLi0oAblICTsjFyAQlAgfHP2SAAACAOAB0QPsBLkADwAbACpAJwQBAQUBAwIBA2kAAgIAYQAAADUAThAQAAAQGxAaFhQADwAOJgYJFysAFhYVFAYGIyImJjU0NjYzBgYVFBYzMjY1NCYjAtuxYGCxdXSxYWGxdFNlZVNUZGRUBLlgqWtrqWBgqWtrqWCubFpaa2taWmwABP/s/yYE4wVzAB8AMQBQAFMAu7EGZERAEwsBAgMhAQABUioCBQpEAQcLBExLsBtQWEA4AAMCA4UAAgEChQAFCgsKBQuABgQCAQAACgEAaAAKBQgKWQ4MDQMLCQEHCAsHaQAKCghiAAgKCFIbQDwAAwIDhQACBgKFAAYBBoUABQoLCgULgAQBAQAACgEAaAAKBQgKWQ4MDQMLCQEHCAsHaQAKCghiAAgKCFJZQBxRUTIyUVNRUzJQMk9MSkFAIyYYGSMnIyQxDwgfK7EGAEQABiMhIiY1NDYzMxEHBiMiJyY1NDclNjMyFhURMzIWFSQVFAcBBiMiJyY1NDcBNjMyFxIWFRQGIyMVFAYjIiY1NSEiJjU0NjcBNjYzMhYVETMjNwcCIRQX/ikYExQXnXQNDR4XDRsBAQ4SFx+YFxQCVRT8VwwIGx0YFAOpDAgbHXAVFBdLHyowKv7eEyIGCAE2DisjLS1L7gWbAs4iISYmIQFwPAcxGxUcDXsHGhf9+CIlCRYTDP33BS0kFhMMAgkFLf0xIiUlIXYVExQUdkEjDxMLAXoSEhkW/o3HxwAD/+z/JwTfBXMAHwAxAF8BFbEGZERADwsBAgMhAQABRioCBQgDTEuwGVBYQEAAAwIDhQACBgKFAAYBBoUJAQUIDAgFDIANAQwLCwxwBAEBAAAKAQBoAAoACAUKCGkACwcHC1cACwsHYAAHCwdQG0uwIFBYQEYAAwIDhQACBgKFAAYBBoUABQgJCAUJgAAJDAgJDH4NAQwLCwxwBAEBAAAKAQBoAAoACAUKCGkACwcHC1cACwsHYAAHCwdQG0BHAAMCA4UAAgYChQAGAQaFAAUICQgFCYAACQwICQx+DQEMCwgMC34EAQEAAAoBAGgACgAIBQoIaQALBwcLVwALCwdgAAcLB1BZWUAYMjIyXzJeW1pUUktJKTcYGSMnIyQxDggfK7EGAEQABiMhIiY1NDYzMxEHBiMiJyY1NDclNjMyFhURMzIWFSQVFAcBBiMiJyY1NDcBNjMyFxIWFRUUBiMhIjU0NyU2NjU0JiMiBxUUBiMiJjU1NDc2NjMyFhUUBgcHMzU0NjMCIRQX/ikYExQXnXQNDR4XDRsBAQ4SFx+YFxQCVRT8VwwIGx0YFAOpDAgbHVkoEhX+BywXAREwKzQuPjAfKSsoGjaFQXmET0ylxh8pAs4iISYmIQFwPAcxGxUcDXsHGhf9+CIlOxYTDP33BS0kFhMMAgkFLfyyFBSOFRJULRLUIzcfKC4VShUTFBSRFw4cHnplQWo3eCcVEwAABP/2/yYE4wVyADkASwBqAG0A5rEGZERAGC0BBQQEAQIDPw8CAAFtSAIIDWMBCgkFTEuwDFBYQEYABQQDBAUDgAAIDQkNCAmADwEGAAQFBgRpAAMAAgEDAmkHAQEAAA0BAGkQAQ0ICw1ZDgEJDAEKCwkKaRABDQ0LYgALDQtSG0BNAAUEAwQFA4AABwIBAgcBgAAIDQkNCAmADwEGAAQFBgRpAAMAAgcDAmkAAQAADQEAaRABDQgLDVkOAQkMAQoLCQppEAENDQtiAAsNC1JZQCNMTAAAbGtMakxpYF9cWldVUU9FRDw7ADkAOCQjNDMtKREIHCuxBgBEABYVFAcWFhUUBiMiJicmNTQ3NjYzMhcWFjMyNTQmIyMiJjU0NjMzMjU0JiMiBxUUBiMiNTU0NzY2MwAzMhcWFRQHAQYjIicmNTQ3ARIWFREzMhYVFAYjIxUUBiMiJjU1ISImNTQ2NwE2NjMDMzcBlYtmNTuZjD2FMB0JChsOAwYvZyx8LixNFBUVFD1oOTY4Oh4qUho1hUQDCggbHRgU/FcMCBsdGBQDqS4tSxYVFBdLHyowKv7eEyIGCAE2Disj35YFBXJvYmMxFFA5aWsZFA0hERgcHgITGEgjJSImJiJMIiYVMRUTKIAaDBca/eUtJBYTDP33BS0kFhMMAgn+oRkW/o0iJSUhdhUTFBR2QSMPEwsBehIS/l7HAAIA5v6nA/wDpgANADIAe0AMGhQTAwQCJgEDBAJMS7AXUFhAJgACAQQBAgSAAAQDAQQDfgYBAQEAYQAAACVNAAMDBWIHAQUFJwVOG0AjAAIBBAECBIAABAMBBAN+AAMHAQUDBWYGAQEBAGEAAAAlAU5ZQBYODgAADjIOMSspJSMYFgANAAwlCAgXKwAmNTU0NjMyFhUVFAYjAiY1NDY3NzY2MzIWFxcWBwcGBhUUFjMyNzU0NjMyFhUVFAcGIwI3RERNTURETdHNl5wGAiw3NywCDAIhZ0hGT01LTi4+QDopuqUCeh0iriIdHSKuIh38Lbyni58rVhkXFxnRLAcUDkc+REYeXCMcHSK+KRRY////9gAABNYGsgAiACQAAAEHAEP/2gEOAAmxAgG4AQ6wNSsA////9gAABNYGsgAiACQAAAEHAHP/wgEOAAmxAgG4AQ6wNSsA////9gAABNYGkAAiACQAAAEHASr/7AEOAAmxAgG4AQ6wNSsA////9gAABNYGbgAiACQAAAEHATD/2AEOAAmxAgG4AQ6wNSsA////9gAABNYGYQAiACQAAAEHAGn/7AEOAAmxAgK4AQ6wNSsA////9gAABNYHIwAiACQAAAEHAS7/7AEOAAmxAgK4AQ6wNSsAAAL/4gAABJwEowBHAEsA6EuwClBYQDoAAAECAQByAAUDBwQFcgACAAMFAgNpAA0ABwQNB2cQDgsDAQEMXw8BDAwiTQoIAgQEBmAJAQYGIwZOG0uwDlBYQDsAAAECAQByAAUDBwMFB4AAAgADBQIDaQANAAcEDQdnEA4LAwEBDF8PAQwMIk0KCAIEBAZgCQEGBiMGThtAPAAAAQIBAAKAAAUDBwMFB4AAAgADBQIDaQANAAcEDQdnEA4LAwEBDF8PAQwMIk0KCAIEBAZgCQEGBiMGTllZQCBISAAASEtIS0pJAEcART89PDo0MSETNiMRJCETJREIHysAFhURFAYjIiY1NSMVMzIWFRQGIyMRMzU0NjMyFhYVERQGIyEiJjURIwczMhYWFRQGBiMhIiYmNTQ2NjMzEyMiJiY1NDY2MyEFAzMRBGoeNDw6KKpyIxwcI3K0NT8qLREeI/4MIh/KICkYGg0NGhj+vBgaDQ0aGDXHZhgaDQ0aGAOQ/bBnlgSjHiP+8CIdHCOE/S4+Pi3+y7YiHQ0aGP6+Ih8fIgEJfREsKiosEBAsKiosEQMJECwqKiwRzf5LAbUAAQBn/igEZwS5AE0A+0uwEFBYQA8uAQgFJAUCAAkQAQECA0wbQA8uAQgFJAUCAAkQAQEDA0xZS7AMUFhANgAKBwkHCgmAAAAJBAIAcgAJAAQCCQRpAwECAAECAWYACAgFYQYBBQUoTQAHBwVhBgEFBSgHThtLsBBQWEA3AAoHCQcKCYAAAAkECQAEgAAJAAQCCQRpAwECAAECAWYACAgFYQYBBQUoTQAHBwVhBgEFBSgHThtAPgAKBwkHCgmAAAAJBAkABIAAAgQDBAIDgAAJAAQCCQRpAAMAAQMBZgAICAVhBgEFBShNAAcHBWEGAQUFKAdOWVlAEExKR0UlJSQpVCMWJBYLCB8rJBUUBwYHFTIWFRQGIyInJjU0NzYzMhcWMzI2NTQmIwcGIyI1NSYmAjU0EjYzMhc1NDYzMhYVERQGIyImJjU0JiMiBhUUFjMyNjc2MzIXBGcusLVrbY+Ik20YChgeBAhSTzEvMCsXCBAlhMVrhu2Wr1U6QD4uPUcvMxRtZYuQmYxXoF4QDi8fux4zFlgPQGlVYGcqCh0TGkACHRkaGhUBASmkGKEBAKW6AReWfj8iHRwj/oAiHQ0aGGR4yLy6yy8wCFMA//8APAAABGAGsgAiACgAAAEHAEMAIAEOAAmxAQG4AQ6wNSsA//8APAAABGAGsgAiACgAAAEHAHP/4AEOAAmxAQG4AQ6wNSsA//8APAAABGAGkAAiACgAAAEHASoAHgEOAAmxAQG4AQ6wNSsA//8APAAABGAGYQAiACgAAAEHAGkAHgEOAAmxAQK4AQ6wNSsA//8AqgAABCIGsgAiACwAAAEHAEMAAAEOAAmxAQG4AQ6wNSsA//8AqgAABCIGsgAiACwAAAEHAHMAAAEOAAmxAQG4AQ6wNSsA//8AqgAABCIGkAAiACwAAAEHASoAAAEOAAmxAQG4AQ6wNSsA//8AqgAABCIGYQAiACwAAAEHAGkAAAEOAAmxAQK4AQ6wNSsAAAIAKAAABIMEowAnADsAekuwMVBYQCMHAQMIAQIBAwJpBgEEBAVfCgEFBSJNCwkCAQEAXwAAACMAThtALwAEBQYGBHIAAQkACQFyBwEDCAECCQMCaQAGBgVgCgEFBSJNCwEJCQBfAAAAIwBOWUAaKCgAACg7KDo5NzEvLiwAJwAlISYhJjYMCBsrABYSFRQCBiMhIiYmNTQ2NjMzESMiJiY1NDY2MzMRIyImJjU0NjYzIRI2NTQmIyMVMzIWFhUUBgYjIxEzAwH8hob8r/4pGBoNDRoYYXUYGg0NGhh1YRgaDQ0aGAHXh56em2iHGBoNDRoYh2gEo4r+9by8/vWLECwqKiwRASERMC8vMBIBBxAsKiosEfw0wbq6wP0SMC8vMBH+6f//ADL/6gSuBm4AIgAxAAABBwEwAAABDgAJsQEBuAEOsDUrAP//AD//6gSNBrIAIgAyAAABBwBDABYBDgAJsQIBuAEOsDUrAP//AD//6gSNBrIAIgAyAAABBwBz/+oBDgAJsQIBuAEOsDUrAP//AD//6gSNBpAAIgAyAAABBwEqAAABDgAJsQIBuAEOsDUrAP//AD//6gSNBm4AIgAyAAABBwEwAAABDgAJsQIBuAEOsDUrAP//AD//6gSNBmEAIgAyAAABBwBpAAABDgAJsQICuAEOsDUrAAABANYAtwP2A9YALwBDQAkuIhYKBAEAAUxLsBtQWEANAgEBAQBhAwEAACsBThtAEwMBAAEBAFkDAQAAAWECAQEAAVFZQAosKhoYFBIgBAgXKwAzMhYXFhYVFAcHFxYVFAYHBgYjIicnBwYjIiYnJiY1NDc3JyY1NDY3NjYzMhcXNwNXEg8oHh4ZFNzcFRoeHicQExTc3BQTECceHhoV3NwUGR4eKA8SFdzcA9YaHh4nEBMU3NwVEg8oHh4ZFNzcFBkeHigPEhXc3BQTECceHhoV3NwAAAMAP/+kBI0E/wAnAC8ANwByQBMiBQIEAjc2LSwEBQQZDgIABQNMS7AgUFhAIAABAAGGAAMDJE0GAQQEAmEAAgIoTQAFBQBhAAAAKQBOG0AgAAMCA4UAAQABhgYBBAQCYQACAihNAAUFAGEAAAApAE5ZQA8oKDIwKC8oLiMtIysHCBorABYVFAcHFhYVFAIGIyInBwYjIicmJjU0NzcmJjU0EjYzMhc3NjMyFwAGFRQXASYjAjMyNjU0JwEEThoPU0JFifqkl3lKFBgYLB0bD1NBRon6pJd5SxQXFy79qpAcAYc5T05Oi5Ac/nkEzCAQEBV2UdqEu/7plkFqHR8UIBAPFndQ2oW7AReVQWodH/72yLxzVwItIfz3ybx2U/3S//8AMv/qBJoGsgAiADgAAAEHAEMAAAEOAAmxAQG4AQ6wNSsA//8AMv/qBJoGsgAiADgAAAEHAHMAAAEOAAmxAQG4AQ6wNSsA//8AMv/qBJoGkAAiADgAAAEHASoAAAEOAAmxAQG4AQ6wNSsA//8AMv/qBJoGYQAiADgAAAEHAGkAAAEOAAmxAQK4AQ6wNSsA//8AKAAABKQGsgAnAHMAAAEOAQIAPAAAAAmxAAG4AQ6wNSsAAAIAeAAABD8EowAwADkAdEuwG1BYQCoACAACAwgCaQYBAAAHXwoBBwciTQAJCQFhAAEBJU0FAQMDBF8ABAQjBE4bQCgAAQAJCAEJaQAIAAIDCAJpBgEAAAdfCgEHByJNBQEDAwRfAAQEIwROWUAUAAA5NzMxADAALiEmNiEkISYLCB0rABYWFRQGBiMjFTMyFhUUBiMjFTMyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzIQMzMjY1NCYjIwMXGg0NGhi7jLe4uLeMuxgaDQ0aGP24GBoNDRoYk5MYGg0NGhgCSLttSUNDSW0EoxEsKiosEGCZi4uaYBEsKiosEBAsKiosEQMJECwqKiwR/U0uNDMuAAEAFv/qBEIFJQA5AJ+1BgECAwFMS7AXUFhAIAACAwEDAgGAAAMDBmEHAQYGJE0FAQEBAGEEAQAAKQBOG0uwIFBYQCoAAgMBAwIBgAADAwZhBwEGBiRNBQEBAQRfAAQEI00FAQEBAGEAAAApAE4bQCgAAgMBAwIBgAcBBgADAgYDaQUBAQEEXwAEBCNNBQEBAQBhAAAAKQBOWVlADwAAADkAOCY1KSMkLAgIHCsAFhYVFAYHFhYVFAYGIyImNTQ2MzI1NCYjIiY1NDY3NjU0JiMiBhURFAYjISImJjU0NjYzMxE0NjYzAvC4X01PZ3BtxoYoJRghwV9VIh0cI41PT1FWHSL+yhgaDQ0aGHtiuoMFJV6obV6DKyefcX+vVzM+QTG2TlQxPz4wAw6URVVuavzVIh0QLCoqLBECoIbGbAD//wBu/+oEmwWkACIARAAAAAIAQz4AAAD//wBu/+oEmwWkACIARAAAAAIAc8IAAAD//wBu/+oEmwWCACIARAAAAAIBKgAAAAD//wBu/+oEmwVgACIARAAAAAIBMAAAAAD//wBu/+oEmwVTACIARAAAAAIAaQAAAAD//wBu/+oEmwYgACIARAAAAQYBLgcLAAixAgKwC7A1KwADACD/6gSpA7IAOgBBAE0Bc0uwF1BYQA44AQYIJAEABRkBAwEDTBtLsCBQWEAOOAEGCCQBCgUZAQMBA0wbQA44AQYIJAEKBRkBAw0DTFlZS7AXUFhANgAHBgUGBwWAAAIAAQACAYAKAQUQDAIAAgUAaQ8LAgYGCGEOCQIICCtNDQEBAQNhBAEDAykDThtLsBlQWEA7AAcGBQYHBYAAAgABAAIBgAAFCgAFWQAKEAwCAAIKAGkPCwIGBghhDgkCCAgrTQ0BAQEDYQQBAwMpA04bS7AgUFhAPAAHBgUGBwWAAAIAAQACAYAABRABDAAFDGkACgAAAgoAZw8LAgYGCGEOCQIICCtNDQEBAQNhBAEDAykDThtARgAHBgUGBwWAAAIAAQACAYAABRABDAAFDGkACgAAAgoAZw8LAgYGCGEOCQIICCtNAAEBA2EEAQMDKU0ADQ0DYQQBAwMpA05ZWVlAIkRCOzsAAEpIQk1ETTtBO0A+PQA6ADknIyQlIicjISURCB8rABYWFRQGIyEWMzI2NzYzMhYXFhUUBwYjIicGIyImJjU0NjMyFzU0JiMiBgcGIyInJjU0NzY2MzIXNjMGBgczJiYjACMiBhUUFjMyNjU1A9yTOh0i/moVcTdkPw8NGCIODi2kip1TXq5aiUzbqCgySEgrVDEQDiwlEiRBmU+gUVONPD8L9AU3Mv5xFVhaMjBGUQOygOGhIhylFxsGKigoGS4TR3x8R4Zco5UFBkBDGxkITycdKhQmKF5e40tPSlD+uS49LTNfSiAAAAEAf/4oBDYDsgBRAPtLsBBQWEAPLwEIBSUGAgAJEQEBAgNMG0APLwEIBSUGAgAJEQEBAwNMWUuwDFBYQDYACgcJBwoJgAAACQQCAHIACQAEAgkEaQMBAgABAgFmAAgIBWEGAQUFK00ABwcFYQYBBQUrB04bS7AQUFhANwAKBwkHCgmAAAAJBAkABIAACQAEAgkEaQMBAgABAgFmAAgIBWEGAQUFK00ABwcFYQYBBQUrB04bQD4ACgcJBwoJgAAACQQJAASAAAIEAwQCA4AACQAEAgkEaQADAAEDAWYACAgFYQYBBQUrTQAHBwVhBgEFBSsHTllZQBBQTktJJiUkKVQjFiQXCwgfKyQVFAcGBgcVMhYVFAYjIicmNTQ3NjMyFxYzMjY1NCYjBwYjIjU1LgI1NDY2MzIXNTQ2MzIWFREUBiMiJiY1NCYmIyIGBhUUFhYzMjY3NjMyFwQ2K0+uWGttj4iTbRgKGB4ECFJPMS8wKxcIECV1rF1+2YaiQzpAPi49Ry8zFClROUhsOztsSE2hTBIPLSK7Hi0YLDgHQGlVYGcqCh0TGkACHRkaGhUBASmmGITFd4zde3U2Ih0cI/6/Ih0NGhgqSCs/dU1NdT8yLApP//8Ag//qBE8FpAAiAEgAAAACAEM0AAAA//8Ag//qBE8FpAAiAEgAAAACAHPgAAAA//8Ag//qBE8FggAiAEgAAAACASoKAAAA//8Ag//qBE8FUwAiAEgAAAACAGkAAAAA//8ApwAABEkFpAAiAWUAAAACAEPaAAAA//8ApwAABEkFpAAiAWUAAAACAHPCAAAA//8ApwAABEkFggAiAWUAAAACASoAAAAA//8ApwAABEkFUwAiAWUAAAACAGkAAAAAAAIAev/qBFIFRgA2AEIAukuwE1BYQA82MioeGhIGAgMQAQUBAkwbQA82MioeGhIGAgQQAQUBAkxZS7ATUFhAIgACAwEDAgGAAAEABQYBBWkEAQMDKk0HAQYGAGEAAAApAE4bS7AgUFhAJgACBAEEAgGAAAEABQYBBWkAAwMqTQAEBCRNBwEGBgBhAAAAKQBOG0AjAAMEA4UABAIEhQACAQKFAAEABQYBBWkHAQYGAGEAAAApAE5ZWUAPNzc3QjdBLSYfJSYlCAgcKwASFRQGBiMiJiY1NDY2MzIXJicHBiMiJicmNTQ2NzcnJjU0NzY2MzIXFhc3NjMyFhcWFRQGBwcCNjU0JiMiBhUUFjMDzoR53pWT33pz0olrUztfmRQOER4SFxESQUMfJhkqFhAUYVSWEw8RHhIWERFUgHp6ZmZ6emYDy/68uZTbdXHKgYHKcTJaTlELHSIsFg8WCSMjEB4iPCciCjE7UAodIisWDxYJLfx+dGVldHRlZXT//wA5AAAErwVgACIAUQAAAAIBMAAAAAD//wBv/+oEXQWkACIAUgAAAAIAQxYAAAD//wBv/+oEXQWkACIAUgAAAAIAc+oAAAD//wBv/+oEXQWCACIAUgAAAAIBKgAAAAD//wBv/+oEXQVgACIAUgAAAAIBMAAAAAD//wBv/+oEXQVTACIAUgAAAAIAaQAAAAAAAwCqAEYEIgRHAA0AHwAtAEFAPgYBAQAAAwEAaQcBAwACBQMCZwgBBQQEBVkIAQUFBGEABAUEUSAgDg4AACAtICwnJQ4fDh0XFAANAAwlCQgXKwAWFRUUBiMiJjU1NDYzABYWFRQGBiMhIiYmNTQ2NjMhABYVFRQGIyImNTU0NjMCqDs7QkI7O0IBlRoNDRoY/QYYGg0NGhgC+v7FOztCQjs7QgRHHSKQIh0dIpAiHf5wEjAvLzARETAvLzAS/p0dIpAiHR0ikCIdAAMAU/+uBHkD7gAjACwANQBAQD0eBAEDBAIvLiYlBAUEFhMMAwAFA0wAAwIDhQABAAGGAAQEAmEAAgIrTQAFBQBhAAAAKQBOJyUjKyMpBggcKwAVFAcHFhUUBgYjIicHBiMiJyY1NDc3JjU0NjYzMhc3NjMyFwAXASYjIgYGFSQnARYzMjY2NQR5FWBZe+SYnXZlFRUaKywVYFl75JiddmUVFRor/S4NAUMvNkhqOQHWDf69MDVIajkDmRoSF2N7qozcfENoFyorGhIXY3uqjNx8Q2gXKv3TKAFNEz90Tjco/rMTP3ROAP//ADL/6gSUBaQAIgBYAAAAAgBDDAAAAP//ADL/6gSUBaQAIgBYAAAAAgBz/gAAAP//ADL/6gSUBYIAIgBYAAAAAgEq9gAAAP//ADL/6gSUBVMAIgBYAAAAAgBp7AAAAP//ACj+ZQSkBaQAIgBcAAAAAgBzAAAAAAACACX+fARrBSAAMABAAIdACgMBCAARAQEHAkxLsCBQWEAsAAUFBl8JAQYGJE0KAQgIAGEAAAArTQAHBwFhAAEBKU0EAQICA18AAwMnA04bQCoJAQYABQAGBWkKAQgIAGEAAAArTQAHBwFhAAEBKU0EAQICA18AAwMnA05ZQBcxMQAAMUAxPzk3ADAALiEmNiMmJQsIHCsAFhURNjYzMhYWFRQGBiMiJicRMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMhEgYGFRQWFjMyNjY1NCYmIwGYHTOGToPEaGjEg06GM6cYGg0NGhj+CBgaDQ0aGFdXGBoNDRoYARLeaD4+aEA+XDExXD4FIB0i/ls5PYDciIjcgD05/ukQLCoqLBEQLCoqLBEFChAsKiosEf2vPHVQUHU8P3ROTnQ///8AKP5lBKQFUwAiAFwAAAACAGkAAAAA////9gAABNYGCQAnAG7/zgEOAQIAJAAAAAmxAAG4AQ6wNSsA//8Abv/qBJsE+wAiAEQAAAACAG4AAAAA////9gAABNYGgAAiACQAAAEHASz/7AEOAAmxAgG4AQ6wNSsA//8Abv/qBJsFcgAiAEQAAAACASwDAAAAAAL/9v4oBNYEowBLAE8ARUBCTgEIAUsADAAEAwwEZwAAAAEAAWUACAgJXwAJCSJNCgcFAwMDAmELBgICAiMCTk1MS0lDQT47ISY2IREmJSciDQgfKwQVFDMyNzYVFAYHBiMiJjU0NjcjIiYmNTQ2NjMzJyEHMzIWFhUUBgYjISImJjU0NjYzMxMjIiYmNTQ2NjMhMhYXATMyFhYVFAYGIyMBMwMjA6RYLkozFBRmcnaAYVl8GBoNDRoYVi3+lC1KGBoNDRoY/mwYGg0NGhhU/acYGg0NGhgB2igyCwEiVxgaDQ0aGFf9pvl4BnxXQw0IaSEkByJoY1CBPBEsKiosEJGRECwqKiwRESwqKiwQAwkRLCoqLBAfIvxrECwqKiwRAisBqwACAG7+KASdA7IARABQAQdLsBdQWEAQGAEJAlBFAgYJDAoCAQYDTBtLsCBQWEAQGAEJAlBFAgYJDAoCBwYDTBtAEBgBCQJQRQIGCQwKAgcKA0xZWUuwF1BYQC4ABAMCAwQCgAACAAkGAglpAAgAAAgAZQADAwVhAAUFK00KAQYGAWEHAQEBKQFOG0uwIFBYQDgABAMCAwQCgAACAAkGAglpAAgAAAgAZQADAwVhAAUFK00KAQYGB2EABwcjTQoBBgYBYQABASkBThtANgAEAwIDBAKAAAIACQYCCWkACAAACABlAAMDBWEABQUrTQAGBgdhAAcHI00ACgoBYQABASkBTllZQBBOTEhGIyY1KCMkJSkjCwgfKwAGBwYjIiY1NDY3JicGBiMiJiY1NDYzMhc1NCYjIgYHBiMiJicmNTQ3NjYzMhYVERQWMzMyFhYVFAYGIyMGFRQzMjc2FQEmIyIGFRQWMzI2NwSdFBRmcnaAc2o0Gk+wXXGkV8ayhZZUajuRRxEMGScQDy5ZyFjcxCIgHxgaDQ0aGCacWC5KM/5khH5GSUdDRYc7/nUkByJoY1iJQxs4PUNNj2GMmh4dQ0AdGAUlLCwcMxEgIL6x/t8oLREsKiosEHxXQw0IaQLOGzIwLzE3MP//AGf/6gRnBrIAJwBzABIBDgECACYAAAAJsQABuAEOsDUrAP//AH//6gQ2BaQAIgBGAAAAAgBz/QAAAP//AGf/6gRnBpAAJwEqACgBDgECACYAAAAJsQABuAEOsDUrAP//AH//6gQ2BYIAIgEqCgAAAgBGAAAAAP//AGf/6gRnBmEAJwEtACgBDgECACYAAAAJsQABuAEOsDUrAP//AH//6gQ2BVMAIgBGAAAAAgEtCgAAAP//AGf/6gRnBpoAIgAmAAABBwErACgBDgAJsQEBuAEOsDUrAP//AH//6gQ2BYwAIgBGAAAAAgErCgAAAP//ADwAAASDBpoAIgAnAAABBwEr/+wBDgAJsQIBuAEOsDUrAAADAE3/6gVqBSAAKgA7AEcA50APLAEEBTUfAgYDEQEBAANMS7AXUFhAMgAEBAVfCwcKAwUFJE0ABgYFXwsHCgMFBSRNDAEJCQNhAAMDK00IAQAAAWECAQEBIwFOG0uwIFBYQDwABAQFXwsHCgMFBSRNAAYGBV8LBwoDBQUkTQwBCQkDYQADAytNCAEAAAFfAAEBI00IAQAAAmEAAgIpAk4bQDMABAMFBFcLBwoDBQAGCQUGaQwBCQkDYQADAytNCAEAAAFfAAEBI00IAQAAAmEAAgIpAk5ZWUAePDwrKwAAPEc8RkJAKzsrOTMxACoAKCMmJTYjDQgbKwAWFREzMhYWFRQGBiMjIiY1NQYGIyImJjU0NjYzMhYXESMiJiY1NDY2MyEgFRQHAwYGIyImNTQ3EzYzMwAGFRQWMzI2NTQmIwN8HVcYGg0NGhjqIh0ueVZzrV1drXNEZC2TGBoNDRoYAU4CEAWXDDkyKykCVQgjyfxeU1NGUmJiUgUgHSL77BAsKiosER0iSk9QfdyLi9x9OzwBGBAsKiosERwJD/59HxkYGw0HAYch/a+HenqHhH1+gwAAAgA8AAAEgwSjACcAOwB6S7AxUFhAIwcBAwgBAgEDAmkGAQQEBV8KAQUFIk0LCQIBAQBfAAAAIwBOG0AvAAQFBgYEcgABCQAJAXIHAQMIAQIJAwJpAAYGBWAKAQUFIk0LAQkJAF8AAAAjAE5ZQBooKAAAKDsoOjk3MS8uLAAnACUhJiEmNgwIGysAFhIVFAIGIyEiJiY1NDY2MzMRIyImJjU0NjYzMxEjIiYmNTQ2NjMhEjY1NCYjIxEzMhYWFRQGBiMjETMDAfyGhvyv/ikYGg0NGhhhSxgaDQ0aGEthGBoNDRoYAdeHnp6baNkYGg0NGhjZaASjiv71vLz+9YsQLCoqLBEBLhAsKiosEQEOECwqKiwR/DTBurrA/vwRLCoqLBD+3AAAAgB7/+oEpwUgADoASADIQAodAQkDDwEBAAJMS7AXUFhAKAADAAkAAwlpAAYGJE0LCAIEBAVhBwEFBSJNDAoCAAABYgIBAQEjAU4bS7AgUFhAMwADAAkAAwlpAAYGJE0LCAIEBAVhBwEFBSJNDAoCAAABYAABASNNDAoCAAACYgACAikCThtAMQAGBQaFBwEFCwgCBAMFBGkAAwAJAAMJaQwKAgAAAWAAAQEjTQwKAgAAAmIAAgIpAk5ZWUAZOzsAADtIO0dDQQA6ADkjMyYjJiU2IQ0IHisBETMyFhYVFAYGIyMiJjU1BgYjIiYmNTQ2NjMyFhc1IyImJjU0NjYzMzU0NjMzMhYVFTMyFhYVFAYGIwA2NjU0JiYjIgYVFBYzA/1XGBoNDRoY6iIdL5VXfbdhYbd9R38tzRgaDQ0aGM0dInwiHWsYGg0NGhj+CmA4OF87VWJiVQO2/RcQLCoqLBEdIj1ETnPGeXjGdDcx0BAsKiosEV4iHR0iXhEsKiosEP0cL1w/QFwubV1dbf//ADwAAARgBgkAJwBuABUBDgECACgAAAAJsQABuAEOsDUrAP//AIP/6gRPBPsAIgBuCgAAAgBIAAAAAP//ADwAAARgBmEAJwEtAAABDgECACgAAAAJsQABuAEOsDUrAP//AIP/6gRPBVMAIgEtCgAAAgBIAAAAAAABADz+KARrBKMASgDkS7AMUFhAOQAFAwcDBXIABwAICgcIZwAMAAAMAGUGAQMDBF8ABAQiTQAKCgFhCwEBASNNCQECAgFhCwEBASMBThtLsDFQWEA6AAUDBwMFB4AABwAICgcIZwAMAAAMAGUGAQMDBF8ABAQiTQAKCgFhCwEBASNNCQECAgFhCwEBASMBThtARgADBAYGA3IABQYHBgUHgAACCQEJAnIABwAICgcIZwAMAAAMAGUABgYEYAAEBCJNAAoKAWELAQEBI00ACQkBYQsBAQEjAU5ZWUAUR0VCQDs5NjUkIRMlNiEmJSMNCB8rAAYHBiMiJjU0NjchIiYmNTQ2NjMzESMiJiY1NDY2MyEyFhURFAYjIiY1NSEVMzIWFRQGIyMRITU0NjMyFhURFAYjIwYVFDMyNzYVBGsUFGZydoBhWf1MGBoNDRoYYWEYGg0NGhgDkCMeOkA+Lv5w9CMcHCP0AZo7Q0IwHiMbnFguSjP+dSQHImhjUIE8ECwqKiwRAwkQLCoqLBEeI/7SIh0cI5j9Lj4+Lf7fyiIdHCP+oCIffFdDDQhpAAIAg/4oBE8DsgA2ADwATkBLLAEFAQFMAAIAAQACAYAABwAAAgcAZwADAAQDBGUKAQgIBmEJAQYGK00AAQEFYQAFBSkFTjc3AAA3PDc7OTgANgA1JictEyIlCwgcKwAWFhUUBiMhFhYzMjc2MzIWFxYVFAYHBgYHBhUUMzI3NhYVFAcGIyImNTQ2NwYjIiYmNTQ2NjMGByEmJiMDDNZtHSL9fhN9YJu1DAwWIA0LFBUPJCSOWChQFhsmbGx2gFZOMjuY3HN44pe3KwG4EW9WA7KD6ZYiHFBVNwQoMCkWGBwJBhwhf1lDDQMtKjkMImhjS3s4B3zbjYzcfOOaSVH//wA8AAAEYAaaACIAKAAAAQcBKwAAAQ4ACbEBAbgBDrA1KwD//wCD/+oETwWMACIASAAAAAIBKwoAAAD//wBJ/+oEpAaQACcBKgAeAQ4BAgAqAAAACbEAAbgBDrA1KwD//wBh/mYEpwWCACIASgAAAAIBKgAAAAD//wBJ/+oEpAaAACIAKgAAAQcBLAAKAQ4ACbEBAbgBDrA1KwD//wBh/mYEpwVyACIASgAAAAIBLAAAAAD//wBJ/+oEpAZhACcBLQAKAQ4BAgAqAAAACbEAAbgBDrA1KwD//wBh/mYEpwVTACIASgAAAAIBLQAAAAD//wBJ/eAEpAS5ACIAKgAAAAMBgATMAAAAAwBh/mYEpwW2ABEAQwBRALZADwsCAgABFAEDAjgBBwkDTEuwF1BYQDQABQcGBwUGgAsBAQAAAgEAZw0KAgMDAmEMCAICAiVNAAkJB2EABwcjTQAGBgRhAAQELQROG0A/AAUHBgcFBoALAQEAAAgBAGcNCgIDAwhhDAEICCtNDQoCAwMCXwACAiVNAAkJB2EABwcjTQAGBgRhAAQELQROWUAkREQSEgAARFFEUEpIEkMSQjw6NTMwLyclIiAaFwARABA3DggXKwAWFRQHAwYGIyMiNTQ3EzY2MwIWFzU0NjMzMhYWFRQGBiMjERQGIyImJyY1NDc2NjMyFxYzMjY1NQYGIyImJjU0NjYzBgYVFBYzMjY2NTQmJiMC6y8BOwIUDs4YBHwKLyxKnDQdIuoYGg0NGhhX6+pWzF0wDQ8lGQ0Lv3R5bDOGToHEamrEgTVubl1AaT09aUAFthkaCQX+zg0OFwsJATIZGP38UEtGIh0RLCoqLBD9MsTXIR0PNhguLyoEO2VnZjc8edWHh9V5439zc383bU5ObTcA//8AMgAABJoGkAAiACsAAAEHASoAAAEOAAmxAQG4AQ6wNSsA//8AJQAABJsG9AAnASr/9gFyAQIAS/YAAAmxAAG4AXKwNSsAAAIAHgAABK4EowBlAGkAYkBfABIABgMSBmcQDgwDAAANXxQRAg0NIk0VEwoDAgIBYQ8LAgEBJU0JBwUDAwMEXwgBBAQjBE5mZgAAZmlmaWhnAGUAY11bWllYVlBNR0VEQj48Ozk2IREmNiEkISYWCB8rABYWFRQGBiMjFTMyFhUUBiMjETMyFhYVFAYGIyEiJiY1NDY2MzMRIREzMhYWFRQGBiMhIiYmNTQ2NjMzESMiJjU0NjMzNSMiJiY1NDY2MyEyFhYVFAYGIyMVITUjIiYmNTQ2NjMhARUhNQRzGg0NGhg5TSIdHSJNORgaDQ0aGP6KGBoNDRoYQ/58QxgaDQ0aGP6KGBoNDRoYOU0iHR0iTTkYGg0NGhgBdhgaDQ0aGEMBhEMYGg0NGhgBdv1JAYQEoxEsKiosEE4fJSUf/c0RLCoqLBAQLCoqLBEBA/79ESwqKiwQECwqKiwRAjMfJSUfThAsKiosEREsKiosEE5OECwqKiwR/l1ZWQAAAQAeAAAEpQUgAFUAfbVMAQILAUxLsCBQWEApAAsAAgELAmkACAgkTQoBBgYHYQkBBwciTQ0MBQMEAQEAYAQBAAAjAE4bQCcACAcIhQkBBwoBBgsHBmkACwACAQsCaQ0MBQMEAQEAYAQBAAAjAE5ZQBgAAABVAFRQTktJQ0EzJiEmNiQjJjYOCB8rJBYWFRQGBiMhIiYmNTQ2NjMzETQmIyIGBhUVMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMzNTQ2MzMyFhUVMzIWFhUUBgYjIxE2NjMyFhYVETMEfhoNDRoY/ooYGg0NGhgvNj87Zz8vGBoNDRoY/ooYGg0NGhhNchgaDQ0aGHIdInwiHcYYGg0NGhjGO5NUW4lKTc0RLCoqLBAQLCoqLBEBFERGVZBSZxEsKiosEBAsKiosEQLpECwqKiwRXiIdHSJeESwqKiwQ/vVSUVCTY/7F//8AqgAABCIGCQAiACwAAAEHAG4AAAEOAAmxAQG4AQ6wNSsA//8ApwAABEkE+wAiAWUAAAACAG7sAAAAAAEAqv4oBCIEowA7ADRAMQABAAIBAmUHAQUFBl8ABgYiTQkIAgQEAF8DAQAAIwBOAAAAOwA6JjYhJiUnIyYKCB4rJBYWFRQGBiMhBhUUMzI3NhUUBgcGIyImNTQ2NyEiJiY1NDY2MyERIyImJjU0NjYzITIWFhUUBgYjIxEhA/saDQ0aGP7rnFguSjMUFGZydoBhWf7wGBoNDRoYAQDsGBoNDRoYAtIYGg0NGhjsAQDNESwqKiwQfFdDDQhpISQHImhjUIE8ECwqKiwRAwkQLCoqLBERLCoqLBD89wACAKf+KARJBVMADQBDAH5LsCBQWEAqAAMABAMEZQoBAQEAYQAAACpNAAcHCF8ACAglTQsJAgYGAl8FAQICIwJOG0AoAAAKAQEIAAFpAAMABAMEZQAHBwhfAAgIJU0LCQIGBgJfBQECAiMCTllAHg4OAAAOQw5CPzw2NDMxKykkIhsZFhQADQAMJQwIFysAJjU1NDYzMhYVFRQGIwAWFhUUBgYjIQYVFDMyNzYVFAYHBiMiJjU0NjchIiYmNTQ2NjMhESMiJiY1NDY2MyEyFhURIQIwOTRGRzk1RgGsGg0NGhj+2JxYLkozFBRmcnaAYVn+2RgaDQ0aGAER1RgaDQ0aGAGQIh0BGQQxHSKkIxwdIqQiHfycESwqKiwQfFdDDQhpISQHImhjUIE8ECwqKiwRAgIQLCoqLBEdIv1wAP//AKoAAAQiBmEAIgAsAAABBwEtAAABDgAJsQEBuAEOsDUrAAAC/+L/6gTgBKMAJwBRAIq1QQEBCAFMS7AXUFhAJgAIAAEACAGACgYEAwAABV8NCwwDBQUiTQkDAgEBAmEHAQICIwJOG0AxAAgAAQAIAYAKBgQDAAAFXw0LDAMFBSJNCQMCAQECXwACAiNNCQMCAQEHYQAHBykHTllAHigoAAAoUShPSUdEQj48NTMwLgAnACUhJjYhJg4IGysAFhYVFAYGIyMRMzIWFhUUBgYjISImJjU0NjYzMxEjIiYmNTQ2NjMhIBYWFRQGBiMjERQGIyImJyY1ETQ2MzIWFRUWMzI2NREjIiYmNTQ2NjMhAZkaDQ0aGC44GBoNDRoY/pYYGg0NGhg4LhgaDQ0aGAFWAzgaDQ0aGC6fokyiPhM7Q0IwJScoIpwYGg0NGhgBxASjESwqKiwQ/PcRLCoqLBAQLCoqLBEDCRAsKiosEREsKiosEP1Pnp0sJQwlAUciHRwj1RE0OAKdECwqKiwRAAQAJf5mBGMFUwANABsAPQBfAOpLsAxQWEAzAgEAAAFhDwMOAwEBKk0MAQcHCF8RDRADCAglTQYBBAQFXwAFBSNNCwEKCglhAAkJLQlOG0uwIFBYQDoACgULBQoLgAIBAAABYQ8DDgMBASpNDAEHBwhfEQ0QAwgIJU0GAQQEBV8ABQUjTQALCwlhAAkJLQlOG0A4AAoFCwUKC4APAw4DAQIBAAgBAGkMAQcHCF8RDRADCAglTQYBBAQFXwAFBSNNAAsLCWEACQktCU5ZWUAuPj4cHA4OAAA+Xz5dV1VTUU5NRUMcPRw7NTMyMConIR8OGw4aFRMADQAMJRIIFysAFhUVFAYjIiY1NTQ2MyAWFRUUBiMiJjU1NDYzABYVETMyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzISAWFREUBiMiJyYmNTQ3NjYzMhcWMzI1ESMiJiY1NDY2MyEBqjk1RkY5NEYCxzk1RkY5NEb94x2NGBoNDRoY/fQYGg0NGhiFexgaDQ0aGAE2AqIdt66HhBsaCg4kGgsRaU+BtxgaDQ0aGAFyBVMdIqQiHR0ipCMcHSKkIh0dIqQjHP5JHSL9cBEsKiosEBAsKiosEQICECwqKiwRHSL8hbrCLgoiGxUlLywFIqYC4BAsKiosEf//AGP/6gSaBpAAJwEqAKABDgECAC0AAAAJsQABuAEOsDUrAP//AJ/+ZgQ6BYIAIgEqbgAAAgEpAAAAAP//ADL94ATMBKMAIgAuAAAAAwGABOAAAP//ADn94ASRBSAAIgBOAAAAAwGABMwAAP//ADwAAARgBrIAJwBz/zYBDgECAC8AAAAJsQABuAEOsDUrAP//AJ0AAAQ/BxYAJwBz/+ABcgECAE8AAAAJsQABuAFysDUrAP//ADz94ARgBKMAIgAvAAAAAwGABMwAAP//AJ394AQ/BSAAIgBPAAAAAwGABMIAAP//ADwAAATABKMAIgAvAAABBwGEAoD/gwAJsQEBuP+DsDUrAP//AHUAAATABSAAIgBP2AAAAwGEAoAAAAABAAMAAARgBKMAQwDEQAw4CQIDAS0UAgYDAkxLsBtQWEAsAAMBBgEDBoAABgIBBgJ+BwEAAAhfCQEICCJNAAEBJU0FAQICBGAABAQjBE4bS7AxUFhALgABAAMAAQOAAAMGAAMGfgAGAgAGAn4HAQAACF8JAQgIIk0FAQICBGAABAQjBE4bQDQAAQADAAEDgAADBgADBn4ABgIABgJ+AAUCBAIFcgcBAAAIXwkBCAgiTQACAgRgAAQEIwROWVlAEQAAAEMAQSgjJjYjGCMmCggeKwAWFhUUBgYjIxU3NjMyFhcWFRQHBREhETQ2MzIWFhURFAYjISImJjU0NjYzMzUHBiMiJicmNTQ3NxEjIiYmNTQ2NjMhAvkaDQ0aGNqrFA8QIRcdH/7sAV89Ry8zFB4j/FwYGg0NGhiSghMPESIVHiDqkhgaDQ0aGAJmBKMRLCoqLBDQZgwfJTEbGROk/r8BOCIdDRoY/jIiHxAsKiosEbdNDB8kNRgZE4sBZBAsKiosEQAAAQCdAAAEPwUgADkAcEAJLiMOAwQEAAFMS7AgUFhAJAAEAAEABAGAAAUFBl8HAQYGJE0AAAArTQMBAQECYAACAiMCThtAJAAABQQFAASAAAQBBQQBfgcBBgAFAAYFZwMBAQECYAACAiMCTllADwAAADkANygjJjYoJQgIHCsAFhURNzYzMhYXFhUUBwcRITIWFhUUBgYjISImJjU0NjYzIREHBiMiJicmNTQ3JREjIiYmNTQ2NjMhAsodkxQPECEXHR/8ARkYGg0NGhj83BgaDQ0aGAERmhMPESIVHiABAukYGg0NGhgBpAUgHSL+jlgMHyUxGxkTlv5MESwqKiwQECwqKiwRASBbDB8kNRgZE5kBeBAsKiosEQD//wAy/+oErgayACcAc//+AQ4BAgAxAAAACbEAAbgBDrA1KwD//wA5AAAErwWkACIAUQAAAAIAc/4AAAD//wAy/eAErgSjACIAMQAAAAMBgATMAAD//wA5/eAErwOyACIAUQAAAAMBgATMAAD//wAy/+oErgaaACIAMQAAAQcBKwAAAQ4ACbEBAbgBDrA1KwD//wA5AAAErwWMACIAUQAAAAIBKwAAAAD//wA//+oEjQYJACIAMgAAAQcAbgAAAQ4ACbECAbgBDrA1KwD//wBv/+oEXQT7ACIAbgAAAAIAUgAAAAD//wA//+oEjQaQACIAMgAAAQcBMQAAAQ4ACbECArgBDrA1KwD//wBv/+oEhQWCACIBMQAAAAIAUgAAAAAAAgA/AAAEkgSjACwANAC6QAo0AQABMwEEBQJMS7AKUFhALAAAAQIBAHIABQMEBAVyAAIAAwUCA2kAAQEHXwgBBwciTQAEBAZgAAYGIwZOG0uwDlBYQC0AAAECAQByAAUDBAMFBIAAAgADBQIDaQABAQdfCAEHByJNAAQEBmAABgYjBk4bQC4AAAECAQACgAAFAwQDBQSAAAIAAwUCA2kAAQEHXwgBBwciTQAEBAZgAAYGIwZOWVlAEAAAACwAKjYjESQhEyUJCB0rABYVERQGIyImNTUjFTMyFhUUBiMjETM1NDYzMhYWFREUBiMhIiYCNTQSNjMhBAYVFBYWFxEEYB40PDooqnIjHBwjcrQ1PyotER4j/gGl739/76UB6/1zgTxrRgSjHiP+8CIdHCOE/S4+Pi3+y7YiHQ0aGP6+Ih+LAQu8vAELiuC/snimVwYC9QADABv/6gSpA7IAKQA1ADsAWEBVJgEIBRoBAwECTAACAAEAAgGAAAkAAAIJAGcNCgwDCAgFYQsGAgUFK00HAQEBA2EEAQMDKQNONjYqKgAANjs2Ojg3KjUqNDAuACkAKCQkKCMhJA4IHCsAEhUUBiMhFjMyNjc2MzIWFxYVFAYHBiMiJicGBiMiAjU0EjMyFhc2NjMEBhUUFjMyNjU0JiMgBzMmJiMEEJkdIv5qGIIxXTgPDBgjDg0VF5t/UH4pKHZKuaysuUt5KC16R/3mNzdAQDc3QAFqFvQCODQDsv7x8yIcpRkZBiooJBwYHwtHODIyOAEE4OABBDk1NDrje4aGe3uGhnuaSVEA//8APAAABLgGsgAnAHP/6gEOAQIANQAAAAmxAAG4AQ6wNSsA//8AfwAABGsFpAAiAHMyAAACAFUAAAAA//8APP3gBLgEowAiADUAAAADAYAEzAAA//8Af/3gBGsDsgAiAFUAAAADAYAEaAAA//8APAAABLgGmgAiADUAAAEHASv/7AEOAAmxAgG4AQ6wNSsA//8AfwAABGsFjAAiAFUAAAACASseAAAA//8Alf/qBD8GsgAiADYAAAEHAHP/6gEOAAmxAQG4AQ6wNSsA//8ApP/qBC4FpAAiAFYAAAACAHPqAAAA//8Alf/qBD8GkAAnASr//AEOAQIANgAAAAmxAAG4AQ6wNSsA//8ApP/qBC4FggAiASr2AAACAFYAAAAAAAEAlf4oBD8EuQBoAQhLsBBQWEAPSgEMCSMhAgAIDQECAwNMG0APSgEMCSMhAgAIDQECBANMWUuwDFBYQDkAAQAFAwFyAAgABQMIBWkEAQMAAgMCZgAMDAlhCgEJCShNAAsLCWEKAQkJKE0ABwcAYQYBAAApAE4bS7AQUFhAOgABAAUAAQWAAAgABQMIBWkEAQMAAgMCZgAMDAlhCgEJCShNAAsLCWEKAQkJKE0ABwcAYQYBAAApAE4bQEEAAQAFAAEFgAADBQQFAwSAAAgABQMIBWkABAACBAJmAAwMCWEKAQkJKE0ACwsJYQoBCQkoTQAHBwBhBgEAACkATllZQBRcWlZUT01IRiQlJ1QjFiQREQ0IHyskBgcVMhYVFAYjIicmNTQ3NjMyFxYzMjY1NCYjBwYjIjU1JicVFAYjIiY1ETQ2MzIWFxYWMzI2NTQmJyYmJyYmJyYmNTQ2NjMyFhc1NDYzMhYVERQGIyImJyYmIyIGFRQWFxYXFhYXFhUEP763a22PiJNtGAoYHgQIUk8xLzArFwgQJVA8MT9ANisxIykLNpZkWFwpJyBNS1ZwMUxWYrFyUIgyMT9ANisxISYLL5RhSVMkIixraIQ6oLnDCz5pVWBnKgodExpAAh0ZGhoVAQEpsBo1JiIdHSIBTiIdEhZnaEhAKDcTEBQQEh4aKIVqaqVcNDAlIh0dIv7uIh0QEEpRSjsdJQ4REhQjJGHYAAEApP4oBC4DsgBiASRLsBBQWEAPRQEMCSMhAgAIDQECAwNMG0APRQEMCSMhAgAIDQECBANMWUuwDFBYQEIAAQAFAwFyAAUDAAVwBAEDAAIDAmYADAwJYQoBCQkrTQALCwlhCgEJCStNAAcHAGEGAQAAKU0ACAgAYQYBAAApAE4bS7AQUFhARAABAAUAAQWAAAUDAAUDfgQBAwACAwJmAAwMCWEKAQkJK00ACwsJYQoBCQkrTQAHBwBhBgEAAClNAAgIAGEGAQAAKQBOG0BKAAEABQABBYAABQMABQN+AAMEAAMEfgAEAAIEAmYADAwJYQoBCQkrTQALCwlhCgEJCStNAAcHAGEGAQAAKU0ACAgAYQYBAAApAE5ZWUAUVlRRT0pIREIjJSdUIxYkERENCB8rJAYHFTIWFRQGIyInJjU0NzYzMhcWMzI2NTQmIwcGIyI1NSYnFRQGIyImNTU0NjMyFxYWMzI1NCYnJicmJicmNTQ2NjMyFzU0NjMyFhUVFAYjIicmJiMiBhUUFxYXFhYXFhYVBC60pmttj4iTbRgKGB4ECFJPMS8wKxcIECVDOjpAQDYvMT0WMpxdoC0sGVtlkTuKXqVnl3UxP0A2KzE1FDuYZDtDSideXXs3UFqaows/aVVgZyoKHRMaQAIdGRoaFQEBKasTIwgiHR0i3yEeHD86UxkeCgUNDB8hTKRXgkVJCiIdHSLTIh0VPzUqIyoSCgkLFhYhdmH//wCV/+oEPwaaACIANgAAAQcBK//7AQ4ACbEBAbgBDrA1KwD//wCk/+oELgWMACIAVgAAAAIBK/kAAAD//wBi/eAEagSjACIANwAAAAMBgAS4AAD//wBh/eAEVQS5ACIAVwAAAAMBgAT0AAD//wBiAAAEagaaACIANwAAAQcBKwAAAQ4ACbEBAbgBDrA1KwD//wBh/+oEVQV4ACIAVwAAAQcBgAYCBgoACbEBAbgGCrA1KwD//wAy/+oEmgYJACcAbgAAAQ4BAgA4AAAACbEAAbgBDrA1KwD//wAy/+oElAT7ACIAbgAAAAIAWAAAAAD//wAy/+oEmgaAACIAOAAAAQcBLAAAAQ4ACbEBAbgBDrA1KwD//wAy/+oElAVyACIAWAAAAAIBLOwAAAD//wAy/+oEmgcjACIAOAAAAQcBLgAAAQ4ACbEBArgBDrA1KwD//wAy/+oElAYVACIAWAAAAAIBLuIAAAD//wAy/+oEmgaQACIAOAAAAQcBMQAAAQ4ACbEBArgBDrA1KwD//wAy/+oElAWCACIAWAAAAAIBMdgAAAAAAQAy/igEmgSjAEkANkAzAAEAAgECZQgGBAMAAAVfCgkCBQUiTQAHBwNhAAMDKQNOAAAASQBHIyMmNiQVJycmCwgfKwAWFhUUBgYjIxEUBgcGFRQzMjc2FRQGBwYjIiY1NDY3LgI1ESMiJiY1NDY2MyEyFhYVFAYGIyMRFBYzMjY1ESMiJiY1NDY2MyEEcxoNDRoYL25nwVguSjMUFGZydoBRS4G6ZC8YGg0NGhgBdhgaDQ0aGE1uXl5uTRgaDQ0aGAF2BKMRLCoqLBD9x4vEMo9gQw0IaSEkByJoY0l4NwdpvoQCORAsKiosEREsKiosEP3bc3FxcwIlECwqKiwRAAEAMv4oBKEDnABLAIVLsBdQWEAKDgEEAgoBAQQCTBtACg4BBAIKAQgEAkxZS7AXUFhAIAAJAAAJAGUFAQICA18GAQMDJU0HAQQEAWEIAQEBKQFOG0AqAAkAAAkAZQUBAgIDXwYBAwMlTQcBBAQIYQAICCNNBwEEBAFhAAEBKQFOWUAOSEYmIzYkJTYkKiMKCB8rAAYHBiMiJjU0NjcmJjU1BiMiJiY1ESMiJiY1NDY2MyEyFhURFBYzMjY2NTUjIiYmNTQ2NjMhMhYVETMyFhYVFAYGIyMGFRQzMjc2FQShFBRmcnaAYlkaFoTGW4lKTRgaDQ0aGAEIIh02PzpoP2sYGg0NGhgBJiIdTRgaDQ0aGBucWC5KM/51JAciaGNRgTwDHR6R5lCTYwGfESwqKiwQHSL+Dk5QYaJcoxEsKiosEB0i/XAQLCoqLBF8V0MNCGn//wAoAAAEpAZhACIAPAAAAQcAaQAAAQ4ACbEBArgBDrA1KwD//wCKAAAEOAayACIAPQAAAQcAc//+AQ4ACbEBAbgBDrA1KwD//wCKAAAEOAWkACIAXQAAAAIAc/QAAAD//wCKAAAEOAZhACcBLQAKAQ4BAgA9AAAACbEAAbgBDrA1KwD//wCKAAAEOAVTACIAXQAAAAIBLQoAAAD//wCKAAAEOAaaACIAPQAAAQcBKwAIAQ4ACbEBAbgBDrA1KwD//wCKAAAEOAWMACIAXQAAAAIBKwcAAAAAAQAD/ukEiQUlADkAqEuwE1BYQB8IAQIHAQMFAgNnBgEFAAQFBGUBAQAACWEKAQkJJABOG0uwIFBYQC0AAAECAQACgAAFAwYDBQaACAECBwEDBQIDZwAGAAQGBGUAAQEJYQoBCQkkAU4bQDMAAAECAQACgAAFAwYDBQaACgEJAAEACQFpCAECBwEDBQIDZwAGBAQGWQAGBgRhAAQGBFFZWUASAAAAOQA4JCIjGCMkIiMYCwgfKwAXFhYVFAcGBiMiJyYjIgcHMzIWFRQGIyEDBgYjIicmJjU0NzY2MzIXFjMyNxMjIiY1NDYzMzc2NjMD6G0aGggLJRsHElZQgg4G7SMcHCP/ADAQya5zbRoaCAslGwcSVlCCDi/GIxwcI9kHEMmuBSUhCCEgFiYwKAQXpjwuPj4t/dy6wiEIISAWJjAoBBemAhctPj4uSbrC//8Alf3gBD8EuQAiADYAAAADAYAEzAAA//8ApP3gBC4DsgAiAFYAAAADAYAEzAAAAAEAn/5mA5sDnAAiAC5AKwABAwIDAQKAAAMDBF8FAQQEJU0AAgIAYQAAAC0ATgAAACIAICIkGCUGCBorABYVERQGIyImJyY1NDc2NjMyFxYWMzI1ESEiJiY1NDY2MyEDfh23rla5Wy0SEiYZDhVSey6B/oEYGg0NGhgCOgOcHSL8hbrCMS4WLRwqKicIJSmmAuAQLCoqLBEAAQEAA/kDzAWCABkAJ7EGZERAHAwBAAIBTAMBAgAChQEBAAB2AAAAGQAYJRgECBgrsQYARAAWFwUWFRQHBiMiJycHBiMiJyY1NDclNjYzAoAfDgEJFhkeHhAR8PAREB4eGRYBCQ4fGgWCCwzhExcZIysLiooLKyMZFxPhDAsAAQEABAMDzAWMABkAJ7EGZERAHAwBAgABTAEBAAIAhQMBAgJ2AAAAGQAYJRgECBgrsQYARAAmJyUmNTQ3NjMyFxc3NjMyFxYVFAcFBgYjAkwfDv73FhkeHhAR8PAREB4eGRb+9w4fGgQDCwzhExcZIysLiooLKyMZFxPhDAsAAQEFBBEDxwVyAB0AL7EGZERAJAoCAgIBAUwDAQECAYUAAgAAAlkAAgIAYQAAAgBREyMoJgQIGiuxBgBEABYVFAcGBiMiJicmNTQ2NzYzMhcWFjMyNjc2MzIXA6cgARi0lJS0GAEgIhgTIAsXYVFRYRcLIBMYBWIdFQkEf5OTfwQJFR0JBxtAOjpAGwcAAAEB6QQxAuMFUwANACexBmREQBwCAQEAAAFZAgEBAQBhAAABAFEAAAANAAwlAwgXK7EGAEQAFhUVFAYjIiY1NTQ2MwKqOTVGRjk0RgVTHSKkIh0dIqQjHAACAWAECQNsBhUADwAbADexBmREQCwEAQEFAQMCAQNpAAIAAAJZAAICAGEAAAIAURAQAAAQGxAaFhQADwAOJgYIFyuxBgBEABYWFRQGBiMiJiY1NDY2MwYGFRQWMzI2NTQmIwKweEREeEpKeEREeEoqMjIqKjIyKgYVRHhKSnhERHhKSnhEqjIqKjIyKioyAAABAV3+KANTABwAEwAmsQZkREAbAAIAAoUAAAEBAFkAAAABYgABAAFSFSciAwgZK7EGAEQEFRQzMjc2FRQGBwYjIiY1NDY3MwJQWC5KMxQUZnJ2gHhtz3NgQw0IaSEkByJoY1qLRAABAOMEJAPpBWAAJQA0sQZkREApAAADAgBZBgUCAQADAgEDaQAAAAJhBAECAAJRAAAAJQAkIiQnIiQHCBsrsQYARAAWFxYWMzI3NjMyFxYVFAcGBiMiJicmJiMiBwYjIicmNTQ3NjYzAg1CLCQtGD1EDhAdJSQKM4BFKEIsJC0YPUQOEB0lJAozgEUFWxgWEhFIDigoJBQOTFUYFhIRSA4oKCQUDkxVAAACARkEDgSFBYIAEgAlACSxBmREQBkUAQIAAQFMAwEBAAGFAgEAAHYoJyglBAgaK7EGAEQAFRQHBQYjIicmJjU0NxM2MzIXBBUUBwUGIyInJiY1NDcTNjMyFwLXDv73Eh0cJxobCN0TJSQ2AfUO/vcSHRwnGhsI3RMlJDYFSiEPDPAQDwoZDgoKAQoWGCAhDwzwEA8KGQ4KCgEKFhgAAAEARgAABIYDnAAhACVAIgQCAgAABV8GAQUFFk0DAQEBFQFOAAAAIQAfIzMTMyQHBxsrABYVFAYjIxEUBiMjIiY1ESERFAYjIyImNREjIiY1NDYzIQRqHBwjUx0ifCId/tgdInwiHVMjHBwjA8IDnC9CQi79hCIdHSICfP2EIh0dIgJ8LkJCLwABAKoB1gQiArcAEQAfQBwCAQEAAAFXAgEBAQBfAAABAE8AAAARAA82AwgXKwAWFhUUBgYjISImJjU0NjYzIQP7Gg0NGhj9BhgaDQ0aGAL6ArcSMC8vMBERMC8vMBIAAf/iAdYE6gK3ABEAH0AcAgEBAAABVwIBAQEAXwAAAQBPAAAAEQAPNgMIFysAFhYVFAYGIyEiJiY1NDY2MyEEwxoNDRoY+3YYGg0NGhgEigK3EjAvLzARETAvLzASAAEBewLFAyIFGwASADS1CwEBAAFMS7AgUFhACwABAQBhAAAAJAFOG0AQAAABAQBZAAAAAV8AAQABT1m0JycCCBgrACY1NDcTNjYzMhYVFAcDBgYjIwGNEgfPEDwyKygDWgQbFfMCxRIPDw8B0yUfHCALD/4oExUAAAEBmwKfA0IE9QASADS1CwEAAQFMS7AXUFhACwAAAAFfAAEBJABOG0AQAAEAAAFXAAEBAGEAAAEAUVm0JycCCBgrABYVFAcDBgYjIiY1NDcTNjYzMwMwEgfPEDwyKygDWgQbFfME9RIPDw/+LSUfHCALDwHYExUA//8Bm/7aA0IBMAEHATYAAPw7AAmxAAG4/DuwNSsAAAD//wBjAsUEOgUbACMBNf7oAAAAAwE1ARgAAAAA//8AgwKfBFoE9QAjATb+6AAAAAMBNgEYAAAAAP//AIP+2gRaATAAIwE3ARgAAAADATf+6AAAAAAAAQD6APgD0gS5ACcAKUAmAwEBAQBfBAEAACVNAAICBWEGAQUFKAJOAAAAJwAmJiQkJiQHCBsrABYWFRUzMhYWFRQGBiMjERQGBiMiJiY1ESMiJiY1NDY2MzM1NDY2MwKVMBG9GBoNDRoYvREwLy8wErwYGg0NGhi8EjAvBLkNGhjeEjAvLzAR/nwYGg0NGhgBhBEwLy8wEt4YGg0AAQD6AKgD0gS5AD0ANUAyCAEABwEBAgABZwYBAgUBAwQCA2cABAQJYQoBCQkoBE4AAAA9ADwmISYkJCYhJiQLCB8rABYWFRUzMhYWFRQGBiMjFTMyFhYVFAYGIyMVFAYGIyImJjU1IyImJjU0NjYzMzUjIiYmNTQ2NjMzNTQ2NjMClTARvRgaDQ0aGL29GBoNDRoYvREwLy8wErwYGg0NGhi8vBgaDQ0aGLwSMC8EuQ0aGI4SMC8vMBG1EjAvLzARjhgaDQ0aGI4RMC8vMBK1ETAvLzASjhgaDQABAWcBNgNlA1oADQAfQBwCAQEAAAFZAgEBAQBhAAABAFEAAAANAAwlAwgXKwAWFREUBiMiJjURNDYzAu14eIeHeHiHA1oyOv60OjIyOgFMOjIAAwBZ//YEcwEiAA0AGwApAC9ALAgFBwMGBQEBAGEEAgIAACMAThwcDg4AABwpHCgjIQ4bDhoVEwANAAwlCQgXKwAWFRUUBiMiJjU1NDYzIBYVFRQGIyImNTU0NjMgFhUVFAYjIiY1NTQ2MwEYOztCQjs7QgHSOztCQjs7QgHSOztCQjs7QgEiHSKuIh0dIq4iHR0iriIdHSKuIh0dIq4iHR0iriIdAAYAMv/qBgMEuQAPACMALwBLAFcAYwCFQIIWAQQFSAELCCABCgs6AQYDBEwAAgEFAQIFgAADCgYKAwaAAAQAAAgEAGkQCQIIEg0RAwsKCAtpDwEFBQFhDgEBAShNDAEKCgZhBwEGBikGTlhYTEwwMCQkAABYY1hiXlxMV0xWUlAwSzBKRkQ+PDg2JC8kLiooHBoSEAAPAA4mEwgXKwAWFhUUBgYjIiYmNTQ2NjMEMzIWFxYVFAcBBiMiJicmNTQ3AQQGFRQWMzI2NTQmIwAWFhUUBgYjIiYnBgYjIiYmNTQ2NjMyFhc2NjMEBhUUFjMyNjU0JiMgBhUUFjMyNjU0JiMBjn5KSn5KSn5KSn5KAqkTDiMZLBb8kxcRDiMYLRcDbf1HMzMkJDMzJAP3fkpKfko2XCMiXDZKfkpKfko1XSIjXDb+czMzJCQzMyQBRTMzJCQzMyQEuUp+Skp+Skp+Skp+SmoXGi0cExb8vhUXGjAbERcDQj0zJCQzMyQkM/4QSn5KSn5KKCUlKEp+Skp+SikkJCm7MyQkMzMkJDMzJCQzMyQkMwAAAQFiAH0DRwOyABcAGkAXCAUCAQABTAABAQBhAAAAKwFOLCACCBgrADMyFxYVFAcHFxYVFAcGIyInASY1NDcBApEZIzlBDtHRDkE5IxkP/ukJCQEXA7InLCoSEfr7ERIqLCcTAW4MDg8KAW4AAQGFAH0DagOyABcAG0AYFw0KAwABAUwAAAABYQABASsATiwlAggYKwAVFAcBBiMiJyY1NDc3JyY1NDc2MzIXAQNqCf7pDxkjOUEO0dEOQTkjGQ8BFwInDw4M/pITJywqEhH7+hESKiwnE/6SAAABAFUAwwR2A1cAEQAYQBUOBQIBAAFMAAABAIUAAQF2GBECCBgrADMyFxYVFAcBBiMiJyY1NDcBBB4IGx0YFPxXDAgbHRgUA6kDVy0kFhMM/fcFLSQWEwwCCQACADIC7AUJBSoAJQA8AmS3IRIKAwEFAUxLsApQWEAnAAEFAAUBAIAGAgIAAIQKCAkEBAMFBQNZCggJBAQDAwVhBwEFAwVRG0uwDFBYQCgJBAIDCAOFAAEFAAUBAIAGAgIAAIQKAQgFBQhXCgEICAVhBwEFCAVRG0uwDVBYQCcAAQUABQEAgAYCAgAAhAoICQQEAwUFA1kKCAkEBAMDBWEHAQUDBVEbS7APUFhAKAkEAgMIA4UAAQUABQEAgAYCAgAAhAoBCAUFCFcKAQgIBWEHAQUIBVEbS7AQUFhAJwABBQAFAQCABgICAACECggJBAQDBQUDWQoICQQEAwMFYQcBBQMFURtLsBJQWEAoCQQCAwgDhQABBQAFAQCABgICAACECgEIBQUIVwoBCAgFYQcBBQgFURtLsBNQWEAnAAEFAAUBAIAGAgIAAIQKCAkEBAMFBQNZCggJBAQDAwVhBwEFAwVRG0uwFVBYQCgJBAIDCAOFAAEFAAUBAIAGAgIAAIQKAQgFBQhXCgEICAVhBwEFCAVRG0uwFlBYQCcAAQUABQEAgAYCAgAAhAoICQQEAwUFA1kKCAkEBAMDBWEHAQUDBVEbS7AYUFhAKAkEAgMIA4UAAQUABQEAgAYCAgAAhAoBCAUFCFcKAQgIBWEHAQUIBVEbS7AZUFhAJwABBQAFAQCABgICAACECggJBAQDBQUDWQoICQQEAwMFYQcBBQMFURtAKAkEAgMIA4UAAQUABQEAgAYCAgAAhAoBCAUFCFcKAQgIBWEHAQUIBVFZWVlZWVlZWVlZWUAZJiYAACY8Jjo2NDEvLCoAJQAkJSYmJQsGGisAFhcTFgYjIiYnJwcGBiMiJicnBwYGIyImNxM2NjMyFhcTEzY2MwQWFRQGIyMRFAYjIiY1ESMiJjU0NjMhBMEmAh4CHi0tJAIKWwwnFRUnDFwJAiQtLR4CHgImLSEgCYyMCSAh/ZIcGyR5IDAwIHkkGxwjAZIFKh4j/kQkHR4j2aUXGBgXpdkjHh0kAbwjHg0Q/wABABANCh8vLx7+qCQdHSQBWB4vLx8AAQAsAAAEoAS5ADsAKUAmAAICBWEGAQUFFE0EAQAAAV8DAQEBFQFOAAAAOwA6JjsrNiYHBxsrABYWFRQGBzMyFhYVFAYGIyEiJiY1NDY3NjY1NCYjIgYVFBYXFhYVFAYGIyEiJiY1NDY2MzMmJjU0NjYzAwr6iWZfmRgaDQ0aGP6OGBoNCxFfVpCLi5BWXxELDRoY/o4YGg0NGhiZX2aJ+qQEuYn/rX3OThQzLy8zExlCPjQwCz+6g6SurqSDuj8LMDQ+QhkTMy8vMxROzn2t/4kAAgCT/+kEIgS5ACYAMgBMQEkUAQYBLwEFBgJMAAMCAQIDAYAHAQQAAgMEAmkAAQgBBgUBBmkABQAABVkABQUAYQAABQBRJycAACcyJzEtKwAmACUxJiYoCQYaKwAWFhUUBgcGBiMiJiY1NDY2MzIWFzY1NCYjIgcGIyInJjU0Njc2MwIGFRQWNzY2NyYmIwLzwG8iH0LoqXOrXWSwbViOLwd3cDtSCgQnGwsbG3Ntk11PQVJqIhpkQgS5atedWL5dwr1Zp3R0smJEQDIxiYoWAlYmFRofCSf9SFlMQU4BAVhcOUUAAgCRAAAEOwS5ABQAGAAgQB0DAQEBFE0AAgIAXwAAABUATgAAFxYAFAATOAQHFysAFhcBFhUUBgYjISImJjU0NwE2NjMDAyEDAq5GCwE1Bw0aGPzUGBoNBwE5C0ZHA7oBdLYEuR4j/DEVLiosEBAsKi4VA88kHf6b/Y0CcwAAAQCgAAAELASjABkAJ0AkAgEAAQCGBAEDAQEDVwQBAwMBXwABAwFPAAAAGQAXMxM1BQYZKwAWFREUBiMjIiY1ESERFAYjIyImNRE0NjMhBA8dHSJ8Ih3+aB0ifCIdHSIDDgSjHSL72yIdHSIDefyHIh0dIgQlIh0AAQCqAAAEGgSjACkALkArIAEBAAFMBAEDAAABAwBnAAECAgFXAAEBAl8AAgECTwAAACkAJzYmJgUGGSsAFhYVFAYGIyETFhUUBwEhMhYWFRQGBiMhIiYmNTQ2NwEBJiY1NDY2MyED3xoNDRoY/lv+Cwv+7QHOGBoNDRoY/Q4YGg0GCQFZ/rsJBg0aGALKBKMUMy8vMxP+xg4QEQ7+qhQzLy8zExEsKhsjCwGvAZQLIxsqLBEAAQCqAdYEIgK3ABEAH0AcAgEBAAABVwIBAQEAXwAAAQBPAAAAEQAPNgMGFysAFhYVFAYGIyEiJiY1NDY2MyED+xoNDRoY/QYYGg0NGhgC+gK3EjAvLzARETAvLzASAAEAZP/qBG0EsQAgAC5AKwIBAgMaAQABAkwAAwIDhQAAAQCGAAIBAQJXAAICAWEAAQIBUSY2IycEBhorABYVFAcBBgYjIiYnAyMiJiY1NDY2MyEyFhcTATY2MzIXBD0wBf6RDUVHRkIPsXUYGg0NGhgBARUZB4MBFAcgHSAzBJkkGQsP++kkHR4jAasRMC8vMBINEf67AzQWEwwAAAMAEgERBLoDewAbACcAMwBOQEsYAQUCKiQCBAUKAQAEA0wIAwICCgcJAwUEAgVpBgEEAAAEWQYBBAQAYQEBAAQAUSgoHBwAACgzKDIuLBwnHCYiIAAbABomJCYLBhkrABYWFRQGBiMiJicGBiMiJiY1NDY2MzIWFzY2MwQGFRQWMzI2NyYmIyAGBxYWMzI2NTQmIwPqhUtLhVJikEBBj2JShUtLhVJijkJAkGL9cEREOTZXLS1YNQIVWC4uVzY5REQ5A3tRjVdXjVFaUFBaUY1XV41RWlBPW8JCMTFCOzg3PDs4ODtCMTFCAAEABf5mBMcF7QAlADlANgAAAQMBAAOAAAMEAQMEfgYBBQABAAUBaQAEAgIEWQAEBAJhAAIEAlEAAAAlACQjFyQjFwcGGysAFhcWFRQHBiMiJyYjIhURFAYjIiYnJjU0NzYzMhcWMzI1ETQ2MwOisEsqDh8xDROGX4G3rlWwSioOHzENE4RhgbeuBe0vKRcsGCVRCD6m+366wi8pFywYJVEIPqYEgrrC//8AgQCmBEsD4wAnAGEAAADmAQcAYQAA/xoAEbEAAbDmsDUrsQEBuP8asDUrAAAAAAEAqgAvBCIEXgBBAHRLsA5QWEArAAYFBQZwAAEAAAFxBwEFCAEEAwUEaAoJAgMAAANXCgkCAwMAYQIBAAMAURtAKQAGBQaFAAEAAYYHAQUIAQQDBQRoCgkCAwAAA1cKCQIDAwBhAgEAAwBRWUASAAAAQQBAJicjJiEmJyMmCwYfKwAWFhUUBgYjIQcGBiMiJyYmNTQ3NyMiJiY1NDY2MzM3ISImJjU0NjYzITc2NjMyFxYWFRQHBzMyFhYVFAYGIyMHIQP7Gg0NGhj+P1UJFg8WLCIdCydnGBoNDRoY1X3+rhgaDQ0aGAHBVQkWDxYsIh0LJmYYGg0NGhjVfQFSAdISMC8vMBGfEhEXEh4RDxNIETAvLzAS6REwLy8wEp8SERcTHhEOFEcSMC8vMBHpAAACAKoAAAQoBHkAHQAvADNAMAoBAQABTAAAAQCFAAEDAYUEAQMCAgNXBAEDAwJfAAIDAk8eHh4vHi0nJBMSIAUGFysAMzIWFxYVFAYHBQUWFhUUBwYGIyInASYmNTQ2NwESFhYVFAYGIyEiJiY1NDY2MyEDvwwWJBIRFBX+FAHsFRQREiQWDA79JxkVFRkC2UoaDQ0aGP0GGBoNDRoYAvoEeSwyLRwVGAi0tAgYFRwtMiwGASwLKSoqKQsBLPxuEjAvLzARETAvLzASAAACAKQAAAQiBHkAHQAvADNAMBEBAAEBTAABAAGFAAADAIUEAQMCAgNXBAEDAwJfAAIDAk8eHh4vHi0nJBoZGAUGFysAFhUUBgcBBiMiJicmNTQ2NyUlJiY1NDc2NjMyFwESFhYVFAYGIyEiJiY1NDY2MyEEDRUVGf0nDQ0WJBIRFBUB7P4UFRQREiQWDQ0C2QcaDQ0aGP0GGBoNDRoYAvoDPCkqKikL/tQGLDItHBUYCLS0CBgVHC0yLAb+1P2aEjAvLzARETAvLzASAAACAK//6gQcBLkAFwAbAB9AHBsaGQMAAQFMAgEBAAGFAAAAdgAAABcAFioDBhcrABYXARYVFAcBBgYjIiYnASY1NDcBNjYzAxMTAwKcPxMBJggI/toTPzY2PhT+2QgIAScUPja6urq6BLkeI/33DRERDf34Ix4eIwIIEA4OEAIJIx79mP6xAU8BUAAB/+wAAATMBTkAQgCpS7AZUFhALAAHCAUIBwWAAAgIBmEABgYkTQQBAgIFXwkBBQUlTQsKAgEBAGEDAQAAIwBOG0uwIFBYQCoABwgFCAcFgAkBBQQBAgEFAmcACAgGYQAGBiRNCwoCAQEAYQMBAAAjAE4bQCgABwgFCAcFgAAGAAgHBghpCQEFBAECAQUCZwsKAgEBAGEDAQAAIwBOWVlAFAAAAEIAQT48IxgjJSQ0ESY2DAgfKyQWFhUUBgYjISImJjU0NjYzMxEhERQGBiMjIiYmNREjIiY1NDY2MzM1NDYzMhcWFhUUBwYGIyInJiMiFRUhMhYVETMEpRoNDRoY/fcYGg0NGhiJ/qsNHBl2GRwNkyMcDRoYk7eulZsZGQoMIxgMEX9fgQIQIh2GzREsKiosEBAsKiosEQHc/bImJw4OJyYCTis+KSoPSbrCOQkhHBokLCYFJ6Y8HCH9lgAAAQAFAAAExwU5AEIAlrUSAQMCAUxLsBlQWEAkAAICCGEACAgkTQYBBAQDYQcBAwMlTQoJAgEBAGEFAQAAIwBOG0uwIFBYQCIHAQMGAQQBAwRpAAICCGEACAgkTQoJAgEBAGEFAQAAIwBOG0AgAAgAAgMIAmkHAQMGAQQBAwRpCgkCAQEAYQUBAAAjAE5ZWUASAAAAQgBBJCUkNCUjIiY2CwgfKyQWFhUUBgYjISImJjU0NjYzMxEmIyIGFRUzMhYWFRQGIyMRFAYGIyMiJiY1ESMiJjU0NjYzMzU0NjYzMhYXFhYVETMEoBoNDRoY/gAYGg0NGhiHXG1LSKYYGg0cI6YNHBl2GRwNdSMcDRoYdV2sdH/CWx0af80RLCoqLBAQLCoqLBEDZiNQVjwPKik+K/2yJicODicmAk4rPikqD0lzrF0xJAspIvw/AAABAGL+KARqBKMATQD2S7AQUFi1IQEFBgFMG7UhAQUHAUxZS7AMUFhAOAwBAAECAQACgAAEAwgGBHIACAYDCAZ+BwEGAAUGBWYLAQEBDV8OAQ0NIk0KAQICA18JAQMDIwNOG0uwEFBYQDkMAQABAgEAAoAABAMIAwQIgAAIBgMIBn4HAQYABQYFZgsBAQENXw4BDQ0iTQoBAgIDXwkBAwMjA04bQD8MAQABAgEAAoAABAMIAwQIgAAIBgMIBn4ABgcDBgd+AAcABQcFZgsBAQENXw4BDQ0iTQoBAgIDXwkBAwMjA05ZWUAaAAAATQBLRkRBQD89NzVUIxYkESYhEyUPCB8rABYVERQGIyImNREjETMyFhYVFAYGIyMVMhYVFAYjIicmNTQ3NjMyFxYzMjY1NCYjBwYjIjU1IyImJjU0NjYzMxEjERQGIyImNRE0NjMhBEweNzk3K7XYGBoNDRoY92ttj4iTbRgKGB4ECFJPMS8wKxcIECX6GBoNDRoY2LU3OTcrHyIDhgSjHiP+WiEeHSIBEP0BESwqKiwQU2lVYGcqCh0TGkACHRkaGhUBASmwECwqKiwRAv/+8CEeHSIBpiMeAAEAYf4oBFUEuQBNAPlLsBBQWEAKJQEACxEBAgMCTBtACiUBAAsRAQIEAkxZS7AMUFhANwAMBgsGDAuAAAEABQMBcgAFAwAFcAkBBwoBBgwHBmcEAQMAAgMCZgAICChNAAsLAGEAAAApAE4bS7AQUFhAOQAMBgsGDAuAAAEABQABBYAABQMABQN+CQEHCgEGDAcGZwQBAwACAwJmAAgIKE0ACwsAYQAAACkAThtAPwAMBgsGDAuAAAEABQABBYAABQMABQN+AAMEAAMEfgkBBwoBBgwHBmcABAACBAJmAAgIKE0ACwsAYQAAACkATllZQBRLSUZEQkA8OiMkJlQjFiQRFQ0IHyskFRQGBwYHFTIWFRQGIyInJjU0NzYzMhcWMzI2NTQmIwcGIyI1NSYmNREjIiY1NDYzMxE0NjMyFhYVESEyFhUUBiMhERQzMjY3NjMyFhcEVRUVv45rbY+Ik20YChgeBAhSTzEvMCsXCBAlYGTBIxwcI8E9Ry8zFAFzIxwcI/6NgS57UhYNFSQQrBwWHQtgBz5pVWBnKgodExpAAh0ZGhoVAQEptSayiQEjLT4+LgEaIh0NGhj+5i4+Pi3+6qYpJQkjKAD//wA8AAAEYAaAACIAKAAAAQcBLAAAAQ4ACbEBAbgBDrA1KwD//wCqAAAEIgaAACIALAAAAQcBLAAAAQ4ACbEBAbgBDrA1KwD//wCqAAAEIgZuACcBMAAAAQ4BAgAsAAAACbEAAbgBDrA1KwAAAgA8AAAEYASjACsAOwDkS7AKUFhAKgACBwEBAnIFAQAABl8JAQYGIk0ABwcIYQoBCAglTQQBAQEDYAADAyMDThtLsCRQWEArAAIHAQcCAYAFAQAABl8JAQYGIk0ABwcIYQoBCAglTQQBAQEDYAADAyMDThtLsDFQWEApAAIHAQcCAYAKAQgABwIIB2kFAQAABl8JAQYGIk0EAQEBA2AAAwMjA04bQC8AAgcBBwIBgAAEAQMBBHIKAQgABwIIB2kFAQAABl8JAQYGIk0AAQEDYAADAyMDTllZWUAXLCwAACw7LDo0MgArACkhJjYjESYLCBwrABYWFRQGBiMjESE1NDYzMhYWFREUBiMhIiYmNTQ2NjMzESMiJiY1NDY2MyESFhYVFAYGIyImJjU0NjYzAvkaDQ0aGNoBXz1HLzMUHiP8XBgaDQ0aGJKSGBoNDRoYAmZ+UjExUjExUjExUjEEoxEsKiosEP0BtiIdDRoY/rQiHxAsKiosEQMJECwqKiwR/t0xUjExUjExUjExUjEAAAEAMv5mBK4EowBQAIBAC0QhAgQAIAEFBAJMS7AQUFhAJQkHAgAACF8LCgIICCJNBgEEBAVfAAUFI00DAQICAWEAAQEtAU4bQCwAAgUDBQIDgAkHAgAACF8LCgIICCJNBgEEBAVfAAUFI00AAwMBYQABAS0BTllAFAAAAFAATkhGNiEmNiYkGSMmDAgfKwAWFhUUBgYjIxEUBiMiJicmJjU0NzY2MzIXFhYzMjY1NQEjETMyFhYVFAYGIyEiJiY1NDY2MzMRIyImJjU0NjYzITIXATMRIyImJjU0NjYzIQSHGg0NGhg5trQxbjIWFgsMJBgGECVNG0FA/lQEbxgaDQ0aGP5sGBoNDRoYQ0MYGg0NGhgBCCgQAZ8EXBgaDQ0aGAF3BKMRLCoqLBD787GyFRMIIBoZLDErBAwOP0dqAsX9xREsKiosEBAsKiosEQMJECwqKiwRG/1RAf0QLCoqLBEA//8AP//qBI0GgAAiADIAAAEHASwAAAEOAAmxAgG4AQ6wNSsAAAEAYgAABGoEowBDAERAQQoBAAECAQACgAgBAgcBAwQCA2cJAQEBC18MAQsLIk0GAQQEBV8ABQUjBU4AAABDAEE8Ojc2JiEmNiEmIRMlDQgfKwAWFREUBiMiJjURIxEzMhYWFRQGBiMjFTMyFhYVFAYGIyEiJiY1NDY2MzM1IyImJjU0NjYzMxEjERQGIyImNRE0NjMhBEweNzk3K7WcGBoNDRoYnNgYGg0NGhj9VhgaDQ0aGNicGBoNDRoYnLU3OTcrHyIDhgSjHiP+WiEeHSIBEP5pESwqKiwQmxEsKiosEBAsKiosEZsQLCoqLBEBl/7wIR4dIgGmIx4A//8AMv/qBJoGbgAnATAAAAEOAQIAOAAAAAmxAAG4AQ6wNSsA////7P/qBOAGsgAiADoAAAEHAHMACgEOAAmxAQG4AQ6wNSsA////7P/qBOAGkAAiADoAAAEHASoACgEOAAmxAQG4AQ6wNSsA////7P/qBOAGYQAiADoAAAEHAGkACgEOAAmxAQK4AQ6wNSsA////7P/qBOAGsgAiADoAAAEHAEP/9gEOAAmxAQG4AQ6wNSsA//8AKAAABKQGkAAiADwAAAEHASoACgEOAAmxAQG4AQ6wNSsA//8AKAAABKQGsgAiADwAAAEHAEMAAAEOAAmxAQG4AQ6wNSsA//8Ag//qBE8FcgAiAEgAAAACASwKAAAAAAEApwAABEkDnAAhACdAJAADAwRfBQEEBCVNAgEAAAFfAAEBIwFOAAAAIQAfISY2IwYIGisAFhURITIWFhUUBgYjISImJjU0NjYzIREjIiYmNTQ2NjMhAtQdARkYGg0NGhj83BgaDQ0aGAER1RgaDQ0aGAGQA5wdIv1wESwqKiwQECwqKiwRAgIQLCoqLBEA//8ApwAABEkFcgAiAWUAAAACASz2AAAA//8ApwAABEkFYAAiAWUAAAACATDiAAAA//8AdQAABH0FIAAiAE/YAAEHAS0Bmv4MAAmxAQG4/gywNSsAAAEAV/5mBEEDsgBHALS1RQEEAwFMS7AQUFhAJAcBAwMIYQoJAggIJU0GAQQEBV8ABQUjTQIBAQEAYQAAAC0AThtLsBdQWEArAAEFAgUBAoAHAQMDCGEKCQIICCVNBgEEBAVfAAUFI00AAgIAYQAAAC0AThtANQABBQIFAQKABwEDAwlhCgEJCStNBwEDAwhfAAgIJU0GAQQEBV8ABQUjTQACAgBhAAAALQBOWVlAEgAAAEcARjYhJjYkJSQZJgsIHysAFhYVERQGIyImJyYmNTQ3NjYzMhcWFjMyNjURNCYjIgYGFRUzMhYWFRQGBiMhIiYmNTQ2NjMzESMiJiY1NDY2MzMyFhUVNjMDbolKtrQxbjIWFgsMJBgGECVNGz45Nj86aD8vGBoNDRoY/ooYGg0NGhhNYRgaDQ0aGPQiHYTGA7JQk2P9XbGyFRMIIBoZLDErBAwOP0cCWE5QYaJcoxEsKiosEBAsKiosEQICECwqKiwRHSKR5v//AG//6gRdBXIAIgBSAAAAAgEsAAAAAAABAGH/6gRVBLkAQgBBQD4ACwEKAQsKgAYBBAcBAwIEA2cIAQIJAQELAgFpAAUFKE0ACgoAYQAAACkATkA+Ozk4NiEkJCMkISYiJQwIHyskFRQGBwYjIiYnIyImJjU0NjYzMzUjIiY1NDYzMxE0NjMyFhYVESEyFhUUBiMhFTMyFhYVFAYGIyMWMzI2NzYzMhYXBFUVFc6XqrcEbhgaDQ0aGG7BIxwcI8E9Ry8zFAFzIxwcI/6NyhgaDQ0aGMkMdC57UhYNFSQQrBwWHQtoubEQLCoqLBFoLT4+LgEaIh0NGhj+5i4+Pi1oESwqKiwQhyklCSMoAP//ADL/6gSUBWAAIgBYAAAAAgEw5AAAAP///+z/6gTgBaQAIgBaAAAAAgBzCgAAAP///+z/6gTgBYIAIgBaAAAAAgEqAAAAAP///+z/6gTgBVMAIgBaAAAAAgBpAAAAAP///+z/6gTgBaQAIgBaAAAAAgBD9gAAAP//ACj+ZQSkBYIAIgBcAAAAAgEqEAAAAP//ACj+ZQSkBaQAIgBcAAAAAgBDAAAAAAACAOYB2wPRBTYAHwAiADJALyIBAAQYAQEAAkwFAQADAQECAAFpBgEEBDJNAAICMwJOAAAhIAAfAB4TIyQjBwkaKwAWFREzMhYVFAYjIxUUBiMiJjU1ISImJjU0NjcBNjYzATM3Aw03WhsYGBtaJTI5M/6lDx4TCAkBcxE0Kf71tAYFNh4a/kMoLCwojhkXGBiOJDkbERgMAcUWFf4L7wAAAQDIAUYEBAInABEAH0AcAgEBAAABVwIBAQEAXwAAAQBPAAAAEQAPNgMIFysAFhYVFAYGIyEiJiY1NDY2MyED3RoNDRoY/UIYGg0NGhgCvgInEjAvLzARETAvLzAS//8AqgHWBCICtwACABAAAP//AF4AfQRLA7IAIwFA/vwAAAADAUABBAAAAAD//wCBAH0EbgOyACMBQf78AAAAAwFBAQQAAAAAAAEAPP/qBHEEuQBVAKS1UQEBDQFMS7AOUFhANAAHBQYFBwaADAECCwMCAAQCAGkKAQQJAQUHBAVpAAEBDWEPDgINDShNAAYGCGEACAgpCE4bQD8ABwUGBQcGgAwBAgsBAwQCA2kKAQQJAQUHBAVpAAEBDWEPDgINDShNAAAADWEPDgINDShNAAYGCGEACAgpCE5ZQBwAAABVAFRPTUtJRUM/PTk3JyMhJCQkIiUlEAgfKwAWFREUBiMiJiY1NCYjIgYHMzIWFRQGIyMGFRQXMzIWFRQGIyMWMzI2NzYzMhcWFRQHBgYjIiYnIyImNTQ2MzMmNTQ3IyImNTQ2MzM2NjMyFhc1NDYzBDYuPUcvMxRqXkdcGb0jHBwj2gME2SMcHCO5N4tRnV0QDi8fDi5o1mOt7DFdIxwcI0MDA0MjHBwjXDDgnVV9KDpABLkcI/6AIh0NGhhjeUJCJjc2JiEhKiMmNzYmhDAvCFMmHjMWNDa7rCY2NyYkIyQkJjY3Jqq9QTw+Ih0AAAEAHgAABGAEowBFAMpLsBBQWEAxAAABAgEAcgACAAMEAgNnCgEECQEFBgQFZwsBAQEMXw0BDAwiTQgBBgYHXwAHByMHThtLsDFQWEAyAAABAgEAAoAAAgADBAIDZwoBBAkBBQYEBWcLAQEBDF8NAQwMIk0IAQYGB18ABwcjB04bQDgACwwBAQtyAAABAgEAAoAAAgADBAIDZwoBBAkBBQYEBWcAAQEMYA0BDAwiTQgBBgYHXwAHByMHTllZQBgAAABFAEM9Ozo4NDImNiEkISQhEyUOCB8rABYVFRQGIyImNTUhFSEyFhUUBiMhFSEyFhUUBiMhFTMyFhYVFAYGIyEiJiY1NDY2MzM1IyImNTQ2MzMRIyImJjU0NjYzIQRCHjpAPi7+egEwIxwcI/7QAYEiHR0i/n/ZGBoNDRoY/a4YGg0NGhh/nSIdHSKdfxgaDQ0aGAOkBKMeI/wiHRwjZvUuPj4tWB8lJR9TESwqKiwQECwqKiwRUx8lJR8CLhAsKiosEQAD/+L/6gTqBKMAWQBcAF8AVUBSEQEBAAFMAAkFBAUJBIARDgoIBAQQDwMDAAEEAGkNCwcDBQUGXwwBBgYiTQIBAQEpAU4AAF9eXFsAWQBYV1VPTEZEQ0I/PREmNiEmJCYkJhIIHysAFhYVFAYGIyMDDgIjIiYnAwMGBiMiJiYnAyMiJiY1NDY2MzMnIyImJjU0NjYzITIWFhUUBgYjIxczNzY2MzIWFxczNyMiJiY1NDY2MyEyFhYVFAYGIyMHMwE3IwU3IwTDGg0NGhhtOgMWMi5COwygogw8Qy4xFQM3ZhgaDQ0aGFMXMhgaDQ0aGAGKGBoNDRoYdRSeFQcoLzIsBheeFGcYGg0NGhgBdhgaDQ0aGDgXWfzKPk4B9xFOAvwOKCcnJw796BkcDB4jAdf+KSMeDBwZAhgOJycnKA7aECwqKiwRESwqKiwQ2j4XGBMVRdoQLCoqLBERLCoqLBDa/pK1tbUAAQCQ/o0EKwZNAA8AHkAbCgICAAEBTAIBAQABhQAAAHYAAAAPAA4mAwYXKwAWFRQHAQYjIiY1NDcBNjMD0VoE/VkQQkNbBAKnEEIGTSwjBQ74zSstIgcMBzMrAP//ALj+fAQgA5wAAgB0AAAAAQGCAp4DdgS0ABMAGkAXCwICAAEBTAAAAQCGAAEBKAFOKRYCCBgrABYVFAcBBiMiJyY1NDcTNjYzMhcDQTUK/qsWIhMbLwfJCiUfKUAEkC0WDgz+gxgKEiEODQGWFBQTAP//AKYCngRSBLQAIwF+/yQAAAADAX4A3AAAAAAAAfzn/eD+Lf9uABEALbEGZERAIgsCAgEAAUwAAAEBAFcAAAABYQIBAQABUQAAABEAEDcDCBcrsQYARAAmNTQ3EzY2MzMyFRQHAwYGI/0WLwE7AhQOzhgEfAovLP3gGRoJBQEyDQ4XCwn+zhkYAAAB/Of94P4t/24AEQAlQCILAgIBAAFMAAABAQBXAAAAAWECAQEAAVEAAAARABA3AwcXKwAmNTQ3EzY2MzMyFRQHAwYGI/0WLwE7AhQOzhgEfAovLP3gGRoJBQEyDQ4XCwn+zhkYAP//AZgFCwO4BrIBBwBzAAABDgAJsQABuAEOsDUrAAAA//8BBQUfA8cGgAEHASwAAAEOAAmxAAG4AQ6wNSsAAAAAAQDZAzECQAUgABAAPrYKAQIAAQFMS7AgUFhADAAAAAFfAgEBASQAThtAEgIBAQAAAVcCAQEBAGEAAAEAUVlACgAAABAADiYDCBcrABUUBwMGBiMiJjU0NxM2MzMCQAWXDDkyKykCVQgjyQUgHAkP/n0fGRgbDQcBhyEA//8BAAURA8wGmgEHASsAAAEOAAmxAAG4AQ6wNSsAAAD//wFf/igDjgAcAAIAdwAA//8BAAUHA8wGkAEHASoAAAEOAAmxAAG4AQ6wNSsAAAD//wENBT8DvwZhAQcAaQAAAQ4ACbEAArgBDrA1KwAAAP//AekFPwLjBmEBBwEtAAABDgAJsQABuAEOsDUrAAAA//8BFAULAzQGsgEHAEMAAAEOAAmxAAG4AQ6wNSsAAAD//wEZBRwEhQaQAQcBMQAAAQ4ACbEAArgBDrA1KwAAAP//ARgFPAO0BgkBBwBuAAABDgAJsQABuAEOsDUrAAAA//8BXf4oA1MAHAACAS8AAP//AWAFFwNsByMBBwEuAAABDgAJsQACuAEOsDUrAAAA//8A4wUyA+kGbgEHATAAAAEOAAmxAAG4AQ6wNSsAAAA="

async def install_timestamp_font(page):
    """Inject the embedded Courier Bold Prime font into the current page."""
    try:
        await page.evaluate(
            """([family, dataUri]) => {
                if (document.getElementById('akt-timestamp-font-style')) return;

                const style = document.createElement('style');
                style.id = 'akt-timestamp-font-style';
                style.textContent = `
                    @font-face {
                        font-family: '${family}';
                        src: url('${dataUri}') format('truetype');
                        font-style: normal;
                        font-weight: 700;
                        font-display: block;
                    }
                    #akt-saved-stamp, .akt-saved-stamp {
                        font-family: '${family}' !important;
                        font-weight: 700 !important;
                    }
                `;
                (document.head || document.documentElement).appendChild(style);
            }""",
            [TIMESTAMP_FONT_FAMILY, TIMESTAMP_FONT_DATA_URI],
        )
        try:
            await page.evaluate(
                """(family) => document.fonts.load('700 16px "' + family + '"')""",
                TIMESTAMP_FONT_FAMILY,
            )
            await page.evaluate("""() => document.fonts.ready""")
        except Exception:
            pass
    except Exception:
        pass

# ============================================================================
# 2. ADMIN / WRITE HELPERS
# ============================================================================
def is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def can_write(folder: str) -> bool:
    try:
        os.makedirs(folder, exist_ok=True)
        test_file = os.path.join(folder, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except Exception:
        return False

def relaunch_as_admin():
    if os.name != "nt":
        return
    script = os.path.abspath(sys.argv[0])
    print("\n[!] Administrator privileges needed to set up C:\\AKT Media Tools.")
    print("Click YES on the UAC prompt...")
    params = subprocess.list2cmdline([script] + sys.argv[1:])
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, os.path.dirname(script), 1
        )
    except Exception as e:
        print(f"Elevation failed: {e}")
        input("Press Enter to exit...")
    sys.exit(0)

# ============================================================================
# 3. ENVIRONMENT PREPARATION
# ============================================================================
def _has_browser_dir(browser_name: str) -> bool:
    browser_check_path = Path(PW_BROWSERS)
    if not browser_check_path.exists():
        return False
    return any(
        browser_name in d.name for d in browser_check_path.iterdir() if d.is_dir()
    )

def prepare_environment():
    print("=== AKT Environment Setup ===")

    if not can_write(LIB_ROOT):
        if not is_admin():
            relaunch_as_admin()
        else:
            os.makedirs(SITE_PACKAGES, exist_ok=True)
            os.makedirs(TOOLS_DIR, exist_ok=True)
            os.makedirs(PW_BROWSERS, exist_ok=True)

    if SITE_PACKAGES not in sys.path:
        sys.path.insert(0, SITE_PACKAGES)

    pywin32_path = os.path.join(SITE_PACKAGES, "pywin32_system32")
    if os.path.isdir(pywin32_path) and pywin32_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = pywin32_path + os.pathsep + os.environ.get("PATH", "")

    missing_libs = []
    if not os.path.isdir(os.path.join(SITE_PACKAGES, "playwright")):
        missing_libs.append("playwright")
    if not os.path.isdir(os.path.join(SITE_PACKAGES, "browser_cookie3")):
        missing_libs.append("browser-cookie3")

    if missing_libs:
        print(f"[-] Installing missing libraries {missing_libs} to AKT Tools folder...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--target", SITE_PACKAGES] + missing_libs
        )
        importlib.invalidate_caches()
        print("[OK] Libraries installed.")
    else:
        print("[OK] Core libraries are already present.")

    # Universal video download stack (yt-dlp + ffmpeg + gallery-dl + streamlink).
    ensure_video_dependencies(SITE_PACKAGES)
    ensure_deno_runtime()
    cleanup_stale_video_temp_dirs()

    env = os.environ.copy()
    env["PYTHONPATH"] = SITE_PACKAGES + os.pathsep + env.get("PYTHONPATH", "")
    env["PLAYWRIGHT_BROWSERS_PATH"] = PW_BROWSERS

    if not _has_browser_dir("firefox"):
        print("[-] Downloading Playwright Firefox browser binaries (this happens only once)...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "firefox"], env=env)
        print("[OK] Firefox binaries installed.")
    else:
        print("[OK] Firefox browser binaries already present.")

# ============================================================================
# 4. INSTAGRAM CACHE/COOKIE EXTRACTOR
# ============================================================================
def get_instagram_cookies():
    try:
        import browser_cookie3
    except ImportError as e:
        print(f"⚠️ Could not load cookie extractor: {e}. You might hit a login wall.")
        return []

    browsers = [
        ("Firefox", browser_cookie3.firefox),
        ("Brave", browser_cookie3.brave),
        ("Chrome", browser_cookie3.chrome),
        ("Edge", browser_cookie3.edge),
    ]

    print("\n[+] Hunting for active Instagram logins in your local browsers...")
    for name, b_func in browsers:
        try:
            cj = b_func(domain_name="instagram.com")
            cookies = []
            has_session = False

            for c in cj:
                if c.name == "sessionid":
                    has_session = True

                domain = c.domain or ".instagram.com"
                if domain.startswith("."):
                    cookie_domain = domain
                elif "instagram.com" in domain:
                    cookie_domain = domain
                else:
                    cookie_domain = ".instagram.com"

                cookie = {
                    "name": c.name,
                    "value": c.value,
                    "domain": cookie_domain,
                    "path": c.path or "/",
                    "secure": True,
                    "httpOnly": c.name in {"sessionid", "rur", "mid"},
                    "sameSite": "Lax",
                }
                if c.expires is not None:
                    try:
                        exp = int(c.expires)
                        if exp == -1 or exp > 0:
                            cookie["expires"] = exp
                    except (TypeError, ValueError):
                        pass
                cookies.append(cookie)

            if has_session:
                print(f"✅ Successfully copied active Instagram session from {name}!")
                return cookies
        except Exception:
            pass

    print("⚠️ No active Instagram session found. You might hit a login wall.")
    return []

# ============================================================================
# 5. INSTAGRAM HELPERS
# ============================================================================
def instagram_shortcode(url: str) -> str:
    match = IG_SHORTCODE_RE.search(url)
    return match.group(1) if match else ""

def instagram_embed_url(url: str) -> str:
    """Official embed card — same idea as the Twitter embed that already works."""
    code = instagram_shortcode(url)
    if not code:
        return url.split("?")[0].rstrip("/") + "/embed/captioned/"
    kind = "reel" if re.search(r"/(?:reel|reels|tv)/", url, re.IGNORECASE) else "p"
    return f"https://www.instagram.com/{kind}/{code}/embed/captioned/"

async def dismiss_instagram_walls(page):
    """Dismiss login/cookie nags without closing the post itself."""
    try:
        await page.evaluate(
            """() => {
                const skip = /not now|cancel|maybe later|log in later|skip|continue on web/i;
                const cookieOk = /allow all cookies|accept all|accept cookies|allow cookies/i;
                document.querySelectorAll('button, div[role="button"]').forEach(b => {
                    const txt = (b.innerText || b.getAttribute('aria-label') || '').trim();
                    if (!txt) return;
                    if (skip.test(txt) || cookieOk.test(txt)) {
                        try { b.click(); } catch (e) {}
                    }
                });

                document.querySelectorAll('nav, [role="navigation"]').forEach(n => n.remove());

                document.querySelectorAll('a').forEach(a => {
                    if (a.href && (a.href.includes('android-app') || a.href.includes('ios-app'))) {
                        const p = a.closest('div');
                        if (p && /\\bapp\\b/i.test(p.innerText || '')) p.remove();
                    }
                });
            }"""
        )
    except Exception:
        pass

async def is_instagram_age_restriction(page) -> bool:
    """True when Instagram shows the account age/content visibility restriction."""
    try:
        return await page.evaluate(
            """() => {
                const t = ((document.body && document.body.innerText) || '').toLowerCase();
                return t.includes("people under 25 can't see this content")
                    || t.includes("people under 25 can\'t see this content")
                    || (t.includes("this account has set limits on who can see their profile and content")
                        && t.includes("people under 25"));
            }"""
        )
    except Exception:
        return False


async def raise_if_instagram_age_restricted(page, url: str = "") -> None:
    """Stop an Instagram job when the requested post is blocked by an age/content restriction."""
    if await is_instagram_age_restriction(page):
        raise RuntimeError(
            "Instagram content visibility restriction detected: "
            "People under 25 can't see this content. "
            "This account has set limits on who can see their profile and content."
        )


async def is_instagram_app_wall(page) -> bool:
    """True when Instagram shows Open app / Continue on web instead of the post."""
    try:
        return await page.evaluate(
            """() => {
                const t = ((document.body && document.body.innerText) || '').toLowerCase();
                return t.includes('watch this reel in the app')
                    || t.includes('watch this post in the app')
                    || (t.includes('open instagram') && t.includes('continue on web'));
            }"""
        )
    except Exception:
        return False

async def wait_for_instagram_actions(page, timeout_ms: int = 8000) -> bool:
    """Wait for the native Comment / Share / Repost icons (not the embed-only bar)."""
    try:
        await page.wait_for_function(
            """() => {
                const hit = (n) => document.querySelector(
                    'svg[aria-label="' + n + '"], svg[aria-label*="' + n + '" i]'
                );
                return !!(hit('Comment') || hit('Share') || hit('Send') || hit('Repost'));
            }""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False

async def wait_for_instagram_media(page, timeout_ms: int = 25000) -> bool:
    """Wait until a real photo/video frame has painted (not an empty shell)."""
    try:
        await page.wait_for_function(
            """() => {
                const imgs = Array.from(document.images || []);
                const photo = imgs.some(img =>
                    img.complete &&
                    img.naturalWidth > 40 &&
                    img.offsetWidth > 20 &&
                    getComputedStyle(img).visibility !== 'hidden' &&
                    getComputedStyle(img).opacity !== '0'
                );
                const videos = Array.from(document.querySelectorAll('video'));
                const vid = videos.some(v =>
                    (v.readyState >= 2 && v.videoWidth > 40) ||
                    (v.poster && v.offsetWidth > 20)
                );
                return photo || vid;
            }""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False

async def prepare_instagram_media(page):
    """Force lazy images to load and park videos on a visible first frame."""
    try:
        await page.evaluate(
            """() => {
                document.querySelectorAll('img').forEach(img => {
                    img.loading = 'eager';
                    const ds = img.getAttribute('data-src') || img.dataset.src;
                    if (ds && !img.src) img.src = ds;
                    img.scrollIntoView({block: 'center'});
                });
                document.querySelectorAll('video').forEach(v => {
                    v.muted = true;
                    v.playsInline = true;
                    v.pause();
                    try { if (v.currentTime < 0.05) v.currentTime = 0.15; } catch (e) {}
                });
            }"""
        )
    except Exception:
        pass

async def pick_instagram_element(page):
    """Choose a visible, non-zero post container instead of an empty article/main."""
    selectors = [
        "iframe.EmbeddedMediaImage, iframe.embedFrame",
        "div.Embed",
        "article",
        'div[role="dialog"]',
        "main",
        "#react-root",
        "body",
    ]
    best = None
    best_area = 0
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if await loc.count() == 0:
                continue
            box = await loc.bounding_box()
            if not box:
                continue
            area = box["width"] * box["height"]
            if box["width"] >= 80 and box["height"] >= 80 and area > best_area:
                best = loc
                best_area = area
        except Exception:
            continue
    return best or page.locator("body")

def _windows_browser_exe(*relative_parts: str) -> list:
    bases = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    found = []
    for base in bases:
        if not base:
            continue
        path = os.path.join(base, *relative_parts)
        if os.path.isfile(path):
            found.append(path)
    return found

async def launch_installed_chrome_family(playwright):
    """Use Chrome / Brave / Edge already on the PC. Never download Playwright Chromium."""
    chromium = playwright.chromium
    launch_args = ["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]

    for channel, label in (("chrome", "Google Chrome"), ("msedge", "Microsoft Edge")):
        try:
            browser = await chromium.launch(headless=True, channel=channel, args=launch_args)
            print(f"[+] Using installed {label} (no Chromium download).")
            return browser
        except Exception:
            pass

    for exe in _windows_browser_exe("BraveSoftware", "Brave-Browser", "Application", "brave.exe"):
        try:
            browser = await chromium.launch(headless=True, executable_path=exe, args=launch_args)
            print("[+] Using installed Brave (no Chromium download).")
            return browser
        except Exception:
            continue

    raise RuntimeError(
        "Firefox produced a blank Instagram shot, and no installed Chrome/Brave/Edge "
        "could be launched. Install Google Chrome or run the capture again in Firefox."
    )

def screenshot_looks_blank(path: str) -> bool:
    """Treat missing/tiny PNGs as failed Instagram captures."""
    try:
        return (not os.path.exists(path)) or os.path.getsize(path) < 12000
    except Exception:
        return True

async def inject_instagram_timestamp(page, timestamp_str: str):
    await install_timestamp_font(page)
    await page.evaluate(
        """(ts) => {
            const existing = document.getElementById('akt-saved-stamp');
            if (existing) existing.remove();

            const stamp = document.createElement('div');
            stamp.id = 'akt-saved-stamp';
            
            // Format timestamp to guarantee a colon between hours and minutes
            let cleanTs = ts.replace(/:/g, ''); 
            let displayTs = cleanTs.substring(0, cleanTs.length - 2) + ":" + cleanTs.substring(cleanTs.length - 2);
            stamp.innerText = "Post_Saved_On:" + displayTs;

            stamp.style.whiteSpace = "nowrap";
            stamp.style.textAlign = "left";
            stamp.style.setProperty("color", "#000000", "important");
            stamp.style.setProperty("-webkit-text-fill-color", "#000000", "important");
            stamp.style.marginLeft = "auto";
            stamp.style.marginRight = "15px"; 
            stamp.style.paddingLeft = "12px";
            stamp.style.paddingRight = "10px"; 
            stamp.style.flexShrink = "0";
            stamp.style.overflow = "visible";
            stamp.style.lineHeight = "1.2";

            const fitStamp = (row, viewMore) => {
                row.style.overflow = "visible";
                if (row.parentElement) row.parentElement.style.overflow = "visible";

                // Use the exact typography of Instagram's "View more on Instagram".
                const viewStyle = getComputedStyle(viewMore);
                stamp.style.fontFamily = viewStyle.fontFamily;
                stamp.style.fontSize = viewStyle.fontSize;
                stamp.style.fontWeight = viewStyle.fontWeight;
                stamp.style.fontStyle = viewStyle.fontStyle;
                stamp.style.lineHeight = viewStyle.lineHeight;
                stamp.style.letterSpacing = viewStyle.letterSpacing;
                stamp.style.textTransform = viewStyle.textTransform;
                stamp.style.textAlign = "left";
            };

            let viewMore = null;
            document.querySelectorAll('a, span, p, div').forEach(el => {
                const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                if (/^view more on instagram$/i.test(t)) viewMore = el;
            });
            if (viewMore) {
                const row = viewMore.closest('p') || viewMore.parentElement;
                if (row) {
                    row.style.display = "flex";
                    row.style.flexDirection = "row";
                    row.style.alignItems = "center";
                    row.style.justifyContent = "flex-start";
                    row.style.width = "100%";
                    row.style.boxSizing = "border-box";
                    row.style.paddingRight = "8px";
                    row.style.display = "flex";
                    row.style.alignItems = "center";
                    row.style.justifyContent = "flex-start";
                    row.style.overflow = "hidden";

                    // Keep "View more on Instagram" fully visible.
                    viewMore.style.flex = "0 0 auto";
                    viewMore.style.whiteSpace = "nowrap";
                    viewMore.style.overflow = "visible";

                    // EXACTLY TWO-SPACE VISUAL GAP after "View more on Instagram".
                    // Keep this gap fixed; the timestamp itself is allowed to
                    // become smaller so the ENTIRE timestamp always fits.
                    const TIMESTAMP_GAP_PX = 20;

                    stamp.style.marginLeft = `calc(${TIMESTAMP_GAP_PX}px - 2ch)`;
                    stamp.style.marginRight = "0";
                    stamp.style.paddingLeft = "0";
                    stamp.style.paddingRight = "0";
                    stamp.style.textAlign = "left";
                    stamp.style.flex = "0 0 auto";
                    stamp.style.minWidth = "0";
                    stamp.style.whiteSpace = "nowrap";
                    stamp.style.overflow = "visible";
                    stamp.style.textOverflow = "clip";

                    row.appendChild(stamp);

                    // Apply Instagram typography first.
                    fitStamp(row, viewMore);

                    // -------------------------------------------------------------
                    // HARD GUARANTEE:
                    // Calculate the real remaining width of this row and give the
                    // timestamp exactly that width. Then find the largest font
                    // size that makes the COMPLETE string fit inside that width.
                    //
                    // This fixes the previous problem where the timestamp was
                    // still being laid out at its natural width and the rightmost
                    // characters were disappearing outside the screenshot.
                    // -------------------------------------------------------------
                    const rowRect = row.getBoundingClientRect();
                    const viewRect = viewMore.getBoundingClientRect();

                    // Account for the row's right padding and a tiny safety margin.
                    const rowStyle = getComputedStyle(row);
                    const rightPadding = parseFloat(rowStyle.paddingRight) || 0;
                    const safetyPx = 2;

                    const availableStampWidth = Math.max(
                        1,
                        rowRect.right -
                        viewRect.right -
                        TIMESTAMP_GAP_PX -
                        rightPadding -
                        safetyPx
                    );

                    // Give the timestamp a REAL finite width rather than letting
                    // flexbox decide it. This makes the fit deterministic.
                    stamp.style.width = Math.floor(availableStampWidth) + "px";
                    stamp.style.maxWidth = Math.floor(availableStampWidth) + "px";
                    stamp.style.boxSizing = "border-box";

                    const baseSize =
                        parseFloat(getComputedStyle(viewMore).fontSize) || 12;

                    // Start at Instagram's normal size.
                    stamp.style.fontSize = baseSize + "px";

                    // Measure the actual rendered text width using Range.
                    const measureTextWidth = () => {
                        const range = document.createRange();
                        range.selectNodeContents(stamp);
                        const rect = range.getBoundingClientRect();
                        range.detach();
                        return rect.width;
                    };

                    let measuredWidth = measureTextWidth();

                    if (measuredWidth > availableStampWidth) {
                        // Go smaller than the previous 8px floor if necessary.
                        // The priority is: COMPLETE timestamp > font size.
                        let low = 6;
                        let high = baseSize;

                        for (let i = 0; i < 18; i++) {
                            const mid = (low + high) / 2;
                            stamp.style.fontSize = mid + "px";
                            measuredWidth = measureTextWidth();

                            if (measuredWidth <= availableStampWidth) {
                                low = mid;
                            } else {
                                high = mid;
                            }
                        }

                        stamp.style.fontSize = low + "px";
                    }

                    // Final verification after browser sub-pixel rounding.
                    measuredWidth = measureTextWidth();

                    if (measuredWidth > availableStampWidth) {
                        const currentSize =
                            parseFloat(getComputedStyle(stamp).fontSize) || 6;

                        stamp.style.fontSize = Math.max(
                            5.5,
                            currentSize *
                            (availableStampWidth / measuredWidth) *
                            0.995
                        ) + "px";
                    }

                    // Never clip the timestamp. It has already been fitted to the
                    // exact available width, while the two-space left gap remains.
                    stamp.style.overflow = "visible";
                    stamp.style.textOverflow = "clip";
                    stamp.style.whiteSpace = "nowrap";
                    return;
                }
            }

            const svgs = document.querySelectorAll(
                'svg[aria-label="Save"], svg[aria-label="Remove"]'
            );
            if (svgs.length > 0) {
                const btn = svgs[0].closest('div[role="button"]') || svgs[0].parentElement;
                const rightWrapper = btn ? btn.parentElement : null;
                const mainRow = rightWrapper ? rightWrapper.parentElement : null;
                if (mainRow && rightWrapper) {
                    stamp.style.flexGrow = "1";
                    stamp.style.textAlign = "right";
                    stamp.style.marginRight = "10px";
                    stamp.style.display = "flex";
                    stamp.style.alignItems = "center";
                    stamp.style.justifyContent = "flex-end";
                    stamp.style.setProperty("color", "#000000", "important");
                    stamp.style.setProperty("-webkit-text-fill-color", "#000000", "important");
                    mainRow.insertBefore(stamp, rightWrapper);
                    return;
                }
            }

            stamp.style.position = "absolute";
            stamp.style.bottom = "12px";
            stamp.style.right = "12px";
            stamp.style.background = "rgba(255,255,255,0.85)";
            stamp.style.padding = "2px 6px";
            stamp.style.borderRadius = "4px";
            stamp.style.zIndex = "99999";
            const host = document.querySelector('div.Embed, article, main, body');
            if (host) {
                if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
                host.appendChild(stamp);
            }
        }""",
        timestamp_str,
    )

async def hide_instagram_below_actions(page):
    """
    Keep the Instagram post through the likes-count row only.
    Everything after the likes count (caption, comments, comment box, etc.)
    is hidden. The screenshot is then cropped at the bottom of the likes row.
    """
    try:
        return await page.evaluate(
            """() => {
                const visible = (el) => {
                    if (!el) return false;
                    const r = el.getBoundingClientRect();
                    const s = getComputedStyle(el);
                    return r.width > 0 && r.height > 0 &&
                           s.display !== 'none' &&
                           s.visibility !== 'hidden' &&
                           s.opacity !== '0';
                };

                // Find the actual "XXX likes" line without relying on
                // Instagram's changing React/DOM class names.
                const candidates = Array.from(document.querySelectorAll('div, span, p, a'))
                    .filter(visible)
                    .filter(el => {
                        const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
                        return /^[\\d,.]+\\s+likes?$/i.test(t);
                    });

                if (!candidates.length) {
                    return null;
                }

                // Prefer the smallest matching visible element.
                candidates.sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    return (ar.width * ar.height) - (br.width * br.height);
                });

                const likes = candidates[0];
                const likesRect = likes.getBoundingClientRect();

                // Hide large content blocks whose top is below the likes row.
                // This removes caption, comments and comment input while
                // leaving the post and likes row intact.
                Array.from(document.querySelectorAll('body *')).forEach(el => {
                    if (el === likes || likes.contains(el) || el.contains(likes)) return;
                    if (!visible(el)) return;

                    const r = el.getBoundingClientRect();
                    if (r.top >= likesRect.bottom - 1 &&
                        r.width >= Math.min(250, window.innerWidth * 0.55)) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                });

                document.querySelectorAll('form, textarea, input').forEach(el => {
                    const r = el.getBoundingClientRect();
                    if (r.top >= likesRect.bottom - 1) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                });

                return {
                    bottom: Math.ceil(likesRect.bottom + 8)
                };
            }"""
        )
    except Exception:
        return None


# ============================================================================
# 6. SOCIAL MEDIA SCREENSHOTTER (MOBILE VIEWPORT)
# ============================================================================
async def new_mobile_context(browser, user_agent: str, ig_cookies=None):
    context = await browser.new_context(
        viewport=S24_VIEWPORT,
        device_scale_factor=S24_DEVICE_SCALE_FACTOR,
        is_mobile=True,
        has_touch=True,
        user_agent=user_agent,
        locale="en-US",
        color_scheme="light",
        java_script_enabled=True,
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    if ig_cookies is not None:
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        if ig_cookies:
            try:
                await context.add_cookies(ig_cookies)
            except Exception as cookie_err:
                print(f"    [!] Some cookies could not be applied: {cookie_err}")
    return context


async def get_visible_video_regions(page):
    """Return visible video bounding boxes in viewport coordinates."""
    try:
        return await page.evaluate("""() => {
            const out = [];
            for (const v of document.querySelectorAll('video')) {
                const r = v.getBoundingClientRect();
                const cs = getComputedStyle(v);
                if (r.width > 20 && r.height > 20 &&
                    r.bottom > 0 && r.right > 0 &&
                    r.top < window.innerHeight && r.left < window.innerWidth &&
                    cs.display !== 'none' && cs.visibility !== 'hidden' &&
                    cs.opacity !== '0') {
                    out.push({
                        x: Math.max(0, r.left),
                        y: Math.max(0, r.top),
                        width: Math.min(r.width, window.innerWidth - Math.max(0, r.left)),
                        height: Math.min(r.height, window.innerHeight - Math.max(0, r.top))
                    });
                }
            }
            return out;
        }""")
    except Exception:
        return []


async def screenshot_with_video_green(page, output_path, screenshot_kind='page', element=None, clip=None):
    """Save an extra copy with every visible video rectangle replaced by pure green."""
    regions = await get_visible_video_regions(page)
    if not regions:
        return False

    try:
        await page.evaluate("""(regions) => {
            document.querySelectorAll('[data-akt-green-video-overlay]').forEach(e => e.remove());
            for (const r of regions) {
                const d = document.createElement('div');
                d.setAttribute('data-akt-green-video-overlay', '1');
                d.style.position = 'fixed';
                d.style.left = r.x + 'px';
                d.style.top = r.y + 'px';
                d.style.width = r.width + 'px';
                d.style.height = r.height + 'px';
                d.style.background = '#00FF00';
                d.style.zIndex = '2147483647';
                d.style.pointerEvents = 'none';
                d.style.margin = '0';
                d.style.padding = '0';
                document.documentElement.appendChild(d);
            }
        }""", regions)
        await page.wait_for_timeout(100)

        if screenshot_kind == 'element' and element is not None:
            await element.screenshot(path=output_path, animations='disabled')
        elif clip is not None:
            await page.screenshot(path=output_path, clip=clip, animations='disabled')
        else:
            await page.screenshot(path=output_path, full_page=True, animations='disabled')
        return True
    except Exception as e:
        print(f"    [!] Green-screen video screenshot failed: {e}")
        return False
    finally:
        try:
            await page.evaluate("""() => {
                document.querySelectorAll('[data-akt-green-video-overlay]').forEach(e => e.remove());
            }""")
        except Exception:
            pass

async def capture_instagram(page, url: str, output_dir: str, timestamp_str: str, timestamp_display: str) -> list:
    """Load IG, screenshot slides, return saved file paths."""
    saved_paths = []
    print("[+] Waiting for Instagram media to paint...")
    media_ready = False
    embed_url = instagram_embed_url(url)

    if embed_url.rstrip("/") != url.split("?")[0].rstrip("/"):
        print(f"[+] Trying Instagram embed card: {embed_url}")
        try:
            await page.goto(embed_url, wait_until="domcontentloaded", timeout=45000)
            await raise_if_instagram_age_restricted(page, url)
            await prepare_instagram_media(page)
            media_ready = await wait_for_instagram_media(page, timeout_ms=18000)
            if await is_instagram_app_wall(page):
                media_ready = False
        except Exception as embed_err:
            print(f"    [!] Embed navigation failed: {embed_err}")

    if not media_ready:
        print("[+] Embed empty or blocked — loading the original post URL...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        await raise_if_instagram_age_restricted(page, url)
        await dismiss_instagram_walls(page)
        try:
            cont = page.get_by_text("Continue on web", exact=False)
            if await cont.count() > 0:
                await cont.first.click(timeout=3000)
                await page.wait_for_timeout(1500)
        except Exception:
            pass
        await prepare_instagram_media(page)
        media_ready = await wait_for_instagram_media(page, timeout_ms=20000)
        if await is_instagram_app_wall(page):
            print("[+] Hit Instagram app wall — returning to embed card...")
            media_ready = False
            try:
                await page.goto(embed_url, wait_until="domcontentloaded", timeout=45000)
                await raise_if_instagram_age_restricted(page, url)
                await prepare_instagram_media(page)
                media_ready = await wait_for_instagram_media(page, timeout_ms=18000)
            except Exception:
                pass

    if not media_ready:
        print("    [!] Media still not painted — extra settle wait...")
        await page.wait_for_timeout(4000)
        await prepare_instagram_media(page)
        media_ready = await wait_for_instagram_media(page, timeout_ms=8000)

    await dismiss_instagram_walls(page)
    await page.wait_for_timeout(800)
    await raise_if_instagram_age_restricted(page, url)

    ig_username = await page.evaluate(
        """() => {
        const ok = (t) => /^[A-Za-z0-9._]+$/.test(t) && t.toLowerCase() !== 'instagram';
        let iosUrl = document.querySelector('meta[property="al:ios:url"]');
        if (iosUrl && iosUrl.content && iosUrl.content.includes('username=')) {
            return iosUrl.content.split('username=')[1].split('&')[0];
        }
        let ogTitle = document.querySelector('meta[property="og:title"]');
        if (ogTitle && ogTitle.content) {
            let match = ogTitle.content.match(/@([a-zA-Z0-9_.]+)/);
            if (match) return match[1];
            let match2 = ogTitle.content.match(/^([a-zA-Z0-9_.]+)\\s+on Instagram/);
            if (match2) return match2[1];
        }
        let header = document.querySelector('header');
        if (header) {
            let first = header.innerText.trim().split('\\n')[0].trim();
            if (ok(first)) return first;
        }
        let headerLinks = document.querySelectorAll('header a, header span, header strong');
        for (let a of headerLinks) {
            let text = (a.innerText || '').trim().split('\\n')[0].trim();
            if (ok(text)) return text;
        }
        for (let a of document.querySelectorAll('a[href]')) {
            let href = a.getAttribute('href') || '';
            let m = href.match(/instagram\\.com\\/([A-Za-z0-9._]+)\\/?$/);
            if (m && ok(m[1]) && !['p','reel','reels','tv','stories','accounts'].includes(m[1])) return m[1];
            let text = (a.innerText || '').trim().split('\\n')[0].trim();
            if (ok(text) && a.closest('header, .Header, .EmbedHeader')) return text;
        }
        return 'unknown';
    }"""
    )
    if ig_username == "unknown":
        m = re.search(r"instagram\.com/([A-Za-z0-9._]+)/(?:p|reel|reels|tv)/", url, re.I)
        if m and m.group(1).lower() not in {"p", "reel", "reels", "tv", "stories"}:
            ig_username = m.group(1)
    filename_base = f"instagram.com_@{ig_username}_{timestamp_str}"
    print(f"[+] Username identified: @{ig_username}")

    print("[+] Injecting perfectly aligned 7pt Bold Timestamp...")
    await inject_instagram_timestamp(page, timestamp_display)
    await hide_instagram_below_actions(page)

    element = await pick_instagram_element(page)

    slide_num = 1
    while True:
        current_filename = (
            f"{filename_base}.png"
            if slide_num == 1
            else f"{filename_base}_slide{slide_num}.png"
        )
        output_path = os.path.join(output_dir, current_filename)

        print(f"[+] Taking tight crop screenshot... Saving as {current_filename}")
        await prepare_instagram_media(page)
        await hide_instagram_below_actions(page)
        await page.wait_for_timeout(400)

        # ----------------------------------------------------------------------
        # FIXED: Removed the buggy 'clip=clip' argument that distorted the image
        # ----------------------------------------------------------------------
        try:
            box = await element.bounding_box()
            if not box or box["height"] < 80:
                element = await pick_instagram_element(page)

            # Crop exactly after the likes-count row.
            crop = await hide_instagram_below_actions(page)
            if crop and crop.get("bottom", 0) > 0:
                viewport = page.viewport_size
                max_h = viewport["height"] if viewport else 915
                await page.screenshot(
                    path=output_path,
                    clip={
                        "x": 0,
                        "y": 0,
                        "width": viewport["width"] if viewport else 412,
                        "height": min(crop["bottom"], max_h),
                    },
                    animations="disabled",
                )
            else:
                await element.screenshot(path=output_path, animations="disabled")
        except Exception:
            await page.screenshot(path=output_path, full_page=True, animations="disabled")

        if screenshot_looks_blank(output_path):
            print("    [!] Capture looked blank — retrying as a full-page shot...")
            await page.wait_for_timeout(1500)
            await prepare_instagram_media(page)
            try:
                element = await pick_instagram_element(page)
                crop = await hide_instagram_below_actions(page)
                if crop and crop.get("bottom", 0) > 0:
                    viewport = page.viewport_size
                    max_h = viewport["height"] if viewport else 915
                    await page.screenshot(
                        path=output_path,
                        clip={
                            "x": 0,
                            "y": 0,
                            "width": viewport["width"] if viewport else 412,
                            "height": min(crop["bottom"], max_h),
                        },
                        animations="disabled",
                    )
                else:
                    await element.screenshot(path=output_path, animations="disabled")
            except Exception:
                pass
            if screenshot_looks_blank(output_path):
                await page.screenshot(
                    path=output_path, full_page=True, animations="disabled"
                )

        saved_paths.append(output_path)

        # Extra green-screen copy ONLY when this slide contains a real video.
        green_output_path = os.path.splitext(output_path)[0] + "_GREEN_VIDEO.png"
        green_clip = None
        try:
            crop_for_green = await hide_instagram_below_actions(page)
            if crop_for_green and crop_for_green.get("bottom", 0) > 0:
                viewport = page.viewport_size
                green_clip = {
                    "x": 0,
                    "y": 0,
                    "width": viewport["width"] if viewport else 412,
                    "height": min(crop_for_green["bottom"], viewport["height"] if viewport else 915),
                }
            if await screenshot_with_video_green(page, green_output_path, clip=green_clip):
                print(f"    [+] Green-screen video screenshot saved: {os.path.basename(green_output_path)}")
            elif os.path.exists(green_output_path):
                os.remove(green_output_path)
        except Exception as green_err:
            print(f"    [!] Could not create green-screen video screenshot: {green_err}")
            if os.path.exists(green_output_path):
                try:
                    os.remove(green_output_path)
                except Exception:
                    pass

        next_btn = page.locator('button[aria-label="Next"]')
        if await next_btn.count() > 0 and await next_btn.is_visible():
            print("    [>] Found multi-slide post. Clicking next...")
            await next_btn.click()
            await page.wait_for_timeout(1500)
            await prepare_instagram_media(page)
            await hide_instagram_below_actions(page)
            await wait_for_instagram_media(page, timeout_ms=8000)

            if slide_num == 1:
                first_slide_new_name = os.path.join(
                    output_dir, f"{filename_base}_slide1.png"
                )
                if os.path.exists(output_path):
                    os.rename(output_path, first_slide_new_name)
                    saved_paths[-1] = first_slide_new_name

                first_green_name = os.path.join(
                    output_dir, f"{filename_base}_slide1_GREEN_VIDEO.png"
                )
                current_green_name = os.path.join(
                    output_dir, f"{filename_base}_GREEN_VIDEO.png"
                )
                if os.path.exists(current_green_name):
                    os.rename(current_green_name, first_green_name)

            slide_num += 1
            if slide_num > 20:
                break
        else:
            break

    return saved_paths

def download_videos_for_url(url: str, platform: str, username: str, timestamp_str: str, cookies=None):
    """Download video/media for any URL into Social Media Videos/.

    cookies is accepted for call-site compatibility but intentionally ignored —
    video downloads are fully browser/cookie independent.
    """
    os.makedirs(VIDEO_DIR, exist_ok=True)
    print(f"[+] Starting cookie-independent video download for: {url}")
    results = run_yt_dlp_download(
        url,
        VIDEO_DIR,
        platform,
        cookies=None,
        username=username or "unknown",
        timestamp_str=timestamp_str,
    )
    if results:
        print(f"[OK] Downloaded {len(results)} video file(s):")
        for path in results:
            print(f"    → {path}")
    else:
        print("[!] No downloadable video found for this URL.")
    return results


async def capture_post(url: str):
    """
    Universal entry point.

    - X/Twitter + Instagram keep the mature screenshot paths.
    - ANY other http(s) URL is accepted for video download (yt-dlp ladder).
    - Screenshots are still attempted for known social platforms when possible.
    """
    from playwright.async_api import async_playwright

    if not is_downloadable_url(url):
        error = "Please enter a valid http(s) URL."
        print(f"\n❌ ERROR: {error}")
        record_error(url, error, "URL validation")
        return False

    platform = detect_platform(url)
    is_twitter = platform == "x"
    is_instagram = platform == "instagram"
    is_youtube = platform == "youtube"

    now = datetime.now()
    timestamp_str = now.strftime("%d_%b_%Y_%H%M")
    timestamp_display = now.strftime("%d_%b_%Y_%H:%M")
    output_dir = os.path.join(SCRIPT_DIR, "Social Media Screenshots")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(VIDEO_DIR, exist_ok=True)

    username = platform_username_from_url(url, platform)
    domain = (urlparse(url).hostname or "").lower()
    # Screenshot sessions may reuse browser cookies (Instagram/X login walls).
    # Video downloads NEVER use browser cookies — fully cookie-independent.
    cookies = get_browser_cookies_for_domain(domain) if domain else []

    # =========================================================================
    # YouTube / generic / other platforms: VIDEO FIRST (any URL supported)
    # =========================================================================
    if not is_twitter and not is_instagram:
        print(f"[+] Platform detected: {platform}")
        print("[+] Universal cookie/browser-independent video download enabled.")
        downloaded = download_videos_for_url(
            url, platform, username, timestamp_str, cookies=None
        )

        # YouTube intentionally skips screenshots.
        if is_youtube:
            return bool(downloaded)

        # Best-effort mobile screenshot for other social/generic pages.
        screenshot_ok = False
        try:
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)
                try:
                    context = await new_mobile_context(browser, S24_FIREFOX_UA, cookies)
                    page = await context.new_page()
                    print(f"[+] Loading page for screenshot: {url}")
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(2500)
                    await install_timestamp_font(page)
                    await page.evaluate(
                        """(ts) => {
                            const existing = document.getElementById('akt-saved-stamp');
                            if (existing) existing.remove();
                            const stamp = document.createElement('div');
                            stamp.id = 'akt-saved-stamp';
                            stamp.innerText = 'Post_Saved_On:' + ts;
                            stamp.style.position = 'fixed';
                            stamp.style.right = '10px';
                            stamp.style.bottom = '10px';
                            stamp.style.zIndex = '2147483646';
                            stamp.style.fontFamily = 'Courier Bold Prime, monospace';
                            stamp.style.fontWeight = '700';
                            stamp.style.fontSize = '11px';
                            stamp.style.color = '#000';
                            stamp.style.background = 'rgba(255,255,255,0.90)';
                            stamp.style.padding = '2px 5px';
                            stamp.style.pointerEvents = 'none';
                            document.documentElement.appendChild(stamp);
                        }""",
                        timestamp_display,
                    )
                    host = (urlparse(url).hostname or platform).replace("www.", "")
                    filename = f"{host}_@{username}_{timestamp_str}.png"
                    output_path = os.path.join(output_dir, filename)
                    element = page.locator("article, [role='article'], main, body").first
                    try:
                        await element.screenshot(path=output_path, animations="disabled")
                    except Exception:
                        await page.screenshot(
                            path=output_path, full_page=True, animations="disabled"
                        )
                    screenshot_ok = os.path.exists(output_path) and not screenshot_looks_blank(output_path)
                    if screenshot_ok:
                        print(f"[+] Screenshot saved: {output_path}")
                        green_path = os.path.splitext(output_path)[0] + "_Video2GreenScreen.png"
                        try:
                            if not await screenshot_with_video_green(
                                page, green_path, screenshot_kind="element", element=element
                            ):
                                if os.path.exists(green_path):
                                    os.remove(green_path)
                        except Exception:
                            if os.path.exists(green_path):
                                try:
                                    os.remove(green_path)
                                except Exception:
                                    pass
                finally:
                    await browser.close()
        except Exception as e:
            print(f"[!] Screenshot step recovered from: {type(e).__name__}: {e}")

        # Success if either video or screenshot worked. Prefer video for "any URL".
        return bool(downloaded) or screenshot_ok

    # =========================================================================
    # Existing Instagram / X screenshot paths + independent video download
    # =========================================================================
    if is_twitter:
        match = re.search(r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)", url)
        tw_username = match.group(1) if match else username
        tweet_id = match.group(2) if match else "0"
        filename_base = f"x.com_@{tw_username}_{timestamp_str}"
        target_url = (
            f"https://platform.twitter.com/embed/Tweet.html"
            f"?id={tweet_id}&theme=light"
        )
    else:
        target_url = url
        filename_base = ""
        tw_username = username

    print("[+] Launching Playwright Firefox in Mobile (S24 Ultra) Mode...")
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.firefox.launch(headless=True)
            ig_cookies = get_instagram_cookies() if is_instagram else None
            ua = S24_FIREFOX_UA if is_instagram else S24_UA
            context = await new_mobile_context(
                browser, ua, ig_cookies if is_instagram else cookies
            )
            page = await context.new_page()

            print(f"[+] Loading Target URL: {target_url}")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

            if is_twitter:
                print("[+] Waiting for the tweet to render...")
                await page.wait_for_selector("article", state="visible", timeout=15000)
                await page.wait_for_timeout(3000)

                print("[+] Injecting 11pt Bold Timestamp...")
                await install_timestamp_font(page)
                await page.evaluate(
                    """(ts) => {
                    let timeElems = document.querySelectorAll('time');
                    if (timeElems.length > 0) {
                        let parent = timeElems[0].parentElement;
                        let stamp = document.createElement('span');
                        stamp.innerText = "Post_Saved_On:" + ts;
                        stamp.style.fontFamily = "Courier Bold Prime";
                        stamp.style.fontWeight = "700";
                        stamp.style.fontSize = "12px";
                        stamp.style.whiteSpace = "nowrap";
                        stamp.style.textAlign = "left";
                        stamp.style.marginLeft = "10ch";
                        stamp.style.marginRight = "0";
                        stamp.style.paddingLeft = "0";
                        stamp.style.color = "#000";

                        parent.style.display = "flex";
                        parent.style.width = "100%";
                        parent.style.alignItems = "center";
                        parent.style.justifyContent = "flex-start";
                        parent.appendChild(stamp);
                    }
                }""",
                    timestamp_display,
                )

                output_path = os.path.join(output_dir, f"{filename_base}.png")
                element = page.locator("article").first
                await element.screenshot(path=output_path, animations="disabled")

                green_output_path = os.path.join(
                    output_dir, f"{filename_base}_Video2GreenScreen.png"
                )
                try:
                    if await screenshot_with_video_green(
                        page, green_output_path, screenshot_kind="element", element=element
                    ):
                        print(
                            f"    [+] Green-screen video screenshot saved: "
                            f"{os.path.basename(green_output_path)}"
                        )
                    elif os.path.exists(green_output_path):
                        os.remove(green_output_path)
                except Exception as green_err:
                    print(f"    [!] Could not create green-screen video screenshot: {green_err}")
                    if os.path.exists(green_output_path):
                        try:
                            os.remove(green_output_path)
                        except Exception:
                            pass

                downloaded = download_videos_for_url(
                    url, "x", tw_username, timestamp_str, cookies=None
                )
                if not downloaded and target_url != url:
                    downloaded = download_videos_for_url(
                        target_url, "x", tw_username, timestamp_str, cookies=None
                    )

                print(f"\n✅ X/Twitter screenshot saved: {output_dir}")
                if downloaded:
                    print(f"✅ X/Twitter video(s) downloaded: {len(downloaded)}")
                return True

            else:
                saved_paths = await capture_instagram(
                    page, url, output_dir, timestamp_str, timestamp_display
                )
                still_blank = saved_paths and all(
                    screenshot_looks_blank(pth) for pth in saved_paths
                )

                if still_blank:
                    print(
                        "[!] Firefox still saved a blank Instagram frame. "
                        "Falling back to your installed Chrome/Brave/Edge "
                        "(not downloading Chromium)..."
                    )
                    await browser.close()
                    browser = None
                    browser = await launch_installed_chrome_family(p)
                    context = await new_mobile_context(browser, S24_CHROME_UA, ig_cookies)
                    page = await context.new_page()
                    saved_paths = await capture_instagram(
                        page, url, output_dir, timestamp_str, timestamp_display
                    )

                downloaded = download_videos_for_url(
                    url,
                    "instagram",
                    platform_username_from_url(url, "instagram"),
                    timestamp_str,
                    cookies=None,
                )

                print(f"\n✅ Instagram screenshot(s) saved: {output_dir}")
                if downloaded:
                    print(f"✅ Instagram video(s) downloaded: {len(downloaded)}")
                return bool(saved_paths) or bool(downloaded)

        except Exception as e:
            print("\n❌ AN ERROR OCCURRED DURING CAPTURE:")
            print(str(e))
            record_error(url, e, "Capture execution")
            # Still attempt a standalone video download if screenshots failed.
            try:
                downloaded = download_videos_for_url(
                    url, platform, username, timestamp_str, cookies=None
                )
                if downloaded:
                    return True
            except Exception as video_err:
                record_error(url, video_err, "Video download after capture failure")
            return False

        finally:
            if browser is not None:
                await browser.close()


if __name__ == "__main__":
    try:
        prepare_environment()

        print("\n" + "=" * 60)
        print("AKT UNIVERSAL SNAPSHOTTER + COOKIE-INDEPENDENT VIDEO DOWNLOADER")
        print("S24 Ultra-style screenshots + 1080p-max video extraction")
        print("Videos save to: Social Media Videos/")
        print("=" * 60)
        ensure_url_picker_file()
        picker_urls = load_urls_from_picker()

        if picker_urls:
            print(
                f"[+] Found {len(picker_urls)} URL(s) in "
                f"{URL_PICKER_FILE.name} — processing them first."
            )

            for i, picker_url in enumerate(picker_urls, start=1):
                print(f"\n[Picker URL {i}/{len(picker_urls)}] {picker_url}")
                try:
                    success = asyncio.run(capture_post(picker_url))
                    if success:
                        record_completed_url(picker_url)
                        remove_url_from_picker(picker_url)
                    else:
                        print(
                            "[!] Job did not complete successfully — "
                            "URL kept in picker for retry."
                        )
                except Exception as e:
                    print(f"[!] Picker URL job failed: {e}")
                    print("[!] URL kept in picker for retry.")
                    record_error(picker_url, e, "Picker URL job")
        else:
            # CLI: python AKT_Universal_Video_Downloader.py "https://..."
            arg_url = None
            if len(sys.argv) > 1:
                m = re.search(
                    r"https?://[^\s<>\"'\])\}]+", " ".join(sys.argv[1:]), re.I
                )
                if m:
                    arg_url = m.group(0).rstrip(".,;:)")
            user_url = arg_url or get_url_with_timeout()
            if user_url:
                try:
                    success = asyncio.run(capture_post(user_url))
                    if success:
                        record_completed_url(user_url)
                except Exception as e:
                    print(f"[!] Manual URL job failed: {e}")
                    record_error(user_url, e, "Manual URL job")

    except Exception as e:
        print(f"\nCRITICAL SCRIPT CRASH: {e}")
        record_error("", e, "Critical script crash")
    finally:
        try:
            input("\nPress Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            print()
