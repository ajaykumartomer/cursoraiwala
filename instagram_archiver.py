#!/usr/bin/env python3
"""
ULTIMATE INSTAGRAM ARCHIVER (YT-DLP + Browser Cookies)

- Accepts: Reels, Posts, Carousels, Stories, Highlights, Profiles
- Mode: MEDIA ONLY (no JSON / no thumbnails)
- Auth: Scans C: for cookies — Firefox FIRST, then Chrome, Edge, Brave, …

Usage:
  1. Open Firefox → instagram.com → log in → CLOSE Firefox
  2. python instagram_archiver.py
  3. Paste any Instagram URL
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

# =============================================================================
# 1. Auto-install yt-dlp
# =============================================================================
try:
    import yt_dlp  # noqa: F401
except ImportError:
    print("=" * 55)
    print("Library 'yt-dlp' is missing. Installing it automatically...")
    print("=" * 55)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"])
        import importlib
        import site

        importlib.invalidate_caches()
        user_site = site.getusersitepackages()
        if user_site and user_site not in sys.path:
            sys.path.append(user_site)
        site.main()
        import yt_dlp  # noqa: F401

        print("\nInstallation successful! Loading archiver...\n")
    except Exception as e:
        print("\n" + "=" * 55)
        print(f"AUTO-INSTALL FAILED: {e}")
        input("Press Enter to close this window...")
        sys.exit(1)

# Browser try order (Firefox MUST be first)
BROWSERS = ["firefox", "chrome", "edge", "brave", "opera", "chromium", "vivaldi"]


def get_target_name(url: str) -> str | None:
    """Intelligently extract a folder name based on the Instagram URL type."""
    url_clean = url.split("?")[0].rstrip("/")

    if "/reels/" in url_clean:
        return f"Insta_Reel_{url_clean.split('/reels/')[1].split('/')[0]}"
    if "/reel/" in url_clean:
        return f"Insta_Reel_{url_clean.split('/reel/')[1].split('/')[0]}"
    if "/p/" in url_clean:
        return f"Insta_Post_{url_clean.split('/p/')[1].split('/')[0]}"
    if "/stories/highlights/" in url_clean:
        highlight_id = url_clean.split("/stories/highlights/")[1].split("/")[0]
        return f"Insta_Highlight_{highlight_id}"
    if "/highlights/" in url_clean:
        highlight_id = url_clean.split("/highlights/")[1].split("/")[0]
        return f"Insta_Highlight_{highlight_id}"
    if "/stories/" in url_clean:
        parts = url_clean.split("/stories/")[1].split("/")
        username = parts[0]
        story_id = parts[1] if len(parts) > 1 else "All"
        return f"Insta_Stories_{username}_{story_id}"

    match = re.search(r"instagram\.com/([^/?]+)/?", url_clean)
    if match and match.group(1) not in {
        "", "explore", "reel", "reels", "p", "stories", "highlights", "tv", "accounts",
    }:
        return f"Insta_Profile_{match.group(1)}"
    return None


def run_ytdlp(cmd: list[str], timeout: int = 600) -> int:
    """Run yt-dlp with live console output."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    start = time.time()
    try:
        for line in process.stdout:
            print(f"  [yt-dlp] {line.rstrip()}")
            if time.time() - start > timeout:
                print(f"\nDownload timed out after {timeout // 60} minutes.")
                process.kill()
                return 124
        return process.wait(timeout=60)
    except Exception:
        process.kill()
        raise


def ytdlp_cmd(url: str, out_tmpl: str) -> list[str]:
    # bv*+ba/b = best video+audio OR best single file (photos won't crash on -f best)
    return [
        sys.executable,
        "-m",
        "yt_dlp",
        url,
        "-o",
        out_tmpl,
        "--yes-playlist",
        "--no-mtime",
        "--ignore-errors",
        "--ignore-no-formats-error",
        "-f",
        "bv*+ba/b",
        "--format-sort",
        "res,br,size",
        "--concurrent-fragments",
        "8",
        "--no-warnings",
        # MEDIA ONLY — no JSON, no thumbnails
        "--no-write-info-json",
        "--no-write-thumbnail",
        "--no-write-comments",
        "--no-write-description",
    ]


def download_instagram_media(url: str, dest_folder: Path) -> bool:
    """
    Scan browsers for cookies (Firefox → Chrome → …), then download MEDIA ONLY.
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(dest_folder / "%(id)s_%(title).80B.%(ext)s")

    print("\nCookie auth order: Firefox → Chrome → Edge → Brave → Opera → …")
    print("(Make sure you are logged into Instagram in the browser, then CLOSE it.)\n")

    for browser in BROWSERS:
        print(f"---> Trying {browser.upper()} cookies...")
        cmd = ytdlp_cmd(url, out_tmpl) + ["--cookies-from-browser", browser]
        try:
            code = run_ytdlp(cmd, timeout=600)
            files = [p for p in dest_folder.rglob("*") if p.is_file()]
            if code == 0 or files:
                print(f"\n✅ Download finished via {browser.upper()}!")
                print(f"Files saved to:\n{dest_folder}")
                return True
            print(f"⚠️  {browser} failed (not installed / not logged in / locked). Next...\n")
        except Exception as e:
            print(f"❌ {browser} error: {e}\n")

    # Last try: no cookies (public posts only — usually fails on IG)
    print("---> Final attempt without cookies (public only)...")
    try:
        code = run_ytdlp(ytdlp_cmd(url, out_tmpl), timeout=600)
        files = [p for p in dest_folder.rglob("*") if p.is_file()]
        if code == 0 or files:
            print(f"\n✅ Download finished (no cookies)!\nFiles saved to:\n{dest_folder}")
            return True
    except Exception as e:
        print(f"❌ Download failed: {e}")

    print("\n" + "=" * 55)
    print("CRITICAL: Could not authenticate with any browser.")
    print("FIX:")
    print("  1) Open FIREFOX → https://www.instagram.com → log in")
    print("  2) CLOSE Firefox completely")
    print("  3) Re-run this script")
    print("=" * 55)
    return False


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    script_directory = Path(__file__).resolve().parent
    base_download_dir = script_directory / "Instagram_Archives"

    try:
        base_download_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Failed to create base directory: {e}")
        input("Press Enter to close this window...")
        sys.exit(1)

    print("=" * 55)
    print("   ULTIMATE INSTAGRAM ARCHIVER (YT-DLP)")
    print(f"   Save Location: {base_download_dir}")
    print("=" * 55)
    print("  Accepts: Reels, Posts, Carousels, Stories,")
    print("           Highlights, and Full User Profiles.")
    print("  Mode:    MEDIA ONLY (No JSON/Thumbnails)")
    print("  Auth:    Firefox → Chrome → Edge → Brave → …")
    print("=" * 55)

    while True:
        try:
            url = input("\nEnter ANY Instagram URL (or type 'exit' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nOperation cancelled by user.")
            break

        if url.lower() in {"exit", "quit", "q"}:
            print("Exiting archiver...")
            break

        if not url:
            continue

        if "instagram.com" not in url and "instagr.am" not in url:
            print("❌ That doesn't look like an Instagram URL.")
            continue

        try:
            target_name = get_target_name(url)
            if not target_name:
                print("❌ Couldn't figure out the URL type. Make sure you copied it correctly.")
                continue

            print(f"\nDetected Target: {target_name}...")
            target_folder = base_download_dir / target_name
            download_instagram_media(url, target_folder)
            print("=" * 55)

        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error occurred: {e}")
            print("=" * 55)

    print("\nThanks for using Instagram Archiver!")
    try:
        input("Press Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass
