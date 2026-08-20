#!/usr/bin/env python3
"""
AKT Universal Video Downloader — complete single-file script.

Downloads .mp4 / video from ANY http(s) URL:
  YouTube, Instagram, Facebook, X/Twitter, TikTok, Reddit, Twitch,
  direct .mp4/.m3u8 links, and most other sites yt-dlp supports.

Usage:
  1. Put URLs in "Video URL Picker.txt" (one per line), OR
  2. Run the script and paste a URL when prompted.

Output folder (next to this .py):
  Social Media Videos/
  Naming: domain_@user_DD_Mon_YYYY_HHMM_Video.mp4

Windows tools install to: C:\\AKT Media Tools
Other OS: .akt_media_tools next to this script
"""

from __future__ import annotations

import os
import re
import sys
import ctypes
import shutil
import zipfile
import tempfile
import importlib
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Iterable, List, Optional
from urllib.parse import urlparse

# ============================================================================
# PATHS / BOOTSTRAP
# ============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.name == "nt":
    LIB_ROOT = r"C:\AKT Media Tools"
else:
    LIB_ROOT = os.path.join(SCRIPT_DIR, ".akt_media_tools")

SITE_PACKAGES = os.path.join(LIB_ROOT, "Lib", "site-packages")
TOOLS_DIR = os.path.join(LIB_ROOT, "Tools")
VIDEO_DIR = os.path.join(SCRIPT_DIR, "Social Media Videos")

URL_PICKER_FILE = Path(SCRIPT_DIR) / "Video URL Picker.txt"
DONE_URL_LOG_FILE = Path(SCRIPT_DIR) / "Completed Video Downloads.txt"
ERROR_LOG_FILE = Path(SCRIPT_DIR) / "Error Video Downloads.txt"

S24_CHROME_UA = (
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36"
)

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
    """Prefer this script's TOOLS_DIR when already configured."""
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
    return (
        "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
        "bv*[height<=1080]+ba/"
        "b[height<=1080]/"
        "bv*[height<=720]+ba/"
        "b[height<=720]/"
        "bv*[height<=480]+ba/"
        "b[height<=480]/"
        "bestvideo*+bestaudio/best"
    )


def _base_ytdlp_cmd(
    outtmpl: str,
    cookie_file: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
) -> list:
    ffmpeg = get_ffmpeg_executable()
    runtime, runtime_path = ensure_deno_runtime()

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--retries", "10",
        "--fragment-retries", "10",
        "--file-access-retries", "5",
        "--extractor-retries", "5",
        "--retry-sleep", "1",
        "--concurrent-fragments", "4",
        "--newline",
        "--no-mtime",
        "--ignore-errors",
        "--ignore-no-formats-error",
        "--merge-output-format", "mp4",
        "--remux-video", "mp4",
        "--output", outtmpl,
        "--format", _ytdlp_format_selector(),
        "--add-header", f"User-Agent: {S24_CHROME_UA}",
        "--add-header", "Accept-Language: en-US,en;q=0.9",
        "--remote-components", "ejs:github",
    ]
    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]
    if cookie_file:
        cmd += ["--cookies", cookie_file]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    if runtime and runtime_path:
        cmd += ["--js-runtimes", f"{runtime}:{runtime_path}"]
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
    cookie_file: Optional[str],
    username: str,
    timestamp_str: str,
    temp_dir: str,
) -> list:
    try:
        os.makedirs(temp_dir, exist_ok=True)
        before = set(str(p) for p in _find_video_files(temp_dir))
        outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
        cmd = _base_ytdlp_cmd(outtmpl, cookie_file=cookie_file) + [url]

        print("[+] VIDEO ENGINE B: yt-dlp CLI")
        r = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=1800,
            cwd=temp_dir,
        )
        if r.returncode != 0:
            lines = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
            for line in lines[-8:]:
                print(f"    {line}")
            # Still salvage any completed files.
        return _collect_renamed(
            temp_dir, output_dir, platform, username, timestamp_str, before
        )
    except subprocess.TimeoutExpired:
        print("[!] yt-dlp CLI timed out; moving to the next fallback.")
        return []
    except Exception as e:
        print(f"[i] yt-dlp CLI fallback failed: {type(e).__name__}: {e}")
        return []


def _browser_cookie_ytdlp_fallback(
    url: str,
    output_dir: str,
    platform: str,
    username: str,
    timestamp_str: str,
    temp_dir: str,
) -> list:
    """
    Let yt-dlp read browser cookie DBs directly.
    CRITICAL FIX: the original script built the command but never appended `url`.
    """
    browsers = [
        "firefox", "chrome", "edge", "brave",
        "chromium", "opera", "vivaldi",
    ]
    outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")

    for browser in browsers:
        before = set(str(p) for p in _find_video_files(temp_dir))
        print(f"[+] VIDEO COOKIE FALLBACK: trying {browser.upper()} cookies...")
        cmd = _base_ytdlp_cmd(outtmpl, cookies_from_browser=browser) + [url]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
                cwd=temp_dir,
            )
            log = proc.stdout or ""
            for line in log.splitlines():
                low = line.lower()
                if any(x in low for x in (
                    "extract", "cookie", "download", "destination",
                    "100%", "merging", "error", "warning",
                )):
                    print(f"      {line.strip()[:180]}")

            results = _collect_renamed(
                temp_dir, output_dir, platform, username, timestamp_str, before
            )
            if results:
                print(f"[OK] VIDEO COOKIE FALLBACK succeeded with {browser.upper()}.")
                return results
        except Exception as e:
            print(
                f"[i] Browser-cookie video attempt {browser} failed: "
                f"{type(e).__name__}: {e}"
            )
    return []


def _run_gallery_dl_get_urls(url: str, cookie_file: Optional[str] = None) -> list:
    try:
        cmd = [sys.executable, "-m", "gallery_dl", "-g", "--no-color"]
        if cookie_file:
            cmd += ["--cookies", cookie_file]
        cmd.append(url)

        print("[+] gallery-dl fallback: extracting direct media URLs...")
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
    cookies=None,
) -> list:
    if not media_url or not re.match(r"^https?://", media_url, re.I):
        return []

    os.makedirs(output_dir, exist_ok=True)
    lower = media_url.lower().split("?", 1)[0]
    target = os.path.join(output_dir, base_name + "_Video.mp4")
    ffmpeg = get_ffmpeg_executable()
    headers_text = _media_headers(referer, cookies)

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
            cookie = _cookie_header(cookies)
            if cookie:
                req_headers["Cookie"] = cookie

            req = urllib.request.Request(media_url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=120) as response, open(target, "wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)

            if _valid_video_file(target):
                # Normalize non-MP4 containers to .mp4 when possible. If remux
                # fails, keep the downloaded file under an .mp4 name anyway —
                # never discard a valid download solely because remux failed.
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
    cookies=None,
) -> list:
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
        cookie = _cookie_header(cookies)
        if cookie:
            cmd += ["--http-header", f"Cookie={cookie}"]

        print("[+] Streamlink fallback: attempting HLS/DASH stream...")
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


def run_yt_dlp_download(
    url: str,
    output_dir: str,
    platform: str,
    cookies=None,
    username: str = "unknown",
    timestamp_str: str = "",
) -> list:
    """
    Multi-engine video ladder for any http(s) URL:
      A. yt-dlp Python API
      B. yt-dlp CLI
      C. browser-native cookies (--cookies-from-browser)  [URL always appended]
      D. gallery-dl → direct / streamlink
      E. yt-dlp URL extract → direct / streamlink
    """
    if not is_downloadable_url(url):
        print("[!] Not a downloadable http(s) URL.")
        return []

    os.makedirs(output_dir, exist_ok=True)
    platform = platform or detect_platform(url)
    username = username or platform_username_from_url(url, platform)

    temp_dir = os.path.join(
        output_dir,
        ".akt_download_tmp",
        re.sub(r"[^A-Za-z0-9_-]+", "_", str(abs(hash(url + timestamp_str))))[:48],
    )
    os.makedirs(temp_dir, exist_ok=True)

    cookie_file = None
    base_name = safe_filename(
        f"{PLATFORM_DOMAIN_MAP.get(platform, platform + '.com')}_@"
        f"{username or 'unknown'}_{timestamp_str}"
    )

    try:
        cookie_file = write_temp_netscape_cookies(cookies or [])
        ffmpeg = get_ffmpeg_executable()
        runtime, runtime_path = ensure_deno_runtime()

        # ---------------------------------------------------------------
        # A) yt-dlp Python API
        # ---------------------------------------------------------------
        try:
            import yt_dlp

            outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
            ydl_opts = {
                "outtmpl": outtmpl,
                "format": _ytdlp_format_selector(),
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": False,
                "no_warnings": False,
                "retries": 10,
                "fragment_retries": 10,
                "file_access_retries": 5,
                "extractor_retries": 5,
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
            if cookie_file:
                ydl_opts["cookiefile"] = cookie_file
            if runtime and runtime_path:
                ydl_opts["js_runtimes"] = {runtime: {"path": runtime_path}}

            print(
                f"[+] VIDEO ENGINE A: yt-dlp API — {platform} "
                f"({urlparse(url).hostname or 'site'})"
            )
            print("[+] Quality ladder: 1080p → 720p → 480p → best available")

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
            print(f"[i] VIDEO ENGINE A failed: {type(e).__name__}: {e}")

        # ---------------------------------------------------------------
        # B) yt-dlp CLI
        # ---------------------------------------------------------------
        results = _run_yt_dlp_cli(
            url, output_dir, platform, cookie_file,
            username, timestamp_str, temp_dir,
        )
        if results:
            return results

        # ---------------------------------------------------------------
        # C) Browser-native cookies (URL always included)
        # ---------------------------------------------------------------
        results = _browser_cookie_ytdlp_fallback(
            url, output_dir, platform, username, timestamp_str, temp_dir
        )
        if results:
            return results

        # ---------------------------------------------------------------
        # D) gallery-dl → direct / streamlink
        # ---------------------------------------------------------------
        for media_url in _run_gallery_dl_get_urls(url, cookie_file):
            results = _download_direct_media_url(
                media_url, output_dir, base_name, referer=url, cookies=cookies
            )
            if results:
                return results
            results = _run_streamlink_fallback(
                media_url, output_dir, base_name, referer=url, cookies=cookies
            )
            if results:
                return results

        # ---------------------------------------------------------------
        # E) Extract formats without downloading, then fetch media URLs
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
            if cookie_file:
                extract_opts["cookiefile"] = cookie_file
            if runtime and runtime_path:
                extract_opts["js_runtimes"] = {runtime: {"path": runtime_path}}

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
                    media_url, output_dir, base_name, referer=url, cookies=cookies
                )
                if results:
                    return results
                results = _run_streamlink_fallback(
                    media_url, output_dir, base_name, referer=url, cookies=cookies
                )
                if results:
                    return results
        except Exception as e:
            print(f"[i] Direct yt-dlp URL extraction failed: {type(e).__name__}: {e}")

        return []
    finally:
        if cookie_file:
            try:
                os.remove(cookie_file)
            except Exception:
                pass
        try:
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def ensure_video_dependencies(site_packages: str) -> None:
    """Install yt-dlp stack into the AKT site-packages target when missing."""
    required = {
        "yt_dlp": "yt-dlp",
        "yt_dlp_ejs": "yt-dlp-ejs",
        "imageio_ffmpeg": "imageio-ffmpeg",
        "gallery_dl": "gallery-dl",
        "streamlink": "streamlink",
    }
    missing = []
    for module, pip_name in required.items():
        if not os.path.isdir(os.path.join(site_packages, module)):
            # Also accept already-importable system installs.
            try:
                __import__(module)
            except Exception:
                missing.append(pip_name)

    if not missing:
        print("[OK] Video download libraries are already present.")
        return

    print(f"[-] Installing video libraries {missing}...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--target", site_packages]
        + missing
    )
    if site_packages not in sys.path:
        sys.path.insert(0, site_packages)
    import importlib
    importlib.invalidate_caches()
    print("[OK] Video download libraries installed.")



# ============================================================================
# URL PICKER / LOGGING
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
        test = os.path.join(folder, ".write_test")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test)
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


def prepare_environment():
    print("=== AKT Video Downloader Setup ===")
    if not can_write(LIB_ROOT):
        if not is_admin():
            relaunch_as_admin()
        else:
            os.makedirs(SITE_PACKAGES, exist_ok=True)
            os.makedirs(TOOLS_DIR, exist_ok=True)

    if SITE_PACKAGES not in sys.path:
        sys.path.insert(0, SITE_PACKAGES)

    ensure_video_dependencies(SITE_PACKAGES)
    # Also install browser-cookie3 for authenticated sites.
    try:
        import browser_cookie3  # noqa: F401
        print("[OK] browser-cookie3 present.")
    except Exception:
        print("[-] Installing browser-cookie3...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade",
             "--target", SITE_PACKAGES, "browser-cookie3"]
        )
        importlib.invalidate_caches()
        print("[OK] browser-cookie3 installed.")

    ensure_deno_runtime()
    ffmpeg = get_ffmpeg_executable()
    if ffmpeg:
        print(f"[OK] FFmpeg: {ffmpeg}")
    else:
        print("[!] FFmpeg not found yet — imageio-ffmpeg should provide it after import.")
    os.makedirs(VIDEO_DIR, exist_ok=True)
    print(f"[OK] Output folder: {VIDEO_DIR}")


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
    if not url:
        return
    try:
        existing = []
        if DONE_URL_LOG_FILE.exists():
            text = DONE_URL_LOG_FILE.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                m = re.search(r"https?://[^\s<>\"'\])\}]+", line, re.IGNORECASE)
                if m:
                    saved = m.group(0).rstrip(".,;:)")
                    if saved and saved.lower() not in {u.lower() for u in existing}:
                        existing.append(saved)
        ordered = [url.strip()] + [
            u for u in existing if u.strip().lower() != url.strip().lower()
        ]
        total = len(ordered)
        DONE_URL_LOG_FILE.write_text(
            "\n".join(f"{total - i}. {u}" for i, u in enumerate(ordered)) + "\n",
            encoding="utf-8",
        )
        print(f"[+] Completed URL recorded: {DONE_URL_LOG_FILE.name}")
    except Exception as e:
        print(f"[!] Could not update completed URL log: {e}")


def record_error(url: str, error: object, context: str = "") -> None:
    try:
        from traceback import format_exc
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with ERROR_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"Time: {timestamp}\n")
            f.write(f"URL: {url or '[unknown]'}\n")
            if context:
                f.write(f"Context: {context}\n")
            f.write(f"Error: {error}\n")
            trace = format_exc()
            if trace.strip() and trace.strip() != "NoneType: None":
                f.write("Traceback:\n" + trace.rstrip() + "\n")
            f.write("\n")
        print(f"[+] Error recorded: {ERROR_LOG_FILE.name}")
    except Exception as log_error:
        print(f"[!] Could not write error log: {log_error}")


def get_url_manual():
    print()
    print(f"[+] No URLs in {URL_PICKER_FILE.name}")
    print("    Enter any video URL (YouTube, Instagram, TikTok, direct .mp4, etc.):")
    try:
        raw = input("    URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not raw:
        return None
    m = re.search(r"https?://[^\s<>\"'\])\}]+", raw, re.IGNORECASE)
    if not m:
        print("[!] No valid URL found.")
        return None
    return m.group(0).rstrip(".,;:)")


def download_one(url: str) -> bool:
    if not is_downloadable_url(url):
        print(f"[!] Not a valid http(s) URL: {url}")
        record_error(url, "Invalid URL", "validation")
        return False

    platform = detect_platform(url)
    username = platform_username_from_url(url, platform)
    timestamp_str = datetime.now().strftime("%d_%b_%Y_%H%M")
    domain = (urlparse(url).hostname or "").lower()
    cookies = get_browser_cookies_for_domain(domain) if domain else []

    print()
    print("-" * 60)
    print(f"[+] URL     : {url}")
    print(f"[+] Platform: {platform}")
    print(f"[+] User    : @{username}")
    print(f"[+] Output  : {VIDEO_DIR}")
    print("-" * 60)

    try:
        results = run_yt_dlp_download(
            url,
            VIDEO_DIR,
            platform,
            cookies=cookies,
            username=username,
            timestamp_str=timestamp_str,
        )
        if results:
            print(f"\n✅ SUCCESS — {len(results)} video file(s):")
            for path in results:
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"    → {path}  ({size_mb:.2f} MB)")
            return True
        print("\n❌ FAILED — no downloadable video found for this URL.")
        record_error(url, "No downloadable video found", "download")
        return False
    except Exception as e:
        print(f"\n❌ FAILED — {type(e).__name__}: {e}")
        record_error(url, e, "download")
        return False


if __name__ == "__main__":
    try:
        prepare_environment()
        print("\n" + "=" * 60)
        print("AKT UNIVERSAL VIDEO DOWNLOADER")
        print("Any URL → Social Media Videos/  (1080p-max when available)")
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
                ok = download_one(picker_url)
                if ok:
                    record_completed_url(picker_url)
                    remove_url_from_picker(picker_url)
                else:
                    print("[!] URL kept in picker for retry.")
        else:
            # CLI arg support: python AKT_Universal_Video_Downloader.py <url>
            arg_url = None
            if len(sys.argv) > 1:
                m = re.search(r"https?://[^\s<>\"'\])\}]+", " ".join(sys.argv[1:]), re.I)
                if m:
                    arg_url = m.group(0).rstrip(".,;:)")
            user_url = arg_url or get_url_manual()
            if user_url:
                ok = download_one(user_url)
                if ok:
                    record_completed_url(user_url)
    except Exception as e:
        print(f"\nCRITICAL SCRIPT CRASH: {e}")
        record_error("", e, "Critical script crash")
    finally:
        try:
            input("\nPress Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            print()
