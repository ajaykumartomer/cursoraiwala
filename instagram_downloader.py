#!/usr/bin/env python3
"""
Instagram Media Downloader — max quality, max speed.

Why the previous yt-dlp-only approach fails:
  1. Instagram blocks anonymous requests → cookies / login are required.
  2. `-f best` crashes on photo posts (no video formats).
  3. gallery-dl handles IG carousels/photos more reliably than yt-dlp.
  4. Subprocess + fixed 180s timeout is slower and less controllable.

Engines (tried in order):
  gallery-dl  → best for photos, carousels, stories, profiles
  yt-dlp      → best for Reels / video bitrate + concurrent fragments

Usage:
  python instagram_downloader.py
  python instagram_downloader.py "https://www.instagram.com/reel/XXXX/"
  python instagram_downloader.py --cookies-from-browser chrome
  python instagram_downloader.py --cookie-file cookies.txt urls.txt
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Auto-install dependencies
# ---------------------------------------------------------------------------
REQUIRED = ("yt_dlp", "gallery_dl")


def ensure_deps() -> None:
    missing = []
    for mod in REQUIRED:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod.replace("_", "-"))
    if not missing:
        return
    print(f"[setup] Installing: {', '.join(missing)} ...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-U", *missing],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )


ensure_deps()

import gallery_dl  # noqa: E402
import yt_dlp  # noqa: E402
from gallery_dl import config as gdl_config  # noqa: E402
from gallery_dl import job as gdl_job  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
IG_HOSTS = {"instagram.com", "www.instagram.com", "instagr.am"}
SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:p|reel|reels|tv|stories/[^/]+)/([^/?#]+)",
    re.I,
)
PROFILE_RE = re.compile(r"instagram\.com/([A-Za-z0-9._]+)/?(?:[?#]|$)", re.I)


def is_instagram_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return host in {h.removeprefix("www.") for h in IG_HOSTS} or host == "instagr.am"
    except Exception:
        return False


def shortcode_or_slug(url: str) -> str:
    m = SHORTCODE_RE.search(url)
    if m:
        return m.group(1)
    m = PROFILE_RE.search(url)
    if m and m.group(1).lower() not in {"p", "reel", "reels", "tv", "stories", "explore"}:
        return m.group(1)
    return "unknown"


def default_download_root() -> Path:
    return Path.home() / "Downloads" / "Instagram_Archives"


def progress_hook(d: dict) -> None:
    status = d.get("status")
    if status == "downloading":
        pct = d.get("_percent_str", "").strip()
        spd = d.get("_speed_str", "").strip()
        eta = d.get("_eta_str", "").strip()
        name = Path(d.get("filename") or d.get("info_dict", {}).get("id", "")).name
        print(f"  ↓ {pct:>7}  {spd:>10}  ETA {eta:>6}  {name}", end="\r", flush=True)
    elif status == "finished":
        print(f"\n  ✓ saved: {d.get('filename')}")


# ---------------------------------------------------------------------------
# gallery-dl (primary — photos / carousels / stories / profiles)
# ---------------------------------------------------------------------------
def _gdl_browser_cookies(spec: str) -> tuple:
    """Parse browser[+keyring][/domain][:profile][::container] like gallery-dl CLI."""
    browser, _, profile = spec.partition(":")
    browser, _, keyring = browser.partition("+")
    browser, _, domain = browser.partition("/")
    if profile and profile.startswith(":"):
        container = profile[1:]
        profile = None
    else:
        profile, _, container = profile.partition("::")
    return (browser, profile or None, keyring or None, container or None, domain or None)


def download_with_gallery_dl(
    url: str,
    dest: Path,
    *,
    cookies_from_browser: str | None,
    cookie_file: Path | None,
) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    gdl_config.clear()
    gdl_config.set(("extractor",), "base-directory", str(dest))
    gdl_config.set(("extractor", "instagram"), "directory", ["{username}", "{post_shortcode}"])
    gdl_config.set(
        ("extractor", "instagram"),
        "filename",
        "{post_shortcode}_{num:>02}_{sidecar_media_id|media_id}.{extension}",
    )
    # Original / highest available quality
    gdl_config.set(("extractor", "instagram"), "videos", True)
    gdl_config.set(("extractor", "instagram"), "include", "all")
    gdl_config.set(("downloader", "http"), "retries", 5)
    gdl_config.set(("downloader", "http"), "timeout", 30.0)
    gdl_config.set(("downloader",), "mtime", False)

    # Root-level cookies (same as gallery-dl CLI) — required for IG auth
    if cookie_file and cookie_file.is_file():
        gdl_config.set((), "cookies", str(cookie_file))
    elif cookies_from_browser:
        gdl_config.set((), "cookies", _gdl_browser_cookies(cookies_from_browser))

    print(f"[gallery-dl] {url}")
    try:
        status = gdl_job.DownloadJob(url).run()
        files = [p for p in dest.rglob("*") if p.is_file()]
        if files:
            print(f"[gallery-dl] OK → {dest} ({len(files)} file(s), status={status})")
            return True
        print("[gallery-dl] no files written; falling back to yt-dlp")
        return False
    except Exception as e:
        print(f"[gallery-dl] failed: {e}")
        return False


# ---------------------------------------------------------------------------
# yt-dlp (fallback / video specialist)
# ---------------------------------------------------------------------------
def download_with_ytdlp(
    url: str,
    dest: Path,
    *,
    cookies_from_browser: str | None,
    cookie_file: Path | None,
    concurrent: int,
) -> bool:
    dest.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest / "%(uploader|owner|id)s" / "%(id)s_%(title).80B.%(ext)s")

    opts: dict = {
        # Prefer merged best video+audio; fall back gracefully for photos
        "format": "bv*+ba/b",
        "format_sort": ["res", "br", "size", "fps"],
        "outtmpl": outtmpl,
        "writethumbnail": True,
        "writeinfojson": True,
        "writesubtitles": False,
        "ignoreerrors": True,
        "no_mtime": True,
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": max(1, concurrent),
        "http_chunk_size": 10 * 1024 * 1024,  # 10 MiB chunks → faster on big reels
        "socket_timeout": 30,
        "quiet": False,
        "no_warnings": False,
        "progress_hooks": [progress_hook],
        # Instagram playlists = carousels
        "noplaylist": False,
    }

    # Convert thumbs to JPG when ffmpeg is available (safe to skip otherwise)
    if shutil.which("ffmpeg"):
        opts["postprocessors"] = [
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
        ]

    if cookie_file and cookie_file.is_file():
        opts["cookiefile"] = str(cookie_file)
    elif cookies_from_browser:
        # e.g. "chrome", "firefox", "edge", "brave", "chromium"
        opts["cookiesfrombrowser"] = (cookies_from_browser,)

    print(f"[yt-dlp] {url}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            code = ydl.download([url])
        files = [p for p in dest.rglob("*") if p.is_file()]
        if code == 0 or files:
            print(f"\n[yt-dlp] OK → {dest} ({len(files)} file(s))")
            return True
        print("[yt-dlp] finished with errors and no files")
        return False
    except yt_dlp.utils.DownloadError as e:
        print(f"[yt-dlp] DownloadError: {e}")
        return False
    except Exception as e:
        print(f"[yt-dlp] failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def download_one(
    url: str,
    root: Path,
    *,
    cookies_from_browser: str | None,
    cookie_file: Path | None,
    concurrent: int,
    engine: str,
) -> bool:
    url = url.strip()
    if not url or not is_instagram_url(url):
        print(f"Skip (not an Instagram URL): {url}")
        return False

    slug = shortcode_or_slug(url)
    dest = root / f"Insta_{slug}"
    print("=" * 55)
    print(f"Archiving: {slug}")
    print(f"Folder:    {dest}")
    print("=" * 55)

    ok = False
    if engine in ("auto", "gallery-dl"):
        ok = download_with_gallery_dl(
            url,
            dest,
            cookies_from_browser=cookies_from_browser,
            cookie_file=cookie_file,
        )
        if ok and engine == "gallery-dl":
            return True
        if ok and engine == "auto":
            # gallery-dl often misses max video bitrate; top up with yt-dlp
            # when URL looks like a reel / video post
            if any(x in url.lower() for x in ("/reel/", "/reels/", "/tv/")):
                print("[auto] Reel detected — also pulling max video via yt-dlp")
                download_with_ytdlp(
                    url,
                    dest,
                    cookies_from_browser=cookies_from_browser,
                    cookie_file=cookie_file,
                    concurrent=concurrent,
                )
            return True

    if engine in ("auto", "yt-dlp") and not ok:
        ok = download_with_ytdlp(
            url,
            dest,
            cookies_from_browser=cookies_from_browser,
            cookie_file=cookie_file,
            concurrent=concurrent,
        )
    elif engine == "yt-dlp":
        ok = download_with_ytdlp(
            url,
            dest,
            cookies_from_browser=cookies_from_browser,
            cookie_file=cookie_file,
            concurrent=concurrent,
        )

    if not ok:
        print(
            "\nFAILED. Instagram almost always needs a logged-in session now.\n"
            "  1) Log into Instagram in Chrome/Firefox\n"
            "  2) Re-run with:  --cookies-from-browser chrome\n"
            "  OR export cookies to Netscape format and use:  --cookie-file cookies.txt\n"
        )
    return ok


def load_urls(items: Iterable[str]) -> list[str]:
    urls: list[str] = []
    for item in items:
        p = Path(item)
        if p.is_file():
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
        else:
            urls.append(item)
    return urls


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download Instagram posts/reels/carousels/stories at max quality.",
    )
    p.add_argument(
        "targets",
        nargs="*",
        help="Instagram URL(s) and/or text files with one URL per line",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_download_root(),
        help="Base download directory (default: ~/Downloads/Instagram_Archives)",
    )
    p.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        default=None,
        help="Load cookies from browser (chrome, firefox, edge, brave, chromium, …)",
    )
    p.add_argument(
        "--cookie-file",
        type=Path,
        default=None,
        help="Netscape cookies.txt exported from your browser",
    )
    p.add_argument(
        "--engine",
        choices=("auto", "gallery-dl", "yt-dlp"),
        default="auto",
        help="Download engine (default: auto = gallery-dl then yt-dlp)",
    )
    p.add_argument(
        "-N",
        "--concurrent",
        type=int,
        default=8,
        help="Concurrent fragment downloads for yt-dlp (default: 8)",
    )
    return p.parse_args(argv)


def interactive_loop(args: argparse.Namespace) -> int:
    print("=" * 55)
    print("  INSTAGRAM MEDIA DOWNLOADER  (gallery-dl + yt-dlp)")
    print(f"  Save to: {args.output}")
    if args.cookies_from_browser:
        print(f"  Cookies: browser={args.cookies_from_browser}")
    elif args.cookie_file:
        print(f"  Cookies: file={args.cookie_file}")
    else:
        print("  Cookies: NONE (public posts only — login recommended)")
    print("=" * 55)
    print("Tip: type 'exit' to quit. Paste any /p/ /reel/ /tv/ or profile URL.")

    failures = 0
    while True:
        try:
            raw = input("\nURL> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not raw:
            continue
        if raw.lower() in {"exit", "quit", "q"}:
            break
        ok = download_one(
            raw,
            args.output,
            cookies_from_browser=args.cookies_from_browser,
            cookie_file=args.cookie_file,
            concurrent=args.concurrent,
            engine=args.engine,
        )
        if not ok:
            failures += 1
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)

    if not args.targets:
        return interactive_loop(args)

    urls = load_urls(args.targets)
    if not urls:
        print("No URLs provided.")
        return 1

    failures = 0
    for url in urls:
        ok = download_one(
            url,
            args.output,
            cookies_from_browser=args.cookies_from_browser,
            cookie_file=args.cookie_file,
            concurrent=args.concurrent,
            engine=args.engine,
        )
        if not ok:
            failures += 1
    print(f"\nDone. {len(urls) - failures}/{len(urls)} succeeded.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
