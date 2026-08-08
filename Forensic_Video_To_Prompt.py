r"""
====
  FORENSIC VIDEO-TO-PROMPT ENGINE  |  Gemini Flash (auto model fallback)
  - ALL libraries ONLY in:  C:\AKT Media Tools
  - Videos + output in:     folder of this .py  \  Video to Prompt
  - Done folder:            Video to Prompt Done  (files renamed: Video 1 xxx.mp4)
  - Force-install packages into C:\AKT Media Tools\Lib\site-packages
  - Auto UAC elevation when needed
  - 1-FPS extraction | Master + Forensic | Timestamped | Continuous numbering
  - Naming (Ultimate Media Tool style): Video 1 originalname.mp4
  - ONE-CLICK: Gemini API keys from USER_CONFIG only (top block) — 12-key rotation
  - Model auto-fallback: gemini-3.6-flash → 3.5 → 3.1-lite → 2.5 → 2.0
  - If USER_THEMATIC_OVERRIDES are blank → pure original video (zero manipulation)
  - PIN-POINT MOVEMENT: second-by-second direction, face, object position tracking
  - 10-minute active / 10-minute pause loop (API friendly)
  - Video order: Media/EXIF Date created FIRST (earliest first) → file created → mtime → name
  - Key-switch delay: 600 seconds between API keys (same-IP multi-account protection)
  - URL Picker: "Video to Prompt URL Picker.txt" in script folder
      * auto-created if missing
      * if any URL present → download + process first
      * after job completes → URL erased from picker (remaining = unfinished balance)
      * completed URLs archived in "Video to Prompt URL Picker Done.txt"
      * job record (files + key RPM/RPD balance) → "Video to Prompt Job Log.txt"
      * permanent download failures → "Video to Prompt URL Picker Failed.txt"
      * if picker empty → Enter URL prompt (8s auto-skip) then local videos
  - Download: direct video via urllib | Instagram via yt-dlp + browser cookies (Firefox→Chrome→…; MEDIA ONLY) then gallery-dl | other social via yt-dlp (+ gallery-dl)
====
"""

# ====
# INSTRUCTIONS
# ====
# 1. Put Gemini API keys in USER_CONFIG (one per numbered slot).
# 2. Leave thematic overrides blank for pure original video reconstruction.
# 3. Put video/social URLs in "Video to Prompt URL Picker.txt" OR paste at 8s prompt.
# 4. SECURITY: never commit real API keys. Rotate any key that was shared/pasted.
# ====

# ============================================================================
# USER CONFIG + API KEYS  (edit only this block)
#   Gemini free tier limits:  RPM = 10  |  RPD = 250  |  TPM = 250,000
#   Rotator switches keys at:  RPM @ 9   |  RPD @ 249
# ============================================================================
USER_CONFIG = """

1. Enter Gemini API Key (userID: your_email_1@example.com):		YOUR_GEMINI_API_KEY_1

2. Enter Gemini API Key (userID: your_email_2@example.com):		YOUR_GEMINI_API_KEY_2

3. Enter Gemini API Key (userID: your_email_3@example.com):		YOUR_GEMINI_API_KEY_3

4. Enter Gemini API Key (userID: your_email_4@example.com):		YOUR_GEMINI_API_KEY_4

5. Enter Gemini API Key (userID: your_email_5@example.com):		YOUR_GEMINI_API_KEY_5

6. Enter Gemini API Key (userID: your_email_6@example.com):		YOUR_GEMINI_API_KEY_6

7. Enter Gemini API Key (userID: your_email_7@example.com):		YOUR_GEMINI_API_KEY_7

8. Enter Gemini API Key (userID: your_email_8@example.com):		YOUR_GEMINI_API_KEY_8

9. Enter Gemini API Key (userID: your_email_9@example.com):		YOUR_GEMINI_API_KEY_9

10. Enter Gemini API Key (userID: your_email_10@example.com):		YOUR_GEMINI_API_KEY_10

11. Enter Gemini API Key (userID: your_email_11@example.com):		YOUR_GEMINI_API_KEY_11

12. Enter Gemini API Key (userID: your_email_12@example.com):		YOUR_GEMINI_API_KEY_12

"""
# ============================================================================
# END USER CONFIG
# ============================================================================

# ====
# USER THEMATIC OVERRIDES
# ====
USER_THEMATIC_OVERRIDES = """

Art Style
What I Require: 
What I Don't Require:

Body Rendering
What I Require: 
What I Don't Require:

Texture
What I Require: 
What I Don't Require:

Face
What I Require: 
What I Don't Require: 

Cloths
What I Require: 
What I Don't Require: 

Weapons
What I Require: 
What I Don't Require:

Aspect Ratio
What I Require: 
What I Don't Require:

Movement
What I Require: 
What I Don't Require:

Any Other Information
What I Require: 
What I Don't Require:

"""
# ====
# END OF USER OVERRIDES
# ====

import sys
import os
import ctypes
import subprocess
import traceback
import importlib
import time
import json
import shutil
import hashlib
import re
import textwrap
import urllib.request
import ssl
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Tuple, Dict

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


def _mask_user_id(user_id: str) -> str:
    """Never print full emails / account ids in console logs."""
    uid = (user_id or "").strip()
    if not uid:
        return "unknown"
    if "@" in uid:
        local, _, domain = uid.partition("@")
        if len(local) <= 2:
            return f"**@{domain}"
        return f"{local[:2]}***@{domain}"
    if len(uid) <= 4:
        return "***"
    return f"{uid[:2]}***{uid[-2:]}"


# ====
# GEMINI MULTI-KEY ROTATOR
# ====
class GeminiApiKeyRotator:
    ROTATE_AT_RPM = 9
    ROTATE_AT_RPD = 249
    RPM_LIMIT = 10
    RPD_LIMIT = 250
    RPM_WINDOW = 60
    RPD_WINDOW = 86400
    KEY_SWITCH_DELAY_SECONDS = 600

    def __init__(self, keys: List[Tuple[str, str, int]]):
        now = time.time()
        self.keys = []
        for (key, user_id, slot) in keys:
            self.keys.append({
                "key": key,
                "user_id": user_id,
                "slot": slot,
                "rpm_count": 0,
                "rpm_window_start": now,
                "rpd_count": 0,
                "rpd_window_start": now,
                "disabled": False,
                "cooldown_until": 0.0,
            })
        self.current_idx = 0
        self._last_switched_from = None

    def _refresh_windows(self, k: dict) -> None:
        now = time.time()
        if now - k["rpm_window_start"] >= self.RPM_WINDOW:
            k["rpm_count"] = 0
            k["rpm_window_start"] = now
        if now - k["rpd_window_start"] >= self.RPD_WINDOW:
            k["rpd_count"] = 0
            k["rpd_window_start"] = now

    def _is_usable(self, k: dict) -> bool:
        now = time.time()
        if k["disabled"]:
            return False
        if k["cooldown_until"] > now:
            return False
        self._refresh_windows(k)
        if k["rpm_count"] >= self.ROTATE_AT_RPM:
            return False
        if k["rpd_count"] >= self.ROTATE_AT_RPD:
            return False
        return True

    def _apply_key_switch_delay(self, old_slot: int, new_slot: int, reason: str = "") -> None:
        delay = max(0, int(self.KEY_SWITCH_DELAY_SECONDS))
        if delay <= 0:
            return
        reason_s = f" ({reason})" if reason else ""
        print(
            f"  {C.YELLOW}[KEY ROTATOR] Waiting {delay}s before next key "
            f"#{old_slot} → #{new_slot}{reason_s}...{C.RESET}"
        )
        time.sleep(delay)

    def get_current_key(self) -> Tuple[Optional[str], Optional[str], int]:
        n = len(self.keys)
        prev_idx = self.current_idx
        for offset in range(n):
            idx = (self.current_idx + offset) % n
            if self._is_usable(self.keys[idx]):
                if idx != prev_idx and self._last_switched_from is not None:
                    old_k = self.keys[prev_idx]
                    new_k = self.keys[idx]
                    self._apply_key_switch_delay(
                        old_k["slot"], new_k["slot"], "skip to usable key"
                    )
                self.current_idx = idx
                self._last_switched_from = prev_idx
                k = self.keys[idx]
                return (k["key"], k["user_id"], idx)
        return (None, None, -1)

    def record_request(self, idx: int) -> None:
        k = self.keys[idx]
        self._refresh_windows(k)
        k["rpm_count"] += 1
        k["rpd_count"] += 1
        print(f"  {C.CYAN}[KEY ROTATOR] Key #{k['slot']} ({_mask_user_id(k['user_id'])}) "
              f"→ RPM: {k['rpm_count']}/{self.RPM_LIMIT}, "
              f"RPD: {k['rpd_count']}/{self.RPD_LIMIT}{C.RESET}")
        if k["rpm_count"] >= self.ROTATE_AT_RPM or k["rpd_count"] >= self.ROTATE_AT_RPD:
            reason = "RPM" if k["rpm_count"] >= self.ROTATE_AT_RPM else "RPD"
            print(f"  {C.YELLOW}[KEY ROTATOR] Key #{k['slot']} ({_mask_user_id(k['user_id'])}) "
                  f"reached {reason} threshold → pre-rotating{C.RESET}")
            self._rotate(reason=f"{reason} threshold")

    def handle_rate_limit(self, idx: int, retry_after: Optional[float] = None) -> None:
        k = self.keys[idx]
        wait = retry_after if retry_after else 60
        k["cooldown_until"] = time.time() + wait
        print(f"  {C.RED}[KEY ROTATOR] 429 on Key #{k['slot']} "
              f"({_mask_user_id(k['user_id'])}) → cooling down {int(wait)}s{C.RESET}")
        self._rotate(reason="429 rate limit")

    def handle_auth_error(self, idx: int) -> None:
        k = self.keys[idx]
        k["disabled"] = True
        print(f"  {C.RED}[KEY ROTATOR] 401/403 on Key #{k['slot']} "
              f"({_mask_user_id(k['user_id'])}) → DISABLED for this session{C.RESET}")
        self._rotate(reason="auth error")

    def _rotate(self, reason: str = "") -> None:
        n = len(self.keys)
        old_idx = self.current_idx
        old_slot = self.keys[old_idx]["slot"]
        self.current_idx = (self.current_idx + 1) % n
        k = self.keys[self.current_idx]
        print(f"  {C.GREEN}[KEY ROTATOR] Now using Key #{k['slot']} "
              f"({_mask_user_id(k['user_id'])}){C.RESET}")
        self._apply_key_switch_delay(old_slot, k["slot"], reason or "rotate")
        self._last_switched_from = old_idx

    def all_exhausted(self) -> bool:
        """True when no key is currently usable (disabled / cooldown / RPM / RPD)."""
        for k in self.keys:
            if self._is_usable(k):
                return False
        return True

    def get_status_summary(self) -> str:
        now = time.time()
        lines = [f"  {C.BOLD}[KEY ROTATOR] Status Summary "
                 f"({len(self.keys)} key(s)):{C.RESET}"]
        for k in self.keys:
            self._refresh_windows(k)
            if k["disabled"]:
                status = f"{C.RED}DISABLED{C.RESET}"
            elif k["cooldown_until"] > now:
                status = f"{C.YELLOW}COOLDOWN {int(k['cooldown_until'] - now)}s{C.RESET}"
            elif k["rpm_count"] >= self.ROTATE_AT_RPM or k["rpd_count"] >= self.ROTATE_AT_RPD:
                status = f"{C.YELLOW}threshold{C.RESET}"
            else:
                status = f"{C.GREEN}active{C.RESET}"
            lines.append(
                f"    {C.DIM}Key #{k['slot']} ({_mask_user_id(k['user_id'])}) → "
                f"RPM: {k['rpm_count']}/{self.RPM_LIMIT}, "
                f"RPD: {k['rpd_count']}/{self.RPD_LIMIT}{C.RESET} | {status}"
            )
        return "\n".join(lines)


LIB_ROOT = r"C:\AKT Media Tools"
SITE_PACKAGES = os.path.join(LIB_ROOT, "Lib", "site-packages")
TOOLS_DIR = Path(LIB_ROOT) / "Tools"
YTDLP_PATH = TOOLS_DIR / "yt-dlp.exe"
# Pinned yt-dlp release (avoid floating "latest" without integrity checks when possible)
YTDLP_RELEASE_TAG = "2025.10.14"
YTDLP_DOWNLOAD_URL = (
    f"https://github.com/yt-dlp/yt-dlp/releases/download/"
    f"{YTDLP_RELEASE_TAG}/yt-dlp.exe"
)


def _script_folder() -> str:
    try:
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        return os.getcwd()


MEDIA_ROOT = _script_folder()


def _is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _pause_exit(code: int = 1):
    try:
        input("\n  Press Enter to exit...")
    except Exception:
        pass
    sys.exit(code)


def _relaunch_as_admin():
    if os.name != "nt":
        return
    script = os.path.abspath(sys.argv[0])
    if not os.path.isfile(script):
        print("  ERROR: cannot find script path for elevation.")
        _pause_exit(1)
    params = subprocess.list2cmdline([script] + sys.argv[1:])
    print("=" * 60)
    print("  Administrator needed for library folder:")
    print(f"    {LIB_ROOT}")
    print("  Click YES on UAC")
    print("=" * 60)
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, os.path.dirname(script), 1
        )
        if rc <= 32:
            print(f"\n  UAC failed/cancelled (code {rc}).")
            print("  Right-click script / CMD -> Run as administrator")
            _pause_exit(1)
    except Exception as e:
        print(f"  Elevation error: {e}")
        _pause_exit(1)
    sys.exit(0)


def _grant_full_control(folder: str) -> None:
    """Grant current user write access only (not all Users)."""
    if os.name != "nt" or not os.path.isdir(folder):
        return
    user = os.environ.get("USERNAME", "")
    if not user:
        return
    try:
        subprocess.run(
            ["icacls", folder, "/grant", f"{user}:(OI)(CI)F", "/T", "/C"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except Exception:
        pass


def _can_write(folder: str) -> bool:
    try:
        os.makedirs(folder, exist_ok=True)
        test = os.path.join(folder, ".write_test")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test)
        return True
    except Exception:
        return False


def _ensure_lib_folder():
    need = [os.path.join(LIB_ROOT, "Lib", "site-packages"), str(TOOLS_DIR)]
    try:
        for d in need:
            os.makedirs(d, exist_ok=True)
        if _can_write(LIB_ROOT):
            if _is_admin():
                _grant_full_control(LIB_ROOT)
            return
    except Exception:
        pass
    if os.name == "nt" and not _is_admin():
        _relaunch_as_admin()
        return
    try:
        for d in need:
            os.makedirs(d, exist_ok=True)
        _grant_full_control(LIB_ROOT)
        if not _can_write(LIB_ROOT):
            raise PermissionError(f"Cannot write: {LIB_ROOT}")
    except Exception as e:
        print("!" * 60)
        print(f"  Cannot prepare library folder: {LIB_ROOT}")
        print(f"  Error: {e}")
        print("!" * 60)
        _pause_exit(1)


def _ensure_media_folder():
    try:
        os.makedirs(MEDIA_ROOT, exist_ok=True)
        test = os.path.join(MEDIA_ROOT, ".write_test_media")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test)
    except Exception as e:
        print("!" * 60)
        print(f"  Cannot write media folder: {MEDIA_ROOT}")
        print(f"  Error: {e}")
        print("!" * 60)
        _pause_exit(1)


def _package_present_in_target(imp_name: str, pip_name: str) -> bool:
    checks = []
    if imp_name == "PIL":
        checks += [
            os.path.join(SITE_PACKAGES, "PIL"),
            os.path.join(SITE_PACKAGES, "Pillow"),
        ]
    elif imp_name == "cv2":
        checks += [
            os.path.join(SITE_PACKAGES, "cv2"),
            os.path.join(SITE_PACKAGES, "opencv_python"),
            os.path.join(SITE_PACKAGES, "opencv-python"),
        ]
    elif imp_name == "google.genai":
        checks += [
            os.path.join(SITE_PACKAGES, "google", "genai"),
            os.path.join(SITE_PACKAGES, "google_genai"),
            os.path.join(SITE_PACKAGES, "google-genai"),
        ]
    elif imp_name == "gallery_dl":
        checks += [
            os.path.join(SITE_PACKAGES, "gallery_dl"),
        ]
    else:
        checks += [
            os.path.join(SITE_PACKAGES, imp_name),
            os.path.join(SITE_PACKAGES, pip_name),
            os.path.join(SITE_PACKAGES, pip_name.replace("-", "_")),
        ]
    for c in checks:
        if os.path.isdir(c) or os.path.isfile(c):
            return True
    try:
        for name in os.listdir(SITE_PACKAGES):
            low = name.lower()
            if low.startswith(pip_name.lower().replace("-", "_")) and low.endswith((".dist-info", ".egg-info")):
                return True
            if low.startswith(pip_name.lower()) and low.endswith(".dist-info"):
                return True
            if imp_name == "PIL" and low.startswith("pillow") and low.endswith(".dist-info"):
                return True
            if imp_name == "cv2" and "opencv" in low and low.endswith(".dist-info"):
                return True
            if ("google_genai" in low or "google-genai" in low) and low.endswith(".dist-info"):
                return True
            if "gallery_dl" in low and low.endswith(".dist-info"):
                return True
    except Exception:
        pass
    return False


_ensure_lib_folder()
_ensure_media_folder()

if SITE_PACKAGES in sys.path:
    sys.path.remove(SITE_PACKAGES)
sys.path.insert(0, SITE_PACKAGES)

try:
    import site
    for p in (site.getsitepackages() or []):
        if p and p not in sys.path:
            sys.path.append(p)
    try:
        usp = site.getusersitepackages()
        if usp and usp not in sys.path:
            sys.path.append(usp)
    except Exception:
        pass
except Exception:
    pass

REQUIRED_PACKAGES = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "google.genai": "google-genai",
    "gallery_dl": "gallery-dl",
}

print("=" * 60)
print(f"  LIBRARIES FOLDER : {LIB_ROOT}")
print(f"  site-packages    : {SITE_PACKAGES}")
print(f"  MEDIA FOLDER     : {MEDIA_ROOT}")
print(f"  Admin            : {_is_admin()}")
print("=" * 60)
print("  Installing / verifying packages in C:\\AKT Media Tools only")
print("=" * 60)

for imp_name, pip_name in REQUIRED_PACKAGES.items():
    if _package_present_in_target(imp_name, pip_name):
        print(f"  [OK] {pip_name}")
        continue
    print(f"  [..] Installing {pip_name} -> {SITE_PACKAGES}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "--target", SITE_PACKAGES, pip_name]
        )
        importlib.invalidate_caches()
        if _package_present_in_target(imp_name, pip_name):
            print(f"  [INSTALLED] {pip_name}")
        else:
            print(f"  [WARN] pip finished but files not found for {pip_name}")
    except Exception as e:
        print(f"  [WARN] Failed {pip_name}: {e}")

print("=" * 60)
print(f"  Path: {SITE_PACKAGES}")
print("=" * 60 + "\n")

importlib.invalidate_caches()
if SITE_PACKAGES in sys.path:
    sys.path.remove(SITE_PACKAGES)
sys.path.insert(0, SITE_PACKAGES)

try:
    from PIL import Image
except Exception as e:
    print(f"  FATAL: Pillow import failed: {e}")
    _pause_exit(1)

try:
    import cv2
except Exception as e:
    print(f"  FATAL: opencv-python import failed: {e}")
    _pause_exit(1)

try:
    from google import genai
except Exception as e:
    print(f"  FATAL: google-genai import failed: {e}")
    print(f'  Try: py -m pip install --upgrade --target "{SITE_PACKAGES}" google-genai Pillow opencv-python')
    _pause_exit(1)

SCRIPT_DIR            = Path(MEDIA_ROOT)
VIDEO_FOLDER          = SCRIPT_DIR / "Video to Prompt"
DONE_FOLDER           = VIDEO_FOLDER / "Video to Prompt Done"
OUTPUT_COMBINED_FILE  = VIDEO_FOLDER / "combined_video_output.txt"
KEY_USAGE_LOG         = VIDEO_FOLDER / "Gemini_Key_Usage_Log.txt"
URL_PICKER_FILE       = SCRIPT_DIR / "Video to Prompt URL Picker.txt"
URL_PICKER_FAILED     = SCRIPT_DIR / "Video to Prompt URL Picker Failed.txt"
URL_PICKER_DONE       = SCRIPT_DIR / "Video to Prompt URL Picker Done.txt"
JOB_LOG_FILE          = SCRIPT_DIR / "Video to Prompt Job Log.txt"

VALID_EXTENSIONS = {
    ".mp4", ".m4v", ".mp4v", ".f4v",
    ".avi", ".av",
    ".mov", ".qt",
    ".mkv", ".mk3d",
    ".webm",
    ".wmv", ".asf",
    ".flv",
    ".mpeg", ".mpg", ".mpe", ".mpv", ".m2v", ".m2ts", ".mts", ".ts", ".vob",
    ".3gp", ".3g2",
    ".ogv", ".ogg",
    ".rm", ".rmvb",
    ".divx", ".xvid",
    ".mxf", ".dv", ".hevc", ".h264", ".h265",
    ".dat", ".mod", ".tod", ".m2t",
}

# Ultimate Media Tool-style rename: "Video 1 originalname.mp4"
_RE_DONE_NAME = re.compile(r"(?i)^Video(?:\s+No\.)?\s+(\d+)\s+")


def _is_already_named_output(filename: str) -> bool:
    """Skip files already renamed as Video N ... (or legacy Video No. N ...)."""
    return bool(_RE_DONE_NAME.match(filename or ""))


def _safe_filename(name: str) -> str:
    """Sanitize like Ultimate Media Tool (Windows-illegal chars → _)."""
    return re.sub(r'[<>:"/\\|?*]', "_", name or "video")

REQUEST_DELAY_SEC     = 6
MAX_RETRIES           = 4
RETRY_BASE_DELAY      = 8
MAX_FRAME_PX          = 768
MAX_FRAMES_SAFETY     = 60
MAX_RUN_TIME_MIN      = 10
PAUSE_TIME_MIN        = 10

# Gemini model preference (2.5-flash is blocked for many new API keys → 404).
# First working model is cached for the rest of the run.
GEMINI_MODEL_CANDIDATES = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]
_RESOLVED_GEMINI_MODEL: Optional[str] = None

# Patterns that mean "this social URL will never work with our downloaders as-is"
_PERMANENT_DL_HINTS = (
    "no video formats found",
    "unsupported url",
    "unable to download webpage",
    "private video",
    "login required",
    "requested content is not available",
    "404",
)


def parse_user_config() -> List[Tuple[str, str, int]]:
    text = USER_CONFIG or ""
    keys: List[Tuple[str, str, int]] = []
    seen = set()
    pat_numbered = re.compile(
        r"(?m)^\s*(\d+)\s*[\.\)]\s*"
        r"(?:Enter\s+)?Gemini\s+API\s+Key"
        r"(?:\s*\(\s*userID\s*:\s*([^)]+?)\s*\))?"
        r"\s*:\s*"
        r"(\S+)",
        re.IGNORECASE,
    )
    for m in pat_numbered.finditer(text):
        slot = int(m.group(1))
        uid = (m.group(2) or "").strip()
        key = m.group(3).strip()
        if not key:
            continue
        placeholder_markers = (
            "YOUR_GEMINI_API_KEY", "AIZA_XYZ", "AIZA_YOUR_KEY_HERE", "AIZA_XXX",
            "PASTE", "XYZ", "YOUR_KEY", "REPLACE_ME",
        )
        up = key.upper()
        if any(p in up for p in placeholder_markers):
            continue
        if key.lower() in ("aiza_xyz", "aiza_your_key_here", "aiza_xxx"):
            continue
        if len(key) < 20:
            continue
        if key in seen:
            continue
        seen.add(key)
        keys.append((key, uid, slot))
    if not keys:
        raise RuntimeError(
            "No valid Gemini API keys found in USER_CONFIG (top of script). "
            "Replace the YOUR_GEMINI_API_KEY_* placeholders with real Gemini keys."
        )
    keys.sort(key=lambda t: t[2])
    return keys


def is_overrides_empty(text: str) -> bool:
    if not text:
        return True
    cleaned = text
    cleaned = re.sub(r"Enter Gemini API Key\s*:.*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "", cleaned)
    cleaned = re.sub(r"AQ\.[0-9A-Za-z_\-]{20,}", "", cleaned)
    labels = [
        r"Art Style", r"Body Rendering", r"Texture", r"Face",
        r"Cloths?", r"Weapons", r"Any Other Information", r"Aspect Ratio", r"Movement",
        r"What I Require\s*:", r"What I Don't Require\s*:",
        r"What I Require", r"What I Don't Require",
    ]
    for lab in labels:
        cleaned = re.sub(lab, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return len(cleaned) < 8


def get_clean_overrides() -> str:
    text = USER_THEMATIC_OVERRIDES or ""
    text = re.sub(r"Enter Gemini API Key\s*:.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "", text)
    text = re.sub(r"AQ\.[0-9A-Za-z_\-]{20,}", "", text)
    return text.strip()



def log_key_event(message: str) -> None:
    try:
        VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(KEY_USAGE_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass


FORENSIC_SYSTEM_PROMPT = """
You are a world-class forensic video analyst + elite AI video prompt engineer.
You receive a chronological sequence of frames extracted at exact 1-second intervals from a video.
Each consecutive frame = exactly +1 second of real time.

Your mission: Produce a reconstruction prompt so precise that Kling, Runway Gen-3/4, Luma, Hailuo, Veo or any video AI can recreate the original video with near pin-point accuracy (timing, motion, camera, style, character consistency).

=== ABSOLUTE RULES ===
1. ZERO TEXT POLICY: Completely ignore ALL text, watermarks, logos, subtitles, numbers. Never mention or recreate any text.
2. Character & object consistency is sacred — describe once thoroughly, then lock it.
3. Be extremely specific about time, camera movement, micro-actions, lighting changes, and motion between frames.
4. Fuse forensic-level detail into a single dense, ready-to-paste Master Prompt.
5. If no user thematic overrides are provided, you MUST describe the video EXACTLY as it appears — zero creative changes, zero style forcing, pure forensic recreation of the original.

=== CRITICAL: PIN-POINT MOVEMENT & POSITION PROTOCOL (HIGHEST PRIORITY) ===
You MUST track with second-by-second exactness:

FOR EVERY CHARACTER / PERSON (every second):
- Exact body direction / facing (e.g. facing camera, 3/4 left, profile right, back to camera, looking up-left, etc.)
- Head orientation and face position in frame (center, left third, right third, top, bottom, etc.)
- What the face is doing (looking at X, speaking, smiling, neutral, eyes closed, head turn direction + speed)
- Limb / body action at that exact second (arm raised, walking left, turning torso, standing still, etc.)
- Direction of movement if any (moving left→right, forward toward camera, retreating, circling, etc.)
- Change from previous second (e.g. "at 0:03 facing right → at 0:04 starts turning left 45°")

FOR EVERY IMPORTANT OBJECT (every second):
- Exact screen position (left/center/right, top/mid/bottom, approximate rule-of-thirds or % if clear)
- Orientation / direction the object is pointing or facing
- What it is doing (held in right hand, falling, rotating, resting on table, being moved leftward, etc.)
- Relation to character (in left hand, on ground near feet, flying past face, etc.)
- Change from previous second

MOTION PATH RULES:
- Never say vague "moves" or "walks". Always specify direction + relative speed + facing during motion.
- Explicitly note turns, stops, starts, acceleration, deceleration between consecutive seconds.
- If something is static, say "static / no movement" for that second.
- Prefer 1-second or very short ranges in shot_list when actions change.

This pin-point temporal tracking of directions, face, and objects is NON-NEGOTIABLE and must appear in both shot_list and master_prompt.

=== 14-DIMENSION FORENSIC PROTOCOL ===
1. Overall Concept & Narrative Arc
2. Character Bible (age, face, body, clothing, distinctive features, movement style)
3. Environment & Set Design
4. Shot-by-Shot Temporal Breakdown (prefer ~1 second granularity when motion/face/object changes)
5. Camera Language
6. Lighting Architecture over time
7. Color Palette & Grade (with approximate hex)
8. Motion, Physics & Dynamism (include full second-by-second direction tracking)
9. Texture, Grain, Imperfections, Particles
10. Artistic Medium / Style
11. Pacing & Editing rhythm
12. Mood & Atmosphere
13. Technical Look
14. Consistency Locks & Negative Space

=== OUTPUT FORMAT (STRICT JSON ONLY) ===
Return ONLY one valid JSON object. No markdown, no extra text.

{
  "forensic_analysis": {
    "overall_concept": "<detailed>",
    "character_bible": "<extremely detailed consistency description including default facing/movement style>",
    "environment": "<detailed>",
    "camera_language": "<detailed>",
    "lighting_architecture": "<detailed>",
    "color_grade": "<palette with hex + grade>",
    "motion_physics": "<detailed + explicit second-level direction/position notes>",
    "texture_grain": "<detailed>",
    "artistic_style": "<exact medium>",
    "mood_atmosphere": "<4-6 adjectives + genre>",
    "technical_look": "<detailed>",
    "consistency_locks": "<critical rules>"
  },
  "shot_list": [
    {
      "time_range": "0:00-0:01",
      "shot_type": "...",
      "camera": "...",
      "action": "PIN-POINT: character facing X, face position Y, doing Z; object A at position B, oriented C, doing D. Note any direction change from previous second.",
      "lighting": "...",
      "notes": "Any micro-details about head/face/object position or motion direction"
    }
  ],
  "master_prompt": "<ONE single ultra-dense 350-550 word reconstruction prompt. MUST contain clear second-level or short-range timestamp blocks like [0:00], [0:01], [0:02-0:03] etc. Inside each block: exact character direction/facing, face location + action, object positions + what they are doing, motion paths. Include full forensic detail, consistency locks, and negative prompt. Ready to paste into any video AI.>"
}
"""


class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    DIM    = "\033[2m"
    BLUE   = "\033[94m"
    MAGENTA= "\033[95m"


def print_banner() -> None:
    print(f"""
{C.CYAN}{C.BOLD}
 +----+
 |   FORENSIC VIDEO-TO-PROMPT ENGINE  (ONE-CLICK + PIN-POINT)      |
 |   Libs: C:\\AKT Media Tools  |  1-FPS Token Optimized            |
 |   Gemini Flash (auto model) | Master + Forensic | Auto-Done     |
 |   12-Key Rotation | PIN-POINT direction / face / object track  |
 |   Sort: Media/EXIF Date created FIRST (earliest first)         |
 |   Key-switch delay: 600s | URL Picker + 8s Enter-URL prompt    |
 |   Download: IG cookies+yt-dlp | yt-dlp + gallery-dl fallback   |
 +----+
{C.RESET}""")


def print_step(icon: str, message: str, color: str = C.WHITE) -> None:
    print(f"  {color}{icon}  {message}{C.RESET}")


def print_progress(current: int, total: int, filename: str) -> None:
    bar_width = 30
    filled    = int(bar_width * current / max(total, 1))
    bar       = "#" * filled + "-" * (bar_width - filled)
    pct       = int(100 * current / max(total, 1))
    print(f"\n  {C.CYAN}[{bar}] {pct:3d}%  ({current}/{total}){C.RESET}")
    print(f"  {C.BOLD}Analyzing:{C.RESET} {C.YELLOW}{filename}{C.RESET}")


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ====
# DATE CREATED (MEDIA/EXIF-EQUIVALENT) — earliest first
# ====
_DATE_STRING_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y:%m:%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y:%m:%d",
)

_MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


def _parse_date_string(value: str):
    if not value:
        return None
    s = value.strip().strip("\x00").strip().strip('"').strip("'")
    if not s:
        return None
    for fmt in _DATE_STRING_FORMATS:
        try:
            if fmt.endswith("Z") and s.endswith("Z"):
                dt = datetime.strptime(s[:32].rstrip("Z"), fmt.rstrip("Z"))
            else:
                dt = datetime.strptime(s[:26], fmt.rstrip("Z") if fmt.endswith("Z") else fmt)
            return dt.timestamp()
        except Exception:
            continue
    m = re.match(
        r"(\d{4})[:\-/.](\d{1,2})[:\-/.](\d{1,2})[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?",
        s,
    )
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            hh = int(m.group(4) or 0)
            mm = int(m.group(5) or 0)
            ss = int(m.group(6) or 0)
            return datetime(y, mo, d, hh, mm, ss).timestamp()
        except Exception:
            pass
    return None


def _mp4_seconds_to_unix(seconds: int):
    try:
        if seconds <= 0 or seconds < 60:
            return None
        dt = _MP4_EPOCH.timestamp() + float(seconds)
        if 0 < dt < 4102444800:
            return dt
    except Exception:
        pass
    return None


def _read_mp4_creation_time(path: Path):
    try:
        with open(path, "rb") as f:
            file_size = path.stat().st_size
            pos = 0
            max_scan = min(file_size, 8 * 1024 * 1024)
            while pos + 8 <= max_scan:
                f.seek(pos)
                header = f.read(8)
                if len(header) < 8:
                    break
                size, atom = struct.unpack(">I4s", header)
                try:
                    atom_type = atom.decode("latin-1")
                except Exception:
                    atom_type = ""
                header_len = 8
                if size == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        break
                    size = struct.unpack(">Q", ext)[0]
                    header_len = 16
                elif size == 0:
                    size = file_size - pos
                if size < header_len:
                    break
                if atom_type == "moov":
                    end = pos + size
                    inner = pos + header_len
                    while inner + 8 <= end and inner < max_scan + 2_000_000:
                        f.seek(inner)
                        h2 = f.read(8)
                        if len(h2) < 8:
                            break
                        s2, a2 = struct.unpack(">I4s", h2)
                        try:
                            t2 = a2.decode("latin-1")
                        except Exception:
                            t2 = ""
                        h2_len = 8
                        if s2 == 1:
                            e2 = f.read(8)
                            if len(e2) < 8:
                                break
                            s2 = struct.unpack(">Q", e2)[0]
                            h2_len = 16
                        elif s2 == 0:
                            s2 = end - inner
                        if s2 < h2_len:
                            break
                        if t2 == "mvhd":
                            f.seek(inner + h2_len)
                            version_flags = f.read(4)
                            if len(version_flags) < 4:
                                break
                            version = version_flags[0]
                            if version == 1:
                                data = f.read(16)
                                if len(data) >= 16:
                                    creation = struct.unpack(">Q", data[0:8])[0]
                                    ts = _mp4_seconds_to_unix(int(creation & 0xFFFFFFFF))
                                    if ts is not None:
                                        return ts
                            else:
                                data = f.read(8)
                                if len(data) >= 8:
                                    creation = struct.unpack(">I", data[0:4])[0]
                                    ts = _mp4_seconds_to_unix(int(creation))
                                    if ts is not None:
                                        return ts
                            return None
                        if t2 in ("trak", "mdia", "minf", "stbl", "udta", "meta"):
                            inner += h2_len
                            continue
                        inner += s2
                    return None
                if atom_type == "mdat" and size > 1024 * 1024:
                    pos += size
                    continue
                pos += size
    except Exception:
        pass
    return None


def _read_ffprobe_creation_time(path: Path):
    for bin_name in ("ffprobe", "ffprobe.exe"):
        try:
            cmd = [
                bin_name, "-v", "quiet", "-print_format", "json",
                "-show_entries", "format_tags=creation_time:stream_tags=creation_time",
                str(path),
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            data = json.loads(proc.stdout)
            tags = (data.get("format") or {}).get("tags") or {}
            for key in ("creation_time", "Creation Time", "DATE", "date", "com.apple.quicktime.creationdate"):
                if key in tags:
                    ts = _parse_date_string(str(tags[key]))
                    if ts is not None:
                        return ts
            for stream in data.get("streams") or []:
                stags = stream.get("tags") or {}
                for key in ("creation_time", "Creation Time", "DATE", "date",
                            "com.apple.quicktime.creationdate"):
                    if key in stags:
                        ts = _parse_date_string(str(stags[key]))
                        if ts is not None:
                            return ts
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return None


def _read_media_date_created(path: Path):
    ts = _read_ffprobe_creation_time(path)
    if ts is not None:
        return ts, "Media Date created (metadata/EXIF-equivalent)"
    ext = path.suffix.lower()
    if ext in {".mp4", ".m4v", ".mp4v", ".mov", ".qt", ".3gp", ".3g2", ".f4v"}:
        ts = _read_mp4_creation_time(path)
        if ts is not None:
            return ts, "Media Date created (MP4/MOV container)"
    return None, ""


def _filesystem_date_created(path: Path):
    try:
        st = path.stat()
        birth = getattr(st, "st_birthtime", None)
        if birth is not None:
            return float(birth), "File Date created (birthtime)"
        return float(st.st_ctime), "File Date created"
    except Exception:
        return None, ""


def get_video_sort_timestamp(path: Path):
    name_key = path.name.lower()
    ts, source = _read_media_date_created(path)
    if ts is not None:
        return (ts, source, name_key)
    ts, source = _filesystem_date_created(path)
    if ts is not None:
        return (ts, source, name_key)
    try:
        return (path.stat().st_mtime, "mtime", name_key)
    except Exception:
        return (0.0, "unknown", name_key)


def format_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "?"


def find_all_videos():
    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
    found = []
    seen_names = set()
    search_dirs = [VIDEO_FOLDER, SCRIPT_DIR]
    print_step("~", "Scanning for videos (brute-force all formats)...", C.DIM)
    for folder in search_dirs:
        if not folder.exists():
            continue
        try:
            for p in folder.iterdir():
                if not p.is_file():
                    continue
                if _is_already_named_output(p.name):
                    continue
                ext = p.suffix.lower()
                if ext in VALID_EXTENSIONS:
                    key = (p.name.lower(), p.stat().st_size)
                    if key not in seen_names:
                        seen_names.add(key)
                        found.append(p)
                        loc = "Video to Prompt" if folder == VIDEO_FOLDER else "script folder"
                        print(f"      {C.GREEN}Found:{C.RESET} {p.name}  ({loc})")
        except Exception as e:
            print_step("!", f"Scan error in {folder}: {e}", C.YELLOW)

    if not found:
        print_step("~", "No standard extensions found. Trying deep scan with OpenCV...", C.DIM)
        for folder in search_dirs:
            try:
                for p in folder.iterdir():
                    if not p.is_file() or p.suffix.lower() in {".py", ".txt", ".json", ".log", ".md"}:
                        continue
                    if _is_already_named_output(p.name):
                        continue
                    try:
                        cap = cv2.VideoCapture(str(p))
                        if cap.isOpened():
                            ret, _ = cap.read()
                            cap.release()
                            if ret:
                                key = (p.name.lower(), p.stat().st_size)
                                if key not in seen_names:
                                    seen_names.add(key)
                                    found.append(p)
                                    print(f"      {C.GREEN}Deep-found:{C.RESET} {p.name}")
                    except Exception:
                        pass
            except Exception:
                pass

    print_step("~", "Sorting by Media/EXIF Date created (earliest first)...", C.DIM)
    keyed = []
    for p in found:
        ts, source, name_key = get_video_sort_timestamp(p)
        keyed.append((ts, name_key, p, source))
        print(f"      {C.DIM}{p.name}  →  {format_ts(ts)}  [{source}]{C.RESET}")
    keyed.sort(key=lambda item: (item[0], item[1]))
    sorted_paths = [item[2] for item in keyed]
    if sorted_paths:
        print_step("+", f"Order locked: earliest Date created → latest ({len(sorted_paths)} video(s))", C.GREEN)
    return sorted_paths


def extract_1fps_frames(video_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        for backend in [cv2.CAP_FFMPEG, cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]:
            try:
                cap = cv2.VideoCapture(str(video_path), backend)
                if cap.isOpened():
                    break
            except Exception:
                continue
    if not cap.isOpened():
        print_step("!", f"Cannot open video: {video_path.name}", C.RED)
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or fps != fps:
        fps = 30.0
    fps = max(1.0, fps)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    print_step("~", f"Detected ≈ {fps:.1f} FPS | Duration ≈ {duration:.1f}s", C.DIM)

    frames = []
    frame_idx = 0
    extracted = 0
    step = max(1, int(round(fps)))
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % step == 0:
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(rgb)
                max_dim = max(pil.size)
                if max_dim > MAX_FRAME_PX:
                    scale = MAX_FRAME_PX / max_dim
                    new_size = (int(pil.width * scale), int(pil.height * scale))
                    pil = pil.resize(new_size, Image.Resampling.LANCZOS)
                frames.append(pil)
                extracted += 1
                if extracted >= MAX_FRAMES_SAFETY:
                    print_step("!", f"Safety limit ({MAX_FRAMES_SAFETY} frames). Truncating.", C.YELLOW)
                    break
            except Exception:
                pass
        frame_idx += 1
    cap.release()
    print_step("+", f"Extracted {len(frames)} key frames (1 FPS)", C.GREEN)
    return frames



def parse_gemini_json(raw_text: str) -> Optional[dict]:
    text = raw_text.strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except Exception:
        return None


def _is_model_not_found_error(err_str: str) -> bool:
    low = (err_str or "").lower()
    return (
        "404" in err_str
        or "not_found" in low
        or "no longer available" in low
        or "is not found" in low
        or "was not found" in low
    ) and ("model" in low or "models/" in low)


def _model_candidates() -> List[str]:
    global _RESOLVED_GEMINI_MODEL
    if _RESOLVED_GEMINI_MODEL:
        rest = [m for m in GEMINI_MODEL_CANDIDATES if m != _RESOLVED_GEMINI_MODEL]
        return [_RESOLVED_GEMINI_MODEL] + rest
    return list(GEMINI_MODEL_CANDIDATES)


def call_gemini_with_retry(rotator: "GeminiApiKeyRotator", frames: List[Image.Image], filename: str) -> Optional[dict]:
    global _RESOLVED_GEMINI_MODEL
    delay = RETRY_BASE_DELAY
    final_system_prompt = FORENSIC_SYSTEM_PROMPT
    overrides_empty = is_overrides_empty(USER_THEMATIC_OVERRIDES)
    clean_overrides = get_clean_overrides()

    if overrides_empty:
        print_step("~", "Overrides are blank → Pure original video mode (no style change)", C.CYAN)
        pure_block = """
=== PURE ORIGINAL MODE (NO USER OVERRIDES) ===
The user has left all thematic overrides blank.
You MUST describe and recreate the video EXACTLY as it appears in the frames.
- Do NOT force any art style, ink, grunge, silhouette, abstract, or any other look.
- Do NOT invent or change clothing, face, body, weapons, texture, or mood.
- Stay 100% faithful to the real visual content, lighting, colors, camera and motion.
- Still apply full PIN-POINT second-by-second direction / face / object tracking on the real content.
This is a pure forensic reconstruction with zero creative manipulation.
"""
        final_system_prompt = final_system_prompt.replace(
            "=== OUTPUT FORMAT (STRICT JSON ONLY) ===",
            pure_block + "\n=== OUTPUT FORMAT (STRICT JSON ONLY) ==="
        )
    else:
        print_step("~", "User overrides detected → Applying thematic instructions", C.YELLOW)
        override_block = f"""
=== USER THEMATIC OVERRIDES (HIGHEST PRIORITY) ===
These instructions OVERRIDE the original video if they conflict.
You MUST force both forensic_analysis and especially the master_prompt to obey them:

"{clean_overrides}"

Still keep full PIN-POINT second-by-second tracking of directions, face position/action, and object positions/actions.
"""
        final_system_prompt = final_system_prompt.replace(
            "=== OUTPUT FORMAT (STRICT JSON ONLY) ===",
            override_block + "=== OUTPUT FORMAT (STRICT JSON ONLY) ==="
        )

    payload = [final_system_prompt] + frames

    for attempt in range(1, MAX_RETRIES + 1):
        key, user_id, idx = rotator.get_current_key()
        if idx == -1:
            print_step("!", "All API keys exhausted / cooling down → waiting 60s before retry", C.YELLOW)
            log_key_event("All keys exhausted/cooling — waiting 60s")
            time.sleep(60)
            continue
        client = genai.Client(api_key=key)
        last_err = ""
        model_404_all = True
        rotator.record_request(idx)
        log_key_event(f"REQUEST Key #{rotator.keys[idx]['slot']} userID={_mask_user_id(user_id or '')} file={filename}")
        for model_name in _model_candidates():
            try:
                print_step(
                    "~",
                    f"Sending {len(frames)} frames to {model_name}  (Key #{rotator.keys[idx]['slot']} / {_mask_user_id(user_id or '')})...",
                    C.DIM,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=payload,
                )
                if _RESOLVED_GEMINI_MODEL != model_name:
                    _RESOLVED_GEMINI_MODEL = model_name
                    print_step("+", f"Using Gemini model: {model_name}", C.GREEN)
                raw = response.text.strip()
                parsed = parse_gemini_json(raw)
                if parsed and "master_prompt" in parsed:
                    return parsed
                return {
                    "master_prompt": raw,
                    "forensic_analysis": {},
                    "shot_list": [],
                    "_raw_fallback": True,
                }
            except Exception as exc:
                err_str = str(exc)
                last_err = err_str
                low = err_str.lower()
                if "429" in err_str or "quota" in low or "rate limit" in low or "resource_exhausted" in low:
                    model_404_all = False
                    retry_after = None
                    m = re.search(r"retry(?:[-_ ]?after)?[^0-9]{0,20}(\d+)", low)
                    if m:
                        try:
                            retry_after = float(m.group(1))
                        except Exception:
                            retry_after = None
                    print_step("~", f"[{filename}] Attempt {attempt}: rate-limit/quota on Key #{rotator.keys[idx]['slot']}", C.YELLOW)
                    log_key_event(f"429 Key #{rotator.keys[idx]['slot']} userID={_mask_user_id(user_id or '')} file={filename}")
                    rotator.handle_rate_limit(idx, retry_after)
                    break
                if ("401" in err_str or "403" in err_str
                        or "permission_denied" in low or "permission denied" in low
                        or "unauthorized" in low or "api key not valid" in low
                        or "api_key_invalid" in low or "invalid api key" in low):
                    model_404_all = False
                    print_step("~", f"[{filename}] Attempt {attempt}: auth error on Key #{rotator.keys[idx]['slot']}", C.YELLOW)
                    log_key_event(f"401/403 Key #{rotator.keys[idx]['slot']} userID={_mask_user_id(user_id or '')} file={filename}")
                    rotator.handle_auth_error(idx)
                    break
                if _is_model_not_found_error(err_str):
                    print_step("~", f"Model {model_name} unavailable → trying next", C.YELLOW)
                    continue
                model_404_all = False
                print_step("~", f"[{filename}] Attempt {attempt} failed: {err_str[:90]}... Retry in {delay}s", C.YELLOW)
                time.sleep(delay)
                delay *= 2
                break
        else:
            if model_404_all:
                print_step(
                    "!",
                    f"[{filename}] No usable Gemini model (tried {', '.join(GEMINI_MODEL_CANDIDATES)})",
                    C.RED,
                )
                print_step("~", f"Last error: {last_err[:160]}", C.DIM)
                time.sleep(delay)
                delay *= 2
                continue
    return None



# ====
# URL PICKER + DOWNLOAD (direct + gallery-dl + yt-dlp)
# ====
def ensure_url_picker_file() -> Path:
    try:
        if not URL_PICKER_FILE.exists():
            URL_PICKER_FILE.write_text("", encoding="utf-8")
            print_step("+", f"Created URL picker: {URL_PICKER_FILE.name}", C.GREEN)
        else:
            print_step("+", f"URL picker present: {URL_PICKER_FILE.name}", C.GREEN)
    except Exception as e:
        print_step("!", f"Could not ensure URL picker file: {e}", C.YELLOW)
    return URL_PICKER_FILE


def load_urls_from_picker() -> List[str]:
    urls = []
    seen = set()
    try:
        if not URL_PICKER_FILE.exists():
            return []
        text = URL_PICKER_FILE.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print_step("!", f"load_urls_from_picker: {e}", C.YELLOW)
        return []
    for m in re.finditer(r"https?://[^\s<>\"'\])\}]+", text, re.IGNORECASE):
        u = m.group(0).rstrip(".,;:)")
        if not u or u.lower() in seen:
            continue
        seen.add(u.lower())
        urls.append(u)
    return urls


def remove_url_from_picker(url: str) -> bool:
    """
    Erase this URL from the active picker after the job finishes
    (same pattern as Ultimate Media Tool URL Picker).
    Remaining lines in the picker = unfinished balance.
    """
    if not url or not URL_PICKER_FILE.exists():
        return False
    try:
        text = URL_PICKER_FILE.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        new_lines = []
        removed = False
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
                else:
                    removed = True
                    continue
                removed = True
            else:
                new_lines.append(line)
        if removed:
            URL_PICKER_FILE.write_text("".join(new_lines), encoding="utf-8")
            remaining = load_urls_from_picker()
            print_step(
                "+",
                f"Erased completed URL from {URL_PICKER_FILE.name} "
                f"(remaining balance: {len(remaining)} URL(s))",
                C.GREEN,
            )
            return True
    except Exception as e:
        print_step("!", f"Could not remove URL from picker: {e}", C.YELLOW)
    return False


def archive_completed_url(url: str, note: str = "") -> None:
    """Append completed URL to Done archive so you keep a permanent download record."""
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp}\t{url}"
        if note:
            line += f"\t# {note}"
        line += "\n"
        with open(URL_PICKER_DONE, "a", encoding="utf-8") as f:
            f.write(line)
        print_step("+", f"Recorded in {URL_PICKER_DONE.name}", C.GREEN)
    except Exception as e:
        print_step("!", f"Could not write Done URL archive: {e}", C.YELLOW)


def rotator_balance_plain(rotator: "GeminiApiKeyRotator") -> str:
    """Plain-text key balance (RPM/RPD remaining) for job log — no ANSI colors."""
    now = time.time()
    lines = []
    for k in rotator.keys:
        rotator._refresh_windows(k)
        rpm_left = max(0, rotator.ROTATE_AT_RPM - k["rpm_count"])
        rpd_left = max(0, rotator.ROTATE_AT_RPD - k["rpd_count"])
        if k["disabled"]:
            status = "DISABLED"
        elif k["cooldown_until"] > now:
            status = f"COOLDOWN {int(k['cooldown_until'] - now)}s"
        else:
            status = "active"
        lines.append(
            f"  Key #{k['slot']} ({_mask_user_id(k['user_id'])}): "
            f"RPM {k['rpm_count']}/{rotator.RPM_LIMIT} (left~{rpm_left}) | "
            f"RPD {k['rpd_count']}/{rotator.RPD_LIMIT} (left~{rpd_left}) | {status}"
        )
    return "\n".join(lines)


def write_job_log(
    *,
    url: str,
    downloaded_files: List[str],
    processed_ok: List[str],
    processed_fail: List[str],
    success: int,
    failed: int,
    rotator: "GeminiApiKeyRotator",
    status: str,
) -> None:
    """
    Permanent job record: what was downloaded, what succeeded, URL picker balance,
    and API key RPM/RPD balance after this job.
    """
    try:
        remaining_urls = load_urls_from_picker()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        block = []
        block.append("=" * 80)
        block.append(f"JOB COMPLETE  {stamp}")
        block.append(f"Status       : {status}")
        block.append(f"URL          : {url}")
        block.append(f"Downloaded   : {len(downloaded_files)} file(s)")
        for name in downloaded_files:
            block.append(f"  + {name}")
        block.append(f"Processed OK : {success}")
        for name in processed_ok:
            block.append(f"  + {name}")
        block.append(f"Processed FAIL: {failed}")
        for name in processed_fail:
            block.append(f"  ! {name}")
        block.append(f"URL picker remaining balance: {len(remaining_urls)} URL(s)")
        for u in remaining_urls:
            block.append(f"  ~ {u}")
        block.append("API key balance after job:")
        block.append(rotator_balance_plain(rotator))
        block.append("")
        with open(JOB_LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(block) + "\n")
        print_step("+", f"Job record saved → {JOB_LOG_FILE.name}", C.GREEN)
    except Exception as e:
        print_step("!", f"Could not write job log: {e}", C.YELLOW)


def finish_url_job(
    url: str,
    saved_list: List[Path],
    processed_ok: List[str],
    processed_fail: List[str],
    success: int,
    failed: int,
    rotator: "GeminiApiKeyRotator",
) -> None:
    """
    After a picker URL job finishes (download + process):
      1. Erase URL from active picker (remaining lines = unfinished balance)
      2. Archive URL in Done.txt
      3. Append full job record (files + key balance) to Job Log.txt
    Matches Ultimate Media Tool: remove URL when the job for that URL completes.
    """
    downloaded = [p.name for p in saved_list]
    if success > 0:
        status = "OK" if failed == 0 else f"PARTIAL ({success} ok, {failed} fail)"
        remove_url_from_picker(url)
        archive_completed_url(
            url,
            note=f"{success} ok / {failed} fail / {len(downloaded)} downloaded",
        )
        write_job_log(
            url=url,
            downloaded_files=downloaded,
            processed_ok=processed_ok,
            processed_fail=processed_fail,
            success=success,
            failed=failed,
            rotator=rotator,
            status=status,
        )
    else:
        print_step("!", "Processing failed — URL kept in picker for retry", C.YELLOW)
        write_job_log(
            url=url,
            downloaded_files=downloaded,
            processed_ok=processed_ok,
            processed_fail=processed_fail,
            success=success,
            failed=failed,
            rotator=rotator,
            status="FAILED — URL kept in picker",
        )


def quarantine_url_as_failed(url: str, reason: str = "", rotator: Optional["GeminiApiKeyRotator"] = None) -> None:
    """Move a permanently-failed URL out of the active picker so it won't retry forever."""
    remove_url_from_picker(url)
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp}\t{url}"
        if reason:
            line += f"\t# {reason[:200]}"
        line += "\n"
        with open(URL_PICKER_FAILED, "a", encoding="utf-8") as f:
            f.write(line)
        print_step("~", f"URL moved to {URL_PICKER_FAILED.name} (no infinite retry)", C.YELLOW)
    except Exception as e:
        print_step("!", f"Could not write failed-URL log: {e}", C.YELLOW)
    if rotator is not None:
        write_job_log(
            url=url,
            downloaded_files=[],
            processed_ok=[],
            processed_fail=[],
            success=0,
            failed=0,
            rotator=rotator,
            status=f"QUARANTINED — {reason}",
        )


def _looks_permanent_download_error(log_text: str) -> bool:
    low = (log_text or "").lower()
    return any(h in low for h in _PERMANENT_DL_HINTS)


def _ensure_ytdlp() -> bool:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if YTDLP_PATH.exists() and YTDLP_PATH.stat().st_size > 100_000:
        return True
    print_step("~", f"Downloading yt-dlp.exe ({YTDLP_RELEASE_TAG}) → Tools ...", C.YELLOW)
    try:
        req = urllib.request.Request(
            YTDLP_DOWNLOAD_URL,
            headers={"User-Agent": "Mozilla/5.0 (VideoToPrompt/1.1)"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp, open(YTDLP_PATH, "wb") as out:
            shutil.copyfileobj(resp, out)
        if YTDLP_PATH.exists() and YTDLP_PATH.stat().st_size > 100_000:
            print_step("+", f"yt-dlp ready: {YTDLP_PATH}", C.GREEN)
            return True
    except Exception as e:
        print_step("!", f"yt-dlp download failed: {e}", C.RED)
        # Fallback to latest if pinned tag 404s
        try:
            latest = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
            req = urllib.request.Request(latest, headers={"User-Agent": "Mozilla/5.0 (VideoToPrompt/1.1)"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(YTDLP_PATH, "wb") as out:
                shutil.copyfileobj(resp, out)
            if YTDLP_PATH.exists() and YTDLP_PATH.stat().st_size > 100_000:
                print_step("+", f"yt-dlp ready (latest): {YTDLP_PATH}", C.GREEN)
                return True
        except Exception as e2:
            print_step("!", f"yt-dlp latest fallback failed: {e2}", C.RED)
    return False



def _snapshot_files(dest_folder: Path) -> Dict[str, Tuple[int, int]]:
    """Relative-path → (mtime_ns, size) snapshot of all files under dest_folder."""
    snap: Dict[str, Tuple[int, int]] = {}
    try:
        for p in dest_folder.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(dest_folder)).replace("\\", "/").lower()
                try:
                    st = p.stat()
                    snap[rel] = (st.st_mtime_ns, st.st_size)
                except Exception:
                    snap[rel] = (0, 0)
    except Exception:
        pass
    return snap


def _is_openable_video(path: Path) -> bool:
    try:
        if path.suffix.lower() not in VALID_EXTENSIONS:
            # still try opencv for unknown ext
            pass
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return False
        ret, _ = cap.read()
        cap.release()
        return bool(ret)
    except Exception:
        return False


def _collect_new_valid_videos(dest_folder: Path, before_meta: Dict[str, Tuple[int, int]]) -> List[Path]:
    """Return new OR updated valid video files under dest_folder, flattened into dest_folder."""
    found: List[Path] = []
    try:
        for p in dest_folder.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(dest_folder)).replace("\\", "/").lower()
            try:
                st = p.stat()
                meta = (st.st_mtime_ns, st.st_size)
            except Exception:
                continue
            prev = before_meta.get(rel)
            if prev is not None and prev == meta:
                continue
            # skip tiny files / side-car junk
            if st.st_size < 10_000:
                continue
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".json", ".vtt", ".srt", ".info.json"}:
                continue
            if p.suffix.lower() not in VALID_EXTENSIONS and not _is_openable_video(p):
                continue
            if p.suffix.lower() in VALID_EXTENSIONS or _is_openable_video(p):
                if not _is_openable_video(p):
                    continue
                found.append(p)
    except Exception:
        pass

    flattened: List[Path] = []
    for p in found:
        if p.parent == dest_folder:
            flattened.append(p)
            continue
        target = dest_folder / p.name
        n = 1
        while target.exists() and target.resolve() != p.resolve():
            target = dest_folder / f"{p.stem}_{n}{p.suffix}"
            n += 1
        if target.resolve() != p.resolve():
            try:
                shutil.move(str(p), str(target))
                flattened.append(target)
            except Exception:
                flattened.append(p)
        else:
            flattened.append(p)

    flattened.sort(key=lambda x: x.name.lower())
    return flattened


def _gallery_dl_available() -> bool:
    return _package_present_in_target("gallery_dl", "gallery-dl")


BROWSERS = ["firefox", "chrome", "edge", "brave", "opera", "chromium", "vivaldi"]


def _ytdlp_bin() -> Optional[str]:
    """Prefer bundled yt-dlp.exe; fall back to python -m yt_dlp."""
    if _ensure_ytdlp() and YTDLP_PATH.exists():
        return str(YTDLP_PATH)
    return None


def _instagram_ytdlp_base_cmd(url: str, out_tmpl: str) -> List[str]:
    """MEDIA-ONLY Instagram yt-dlp command (archiver logic)."""
    ytdlp = _ytdlp_bin()
    if ytdlp:
        head = [ytdlp, url, "-o", out_tmpl]
    else:
        head = [sys.executable, "-m", "yt_dlp", url, "-o", out_tmpl]
    return head + [
        "--yes-playlist",
        "--no-mtime",
        "--ignore-errors",
        "--ignore-no-formats-error",
        "-f", "bv*+ba/b/best",
        "--format-sort", "res,br,size",
        "--concurrent-fragments", "8",
        "--merge-output-format", "mp4",
        "--no-warnings",
        "--no-write-info-json",
        "--no-write-thumbnail",
        "--no-write-comments",
        "--no-write-description",
        "--retries", "3",
    ]


def download_via_instagram_ytdlp(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    """
    Instagram download (ULTIMATE INSTAGRAM ARCHIVER logic):
      Cookie auth order: Firefox → Chrome → Edge → Brave → Opera → Chromium → Vivaldi
      Then public (no cookies).
      Mode: MEDIA ONLY (no JSON / no thumbnails).
    Success = new valid videos via _collect_new_valid_videos.
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    if _ytdlp_bin() is None:
        return [], "yt-dlp not available"

    out_tmpl = str(
        dest_folder / "%(id)s_%(playlist_index|)s%(playlist_index&_)s%(title).80B.%(ext)s"
    )
    combined_log: List[str] = []
    env = {
        **os.environ,
        "PYTHONPATH": SITE_PACKAGES + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }

    print_step("~", "Instagram cookie auth order: Firefox → Chrome → Edge → Brave → …", C.CYAN)
    print_step("~", "(Log into Instagram in the browser, then CLOSE it before download.)", C.DIM)

    def _run(cmd: List[str], label: str) -> str:
        print_step("~", f"yt-dlp Instagram [{label}]: {url[:80]}...", C.DIM)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                cwd=str(dest_folder),
                env=env,
            )
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            for line in out.splitlines():
                low = line.lower()
                if any(
                    x in low
                    for x in (
                        "download", "100%", "error", "destination", "writing",
                        "merging", "cookie", "extract", "warning",
                    )
                ):
                    print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
            return out
        except subprocess.TimeoutExpired:
            return f"yt-dlp Instagram [{label}] timed out (600s)"
        except Exception as e:
            return f"yt-dlp Instagram [{label}] failed: {e}"

    for browser in BROWSERS:
        before = _snapshot_files(dest_folder)
        cmd = _instagram_ytdlp_base_cmd(url, out_tmpl) + ["--cookies-from-browser", browser]
        print_step("~", f"Trying {browser.upper()} cookies...", C.DIM)
        log = _run(cmd, f"cookies:{browser}")
        combined_log.append(f"=== cookies:{browser} ===\n{log}")
        videos = _collect_new_valid_videos(dest_folder, before)
        if videos:
            for p in videos:
                print_step("+", f"Saved via Instagram yt-dlp ({browser}) → {p.name}", C.GREEN)
            print_step("+", f"Download finished via {browser.upper()} cookies!", C.GREEN)
            return videos, "\n".join(combined_log)
        print_step("!", f"{browser} cookies produced no new videos — next...", C.YELLOW)

    before = _snapshot_files(dest_folder)
    print_step("~", "Final Instagram attempt without cookies (public only)...", C.DIM)
    log = _run(_instagram_ytdlp_base_cmd(url, out_tmpl), "public")
    combined_log.append(f"=== public ===\n{log}")
    videos = _collect_new_valid_videos(dest_folder, before)
    if videos:
        for p in videos:
            print_step("+", f"Saved via Instagram yt-dlp (public) → {p.name}", C.GREEN)
        print_step("+", "Download finished (public / no cookies)!", C.GREEN)
        return videos, "\n".join(combined_log)

    print_step("!", "Instagram yt-dlp finished but no new video in folder", C.YELLOW)
    print_step(
        "!",
        "FIX: Firefox → instagram.com → log in → CLOSE Firefox → re-run",
        C.YELLOW,
    )
    return [], "\n".join(combined_log)


def download_via_gallery_dl(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    """gallery-dl path for hosts that serve video files."""
    if not _gallery_dl_available():
        return [], "gallery-dl not installed"
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    cmd = [
        sys.executable, "-m", "gallery_dl",
        "--dest", str(dest_folder),
        "-f", "{id}_{num}.{extension}",
        "--filter", "extension in ('mp4','webm','mkv','mov','m4v')",
        url,
    ]
    print_step("~", f"gallery-dl downloading videos: {url[:80]}...", C.DIM)
    log = ""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            cwd=str(dest_folder),
            env={**os.environ, "PYTHONPATH": SITE_PACKAGES + os.pathsep + os.environ.get("PYTHONPATH", "")},
        )
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for line in log.splitlines():
            low = line.lower()
            if any(x in low for x in ("download", "error", "#", "http", "writing")):
                print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
        videos = _collect_new_valid_videos(dest_folder, before)
        if videos:
            for p in videos:
                print_step("+", f"Saved via gallery-dl → {p.name}", C.GREEN)
            return videos, log
        return [], log
    except subprocess.TimeoutExpired:
        return [], "gallery-dl timed out (300s)"
    except Exception as e:
        return [], f"gallery-dl failed: {e}"


def download_via_ytdlp(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    """
    Social / reel / post video download via yt-dlp (actual video, not thumbnails).
    """
    if not _ensure_ytdlp():
        print_step("!", "yt-dlp not available — cannot download social media videos", C.RED)
        return [], "yt-dlp not available"
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    out_tmpl = str(dest_folder / "%(id)s_%(playlist_index|)s%(playlist_index&_)s%(title).60B.%(ext)s")

    cmd = [
        str(YTDLP_PATH),
        url,
        "-o", out_tmpl,
        "--no-mtime",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "--retries", "3",
        "--ignore-no-formats-error",
    ]

    print_step("~", f"yt-dlp [video]: {url[:80]}...", C.DIM)
    combined_log = ""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        combined_log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for line in combined_log.splitlines():
            low = line.lower()
            if any(x in low for x in ("download", "100%", "error", "destination", "merging", "writing")):
                print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
    except subprocess.TimeoutExpired:
        print_step("!", "yt-dlp [video] timed out (300s)", C.RED)
        return [], "yt-dlp timed out"
    except Exception as e:
        print_step("!", f"yt-dlp [video] failed: {e}", C.RED)
        return [], f"yt-dlp failed: {e}"

    videos = _collect_new_valid_videos(dest_folder, before)
    if videos:
        for p in videos:
            print_step("+", f"Saved via yt-dlp → {p.name}", C.GREEN)
        return videos, combined_log

    print_step("!", "yt-dlp finished but no new video in folder", C.YELLOW)
    err_tail = combined_log[-400:] if combined_log else ""
    if err_tail.strip():
        print(f"      {C.DIM}{err_tail.strip()[:300]}{C.RESET}")
    return [], combined_log


def _is_direct_video_url(url: str) -> bool:
    path = url.split("?")[0].split("#")[0].rstrip("/").lower()
    return any(path.endswith(ext) for ext in VALID_EXTENSIONS)


def _is_social_media_url(url: str) -> bool:
    low = url.lower()
    hosts = (
        "instagram.com", "instagr.am",
        "twitter.com", "x.com",
        "facebook.com", "fb.watch",
        "tiktok.com", "youtube.com", "youtu.be",
        "reddit.com", "pinterest.com", "threads.net",
        "vimeo.com", "dailymotion.com",
    )
    return any(h in low for h in hosts)


def _is_instagram_url(url: str) -> bool:
    low = url.lower()
    return "instagram.com" in low or "instagr.am" in low


def download_video_from_url(url: str, dest_folder: Path) -> Tuple[List[Path], str, bool]:
    """
    Smart download for videos:
      1. Direct video URL → urllib
      2. Instagram → yt-dlp browser cookies (Firefox first; MEDIA ONLY), then gallery-dl, then yt-dlp
      3. Other social → yt-dlp first, then gallery-dl
    Returns: (videos, log, permanent_failure_hint)
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    logs: List[str] = []

    if _is_direct_video_url(url) or not _is_social_media_url(url):
        path_part = url.split("?")[0].rstrip("/")
        ext = Path(path_part).suffix.lower()
        if ext not in VALID_EXTENSIONS:
            ext = ".mp4"
        stem = re.sub(r"[^\w\-]+", "_", Path(path_part).stem)[:80] or "downloaded_video"
        dest = dest_folder / f"{stem}{ext}"
        n = 1
        while dest.exists():
            dest = dest_folder / f"{stem}_{n}{ext}"
            n += 1

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": url,
        }
        print_step("~", f"Downloading (direct): {url[:100]}...", C.DIM)
        for attempt in range(1, 3):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as out:
                    shutil.copyfileobj(resp, out)
                if not dest.exists() or dest.stat().st_size < 10_000:
                    try:
                        dest.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue
                if _is_openable_video(dest):
                    print_step("+", f"Saved → {dest.name} ({dest.stat().st_size} bytes)", C.GREEN)
                    return [dest], "direct ok", False
                print_step("!", f"Not a valid video: {dest.name}", C.YELLOW)
                try:
                    dest.unlink(missing_ok=True)
                except Exception:
                    pass
            except Exception as e:
                msg = f"Direct download attempt {attempt}: {e}"
                print_step("!", msg, C.YELLOW)
                logs.append(msg)
                try:
                    if dest.exists():
                        dest.unlink(missing_ok=True)
                except Exception:
                    pass

        if _is_direct_video_url(url):
            return [], "\n".join(logs), _looks_permanent_download_error("\n".join(logs))
        if not _is_social_media_url(url):
            print_step("~", "Direct failed — trying social downloaders...", C.DIM)

    # ---- Instagram: archiver cookie / media-only logic ----
    if _is_instagram_url(url):
        vids, log = download_via_instagram_ytdlp(url, dest_folder)
        logs.append(log)
        if vids:
            return vids, "\n".join(logs), False
        print_step("~", "Instagram cookie/yt-dlp produced no videos — trying gallery-dl...", C.DIM)
        vids, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if vids:
            return vids, "\n".join(logs), False
        print_step("~", "gallery-dl produced no videos — trying plain yt-dlp...", C.DIM)
        vids, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if vids:
            return vids, "\n".join(logs), False
        permanent = _looks_permanent_download_error("\n".join(logs))
        return [], "\n".join(logs), permanent

    if _is_social_media_url(url):
        # Other social: prefer yt-dlp (actual video), then gallery-dl
        vids, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if vids:
            return vids, "\n".join(logs), False
        print_step("~", "yt-dlp produced no videos — trying gallery-dl...", C.DIM)
        vids, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if vids:
            return vids, "\n".join(logs), False
        permanent = _looks_permanent_download_error("\n".join(logs))
        return [], "\n".join(logs), permanent

    return [], "\n".join(logs), False


def get_url_with_timeout(timeout_sec: float = 8.0) -> Optional[str]:
    print()
    print(f"  {C.CYAN}{C.BOLD}No URLs in {URL_PICKER_FILE.name}{C.RESET}")
    print(f"  {C.DIM}Paste video/social URL, or wait {int(timeout_sec)}s / Enter → local videos.{C.RESET}")
    if not HAS_MSVCRT:
        try:
            raw = input(f"  {C.YELLOW}Enter video URL (or Enter skip): {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
    else:
        print(f"  {C.YELLOW}Enter video URL (Auto-skips in {int(timeout_sec)}s): {C.RESET}", end="", flush=True)
        raw = ""
        start = time.time()
        while time.time() - start < timeout_sec:
            if msvcrt.kbhit():
                raw = input()
                break
            time.sleep(0.1)
        print()
    if not raw or not raw.strip():
        print_step("~", "No URL entered / timeout → using local videos only", C.DIM)
        return None
    m = re.search(r"https?://[^\s<>\"'\])\}]+", raw.strip(), re.IGNORECASE)
    if not m:
        print_step("!", "No valid http(s) URL detected — using local videos only", C.YELLOW)
        return None
    url = m.group(0).rstrip(".,;:)")
    print_step("+", f"Using entered URL: {url[:90]}...", C.GREEN)
    return url



def get_starting_number() -> int:
    last = 0
    if DONE_FOLDER.exists():
        try:
            for p in DONE_FOLDER.iterdir():
                if not p.is_file():
                    continue
                m = _RE_DONE_NAME.match(p.name)
                if m:
                    last = max(last, int(m.group(1)))
        except Exception:
            pass
    if OUTPUT_COMBINED_FILE.exists():
        try:
            with open(OUTPUT_COMBINED_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"(?i)^Video(?:\s+No\.)?\s+(\d+)\b", line.strip())
                    if m:
                        last = max(last, int(m.group(1)))
        except Exception:
            pass
    return last + 1


def move_to_done(path: Path, video_num: int):
    """Rename like Ultimate Media Tool: Video 1 originalname.mp4"""
    DONE_FOLDER.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(path.name)
    new_name = f"Video {video_num} {safe_name}"
    target = DONE_FOLDER / new_name
    counter = 1
    while target.exists():
        stem = Path(safe_name).stem
        ext = Path(safe_name).suffix
        target = DONE_FOLDER / f"Video {video_num} {stem}_{counter}{ext}"
        counter += 1
    try:
        shutil.move(str(path), str(target))
        print_step("+", f"Moved → Video to Prompt Done\\{target.name}", C.GREEN)
        return target.name
    except Exception as e:
        print_step("!", f"Could not move to Done: {e}", C.YELLOW)
        return new_name


def manage_files() -> Tuple[List[Path], int]:
    seen: Dict[str, str] = {}
    if DONE_FOLDER.exists():
        print_step("~", "Scanning Done folder for multi-run deduplication...", C.DIM)
        for p in DONE_FOLDER.iterdir():
            if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS:
                try:
                    seen[file_md5(p)] = p.name
                except Exception:
                    pass
        print_step("+", f"Loaded {len(seen)} hash(es) from previously processed videos.", C.GREEN)

    all_videos = find_all_videos()
    videos = []
    for p in all_videos:
        try:
            md5 = file_md5(p)
            if md5 in seen:
                print_step("~", f"Duplicate of Done/{seen[md5]} → skipping {p.name}", C.YELLOW)
            else:
                videos.append(p)
        except Exception:
            videos.append(p)
    return videos, get_starting_number()


def write_output(num: int, filename: str, data: dict):
    """Write like Ultimate Media Tool log titles: Video 1 (filename)"""
    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_COMBINED_FILE, "a", encoding="utf-8") as f:
        f.write(f"Video {num} ({filename})\n\n")

        f.write("\t==== MASTER PROMPT (Copy-Paste Ready) ====\n")
        f.write(f"\t{data.get('master_prompt', '')}\n\n")

        f.write("\t==== TIMESTAMPED SHOT LIST (PIN-POINT MOVEMENT) ====\n")
        for shot in data.get("shot_list", []) or []:
            if not isinstance(shot, dict):
                continue
            f.write(f"\t[{shot.get('time_range', '?')}]\n")
            f.write(f"\t  Shot   : {shot.get('shot_type', '')}\n")
            f.write(f"\t  Camera : {shot.get('camera', '')}\n")
            f.write(f"\t  Action : {shot.get('action', '')}\n")
            f.write(f"\t  Light  : {shot.get('lighting', '')}\n")
            if shot.get("notes"):
                f.write(f"\t  Notes  : {shot.get('notes')}\n")
            f.write("\n")

        f.write("\t==== FORENSIC ANALYSIS ====\n")
        forensic = data.get("forensic_analysis", {})
        if isinstance(forensic, dict) and forensic:
            for key, value in forensic.items():
                f.write(f"\t{key.replace('_', ' ').title()}:\n")
                f.write(f"\t  {value}\n\n")
        else:
            json_str = json.dumps(forensic or {}, ensure_ascii=False, indent=4)
            for line in json_str.split("\n"):
                f.write(f"\t{line}\n")
            f.write("\n")

        f.write("=" * 90 + "\n\n")


def main():
    VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)
    print_banner()

    print(f"  {C.DIM}Libraries : {LIB_ROOT}{C.RESET}")
    print(f"  {C.DIM}Videos    : {VIDEO_FOLDER}{C.RESET}")
    print(f"  {C.DIM}Done      : {DONE_FOLDER}{C.RESET}")
    print(f"  {C.DIM}Output    : {OUTPUT_COMBINED_FILE}{C.RESET}")
    print(f"  {C.DIM}Also scans script folder for any video files{C.RESET}")
    print(f"  {C.DIM}Sort      : Media/EXIF Date created FIRST → file created → mtime (earliest first){C.RESET}")
    print(f"  {C.DIM}Key delay : {GeminiApiKeyRotator.KEY_SWITCH_DELAY_SECONDS}s between API key switches{C.RESET}\n")

    if is_overrides_empty(USER_THEMATIC_OVERRIDES):
        print_step("+", "Mode: PURE ORIGINAL (overrides blank → no style change)", C.GREEN)
    else:
        print_step("+", "Mode: USER OVERRIDES ACTIVE (style will be forced)", C.YELLOW)
    print_step("+", "PIN-POINT mode: second-by-second direction / face / object tracking forced", C.MAGENTA)

    try:
        keys = parse_user_config()
    except Exception as e:
        print(f"  {C.YELLOW}{e}{C.RESET}")
        print_step("!", "No valid Gemini API keys in USER_CONFIG (top of script). Exiting.", C.RED)
        return

    rotator = GeminiApiKeyRotator(keys)
    print_step("+", f"Loaded {len(keys)} Gemini API key(s) from USER_CONFIG", C.GREEN)
    print(f"  {C.DIM}Rotation: RPM @ {GeminiApiKeyRotator.ROTATE_AT_RPM}/"
          f"{GeminiApiKeyRotator.RPM_LIMIT} | "
          f"RPD @ {GeminiApiKeyRotator.ROTATE_AT_RPD}/"
          f"{GeminiApiKeyRotator.RPD_LIMIT} | "
          f"Key-switch delay={GeminiApiKeyRotator.KEY_SWITCH_DELAY_SECONDS}s | "
          f"wrap {len(keys)}→1{C.RESET}")
    print(rotator.get_status_summary())
    log_key_event(f"SESSION START — {len(keys)} key(s) loaded")

    print()
    ensure_url_picker_file()
    picker_urls = load_urls_from_picker()

    def process_video_list(
        videos: List[Path], serial_start: int
    ) -> Tuple[int, int, int, List[str], List[str]]:
        if not videos:
            return 0, 0, serial_start, [], []
        serial = serial_start
        success = 0
        failed = 0
        processed_ok: List[str] = []
        processed_fail: List[str] = []
        run_start_time = time.time()
        next_pause_time = run_start_time + (MAX_RUN_TIME_MIN * 60)

        print_step("+", f"Processing {len(videos)} video(s). Starting at Video {serial}\n", C.GREEN)
        print(f"  {C.BOLD}Active Run Time:{C.RESET} {MAX_RUN_TIME_MIN} mins  |  "
              f"{C.BOLD}Pause Time:{C.RESET} {PAUSE_TIME_MIN} mins\n")

        for idx, video_path in enumerate(videos, 1):
            current_time = time.time()
            if current_time >= next_pause_time:
                resume_at = datetime.fromtimestamp(
                    current_time + (PAUSE_TIME_MIN * 60)
                ).strftime("%H:%M:%S")
                print(f"\n{C.MAGENTA}{C.BOLD}===={C.RESET}")
                print(f"{C.MAGENTA}          MAX ACTIVE RUN TIME ({MAX_RUN_TIME_MIN} MINS) REACHED.{C.RESET}")
                print(f"{C.MAGENTA}                FORCED PAUSE FOR {PAUSE_TIME_MIN} MINUTES.{C.RESET}")
                print(f"{C.MAGENTA}     Script will resume automatically at: {resume_at}.{C.RESET}")
                print(f"{C.MAGENTA}===={C.RESET}")
                time.sleep(PAUSE_TIME_MIN * 60)
                print(f"\n{C.CYAN}{C.BOLD}  ==== FORCED PAUSE COMPLETE. RESUMING... ===={C.RESET}\n")
                run_start_time = time.time()
                next_pause_time = run_start_time + (MAX_RUN_TIME_MIN * 60)

            print_progress(idx, len(videos), video_path.name)
            frames = extract_1fps_frames(video_path)
            if not frames:
                failed += 1
                processed_fail.append(video_path.name)
                print_step("!", "No frames extracted → skipping", C.RED)
                continue

            parsed = call_gemini_with_retry(rotator, frames, video_path.name)

            if parsed is None:
                failed += 1
                processed_fail.append(video_path.name)
                print_step("!", f"Failed on {video_path.name}\n", C.RED)
            else:
                master = parsed.get("master_prompt", "")
                preview = textwrap.shorten(str(master), width=120, placeholder="...")
                print_step("+", f"Analysis complete → Video {serial}", C.GREEN)
                print(f"      {C.DIM}Preview: {preview}{C.RESET}")
                write_output(serial, video_path.name, parsed)
                done_name = move_to_done(video_path, serial)
                print_step("+", f"{done_name} written successfully\n", C.GREEN)
                processed_ok.append(f"Video {serial} — {done_name}")
                serial += 1
                success += 1
                time.sleep(REQUEST_DELAY_SEC)

        return success, failed, serial, processed_ok, processed_fail

    total_success = 0
    total_failed = 0
    total_dl_failed = 0
    serial = get_starting_number()

    if picker_urls:
        print(
            f"\n  {C.CYAN}{C.BOLD}Found {len(picker_urls)} URL(s) in "
            f"{URL_PICKER_FILE.name} — downloading & processing them first.{C.RESET}\n"
        )
        for i, url in enumerate(picker_urls, start=1):
            print(f"  {C.BOLD}[Picker URL {i}/{len(picker_urls)}] {url}{C.RESET}")
            try:
                saved_list, dl_log, permanent = download_video_from_url(url, VIDEO_FOLDER)
                if not saved_list:
                    if permanent:
                        print_step("!", "Permanent download failure — URL quarantined", C.RED)
                        quarantine_url_as_failed(
                            url, reason="permanent download failure", rotator=rotator
                        )
                    else:
                        print_step("!", "Download failed — URL kept in picker for retry", C.YELLOW)
                    total_dl_failed += 1
                    continue
                print_step("+", f"Downloaded {len(saved_list)} video(s) from URL", C.GREEN)
                s, f, serial, ok_names, fail_names = process_video_list(saved_list, serial)
                total_success += s
                total_failed += f
                finish_url_job(url, saved_list, ok_names, fail_names, s, f, rotator)
            except Exception as e:
                print_step("!", f"Picker URL job failed (URL kept in file): {e}", C.RED)
                total_dl_failed += 1
            print()
        remaining, serial2 = manage_files()
        serial = max(serial, serial2)
        if remaining:
            print_step("~", f"Also found {len(remaining)} local video(s) to process...", C.CYAN)
            s, f, serial, _, _ = process_video_list(remaining, serial)
            total_success += s
            total_failed += f
    else:
        manual_url = get_url_with_timeout(8.0)
        if manual_url:
            print(f"  {C.BOLD}[Manual URL] {manual_url}{C.RESET}")
            try:
                saved_list, dl_log, permanent = download_video_from_url(manual_url, VIDEO_FOLDER)
                if not saved_list:
                    if permanent:
                        print_step("!", "Permanent download failure — URL quarantined", C.RED)
                        quarantine_url_as_failed(
                            manual_url, reason="permanent download failure", rotator=rotator
                        )
                    else:
                        print_step("!", "Download failed", C.YELLOW)
                    total_dl_failed += 1
                else:
                    print_step("+", f"Downloaded {len(saved_list)} video(s) from URL", C.GREEN)
                    s, f, serial, ok_names, fail_names = process_video_list(saved_list, serial)
                    total_success += s
                    total_failed += f
                    # Manual URL is not in picker — still write job log + Done archive
                    archive_completed_url(manual_url, note="manual Enter-URL")
                    write_job_log(
                        url=manual_url,
                        downloaded_files=[p.name for p in saved_list],
                        processed_ok=ok_names,
                        processed_fail=fail_names,
                        success=s,
                        failed=f,
                        rotator=rotator,
                        status="COMPLETED (manual URL)",
                    )
            except Exception as e:
                print_step("!", f"Manual URL job failed: {e}", C.RED)
                total_dl_failed += 1

        videos, serial2 = manage_files()
        serial = max(serial, serial2)
        if not videos and total_success == 0 and total_dl_failed == 0:
            print_step("!", "No videos found!", C.YELLOW)
            print(f"\n  Put your videos in either:")
            print(f"    1. {VIDEO_FOLDER}")
            print(f"    2. Or next to this .py file: {SCRIPT_DIR}")
            print(f"\n  Or put video/social URLs in: {URL_PICKER_FILE.name}")
            print(f"\n  Supported: mp4, mov, mkv, avi, webm, wmv, flv, mpeg, 3gp, ts, mts, and more.")
            return
        if videos:
            s, f, serial, _, _ = process_video_list(videos, serial)
            total_success += s
            total_failed += f

    print(f"\n{C.CYAN}{C.BOLD}  ==== FINISHED ===={C.RESET}")
    print_step("+", f"Successfully processed: {total_success}", C.GREEN)
    print_step("!", f"Failed (still in source folder): {total_failed}", C.RED if total_failed else C.DIM)
    if total_dl_failed:
        print_step("!", f"Download failures: {total_dl_failed}", C.RED)
    print(f"\n{rotator.get_status_summary()}\n")
    log_key_event(f"SESSION END — success={total_success} failed={total_failed}")
    print(f"\n  Output file:\n  {C.CYAN}{OUTPUT_COMBINED_FILE}{C.RESET}")
    print(f"  Key log:\n  {C.CYAN}{KEY_USAGE_LOG}{C.RESET}")
    print(f"  Job log:\n  {C.CYAN}{JOB_LOG_FILE}{C.RESET}")
    print(f"  Done folder:\n  {C.CYAN}{DONE_FOLDER}{C.RESET}")
    print(f"  URL picker (active / remaining):\n  {C.CYAN}{URL_PICKER_FILE}{C.RESET}")
    print(f"  URL picker Done (completed record):\n  {C.CYAN}{URL_PICKER_DONE}{C.RESET}")
    print(f"  Failed URLs:\n  {C.CYAN}{URL_PICKER_FAILED}{C.RESET}\n")



if __name__ == "__main__":
    try:
        if os.name == "nt":
            try:
                os.system("title FORENSIC VIDEO-TO-PROMPT ENGINE (PIN-POINT + MULTI-KEY) (ONE-CLICK)")
            except Exception:
                pass
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {C.YELLOW}Interrupted. Progress is safe in Done folder + output file.{C.RESET}\n")
    except Exception as e:
        print("\n" + "!" * 60)
        print("  FATAL ERROR")
        print("!" * 60)
        print(traceback.format_exc())
        try:
            log_path = os.path.join(MEDIA_ROOT, "error_log_video.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 80 + "\n" + traceback.format_exc() + "\n")
            print(f"  Saved: {log_path}")
        except Exception:
            pass
    finally:
        try:
            input("  Press Enter to exit...")
        except Exception:
            pass
