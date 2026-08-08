#!/usr/bin/env python3
"""
Instagram Cookie Archiver (Windows-friendly)

Logic (exactly what you asked for):
  1) Scan C: for browser cookie stores
  2) Prefer Firefox first, then Chrome, then Edge/Brave/Opera/...
  3) Authenticate yt-dlp with those cookies
  4) Download Instagram video / photo / carousel

Fixes vs your paste:
  - Actually scans C:\\Users\\... AppData for browsers (not blind name tries only)
  - Exports Firefox Instagram cookies to cookies.txt when sessionid exists
  - Uses format bv*+ba/b so photo posts do not crash on `-f best`
  - Real-time yt-dlp console output (Popen)
  - Tries exported cookie-file BEFORE browser DPAPI (more reliable on Windows)

Usage:
  python ig_archiver.py
  python ig_archiver.py "https://www.instagram.com/reel/XXXX/"
  python ig_archiver.py --deep-scan
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ---------------------------------------------------------------------------
# Auto-install yt-dlp
# ---------------------------------------------------------------------------
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

        print("\nInstallation successful!\n")
    except Exception as e:
        print(f"\nAUTO-INSTALL FAILED: {e}")
        input("Press Enter to close this window...")
        sys.exit(1)

from browser_cookie_scanner import (  # noqa: E402
    pick_best,
    scan_browsers,
)

SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:p|reel|reels|tv|stories/[^/]+)/([^/?#]+)",
    re.I,
)

# Fallback order if disk scan finds nothing (yt-dlp still may resolve profiles)
DEFAULT_BROWSER_ORDER = ["firefox", "chrome", "edge", "brave", "opera", "chromium", "vivaldi"]


def extract_shortcode(url: str) -> str | None:
    m = SHORTCODE_RE.search(url)
    if m:
        return m.group(1)
    if "/reel/" in url:
        return url.split("/reel/")[1].split("/")[0].split("?")[0]
    if "/p/" in url:
        return url.split("/p/")[1].split("/")[0].split("?")[0]
    if "/tv/" in url:
        return url.split("/tv/")[1].split("/")[0].split("?")[0]
    return None


def build_browser_try_list(drive: str, deep: bool, export_dir: Path) -> tuple[Path | None, list[str]]:
    """
    Scan C: (or given drive). Return (cookie_file, browser_names_in_priority_order).
    Firefox always first when present.
    """
    from browser_cookie_scanner import export_firefox_netscape, print_report

    print("=" * 55)
    print("  SCANNING FOR BROWSER COOKIES")
    print(f"  Drive priority: {drive}  |  Order: Firefox → Chrome → others")
    print("=" * 55)

    hits = scan_browsers(drive=drive, deep=deep)
    print_report(hits)
    best = pick_best(hits)

    cookie_file: Path | None = None
    if best and best.browser == "firefox" and best.cookie_db and best.has_instagram_session:
        export_dir.mkdir(parents=True, exist_ok=True)
        out = export_dir / f"firefox_{best.profile_name}_instagram_cookies.txt"
        n = export_firefox_netscape(best.cookie_db, out)
        if n > 0:
            cookie_file = out
            print(f"[auth] Exported {n} Instagram cookies → {out}")
            print("[auth] Will try exported Firefox cookies first.")

    seen: set[str] = set()
    exact_specs: list[str] = []
    browsers: list[str] = []

    for h in hits:
        spec = h.yt_dlp_spec
        if spec not in exact_specs:
            exact_specs.append(spec)
        name = "opera" if h.browser.startswith("opera") else h.browser
        if name not in seen:
            # Keep Firefox names at front: hits are already score-sorted
            browsers.append(name)
            seen.add(name)

    # Force Firefox name ahead of others even if only in fallback list
    ordered_names = [b for b in browsers if b == "firefox"] + [b for b in browsers if b != "firefox"]
    for name in DEFAULT_BROWSER_ORDER:
        if name not in seen:
            ordered_names.append(name)
            seen.add(name)

    final: list[str] = []
    seen_final: set[str] = set()
    for b in exact_specs + ordered_names:
        if b not in seen_final:
            final.append(b)
            seen_final.add(b)

    print(f"[auth] Browser try order: {' → '.join(final[:8])}{'…' if len(final) > 8 else ''}")
    return cookie_file, final


def run_ytdlp(cmd: list[str], timeout: int = 300) -> int:
    """Run yt-dlp with live console output. Returns process return code."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    start = time.time()
    try:
        for line in process.stdout:
            print(f"  [yt-dlp] {line.rstrip()}")
            if time.time() - start > timeout:
                process.kill()
                print(f"\n[TIMEOUT] Killed after {timeout}s")
                return 124
        return process.wait(timeout=30)
    except Exception:
        process.kill()
        raise


def ytdlp_base_cmd(url: str, out_tmpl: str) -> list[str]:
    # bv*+ba/b = best video+audio, OR best single file (photos won't crash)
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
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "--write-info-json",
        "--no-warnings",
    ]


def download_instagram_media(
    url: str,
    dest_folder: Path,
    *,
    drive: str = "C:",
    deep: bool = False,
    timeout: int = 300,
) -> bool:
    dest_folder.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(dest_folder / "%(id)s_%(title).80B.%(ext)s")
    export_dir = dest_folder.parent / "_cookies"

    cookie_file, browsers = build_browser_try_list(drive, deep, export_dir)

    # --- Attempt 0: exported Netscape cookies from Firefox (best on Windows) ---
    if cookie_file and cookie_file.is_file():
        print(f"\n---> Attempting auth via exported cookie file:\n     {cookie_file}")
        cmd = ytdlp_base_cmd(url, out_tmpl) + ["--cookies", str(cookie_file)]
        try:
            code = run_ytdlp(cmd, timeout=timeout)
            files = [p for p in dest_folder.rglob("*") if p.is_file()]
            if code == 0 or files:
                print(f"\n[SUCCESS] Authenticated via Firefox cookie file!")
                print(f"Files saved to: {dest_folder}")
                return True
            print("[FAILED] Cookie file auth did not produce files. Trying browsers...")
        except Exception as e:
            print(f"[ERROR] Cookie file attempt failed: {e}")

    # --- Attempts: each browser found / fallback list (Firefox first) ---
    for browser in browsers:
        print(f"\n---> Attempting to authenticate using {browser.upper()} cookies...")
        cmd = ytdlp_base_cmd(url, out_tmpl) + ["--cookies-from-browser", browser]
        try:
            code = run_ytdlp(cmd, timeout=timeout)
            files = [p for p in dest_folder.rglob("*") if p.is_file()]
            if code == 0 or files:
                print(f"\n[SUCCESS] Download authenticated via {browser}!")
                print(f"Files saved to: {dest_folder}")
                return True
            print(
                f"\n[FAILED] {browser} didn't work "
                "(not installed, not logged in, or cookie DB locked)."
            )
            print("Moving to the next browser...")
        except Exception as e:
            print(f"\n[ERROR] Crash while trying {browser}: {e}")

    print("\n" + "=" * 55)
    print("CRITICAL FAILURE: No valid Instagram cookies found.")
    print("FIX:")
    print("  1) Open FIREFOX → https://www.instagram.com → log in")
    print("  2) Close Firefox completely (unlocks cookies.sqlite)")
    print("  3) Re-run this script")
    print("=" * 55)
    return False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Instagram downloader with C: cookie scan (Firefox first).")
    p.add_argument("url", nargs="?", help="Instagram post/reel URL (optional; interactive if omitted)")
    p.add_argument("--drive", default="C:", help="Drive to scan (default C:)")
    p.add_argument("--deep-scan", action="store_true", help="Deep-walk Users/Program Files for portable browsers")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path.home() / "Downloads" / "Instagram_Archives",
        help="Base save folder",
    )
    p.add_argument("--timeout", type=int, default=300, help="Per-browser download timeout seconds")
    p.add_argument("--scan-only", action="store_true", help="Only scan/export cookies, then exit")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    base = args.output
    base.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("   INSTAGRAM ARCHIVER (C: COOKIE SCAN → DOWNLOAD)")
    print(f"   Save to: {base}")
    print("   Cookie order: Firefox → Chrome → Edge → Brave → …")
    print("=" * 55)

    if args.scan_only:
        build_browser_try_list(args.drive, args.deep_scan, base / "_cookies")
        return 0

    def handle_one(url: str) -> bool:
        url = url.strip()
        if not url:
            return False
        shortcode = extract_shortcode(url)
        if not shortcode:
            print("Invalid URL. Need /p/, /reel/, or /tv/ in the link.")
            return False
        print(f"\nArchiving post {shortcode}...")
        target = base / f"Insta_{shortcode}"
        ok = download_instagram_media(
            url,
            target,
            drive=args.drive,
            deep=args.deep_scan,
            timeout=args.timeout,
        )
        print("=" * 55)
        return ok

    if args.url:
        return 0 if handle_one(args.url) else 1

    # Interactive loop (your original UX)
    failures = 0
    while True:
        try:
            url = input("\nEnter Instagram URL (or type 'exit' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting archiver...")
            break
        if url.lower() in {"exit", "quit", "q"}:
            print("Exiting archiver...")
            break
        if not url:
            continue
        try:
            if not handle_one(url):
                failures += 1
        except Exception as e:
            print(f"\nUnexpected error occurred: {e}")
            print("=" * 55)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
