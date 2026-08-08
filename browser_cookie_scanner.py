#!/usr/bin/env python3
"""
Scan local disks (Windows C: first) for browser cookie stores.

Priority (by design):
  1. Firefox
  2. Chrome
  3. Edge / Brave / Chromium / Opera / Vivaldi / Opera GX

Finds Instagram login cookies (sessionid) when readable, and returns a
browser target that yt-dlp / gallery-dl can consume via --cookies-from-browser.

Also can export Firefox cookies to a Netscape cookies.txt (works even when
Firefox is closed; if open, copies cookies.sqlite first to avoid lock errors).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

# Instagram auth cookie name required by gallery-dl / IG web API
IG_COOKIE_NAMES = ("sessionid", "ds_user_id", "csrftoken")

# Scan order — Firefox MUST be first
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

# Relative paths under each Windows user profile (AppData)
# (browser_key, relative_path_from_user_home, kind)
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

# Extra install / portable roots to poke on C:
EXTRA_SCAN_ROOTS = [
    Path(r"C:\Program Files\Mozilla Firefox"),
    Path(r"C:\Program Files (x86)\Mozilla Firefox"),
    Path(r"C:\Program Files\Google\Chrome"),
    Path(r"C:\Program Files (x86)\Google\Chrome"),
    Path(r"C:\Program Files\Mozilla Thunderbird"),  # skip cookies, just presence
]


@dataclass
class BrowserHit:
    browser: str  # firefox / chrome / ...
    profile_name: str
    profile_path: Path
    cookie_db: Path | None = None
    has_instagram_session: bool | None = None  # None = could not check (encrypted)
    ig_cookie_names: list[str] = field(default_factory=list)
    source: str = ""

    @property
    def yt_dlp_spec(self) -> str:
        """Value for --cookies-from-browser (browser:profile)."""
        # yt-dlp / gallery-dl accept "firefox:xxxxxx.default-release"
        if self.profile_name and self.profile_name.lower() not in {"default", "default-release"}:
            return f"{self.browser}:{self.profile_name}"
        if self.browser == "firefox" and self.profile_name:
            return f"{self.browser}:{self.profile_name}"
        if self.browser == "chrome" and self.profile_name and self.profile_name != "Default":
            return f"{self.browser}:{self.profile_name}"
        if self.browser in {"edge", "brave", "chromium", "vivaldi"} and self.profile_name not in {
            "Default",
            "",
        }:
            return f"{self.browser}:{self.profile_name}"
        # opera profile folders are the root itself
        if self.browser.startswith("opera"):
            return "opera" if self.browser == "opera" else "opera"
        return self.browser

    @property
    def score(self) -> tuple:
        """Higher is better: IG session > priority index > has cookie db."""
        try:
            prio = BROWSER_PRIORITY.index(self.browser)
        except ValueError:
            prio = 99
        ig = 2 if self.has_instagram_session is True else (1 if self.has_instagram_session is None else 0)
        return (ig, -prio, 1 if self.cookie_db else 0)


def _windows_user_homes(drive: str = "C:") -> list[Path]:
    users = Path(f"{drive}\\Users")
    if not users.is_dir():
        # Non-Windows / cloud fallback: current user only
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
    """Copy cookie DB (+ -wal/-shm) to temp so we can read while browser is open."""
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
    """Query Firefox cookies.sqlite for Instagram session cookies."""
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
    """
    Export Firefox cookies to Netscape cookies.txt for yt-dlp/gallery-dl.
    Returns number of cookie lines written.
    """
    copied = _copy_sqlite(cookie_db)
    db_path = copied or cookie_db
    rows = []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute(
            """
            SELECT host, name, value, path, expiry, isSecure
            FROM moz_cookies
            WHERE host LIKE ?
            """,
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
    lines = ["# Netscape HTTP Cookie File", "# Exported from Firefox for Instagram downloads", ""]
    count = 0
    for host, name, value, path, expiry, is_secure in rows:
        # Netscape: domain, flag, path, secure, expiry, name, value
        domain = host if host.startswith(".") else host
        flag = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if is_secure else "FALSE"
        exp = int(expiry) if expiry else 0
        # Escape tabs/newlines in value
        value = str(value).replace("\t", " ").replace("\n", " ").replace("\r", "")
        lines.append(f"{domain}\t{flag}\t{path or '/'}\t{secure}\t{exp}\t{name}\t{value}")
        count += 1
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count


def _parse_firefox_profiles_ini(firefox_root: Path) -> list[tuple[str, Path]]:
    ini = firefox_root / "profiles.ini"
    profiles: list[tuple[str, Path]] = []
    if not ini.is_file():
        # Fallback: any folder with cookies.sqlite
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
        # Linux / macOS fallbacks
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
    # Opera stores profile at the root itself
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
        # Chromium cookies are encrypted on Windows — cannot verify IG session here
        yield BrowserHit(
            browser="opera" if browser.startswith("opera") else browser,
            profile_name=prof.name,
            profile_path=prof,
            cookie_db=db,
            has_instagram_session=None,
            ig_cookie_names=[],
            source=source,
        )


def deep_find_cookie_dbs(roots: list[Path], max_hits: int = 40) -> list[BrowserHit]:
    """
    Limited deep scan: walk given roots for cookies.sqlite / Cookies DBs.
    Skips huge system trees. Used when standard AppData paths miss portable browsers.
    """
    skip_dir_names = {
        "windows",
        "$recycle.bin",
        "system volume information",
        "winsxs",
        "node_modules",
        ".git",
        "appdata\\local\\temp",
    }
    hits: list[BrowserHit] = []
    for root in roots:
        if not root.exists():
            continue
        print(f"[scan] Deep-scanning {root} for cookie databases...")
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Prune noisy dirs
                low = dirpath.lower()
                dirnames[:] = [
                    d
                    for d in dirnames
                    if d.lower() not in skip_dir_names
                    and not d.startswith(".")
                    and "windows\\winsxs" not in low
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
                # Chromium Network/Cookies
                if "Cookies" in filenames and (Path(dirpath).name == "Network" or "User Data" in dirpath):
                    db = Path(dirpath) / "Cookies"
                    prof = Path(dirpath).parent if Path(dirpath).name == "Network" else Path(dirpath)
                    browser = "chrome"
                    lowpath = dirpath.lower()
                    if "firefox" in lowpath:
                        continue
                    if "edge" in lowpath:
                        browser = "edge"
                    elif "brave" in lowpath:
                        browser = "brave"
                    elif "vivaldi" in lowpath:
                        browser = "vivaldi"
                    elif "chromium" in lowpath:
                        browser = "chromium"
                    elif "opera" in lowpath:
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


def scan_browsers(
    drive: str = "C:",
    *,
    deep: bool = False,
) -> list[BrowserHit]:
    """
    Discover browser cookie stores.
    Order preference is applied later via BrowserHit.score (Firefox first).
    """
    hits: list[BrowserHit] = []
    seen: set[str] = set()

    def add(hit: BrowserHit) -> None:
        key = f"{hit.browser}|{hit.profile_path}"
        if key in seen:
            return
        seen.add(key)
        hits.append(hit)

    homes = _windows_user_homes(drive)
    if not homes:
        homes = [Path.home()]

    print(f"[scan] Checking {len(homes)} user profile(s) on {drive}\\ for browsers...")
    print("[scan] Priority: Firefox → Chrome → Edge → Brave → others")

    for home in homes:
        # 1) Firefox first (explicit pass)
        for hit in iter_firefox_hits(home):
            add(hit)

        # 2) Chromium family via known AppData paths
        for browser, rel, kind in WIN_PROFILE_HINTS:
            if browser == "firefox":
                continue
            root = home / rel
            # Linux/mac fallbacks for chrome-ish
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
        # Portable apps often live here
        for extra in (f"{drive}\\PortableApps", f"{drive}\\Browsers", f"{drive}\\Tools"):
            p = Path(extra)
            if p.is_dir():
                deep_roots.append(p)
        for hit in deep_find_cookie_dbs(deep_roots):
            add(hit)

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits


def pick_best(hits: list[BrowserHit]) -> BrowserHit | None:
    """Prefer Firefox with Instagram sessionid, else first Firefox, else best Chromium."""
    if not hits:
        return None
    # Explicit Firefox-with-session first
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
        print("       Log into Instagram in Firefox (preferred) or Chrome, then re-run.")
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
            print(f"[scan] Instagram cookies found: {', '.join(best.ig_cookie_names)}")
        elif best.browser == "firefox" and best.has_instagram_session is False:
            print("[scan] WARNING: Firefox found but no Instagram sessionid.")
            print("       Open Firefox → instagram.com → log in → close Firefox → retry.")


def resolve_auth(
    *,
    drive: str = "C:",
    deep: bool = False,
    export_dir: Path | None = None,
    force_browser: str | None = None,
) -> tuple[str | None, Path | None, BrowserHit | None]:
    """
    Returns (cookies_from_browser, cookie_file, hit).

    Strategy:
      1. Scan browsers (Firefox first).
      2. If Firefox has IG cookies → export Netscape cookies.txt (most reliable).
      3. Else use --cookies-from-browser for the best hit.
    """
    hits = scan_browsers(drive=drive, deep=deep)
    print_report(hits)

    if force_browser:
        forced = [h for h in hits if h.browser == force_browser.lower()]
        best = pick_best(forced) if forced else None
        if not best:
            print(f"[scan] Forced browser '{force_browser}' not found on disk.")
            return force_browser.lower(), None, None
    else:
        best = pick_best(hits)

    if not best:
        return None, None, None

    # Firefox: export cookies.txt so downloads work even if browser name/profile is awkward
    if best.browser == "firefox" and best.cookie_db and best.has_instagram_session:
        out_dir = export_dir or (Path.home() / "Downloads" / "Instagram_Archives" / "_cookies")
        out_file = out_dir / f"firefox_{best.profile_name}_instagram_cookies.txt"
        n = export_firefox_netscape(best.cookie_db, out_file)
        if n > 0:
            print(f"[scan] Exported {n} Instagram cookies → {out_file}")
            return best.yt_dlp_spec, out_file, best
        print("[scan] Export failed; falling back to cookies-from-browser.")

    return best.yt_dlp_spec, None, best


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scan C: for browser cookies (Firefox first).")
    p.add_argument("--drive", default="C:", help="Windows drive to scan (default: C:)")
    p.add_argument(
        "--deep",
        action="store_true",
        help="Also deep-walk Users/Program Files for portable browser cookie DBs",
    )
    p.add_argument(
        "--export",
        type=Path,
        default=None,
        help="Export Firefox Instagram cookies to this Netscape cookies.txt path",
    )
    args = p.parse_args(argv)

    browser, cookie_file, hit = resolve_auth(drive=args.drive, deep=args.deep)
    if args.export and hit and hit.browser == "firefox" and hit.cookie_db:
        n = export_firefox_netscape(hit.cookie_db, args.export)
        print(f"[scan] Wrote {n} cookies to {args.export}")
    if not browser and not cookie_file:
        return 1
    print(f"[scan] Use: --cookies-from-browser {browser}" + (f"  OR  --cookie-file {cookie_file}" if cookie_file else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
