#!/usr/bin/env python3
"""
COMPLETE Instagram Downloader (single file — Windows)

Logic:
  1) Scan C: for browser cookies
  2) Firefox FIRST, then Chrome, Edge, Brave, Opera, …
  3) Export Firefox Instagram cookies when found
  4) Download reel / post / carousel with yt-dlp

How to use (Windows):
  1. Open Firefox → https://www.instagram.com → log in → CLOSE Firefox
  2. Save this file as instagram_complete.py
  3. Run:  python instagram_complete.py
  4. Paste Instagram URL (/reel/ or /p/)

Optional:
  python instagram_complete.py "https://www.instagram.com/reel/XXXX/"
  python instagram_complete.py --scan-only
  python instagram_complete.py --deep-scan
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# =============================================================================
# Auto-install yt-dlp
# =============================================================================
try:
    import yt_dlp  # noqa: F401
except ImportError:
    print("=" * 55)
    print("Library 'yt-dlp' is missing. Installing automatically...")
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

# =============================================================================
# Browser cookie scanner (C: / Firefox first)
# =============================================================================
IG_COOKIE_NAMES = ("sessionid", "ds_user_id", "csrftoken")

BROWSER_PRIORITY = (
    "firefox",
    "chrome",
    "edge",
    "brave",
    "chromium",
    "opera",
    "opera_gx",
    "vivaldi",
)

DEFAULT_BROWSER_ORDER = [
    "firefox",
    "chrome",
    "edge",
    "brave",
    "opera",
    "chromium",
    "vivaldi",
]

WIN_PROFILE_HINTS: list[tuple[str, str, str]] = [
    ("firefox", r"AppData\Roaming\Mozilla\Firefox", "firefox_root"),
    ("chrome", r"AppData\Local\Google\Chrome\User Data", "chromium_root"),
    ("edge", r"AppData\Local\Microsoft\Edge\User Data", "chromium_root"),
    ("brave", r"AppData\Local\BraveSoftware\Brave-Browser\User Data", "chromium_root"),
    ("chromium", r"AppData\Local\Chromium\User Data", "chromium_root"),
    ("opera", r"AppData\Roaming\Opera Software\Opera Stable", "chromium_root"),
    ("opera_gx", r"AppData\Roaming\Opera Software\Opera GX Stable", "chromium_root"),
    ("vivaldi", r"AppData\Local\Vivaldi\User Data", "chromium_root"),
]

SHORTCODE_RE = re.compile(
    r"instagram\.com/(?:p|reel|reels|tv|stories/[^/]+)/([^/?#]+)",
    re.I,
)


@dataclass
class BrowserHit:
    browser: str
    profile_name: str
    profile_path: Path
    cookie_db: Path | None = None
    has_instagram_session: bool | None = None
    ig_cookie_names: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def yt_dlp_spec(self) -> str:
        if self.browser == "firefox" and self.profile_name:
            return f"firefox:{self.profile_name}"
        if self.browser == "chrome" and self.profile_name and self.profile_name != "Default":
            return f"chrome:{self.profile_name}"
        if self.browser in {"edge", "brave", "chromium", "vivaldi"} and self.profile_name not in {
            "Default",
            "",
        }:
            return f"{self.browser}:{self.profile_name}"
        if self.browser.startswith("opera"):
            return "opera"
        return self.browser

    @property
    def score(self) -> tuple:
        try:
            prio = BROWSER_PRIORITY.index(self.browser)
        except ValueError:
            prio = 99
        ig = 2 if self.has_instagram_session is True else (1 if self.has_instagram_session is None else 0)
        return (ig, -prio, 1 if self.cookie_db else 0)


def _windows_user_homes(drive: str = "C:") -> list[Path]:
    users = Path(f"{drive}\\Users")
    if not users.is_dir():
        home = Path.home()
        return [home] if home.is_dir() else []
    skip = {"public", "default", "default user", "all users", "desktop.ini"}
    homes = []
    for p in users.iterdir():
        try:
            if p.is_dir() and p.name.lower() not in skip:
                homes.append(p)
        except OSError:
            continue
    return homes


def _copy_sqlite(src: Path) -> Path | None:
    if not src.is_file():
        return None
    tmp = Path(tempfile.mkdtemp(prefix="ig_cookies_"))
    dest = tmp / src.name
    try:
        shutil.copy2(src, dest)
        for suffix in ("-wal", "-shm"):
            side = Path(str(src) + suffix)
            if side.is_file():
                shutil.copy2(side, tmp / side.name)
        return dest
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        return None


def firefox_has_instagram(cookie_db: Path) -> tuple[bool, list[str]]:
    copied = _copy_sqlite(cookie_db)
    db_path = copied or cookie_db
    found: list[str] = []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute(
            "SELECT name FROM moz_cookies WHERE host LIKE ? AND name IN ({})".format(
                ",".join("?" * len(IG_COOKIE_NAMES))
            ),
            ("%instagram.com%", *IG_COOKIE_NAMES),
        )
        found = sorted({row[0] for row in cur.fetchall()})
        con.close()
    except sqlite3.Error:
        return False, []
    finally:
        if copied:
            shutil.rmtree(copied.parent, ignore_errors=True)
    return ("sessionid" in found), found


def export_firefox_netscape(cookie_db: Path, out_file: Path, domain_filter: str = "instagram.com") -> int:
    copied = _copy_sqlite(cookie_db)
    db_path = copied or cookie_db
    rows = []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute(
            "SELECT host, name, value, path, expiry, isSecure FROM moz_cookies WHERE host LIKE ?",
            (f"%{domain_filter}%",),
        )
        rows = cur.fetchall()
        con.close()
    except sqlite3.Error as e:
        print(f"[cookies] Firefox DB read failed: {e}")
        return 0
    finally:
        if copied:
            shutil.rmtree(copied.parent, ignore_errors=True)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Netscape HTTP Cookie File", "# Exported for Instagram downloads", ""]
    count = 0
    for host, name, value, path, expiry, is_secure in rows:
        domain = host if host.startswith(".") else host
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if is_secure else "FALSE"
        exp = int(expiry) if expiry else 0
        value = str(value).replace("\t", " ").replace("\n", " ").replace("\r", "")
        lines.append(f"{domain}\t{flag}\t{path or '/'}\t{secure}\t{exp}\t{name}\t{value}")
        count += 1
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def _parse_firefox_profiles_ini(firefox_root: Path) -> list[tuple[str, Path]]:
    ini = firefox_root / "profiles.ini"
    profiles: list[tuple[str, Path]] = []
    if not ini.is_file():
        for cookies in firefox_root.glob("Profiles/*/cookies.sqlite"):
            profiles.append((cookies.parent.name, cookies.parent))
        return profiles

    current: dict[str, str] = {}
    sections: list[dict[str, str]] = []

    def flush() -> None:
        nonlocal current
        if current:
            sections.append(current)
            current = {}

    for raw in ini.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            flush()
            current = {"_section": line[1:-1]}
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            current[k.strip().lower()] = v.strip()
    flush()

    for sec in sections:
        if not sec.get("_section", "").lower().startswith("profile"):
            continue
        name = sec.get("name") or sec.get("path", "unknown")
        path_val = sec.get("path")
        if not path_val:
            continue
        is_rel = sec.get("isrelative", "1") == "1"
        prof = (firefox_root / path_val) if is_rel else Path(path_val)
        if (prof / "cookies.sqlite").is_file():
            profiles.append((Path(path_val).name if is_rel else name, prof))
    return profiles


def iter_firefox_hits(user_home: Path) -> Iterator[BrowserHit]:
    root = user_home / r"AppData\Roaming\Mozilla\Firefox"
    if not root.is_dir():
        for alt in (
            user_home / ".mozilla" / "firefox",
            user_home / "Library" / "Application Support" / "Firefox",
        ):
            if alt.is_dir():
                root = alt
                break
        else:
            return

    for name, prof in _parse_firefox_profiles_ini(root):
        db = prof / "cookies.sqlite"
        if not db.is_file():
            continue
        has_ig, names = firefox_has_instagram(db)
        yield BrowserHit(
            browser="firefox",
            profile_name=name,
            profile_path=prof,
            cookie_db=db,
            has_instagram_session=has_ig,
            ig_cookie_names=names,
            source=str(user_home),
        )


def _chromium_cookie_db(profile_dir: Path) -> Path | None:
    for rel in ("Network/Cookies", "Cookies"):
        p = profile_dir / rel
        if p.is_file():
            return p
    return None


def iter_chromium_hits(browser: str, user_data: Path, source: str) -> Iterator[BrowserHit]:
    if not user_data.is_dir():
        return
    candidates: list[Path] = []
    if browser.startswith("opera"):
        candidates = [user_data]
    else:
        for child in user_data.iterdir():
            try:
                if child.is_dir() and (
                    child.name == "Default"
                    or child.name.startswith("Profile")
                    or child.name == "System Profile"
                ):
                    candidates.append(child)
            except OSError:
                continue

    for prof in candidates:
        db = _chromium_cookie_db(prof)
        if not db:
            continue
        yield BrowserHit(
            browser="opera" if browser.startswith("opera") else browser,
            profile_name=prof.name,
            profile_path=prof,
            cookie_db=db,
            has_instagram_session=None,
            source=source,
        )


def deep_find_cookie_dbs(roots: list[Path], max_hits: int = 40) -> list[BrowserHit]:
    skip_dir_names = {
        "windows",
        "$recycle.bin",
        "system volume information",
        "winsxs",
        "node_modules",
        ".git",
    }
    hits: list[BrowserHit] = []
    for root in roots:
        if not root.exists():
            continue
        print(f"[scan] Deep-scanning {root} ...")
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                low = dirpath.lower()
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d.lower() not in skip_dir_names and not d.startswith(".")
                ]
                if "cookies.sqlite" in filenames:
                    prof = Path(dirpath)
                    db = prof / "cookies.sqlite"
                    has_ig, names = firefox_has_instagram(db)
                    hits.append(
                        BrowserHit(
                            browser="firefox",
                            profile_name=prof.name,
                            profile_path=prof,
                            cookie_db=db,
                            has_instagram_session=has_ig,
                            ig_cookie_names=names,
                            source=f"deep:{root}",
                        )
                    )
                    if len(hits) >= max_hits:
                        return hits
                if "Cookies" in filenames and (
                    Path(dirpath).name == "Network" or "User Data" in dirpath
                ):
                    if "firefox" in low:
                        continue
                    db = Path(dirpath) / "Cookies"
                    prof = Path(dirpath).parent if Path(dirpath).name == "Network" else Path(dirpath)
                    browser = "chrome"
                    if "edge" in low:
                        browser = "edge"
                    elif "brave" in low:
                        browser = "brave"
                    elif "vivaldi" in low:
                        browser = "vivaldi"
                    elif "chromium" in low:
                        browser = "chromium"
                    elif "opera" in low:
                        browser = "opera"
                    hits.append(
                        BrowserHit(
                            browser=browser,
                            profile_name=prof.name,
                            profile_path=prof,
                            cookie_db=db,
                            has_instagram_session=None,
                            source=f"deep:{root}",
                        )
                    )
                    if len(hits) >= max_hits:
                        return hits
        except OSError as e:
            print(f"[scan] walk error on {root}: {e}")
    return hits


def scan_browsers(drive: str = "C:", *, deep: bool = False) -> list[BrowserHit]:
    hits: list[BrowserHit] = []
    seen: set[str] = set()

    def add(hit: BrowserHit) -> None:
        key = f"{hit.browser}|{hit.profile_path}"
        if key in seen:
            return
        seen.add(key)
        hits.append(hit)

    homes = _windows_user_homes(drive) or [Path.home()]
    print(f"[scan] Checking {len(homes)} user profile(s) on {drive}\\ ...")
    print("[scan] Priority: Firefox → Chrome → Edge → Brave → others")

    for home in homes:
        for hit in iter_firefox_hits(home):
            add(hit)

        for browser, rel, kind in WIN_PROFILE_HINTS:
            if browser == "firefox":
                continue
            root = home / rel
            if not root.is_dir() and os.name != "nt":
                linux_map = {
                    "chrome": home / ".config" / "google-chrome",
                    "chromium": home / ".config" / "chromium",
                    "brave": home / ".config" / "BraveSoftware" / "Brave-Browser",
                    "edge": home / ".config" / "microsoft-edge",
                    "vivaldi": home / ".config" / "vivaldi",
                    "opera": home / ".config" / "opera",
                }
                root = linux_map.get(browser, root)
            if kind == "chromium_root" and root.is_dir():
                for hit in iter_chromium_hits(browser, root, str(home)):
                    add(hit)

    if deep:
        deep_roots = [
            Path(f"{drive}\\Users"),
            Path(f"{drive}\\Program Files"),
            Path(f"{drive}\\Program Files (x86)"),
        ]
        for extra in (f"{drive}\\PortableApps", f"{drive}\\Browsers", f"{drive}\\Tools"):
            p = Path(extra)
            if p.is_dir():
                deep_roots.append(p)
        for hit in deep_find_cookie_dbs(deep_roots):
            add(hit)

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def pick_best(hits: list[BrowserHit]) -> BrowserHit | None:
    if not hits:
        return None
    for h in hits:
        if h.browser == "firefox" and h.has_instagram_session:
            return h
    for h in hits:
        if h.browser == "firefox":
            return h
    return hits[0]


def print_report(hits: list[BrowserHit]) -> None:
    if not hits:
        print("[scan] No browser cookie stores found.")
        print("       Log into Instagram in Firefox, close it, then re-run.")
        return
    print()
    print(f"{'Browser':<10} {'Profile':<28} {'IG login':<10} Path")
    print("-" * 90)
    for h in hits:
        if h.has_instagram_session is True:
            ig = "YES"
        elif h.has_instagram_session is False:
            ig = "no"
        else:
            ig = "unknown"
        print(f"{h.browser:<10} {h.profile_name:<28} {ig:<10} {h.profile_path}")
    best = pick_best(hits)
    if best:
        print()
        print(f"[scan] Selected: {best.yt_dlp_spec}")
        if best.browser == "firefox" and best.has_instagram_session:
            print(f"[scan] Instagram cookies: {', '.join(best.ig_cookie_names)}")
        elif best.browser == "firefox" and best.has_instagram_session is False:
            print("[scan] WARNING: Firefox found but NO Instagram sessionid.")
            print("       Open Firefox → instagram.com → log in → close Firefox → retry.")


# =============================================================================
# Download
# =============================================================================
def extract_shortcode(url: str) -> str | None:
    m = SHORTCODE_RE.search(url)
    if m:
        return m.group(1)
    for key in ("/reel/", "/p/", "/tv/"):
        if key in url:
            return url.split(key)[1].split("/")[0].split("?")[0]
    return None


def build_browser_try_list(drive: str, deep: bool, export_dir: Path) -> tuple[Path | None, list[str]]:
    print("=" * 55)
    print("  SCANNING FOR BROWSER COOKIES")
    print(f"  Drive: {drive}  |  Order: Firefox → Chrome → others")
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

    exact_specs: list[str] = []
    browsers: list[str] = []
    seen: set[str] = set()

    for h in hits:
        if h.yt_dlp_spec not in exact_specs:
            exact_specs.append(h.yt_dlp_spec)
        name = "opera" if h.browser.startswith("opera") else h.browser
        if name not in seen:
            browsers.append(name)
            seen.add(name)

    ordered = [b for b in browsers if b == "firefox"] + [b for b in browsers if b != "firefox"]
    for name in DEFAULT_BROWSER_ORDER:
        if name not in seen:
            ordered.append(name)
            seen.add(name)

    final: list[str] = []
    seen_final: set[str] = set()
    for b in exact_specs + ordered:
        if b not in seen_final:
            final.append(b)
            seen_final.add(b)

    print(f"[auth] Try order: {' → '.join(final[:8])}{'…' if len(final) > 8 else ''}")
    return cookie_file, final


def run_ytdlp(cmd: list[str], timeout: int = 300) -> int:
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

    if cookie_file and cookie_file.is_file():
        print(f"\n---> Trying exported Firefox cookie file:\n     {cookie_file}")
        cmd = ytdlp_base_cmd(url, out_tmpl) + ["--cookies", str(cookie_file)]
        try:
            code = run_ytdlp(cmd, timeout=timeout)
            files = [p for p in dest_folder.rglob("*") if p.is_file()]
            if code == 0 or files:
                print(f"\n[SUCCESS] Authenticated via Firefox cookie file!")
                print(f"Files saved to: {dest_folder}")
                return True
            print("[FAILED] Cookie file did not work. Trying browsers...")
        except Exception as e:
            print(f"[ERROR] Cookie file attempt failed: {e}")

    for browser in browsers:
        print(f"\n---> Attempting auth with {browser.upper()} cookies...")
        cmd = ytdlp_base_cmd(url, out_tmpl) + ["--cookies-from-browser", browser]
        try:
            code = run_ytdlp(cmd, timeout=timeout)
            files = [p for p in dest_folder.rglob("*") if p.is_file()]
            if code == 0 or files:
                print(f"\n[SUCCESS] Download authenticated via {browser}!")
                print(f"Files saved to: {dest_folder}")
                return True
            print(f"[FAILED] {browser} didn't work. Next browser...")
        except Exception as e:
            print(f"[ERROR] {browser}: {e}")

    print("\n" + "=" * 55)
    print("CRITICAL FAILURE: No valid Instagram cookies found.")
    print("FIX:")
    print("  1) Open FIREFOX → https://www.instagram.com → log in")
    print("  2) CLOSE Firefox completely")
    print("  3) Re-run this script")
    print("=" * 55)
    return False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Complete Instagram downloader (C: cookie scan, Firefox first).")
    p.add_argument("url", nargs="?", help="Instagram URL (optional; interactive if omitted)")
    p.add_argument("--drive", default="C:", help="Drive to scan (default C:)")
    p.add_argument("--deep-scan", action="store_true", help="Deep-scan portable browsers")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path.home() / "Downloads" / "Instagram_Archives",
        help="Save folder",
    )
    p.add_argument("--timeout", type=int, default=300, help="Timeout per browser attempt (seconds)")
    p.add_argument("--scan-only", action="store_true", help="Only scan/export cookies")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    base = args.output
    base.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("   INSTAGRAM COMPLETE DOWNLOADER")
    print(f"   Save to: {base}")
    print("   Cookies: Firefox → Chrome → Edge → Brave → …")
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
            print("Invalid URL. Need /p/, /reel/, or /tv/.")
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

    failures = 0
    while True:
        try:
            url = input("\nEnter Instagram URL (or type 'exit' to quit): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        if url.lower() in {"exit", "quit", "q"}:
            print("Exiting...")
            break
        if not url:
            continue
        try:
            if not handle_one(url):
                failures += 1
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            print("=" * 55)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
