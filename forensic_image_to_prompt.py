r"""
====
  FORENSIC IMAGE-TO-PROMPT ENGINE  |  Gemini Flash (auto model fallback)
  - ALL libraries ONLY in:  C:\AKT Media Tools
  - Images + output in:     folder of this .py  \  Image to Prompt
  - Done folder:            Image to Prompt Done  (files renamed: Image 1 xxx.jpg)
  - Force-install packages into C:\AKT Media Tools\Lib\site-packages
  - Auto UAC elevation when needed
  - Continuous numbering | Master + Forensic | Auto-Done + Dedup
  - Naming (Ultimate Media Tool style): Image 1 originalname.jpg
  - ONE-CLICK: Gemini API keys from USER_CONFIG only (top block) — 12-key rotation
  - Model auto-fallback: gemini-3.6-flash → 3.5 → 3.1-lite → 2.5 → 2.0
  - If USER_THEMATIC_OVERRIDES are blank → pure original image (zero manipulation)
  - 10-minute active / 10-minute pause loop (API friendly)
  - Image order: EXIF Date created FIRST (earliest first) → file created → mtime → name
  - Key-switch delay: 600 seconds between API keys (same-IP multi-account protection)
  - URL Picker: "Image to Prompt URL Picker.txt" in script folder
      * auto-created if missing
      * if any URL present → download + process first
      * after job completes → URL erased from picker (remaining = unfinished balance)
      * completed URLs archived in "Image to Prompt URL Picker Done.txt"
      * job record (files + key RPM/RPD balance) → "Image to Prompt Job Log.txt"
      * permanent download failures → "Image to Prompt URL Picker Failed.txt"
      * if picker empty → Enter URL prompt (8s auto-skip) then local images
  - Download: direct image via urllib | Instagram/social via gallery-dl + yt-dlp
    (photo carousels: 1 best thumbnail per slide, not all quality variants)
====
"""

# ====
# INSTRUCTIONS
# ====
# 1. Put Gemini API keys in USER_CONFIG (one per numbered slot).
# 2. Leave thematic overrides blank for pure original reconstruction.
# 3. Put image/social URLs in "Image to Prompt URL Picker.txt" OR paste at 8s prompt.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
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
    from PIL import Image, UnidentifiedImageError
except Exception as e:
    print(f"  FATAL: Pillow import failed: {e}")
    _pause_exit(1)

try:
    from google import genai
except Exception as e:
    print(f"  FATAL: google-genai import failed: {e}")
    print(f'  Try: py -m pip install --upgrade --target "{SITE_PACKAGES}" google-genai Pillow')
    _pause_exit(1)

SCRIPT_DIR            = Path(MEDIA_ROOT)
IMAGE_FOLDER          = SCRIPT_DIR / "Image to Prompt"
DONE_FOLDER           = IMAGE_FOLDER / "Image to Prompt Done"
OUTPUT_COMBINED_FILE  = IMAGE_FOLDER / "combined_image_output.txt"
URL_PICKER_FILE       = SCRIPT_DIR / "Image to Prompt URL Picker.txt"
URL_PICKER_FAILED     = SCRIPT_DIR / "Image to Prompt URL Picker Failed.txt"
URL_PICKER_DONE       = SCRIPT_DIR / "Image to Prompt URL Picker Done.txt"
JOB_LOG_FILE          = SCRIPT_DIR / "Image to Prompt Job Log.txt"

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"}

# Ultimate Media Tool-style rename: "Image 1 originalname.jpg"
_RE_DONE_NAME = re.compile(r"(?i)^Image(?:\s+No\.)?\s+(\d+)\s+")


def _is_already_named_output(filename: str) -> bool:
    """Skip files already renamed as Image N ... (or legacy Image No. N ...)."""
    return bool(_RE_DONE_NAME.match(filename or ""))


def _safe_filename(name: str) -> str:
    """Sanitize like Ultimate Media Tool (Windows-illegal chars → _)."""
    return re.sub(r'[<>:"/\\|?*]', "_", name or "image")

REQUEST_DELAY_SEC     = 5
MAX_RETRIES           = 4
RETRY_BASE_DELAY      = 8
MAX_IMAGE_PX          = 3072
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


FORENSIC_SYSTEM_PROMPT = """
You are a world-class forensic image analyst and elite AI prompt engineer.
Your sole mission: produce a prompt so precise that a diffusion model (Midjourney v6,
Stable Diffusion XL, FLUX) will reconstruct the original image with near-zero deviation.

=== ABSOLUTE RULE — ZERO TEXT POLICY ===
The source image may contain text, typography, watermarks, logos, subtitles, or
numbers in ANY language. You MUST completely ignore all of it.
Do NOT describe it, transcribe it, paraphrase it, or instruct the model to render any
text whatsoever. Treat the entire image as if it never contained a single letter or digit.
Any violation of this rule makes the entire output worthless.

=== YOUR ANALYSIS PROTOCOL ===
Examine the image with forensic precision across these 12 dimensions:

1.  SUBJECT & ANATOMY
    - Species, gender, age range, build, skin/fur/surface tone with specific descriptors
      (e.g., "deep umber skin with visible muscle striations", not just "dark skin")
    - Every visible garment: exact fabric drape, color, pattern, and physical state
      (torn, pristine, wet, layered)
    - Accessories, props, and weapons: their exact material (rusted iron, polished brass),
      spatial position (held at waist height in right hand, pointing 30 degrees upward),
      and physical condition

2.  POSE & SPATIAL GEOMETRY
    - Body orientation relative to camera (3/4 view, full frontal, profile)
    - Limb angles — describe as clock positions or compass directions
    - Weight distribution and centre of gravity (lunging forward, weight on left foot)
    - Negative space usage (isolated figure vs. embedded in scene)

3.  BACKGROUND & ENVIRONMENT
    - Exact background color with descriptive specificity
      (e.g., "flat muted cream, hex approximately #F0EAD6" rather than "beige")
    - Background texture (smooth paper, canvas grain, vignette, gradient from bottom)
    - Environmental elements (ground surface, sky, architectural details, props)
    - Depth of field — is the background sharp, blurred, or completely flat/abstract?

4.  ARTISTIC MEDIUM & EXECUTION
    - Identify the exact medium with clinical precision:
      * Photography: sensor size feel, lens focal length estimate, film stock or digital
      * Illustration: vector, cel-shaded, ink wash, gouache, watercolor, airbrush
      * Digital painting: brush types, rendering engine feel (Procreate, Photoshop)
      * Mixed media: describe exactly which elements are which medium
    - Line work: present or absent? Weight (hairline, medium, bold), consistency (uniform vs. tapered)
    - Rendering style: flat shading, cell shading, painterly, hyper-realistic, impressionistic

5.  TEXTURE & SURFACE IMPERFECTIONS
    - Describe EVERY texture layer visible:
      * Ink splatters (size, distribution, opacity)
      * Grunge overlays (paper texture, rust, noise, film grain)
      * Distressed edges, halftone dots, screen printing artifacts
      * Brush stroke direction and visible bristle marks
      * Digital noise, chromatic aberration, lens flare artifacts
    - If the surface is perfectly clean and smooth, state that explicitly

6.  LIGHTING ARCHITECTURE
    - Number of light sources and their approximate positions (key light upper-right,
      fill light lower-left, rim light behind)
    - Light quality: hard (sharp shadows), soft (diffused, gradual falloff), or flat
    - Shadow behavior: opacity, color of shadows (black, blue-tinted, warm), edge hardness
    - Highlight behavior: specular spots, broad soft highlights, subsurface scattering
    - Overall contrast level: low-key, high-key, high-contrast, flat

7.  COLOR PALETTE — FORENSIC LEVEL
    - List every dominant color as a descriptive + approximate hex code pairing
      (e.g., "saffron orange: approximately #E8871A")
    - Color temperature of the overall image (cool, warm, neutral)
    - Saturation level (desaturated/muted, fully saturated, oversaturated)
    - Color relationships: monochromatic, complementary, split-complementary, triadic
    - Any color grading effects (sepia wash, cross-processing, teal-and-orange grade)

8.  COMPOSITION & FRAMING
    - Shot type: extreme close-up, close-up, medium, medium-wide, wide, extreme wide
    - Camera angle: eye level, low angle, high angle, Dutch tilt, bird's eye, worm's eye
    - Rule of thirds placement, golden ratio alignment, or dead-center placement
    - Aspect ratio feel (square, landscape 16:9, portrait 4:5, panoramic)
    - Any compositional tension, symmetry, or asymmetry

9.  MOOD & ATMOSPHERE
    - Emotional register: describe the feeling in 3-5 precise adjectives
    - Time-of-day feel (if applicable): pre-dawn, golden hour, blue hour, midday
    - Cultural or genre aesthetic (e.g., South Asian mythological epic, 1980s sci-fi,
      Edo period Japan, Afrofuturism, Nordic noir)

10. MOTION & DYNAMISM
    - Static or dynamic? Describe implied motion direction and energy
    - Motion blur, speed lines, or freeze-frame energy
    - Particle effects: dust, sparks, smoke, rain, petals, energy beams

11. RENDERING QUALITY DESCRIPTORS
    - Identify the target quality tier for the reconstruction prompt:
      (masterpiece, professional illustration, concept art, raw sketch, etc.)
    - Any visible compression artifacts or intentional lo-fi aesthetics
    - Resolution feel: sharp and crisp, soft-focus dream quality, gritty low-res

12. NEGATIVE SPACE & INTENTIONAL OMISSIONS
    - What is deliberately absent that defines the composition?
    - Is the figure isolated? Is the background stripped to pure abstraction?

=== OUTPUT FORMAT ===
Return a single, valid JSON object. No markdown fences, no preamble, no explanation.
Use this exact schema:

{
  "forensic_analysis": {
    "subject_anatomy": "<detailed string>",
    "pose_geometry": "<detailed string>",
    "background_environment": "<detailed string>",
    "artistic_medium": "<detailed string>",
    "texture_imperfections": "<detailed string>",
    "lighting_architecture": "<detailed string>",
    "color_palette": "<detailed string>",
    "composition_framing": "<detailed string>",
    "mood_atmosphere": "<detailed string>",
    "motion_dynamism": "<detailed string>",
    "rendering_quality": "<detailed string>",
    "negative_space": "<detailed string>"
  },
  "master_prompt": "<A single, dense, synthesized reconstruction prompt of 150-300 words that fuses ALL 12 dimensions above into one cohesive Midjourney/SD prompt. Must be purely visual. Must contain zero text instructions. Must include recommended aspect ratio and quality suffix flags at the end.>"
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
 |   FORENSIC IMAGE-TO-PROMPT ENGINE  (ONE-CLICK)                 |
 |   Libs: C:\\AKT Media Tools  |  Naming: Image 1 xxx.jpg            |
 |   Gemini Flash (auto model) | Master + Forensic | Auto-Done + Dedup |
 |   12-Key Rotation | Active 10 min / Pause 10 min loop          |
 |   Sort: EXIF Date created FIRST (earliest first)               |
 |   Key-switch delay: 600s | URL Picker + 8s Enter-URL prompt    |
 |   Download: direct | gallery-dl + yt-dlp (1 thumb per slide)   |
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


_EXIF_DATE_TAGS = (36867, 36868, 306)
_EXIF_DATE_FORMATS = (
    "%Y:%m:%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y:%m:%d %H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y:%m:%d",
    "%Y-%m-%d",
)


def _parse_exif_datetime(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            return None
    if not isinstance(value, str):
        value = str(value)
    s = value.strip().strip("\x00").strip()
    if not s:
        return None
    for fmt in _EXIF_DATE_FORMATS:
        try:
            core = s[:26].rstrip("Z")
            clean_fmt = fmt.replace("%z", "").rstrip("Z") if "%z" not in fmt else fmt
            dt = datetime.strptime(core, clean_fmt)
            return dt.timestamp()
        except Exception:
            continue
    m = re.match(
        r"(\d{4})[:\-/.](\d{1,2})[:\-/.](\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?",
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


def _read_exif_date_created(path: Path) -> Tuple[Optional[float], str]:
    try:
        with Image.open(path) as im:
            try:
                exif = im.getexif()
            except Exception:
                exif = None
            if not exif:
                return None, ""
            ifd = None
            try:
                if hasattr(exif, "get_ifd"):
                    ifd = exif.get_ifd(0x8769)
            except Exception:
                ifd = None
            tag_labels = {
                36867: "EXIF Date created (DateTimeOriginal)",
                36868: "EXIF DateTimeDigitized",
                306:   "EXIF DateTime",
            }
            for tag_id in _EXIF_DATE_TAGS:
                raw = None
                if ifd is not None and tag_id in (36867, 36868):
                    try:
                        raw = ifd.get(tag_id)
                    except Exception:
                        raw = None
                if raw is None:
                    try:
                        raw = exif.get(tag_id)
                    except Exception:
                        raw = None
                ts = _parse_exif_datetime(raw)
                if ts is not None:
                    return ts, tag_labels.get(tag_id, "EXIF")
    except Exception:
        pass
    return None, ""


def _filesystem_date_created(path: Path) -> Tuple[Optional[float], str]:
    try:
        st = path.stat()
        birth = getattr(st, "st_birthtime", None)
        if birth is not None:
            return float(birth), "File Date created (birthtime)"
        return float(st.st_ctime), "File Date created"
    except Exception:
        return None, ""


def get_image_sort_timestamp(path: Path) -> Tuple[float, str, str]:
    name_key = path.name.lower()
    ts, source = _read_exif_date_created(path)
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


def find_all_images() -> List[Path]:
    IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    found = []
    seen_keys = set()
    search_dirs = [IMAGE_FOLDER, SCRIPT_DIR]
    print_step("~", "Scanning for images...", C.DIM)
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
                    if key not in seen_keys:
                        seen_keys.add(key)
                        found.append(p)
                        loc = "Image to Prompt" if folder == IMAGE_FOLDER else "script folder"
                        print(f"      {C.GREEN}Found:{C.RESET} {p.name}  ({loc})")
        except Exception as e:
            print_step("!", f"Scan error in {folder}: {e}", C.YELLOW)
    print_step("~", "Sorting by EXIF Date created (earliest first)...", C.DIM)
    keyed = []
    for p in found:
        ts, source, name_key = get_image_sort_timestamp(p)
        keyed.append((ts, name_key, p, source))
        print(f"      {C.DIM}{p.name}  →  {format_ts(ts)}  [{source}]{C.RESET}")
    keyed.sort(key=lambda item: (item[0], item[1]))
    sorted_paths = [item[2] for item in keyed]
    if sorted_paths:
        print_step("+", f"Order locked: earliest Date created → latest ({len(sorted_paths)} image(s))", C.GREEN)
    return sorted_paths


def prepare_image(path: Path) -> Optional[Image.Image]:
    try:
        img = Image.open(path)
        img.verify()
        img = Image.open(path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        max_dim = max(img.size)
        if max_dim > MAX_IMAGE_PX:
            scale  = MAX_IMAGE_PX / max_dim
            new_sz = (int(img.width * scale), int(img.height * scale))
            img    = img.resize(new_sz, Image.Resampling.LANCZOS)
        return img
    except Exception as exc:
        print_step("!", f"Failed to prepare image {path.name}: {exc}", C.RED)
        return None


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


def call_gemini_with_retry(rotator: "GeminiApiKeyRotator", img: Image.Image, filename: str) -> Optional[dict]:
    global _RESOLVED_GEMINI_MODEL
    delay = RETRY_BASE_DELAY
    final_system_prompt = FORENSIC_SYSTEM_PROMPT
    overrides_empty = is_overrides_empty(USER_THEMATIC_OVERRIDES)
    clean_overrides = get_clean_overrides()

    if overrides_empty:
        print_step("~", "Overrides are blank → Pure original image mode (no style change)", C.CYAN)
        pure_block = """
=== PURE ORIGINAL MODE (NO USER OVERRIDES) ===
The user has left all thematic overrides blank.
You MUST describe and recreate the image EXACTLY as it appears.
- Do NOT force any art style, ink, grunge, silhouette, abstract, or any other look.
- Do NOT invent or change clothing, face, body, weapons, texture, or mood.
- Stay 100% faithful to the real visual content, lighting, colors, composition and pose.
This is a pure forensic reconstruction with zero creative manipulation.
"""
        final_system_prompt = final_system_prompt.replace(
            "=== OUTPUT FORMAT ===",
            pure_block + "\n=== OUTPUT FORMAT ==="
        )
    else:
        print_step("~", "User overrides detected → Applying thematic instructions", C.YELLOW)
        override_block = f"""
=== USER THEMATIC OVERRIDES (HIGHEST PRIORITY) ===
These instructions OVERRIDE the original image if they conflict.
You MUST force both forensic_analysis and especially the master_prompt to obey them:

"{clean_overrides}"

"""
        final_system_prompt = final_system_prompt.replace(
            "=== OUTPUT FORMAT ===",
            override_block + "=== OUTPUT FORMAT ==="
        )

    for attempt in range(1, MAX_RETRIES + 1):
        key, user_id, idx = rotator.get_current_key()
        if idx == -1:
            print_step("!", "All API keys exhausted / cooling down → waiting 60s before retry", C.YELLOW)
            time.sleep(60)
            continue
        client = genai.Client(api_key=key)
        last_err = ""
        model_404_all = True
        # Count one attempt against the key, not one per model fallback try
        rotator.record_request(idx)
        for model_name in _model_candidates():
            try:
                print_step(
                    "~",
                    f"Sending to {model_name}  (Key #{idx + 1} / {_mask_user_id(user_id or '')})...",
                    C.DIM,
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=[final_system_prompt, img],
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
                    print_step("~", f"[{filename}] Attempt {attempt}: rate-limit/quota on Key #{idx + 1}", C.YELLOW)
                    rotator.handle_rate_limit(idx, retry_after)
                    break
                if ("401" in err_str or "403" in err_str
                        or "permission_denied" in low or "permission denied" in low
                        or "unauthorized" in low or "api key not valid" in low
                        or "api_key_invalid" in low or "invalid api key" in low):
                    model_404_all = False
                    print_step("~", f"[{filename}] Attempt {attempt}: auth error on Key #{idx + 1}", C.YELLOW)
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
            # exhausted model list
            if model_404_all:
                print_step(
                    "!",
                    f"[{filename}] No usable Gemini model (tried {', '.join(GEMINI_MODEL_CANDIDATES)})",
                    C.RED,
                )
                print_step("~", f"Last error: {last_err[:160]}", C.DIM)
                # Do NOT disable the API key — this is a model-ID issue, not auth.
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
            headers={"User-Agent": "Mozilla/5.0 (ImageToPrompt/1.1)"},
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
            req = urllib.request.Request(latest, headers={"User-Agent": "Mozilla/5.0 (ImageToPrompt/1.1)"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(YTDLP_PATH, "wb") as out:
                shutil.copyfileobj(resp, out)
            if YTDLP_PATH.exists() and YTDLP_PATH.stat().st_size > 100_000:
                print_step("+", f"yt-dlp ready (latest): {YTDLP_PATH}", C.GREEN)
                return True
        except Exception as e2:
            print_step("!", f"yt-dlp latest fallback failed: {e2}", C.RED)
    return False


def _is_direct_image_url(url: str) -> bool:
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
    )
    return any(h in low for h in hosts)


def _is_instagram_url(url: str) -> bool:
    low = url.lower()
    return "instagram.com" in low or "instagr.am" in low


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


def _thumbnail_group_key(path: Path) -> str:
    """
    Group yt-dlp multi-quality thumbnails of the same carousel slide.
    e.g. 'DbYGxpiCXHs_1_Video by parasmadan.in.0.jpg'
      →  'DbYGxpiCXHs_1_Video by parasmadan.in'
    """
    name = path.name
    # Strip trailing .N before extension (thumbnail quality index 0..N)
    m = re.match(r"^(.*)\.(\d+)(\.[^.]+)$", name)
    if m:
        return m.group(1).lower()
    return path.stem.lower()


def _dedupe_thumbnail_variants(images: List[Path]) -> List[Path]:
    """
    Keep ONE best still per carousel slide (largest file). Delete the rest.
    Prevents 8 slides × 13 thumbnail sizes = 104 junk images.
    """
    if not images:
        return []
    groups: Dict[str, List[Path]] = {}
    for p in images:
        groups.setdefault(_thumbnail_group_key(p), []).append(p)

    kept: List[Path] = []
    removed = 0
    for key, paths in groups.items():
        if len(paths) == 1:
            kept.append(paths[0])
            continue
        # Prefer largest bytes (usually highest-res Instagram thumbnail)
        paths_sorted = sorted(
            paths,
            key=lambda x: (x.stat().st_size if x.exists() else 0, x.name),
            reverse=True,
        )
        best = paths_sorted[0]
        kept.append(best)
        for junk in paths_sorted[1:]:
            try:
                junk.unlink(missing_ok=True)
                removed += 1
            except Exception:
                pass
    if removed:
        print_step("~", f"Kept 1 thumbnail per slide — removed {removed} lower-res variant(s)", C.CYAN)
    kept.sort(key=lambda x: x.name.lower())
    return kept


def _collect_new_valid_images(dest_folder: Path, before_meta: Dict[str, Tuple[int, int]]) -> List[Path]:
    """Return new OR updated valid still images under dest_folder, flattened + deduped."""
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
                continue  # unchanged
            if p.suffix.lower() not in VALID_EXTENSIONS:
                continue
            try:
                with Image.open(p) as im:
                    im.verify()
                found.append(p)
            except Exception:
                continue
    except Exception:
        pass

    # Flatten nested gallery-dl downloads into IMAGE_FOLDER for consistent processing
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

    return _dedupe_thumbnail_variants(flattened)


def _gallery_dl_available() -> bool:
    return _package_present_in_target("gallery_dl", "gallery-dl")


def _http_get_bytes(url: str, referer: str = "https://www.instagram.com/", timeout: int = 30) -> Optional[bytes]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def _http_download_image(url: str, dest: Path, referer: str = "https://www.instagram.com/") -> bool:
    data = _http_get_bytes(url, referer=referer, timeout=30)
    if not data or len(data) < 100:
        return False
    try:
        with open(dest, "wb") as out:
            out.write(data)
        with Image.open(dest) as im:
            im.verify()
        return True
    except Exception:
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def _best_image_url_from_entry(entry: dict) -> Optional[str]:
    """Pick the largest still-image URL from a yt-dlp info dict."""
    if not entry or not isinstance(entry, dict):
        return None

    candidates: List[Tuple[int, str]] = []

    for f in (entry.get("formats") or []):
        if not isinstance(f, dict):
            continue
        u = f.get("url")
        if not u:
            continue
        ext = (f.get("ext") or "").lower()
        vcodec = (f.get("vcodec") or "none").lower()
        acodec = (f.get("acodec") or "none").lower()
        # Still image formats (Instagram photo slides)
        is_image = ext in ("jpg", "jpeg", "png", "webp") or (
            vcodec in ("", "none") and acodec in ("", "none") and ext not in ("mp4", "m4a", "webm", "mkv")
        )
        if not is_image:
            continue
        area = int(f.get("width") or 0) * int(f.get("height") or 0)
        candidates.append((area, u))

    for t in (entry.get("thumbnails") or []):
        if not isinstance(t, dict):
            continue
        u = t.get("url")
        if not u:
            continue
        area = int(t.get("width") or 0) * int(t.get("height") or 0)
        # Prefer higher id / preference when present
        pref = int(t.get("preference") or t.get("id") or 0)
        candidates.append((area * 10 + pref, u))

    thumb = entry.get("thumbnail")
    if thumb:
        candidates.append((1, thumb))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _guess_ext_from_url(url: str) -> str:
    low = (url or "").lower().split("?")[0]
    for cand in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if low.endswith(cand):
            return cand
    return ".jpg"


def download_instagram_fast(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    """
    FAST Instagram path (carousel-friendly):
      1) One yt-dlp -J metadata fetch (no media download)
      2) Parallel CDN image downloads (ThreadPool)
    Much faster than sequential write-thumbnail / gallery-dl.
    """
    if not _ensure_ytdlp():
        return [], "yt-dlp not available"
    dest_folder.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print_step("~", "Instagram FAST: metadata only (yt-dlp -J)...", C.CYAN)
    cmd = [
        str(YTDLP_PATH),
        url,
        "-J",
        "--ignore-no-formats-error",
        "--no-warnings",
        "--socket-timeout", "15",
        "--retries", "2",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=75,
        )
    except subprocess.TimeoutExpired:
        return [], "yt-dlp -J timed out (75s)"
    except Exception as e:
        return [], f"yt-dlp -J failed: {e}"

    raw = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if not raw:
        return [], err[-500:] or "empty yt-dlp -J output"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [], f"JSON parse failed: {e} | stderr={err[-200:]}"

    if data.get("_type") == "playlist":
        entries = [e for e in (data.get("entries") or []) if isinstance(e, dict)]
    else:
        entries = [data]

    jobs: List[Tuple[str, Path]] = []
    for i, entry in enumerate(entries, start=1):
        img_url = _best_image_url_from_entry(entry)
        if not img_url:
            continue
        eid = re.sub(r"[^\w\-]+", "_", str(entry.get("id") or i))[:48]
        ext = _guess_ext_from_url(img_url)
        dest = dest_folder / f"{eid}_{i}{ext}"
        n = 1
        while dest.exists():
            dest = dest_folder / f"{eid}_{i}_{n}{ext}"
            n += 1
        jobs.append((img_url, dest))

    if not jobs:
        return [], "no image URLs found in Instagram metadata"

    print_step("~", f"Instagram FAST: parallel download of {len(jobs)} image(s)...", C.CYAN)
    saved: List[Path] = []

    def _one(job: Tuple[str, Path]) -> Optional[Path]:
        img_url, dest = job
        if _http_download_image(img_url, dest, referer=url):
            return dest
        return None

    workers = min(8, max(1, len(jobs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, j) for j in jobs]
        for fut in as_completed(futures):
            try:
                p = fut.result()
            except Exception:
                p = None
            if p is not None:
                saved.append(p)
                print_step("+", f"Saved → {p.name} ({p.stat().st_size} bytes)", C.GREEN)

    elapsed = time.time() - t0
    saved.sort(key=lambda x: x.name.lower())
    print_step(
        "+",
        f"Instagram FAST: {len(saved)}/{len(jobs)} image(s) in {elapsed:.1f}s",
        C.GREEN if saved else C.YELLOW,
    )
    if not saved:
        return [], f"parallel CDN download failed ({len(jobs)} urls) | {err[-200:]}"
    return saved, f"instagram-fast ok {len(saved)}/{len(jobs)} in {elapsed:.1f}s"


def download_via_gallery_dl(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    """Optional fallback for Pinterest/Reddit galleries (not used first for Instagram)."""
    if not _gallery_dl_available():
        return [], "gallery-dl not installed"
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    cmd = [
        sys.executable, "-m", "gallery_dl",
        "--dest", str(dest_folder),
        "-f", "{id}_{num}.{extension}",
        "--filter", "extension in ('jpg','jpeg','png','webp','gif')",
        url,
    ]
    print_step("~", f"gallery-dl: {url[:80]}...", C.DIM)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            cwd=str(dest_folder),
            env={**os.environ, "PYTHONPATH": SITE_PACKAGES + os.pathsep + os.environ.get("PYTHONPATH", "")},
        )
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        images = _collect_new_valid_images(dest_folder, before)
        if images:
            for p in images:
                print_step("+", f"Saved via gallery-dl → {p.name}", C.GREEN)
            return images, log
        return [], log
    except subprocess.TimeoutExpired:
        return [], "gallery-dl timed out (120s)"
    except Exception as e:
        return [], f"gallery-dl failed: {e}"


def download_via_ytdlp(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    """
    Quiet yt-dlp fallback.
    Instagram: single thumbs-only pass (no slow media pass).
    Other social: one media+thumb pass with ignore-no-formats-error.
    """
    if not _ensure_ytdlp():
        print_step("!", "yt-dlp not available — cannot download social media posts", C.RED)
        return [], "yt-dlp not available"
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    out_tmpl = str(dest_folder / "%(id)s_%(playlist_index|)s%(playlist_index&_)s%(title).40B.%(ext)s")

    if _is_instagram_url(url):
        cmd = [
            str(YTDLP_PATH), url,
            "-o", out_tmpl,
            "--skip-download",
            "--ignore-no-formats-error",
            "--write-thumbnail",
            "--convert-thumbnails", "jpg",
            "--no-mtime",
            "--no-warnings",
            "--socket-timeout", "15",
            "--retries", "2",
        ]
        label = "ig-thumbs"
    else:
        cmd = [
            str(YTDLP_PATH), url,
            "-o", out_tmpl,
            "--ignore-no-formats-error",
            "--write-thumbnail",
            "--convert-thumbnails", "jpg",
            "--no-mtime",
            "--no-warnings",
            "--socket-timeout", "20",
            "--retries", "2",
        ]
        label = "media+thumbs"

    print_step("~", f"yt-dlp [{label}]: {url[:80]}...", C.DIM)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        # Keep console quiet — only show errors
        for line in out.splitlines():
            if "error" in line.lower():
                print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
        images = _collect_new_valid_images(dest_folder, before)
        if images:
            for p in images:
                print_step("+", f"Saved via yt-dlp → {p.name}", C.GREEN)
            return images, out
        print_step("!", "yt-dlp finished but no new still image", C.YELLOW)
        return [], out
    except subprocess.TimeoutExpired:
        print_step("!", f"yt-dlp [{label}] timed out (90s)", C.RED)
        return [], f"yt-dlp [{label}] timed out"
    except Exception as e:
        print_step("!", f"yt-dlp [{label}] failed: {e}", C.RED)
        return [], f"yt-dlp [{label}] failed: {e}"


def download_image_from_url(url: str, dest_folder: Path) -> Tuple[List[Path], str, bool]:
    """
    Smart download (speed-first):
      1. Direct image URL → urllib
      2. Instagram → FAST metadata + parallel CDN (then quiet yt-dlp fallback)
      3. Other social → quiet yt-dlp, then gallery-dl
    Returns: (images, log, permanent_failure_hint)
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    logs: List[str] = []

    if _is_direct_image_url(url) or not _is_social_media_url(url):
        path_part = url.split("?")[0].rstrip("/")
        ext = Path(path_part).suffix.lower()
        if ext not in VALID_EXTENSIONS:
            ext = ".jpg"
        stem = re.sub(r"[^\w\-]+", "_", Path(path_part).stem)[:80] or "downloaded_image"
        dest = dest_folder / f"{stem}{ext}"
        n = 1
        while dest.exists():
            dest = dest_folder / f"{stem}_{n}{ext}"
            n += 1

        print_step("~", f"Downloading (direct): {url[:100]}...", C.DIM)
        if _http_download_image(url, dest, referer=url):
            print_step("+", f"Saved → {dest.name} ({dest.stat().st_size} bytes)", C.GREEN)
            return [dest], "direct ok", False
        logs.append("direct download failed")
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        if _is_direct_image_url(url):
            return [], "\n".join(logs), True
        if not _is_social_media_url(url):
            print_step("~", "Direct failed — trying social downloaders...", C.DIM)

    # Instagram: FAST path first (skip slow gallery-dl / dual yt-dlp passes)
    if _is_instagram_url(url):
        imgs, log = download_instagram_fast(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        print_step("~", "FAST path incomplete — quiet yt-dlp thumbnail fallback...", C.DIM)
        imgs, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        return [], "\n".join(logs), _looks_permanent_download_error("\n".join(logs))

    if "pinterest.com" in url.lower() or "reddit.com" in url.lower():
        imgs, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        imgs, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        return [], "\n".join(logs), _looks_permanent_download_error("\n".join(logs))

    if _is_social_media_url(url):
        imgs, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        imgs, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        return [], "\n".join(logs), _looks_permanent_download_error("\n".join(logs))

    return [], "\n".join(logs), False


def get_url_with_timeout(timeout_sec: float = 8.0) -> Optional[str]:
    print()
    print(f"  {C.CYAN}{C.BOLD}No URLs in {URL_PICKER_FILE.name}{C.RESET}")
    print(f"  {C.DIM}Paste image/social URL, or wait {int(timeout_sec)}s / Enter → local images.{C.RESET}")
    if not HAS_MSVCRT:
        try:
            raw = input(f"  {C.YELLOW}Enter image URL (or Enter skip): {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
    else:
        print(f"  {C.YELLOW}Enter image URL (Auto-skips in {int(timeout_sec)}s): {C.RESET}", end="", flush=True)
        raw = ""
        start = time.time()
        while time.time() - start < timeout_sec:
            if msvcrt.kbhit():
                raw = input()
                break
            time.sleep(0.1)
        print()
    if not raw or not raw.strip():
        print_step("~", "No URL entered / timeout → using local images only", C.DIM)
        return None
    m = re.search(r"https?://[^\s<>\"'\])\}]+", raw.strip(), re.IGNORECASE)
    if not m:
        print_step("!", "No valid http(s) URL detected — using local images only", C.YELLOW)
        return None
    url = m.group(0).rstrip(".,;:)")
    print_step("+", f"Using entered URL: {url[:90]}...", C.GREEN)
    return url


def get_starting_number() -> int:
    """
    Continuous numbering across runs.
    Reads highest 'Image N' / legacy 'Image No. N' from output log and Done folder.
    """
    last = 0
    # From combined output log
    if OUTPUT_COMBINED_FILE.exists():
        try:
            with open(OUTPUT_COMBINED_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"(?i)^Image(?:\s+No\.)?\s+(\d+)\b", line.strip())
                    if m:
                        last = max(last, int(m.group(1)))
        except Exception:
            pass
    # From Done folder filenames: "Image 1 foo.jpg"
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
    return last + 1


def move_to_done(path: Path, image_num: int):
    """Rename like Ultimate Media Tool: Image 1 originalname.jpg"""
    DONE_FOLDER.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(path.name)
    new_name = f"Image {image_num} {safe_name}"
    target = DONE_FOLDER / new_name
    counter = 1
    while target.exists():
        stem = Path(safe_name).stem
        ext = Path(safe_name).suffix
        target = DONE_FOLDER / f"Image {image_num} {stem}_{counter}{ext}"
        counter += 1
    try:
        shutil.move(str(path), str(target))
        print_step("+", f"Moved → Image to Prompt Done\\{target.name}", C.GREEN)
        return target.name
    except Exception as e:
        print_step("!", f"Could not move to Done: {e}", C.YELLOW)
        return new_name


def manage_files() -> Tuple[List[Path], int]:
    # Collapse leftover yt-dlp multi-quality thumbnails from previous runs
    if IMAGE_FOLDER.exists():
        existing = [
            p for p in IMAGE_FOLDER.iterdir()
            if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS
            and not _is_already_named_output(p.name)
        ]
        if existing:
            _dedupe_thumbnail_variants(existing)

    seen: Dict[str, str] = {}
    if DONE_FOLDER.exists():
        print_step("~", "Scanning Done folder for multi-run deduplication...", C.DIM)
        for p in DONE_FOLDER.iterdir():
            if p.is_file() and p.suffix.lower() in VALID_EXTENSIONS:
                try:
                    seen[file_md5(p)] = p.name
                except Exception:
                    pass
        print_step("+", f"Loaded {len(seen)} hash(es) from previously processed images.", C.GREEN)
    all_images = find_all_images()
    images = []
    for p in all_images:
        try:
            md5 = file_md5(p)
            if md5 in seen:
                print_step("~", f"Duplicate of Done/{seen[md5]} → skipping {p.name}", C.YELLOW)
            else:
                images.append(p)
        except Exception:
            images.append(p)
    return images, get_starting_number()


def write_output(num: int, filename: str, master_prompt: str, forensic_analysis: dict):
    """Write like Ultimate Media Tool log titles: Image 1 (filename)"""
    IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_COMBINED_FILE, "a", encoding="utf-8") as f:
        f.write(f"Image {num} ({filename})\n\n")
        f.write("\t==== MASTER PROMPT (Copy-Paste Ready) ====\n")
        f.write(f"\t{master_prompt}\n\n")
        f.write("\t==== FORENSIC ANALYSIS ====\n")
        if isinstance(forensic_analysis, dict) and forensic_analysis:
            for key, value in forensic_analysis.items():
                f.write(f"\t{key.replace('_', ' ').title()}:\n")
                f.write(f"\t  {value}\n\n")
        else:
            json_str = json.dumps(forensic_analysis or {}, ensure_ascii=False, indent=4)
            for line in json_str.split("\n"):
                f.write(f"\t{line}\n")
            f.write("\n")
        f.write("=" * 90 + "\n\n")


def main():
    IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)
    print_banner()

    print(f"  {C.DIM}Libraries : {LIB_ROOT}{C.RESET}")
    print(f"  {C.DIM}Images    : {IMAGE_FOLDER}{C.RESET}")
    print(f"  {C.DIM}Done      : {DONE_FOLDER}{C.RESET}")
    print(f"  {C.DIM}Output    : {OUTPUT_COMBINED_FILE}{C.RESET}")
    print(f"  {C.DIM}Also scans script folder for any image files{C.RESET}")
    print(f"  {C.DIM}Sort      : EXIF Date created FIRST → file created → mtime (earliest first){C.RESET}")
    print(f"  {C.DIM}Key delay : {GeminiApiKeyRotator.KEY_SWITCH_DELAY_SECONDS}s between API key switches{C.RESET}\n")

    if is_overrides_empty(USER_THEMATIC_OVERRIDES):
        print_step("+", "Mode: PURE ORIGINAL (overrides blank → no style change)", C.GREEN)
    else:
        print_step("+", "Mode: USER OVERRIDES ACTIVE (style will be forced)", C.YELLOW)

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

    print()
    ensure_url_picker_file()
    picker_urls = load_urls_from_picker()

    def process_image_list(
        images: List[Path], serial_start: int
    ) -> Tuple[int, int, int, List[str], List[str]]:
        if not images:
            return 0, 0, serial_start, [], []
        serial = serial_start
        success = 0
        failed = 0
        processed_ok: List[str] = []
        processed_fail: List[str] = []
        run_start_time = time.time()
        next_pause_time = run_start_time + (MAX_RUN_TIME_MIN * 60)

        print_step("+", f"Processing {len(images)} image(s). Starting at Image {serial}\n", C.GREEN)
        print(f"  {C.BOLD}Active Run Time:{C.RESET} {MAX_RUN_TIME_MIN} mins  |  "
              f"{C.BOLD}Pause Time:{C.RESET} {PAUSE_TIME_MIN} mins\n")

        for idx, image_path in enumerate(images, 1):
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

            print_progress(idx, len(images), image_path.name)
            img = prepare_image(image_path)
            if img is None:
                failed += 1
                processed_fail.append(image_path.name)
                continue

            print_step("~", f"Prepared {img.size[0]}x{img.size[1]}px", C.DIM)
            parsed = call_gemini_with_retry(rotator, img, image_path.name)

            if parsed is None:
                failed += 1
                processed_fail.append(image_path.name)
                print_step("!", f"Failed on {image_path.name}\n", C.RED)
            else:
                master = parsed.get("master_prompt", "")
                forensic = parsed.get("forensic_analysis", {})
                preview = textwrap.shorten(str(master), width=120, placeholder="...")
                print_step("+", f"Analysis complete → Image {serial}", C.GREEN)
                print(f"      {C.DIM}Preview: {preview}{C.RESET}")
                write_output(serial, image_path.name, master, forensic)
                done_name = move_to_done(image_path, serial)
                print_step("+", f"{done_name} written successfully\n", C.GREEN)
                processed_ok.append(f"Image {serial} — {done_name}")
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
                saved_list, dl_log, permanent = download_image_from_url(url, IMAGE_FOLDER)
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
                print_step("+", f"Downloaded {len(saved_list)} still image(s) from URL", C.GREEN)
                s, f, serial, ok_names, fail_names = process_image_list(saved_list, serial)
                total_success += s
                total_failed += f
                # Job finished → erase URL from picker + write download/balance record
                finish_url_job(url, saved_list, ok_names, fail_names, s, f, rotator)
            except Exception as e:
                print_step("!", f"Picker URL job failed (URL kept in file): {e}", C.RED)
                total_dl_failed += 1
            print()
        remaining, serial2 = manage_files()
        serial = max(serial, serial2)
        if remaining:
            print_step("~", f"Also found {len(remaining)} local image(s) to process...", C.CYAN)
            s, f, serial, _, _ = process_image_list(remaining, serial)
            total_success += s
            total_failed += f
    else:
        manual_url = get_url_with_timeout(timeout_sec=8.0)
        if manual_url:
            print(f"\n  {C.CYAN}{C.BOLD}Processing manually entered URL...{C.RESET}\n")
            saved_list, dl_log, permanent = download_image_from_url(manual_url, IMAGE_FOLDER)
            if saved_list:
                print_step("+", f"Downloaded {len(saved_list)} still image(s) from URL", C.GREEN)
                s, f, serial, ok_names, fail_names = process_image_list(saved_list, serial)
                total_success += s
                total_failed += f
                # Manual URL is not in picker, but still write job record for balance tracking
                write_job_log(
                    url=manual_url,
                    downloaded_files=[p.name for p in saved_list],
                    processed_ok=ok_names,
                    processed_fail=fail_names,
                    success=s,
                    failed=f,
                    rotator=rotator,
                    status="OK (manual URL)" if s > 0 else "FAILED (manual URL)",
                )
                if s > 0:
                    archive_completed_url(manual_url, note=f"manual | {s} ok / {f} fail")
            else:
                print_step("!", "Manual URL download failed", C.YELLOW)
                if permanent:
                    print_step("~", "This looks like a permanent failure (login/private/no media).", C.DIM)
                total_dl_failed += 1
            print()

        print(f"  {C.DIM}Scanning local images...{C.RESET}")
        images, serial2 = manage_files()
        serial = max(serial, serial2)
        if not images and total_success == 0 and total_failed == 0 and total_dl_failed == 0:
            print_step("!", "No images found!", C.YELLOW)
            print(f"\n  Put your images in either:")
            print(f"    1. {IMAGE_FOLDER}")
            print(f"    2. Or next to this .py file: {SCRIPT_DIR}")
            print(f"\n  Or put image/social URLs in: {URL_PICKER_FILE.name}")
            print(f"\n  Supported: png, jpg, jpeg, webp, bmp, tiff, gif")
            print(f"  Social: Instagram photo/carousel posts via gallery-dl + yt-dlp")
            return
        if images:
            s, f, serial, _, _ = process_image_list(images, serial)
            total_success += s
            total_failed += f

    remaining_balance = load_urls_from_picker()
    print(f"\n{C.CYAN}{C.BOLD}  ==== FINISHED ===={C.RESET}")
    print_step("+", f"Successfully processed: {total_success}", C.GREEN)
    print_step("!", f"Failed image processing (still in source folder): {total_failed}",
               C.RED if total_failed else C.DIM)
    print_step("!", f"Failed URL downloads: {total_dl_failed}",
               C.RED if total_dl_failed else C.DIM)
    print_step("+", f"URL picker remaining balance: {len(remaining_balance)} URL(s)", C.CYAN)
    print(f"\n{rotator.get_status_summary()}\n")
    print(f"\n  Output file:\n  {C.CYAN}{OUTPUT_COMBINED_FILE}{C.RESET}")
    print(f"  Done folder:\n  {C.CYAN}{DONE_FOLDER}{C.RESET}")
    print(f"  URL picker (active / remaining):\n  {C.CYAN}{URL_PICKER_FILE}{C.RESET}")
    print(f"  URL picker Done (completed record):\n  {C.CYAN}{URL_PICKER_DONE}{C.RESET}")
    print(f"  Failed URLs:\n  {C.CYAN}{URL_PICKER_FAILED}{C.RESET}")
    print(f"  Job log (files + key balance):\n  {C.CYAN}{JOB_LOG_FILE}{C.RESET}\n")


if __name__ == "__main__":
    try:
        if os.name == "nt":
            try:
                os.system("title FORENSIC IMAGE-TO-PROMPT ENGINE (ONE-CLICK)")
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
            log_path = os.path.join(MEDIA_ROOT, "error_log_image.txt")
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
