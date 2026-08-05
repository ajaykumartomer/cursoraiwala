r"""
====
  ULTIMATE MEDIA TOOL v0.8
  - LIBRARIES / TOOLS only in:  C:\AKT Media Tools
  - MEDIA download + scraper in: folder of this .py file
  - Force-installs all pip packages into C:\AKT Media Tools\Lib\site-packages
  - Soft UAC only if library folder is not writable
  - ONE-CLICK: Groq API keys from USER_CONFIG only (top block) — multi-key rotation
  - Naming: Image 1 xxx | Video 1 xxx | Audio 1 xxx
  - Direct files in Combined Image/Video/Audio Scraper by AKT folders
  - Only 3 text logs outside: Combine Image/Video/Audio Scraper.txt
  - File order: Date created FIRST (earliest first) via EXIF / Media / tags
  - Groq multi-key: rotates at RPM max-1 (Groq RPM=30 → rotate at 29)
  - Key-switch delay: 600 seconds between API keys (same-IP multi-account protection)
  - Masked userIDs in console / job logs
  - URL Picker: "Ultimate Media Tool URL Picker.txt" in script folder
      * auto-created if missing
      * if any URL present → download + scrape first
      * after job completes → URL erased from picker (remaining = unfinished balance)
      * completed URLs archived in "Ultimate Media Tool URL Picker Done.txt"
      * job record (files + key RPM/RPD balance) → "Ultimate Media Tool Job Log.txt"
      * permanent download failures → "Ultimate Media Tool URL Picker Failed.txt"
      * if picker empty → Enter URL prompt (8s auto-skip) then local media
  - Download: Instagram/social via gallery-dl + yt-dlp (ignore-no-formats + media)
  - Models (2026-07 Groq):
      OCR/Vision : qwen/qwen3.6-27b  (+ live /models discovery)
      Translate  : llama-3.3-70b-versatile | openai/gpt-oss-* fallbacks
      Whisper    : whisper-large-v3
====
"""

# ====
# INSTRUCTIONS
# ====
# 1. Put Groq API keys in USER_CONFIG (one per numbered slot).
# 2. Put social URLs in "Ultimate Media Tool URL Picker.txt" OR paste at 8s prompt.
# 3. SECURITY: never commit real API keys. Rotate any key that was shared/pasted.
# ====

# ====
# USER CONFIG + API KEY  (edit only this block)
# ====
USER_CONFIG = """

1. Enter Groq API Key (userID: your_email_1@example.com):		YOUR_GROQ_API_KEY_1

2. Enter Groq API Key (userID: your_email_2@example.com):		YOUR_GROQ_API_KEY_2

3. Enter Groq API Key (userID: your_email_3@example.com):		YOUR_GROQ_API_KEY_3

4. Enter Groq API Key (userID: your_email_4@example.com):		YOUR_GROQ_API_KEY_4

5. Enter Groq API Key (userID: your_email_5@example.com):		YOUR_GROQ_API_KEY_5

6. Enter Groq API Key (userID: your_email_6@example.com):		YOUR_GROQ_API_KEY_6

7. Enter Groq API Key (userID: your_email_7@example.com):		YOUR_GROQ_API_KEY_7

8. Enter Groq API Key (userID: your_email_8@example.com):		YOUR_GROQ_API_KEY_8

9. Enter Groq API Key (userID: your_email_9@example.com):		YOUR_GROQ_API_KEY_9

10. Enter Groq API Key (userID: your_email_10@example.com):		YOUR_GROQ_API_KEY_10

11. Enter Groq API Key (userID: your_email_11@example.com):		YOUR_GROQ_API_KEY_11

12. Enter Groq API Key (userID: your_email_12@example.com):		YOUR_GROQ_API_KEY_12

"""
# ====
# END USER CONFIG
# ====

import sys
import os
import ctypes
import subprocess
import traceback
import importlib
import re

LIB_ROOT = r"C:\AKT Media Tools"
SITE_PACKAGES = os.path.join(LIB_ROOT, "Lib", "site-packages")
TOOLS_DIR_STR = os.path.join(LIB_ROOT, "Tools")


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
            print("  Right-click CMD -> Run as administrator, then:")
            print(f'    py "{script}"')
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
    need = [
        os.path.join(LIB_ROOT, "Lib", "site-packages"),
        os.path.join(LIB_ROOT, "Tools"),
    ]
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


def _log_crash(exc: BaseException):
    tb = traceback.format_exc()
    print("\n" + "!" * 60)
    print("  FATAL ERROR")
    print("!" * 60)
    print(tb)
    for folder in (MEDIA_ROOT, LIB_ROOT):
        try:
            os.makedirs(folder, exist_ok=True)
            log_path = os.path.join(folder, "error_log.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\n" + "=" * 80 + "\n" + tb + "\n")
            print(f"  Saved: {log_path}")
            break
        except Exception:
            continue
    _pause_exit(1)


def _count_files(folder: str) -> int:
    n = 0
    try:
        for root, dirs, files in os.walk(folder):
            n += len(files)
    except Exception:
        pass
    return n


def _package_present_in_target(imp_name: str, pip_name: str) -> bool:
    checks = []
    if imp_name == "PIL":
        checks += [
            os.path.join(SITE_PACKAGES, "PIL"),
            os.path.join(SITE_PACKAGES, "Pillow"),
        ]
    elif imp_name == "Crypto":
        checks += [
            os.path.join(SITE_PACKAGES, "Crypto"),
            os.path.join(SITE_PACKAGES, "Cryptodome"),
        ]
    elif imp_name == "gallery_dl":
        checks += [os.path.join(SITE_PACKAGES, "gallery_dl")]
    else:
        checks += [
            os.path.join(SITE_PACKAGES, imp_name),
            os.path.join(SITE_PACKAGES, pip_name),
            os.path.join(SITE_PACKAGES, pip_name.replace("-", "_")),
            os.path.join(SITE_PACKAGES, f"{imp_name}.py"),
            os.path.join(SITE_PACKAGES, f"{pip_name}.py"),
        ]
    for c in checks:
        if os.path.isdir(c) or os.path.isfile(c):
            return True
    try:
        for name in os.listdir(SITE_PACKAGES):
            low = name.lower()
            if low.startswith(pip_name.lower().replace("-", "_")) and low.endswith((".dist-info", ".egg-info")):
                return True
            if low.startswith(pip_name.lower()) and low.endswith((".dist-info", ".egg-info")):
                return True
            if imp_name == "PIL" and low.startswith("pillow") and low.endswith(".dist-info"):
                return True
            if imp_name == "Crypto" and "pycryptodome" in low and low.endswith(".dist-info"):
                return True
            if "gallery_dl" in low and low.endswith(".dist-info"):
                return True
    except Exception:
        pass
    return False


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


def extract_api_keys() -> list:
    text = USER_CONFIG or ""
    keys = []
    seen = set()
    pat_numbered = re.compile(
        r"(?m)^\s*(\d+)\s*[\.\)]\s*"
        r"(?:Enter\s+)?Groq\s+API\s+Key"
        r"(?:\s*\(\s*userID\s*:\s*([^)]+?)\s*\))?"
        r"\s*:\s*"
        r"(\S+)",
        re.IGNORECASE,
    )
    for m in pat_numbered.finditer(text):
        idx = int(m.group(1))
        uid = (m.group(2) or "").strip()
        key = m.group(3).strip()
        up = key.upper()
        if any(p in up for p in ("PASTE", "YOUR_GROQ", "YOUR_KEY", "REPLACE_ME", "XYZ")):
            continue
        if key.lower() in ("gsk_xyz", "gsk_your_key_here", "gsk_xxx"):
            continue
        if not key.lower().startswith("gsk_"):
            continue
        if len(key) < 20:
            continue
        if key in seen:
            continue
        seen.add(key)
        keys.append({"index": idx, "user_id": uid, "key": key})
    if keys:
        keys.sort(key=lambda d: d["index"])
        for i, d in enumerate(keys, start=1):
            d["slot"] = i
        return keys
    for m in re.finditer(r"(gsk_[A-Za-z0-9_\-]{20,})", text, re.IGNORECASE):
        key = m.group(1).strip()
        if key in seen:
            continue
        up = key.upper()
        if any(p in up for p in ("PASTE", "YOUR", "XYZ")):
            continue
        if key.lower() in ("gsk_xyz", "gsk_your_key_here", "gsk_xxx"):
            continue
        seen.add(key)
        keys.append({"index": len(keys) + 1, "user_id": "", "key": key, "slot": len(keys) + 1})
    if not keys:
        env = (os.environ.get("GROQ_API_KEY") or "").strip()
        if env.startswith("gsk_") and len(env) > 20:
            keys.append({"index": 1, "user_id": "ENV:GROQ_API_KEY", "key": env, "slot": 1})
    return keys


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
    "openai": "openai",
    "Crypto": "pycryptodome",
    "certifi": "certifi",
    "websockets": "websockets",
    "mutagen": "mutagen",
    "brotli": "brotli",
    "zstandard": "zstandard",
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

file_count = _count_files(SITE_PACKAGES)
print("=" * 60)
print(f"  Files in site-packages: {file_count}")
print(f"  Path: {SITE_PACKAGES}")
print("=" * 60 + "\n")

importlib.invalidate_caches()
if SITE_PACKAGES in sys.path:
    sys.path.remove(SITE_PACKAGES)
sys.path.insert(0, SITE_PACKAGES)

import time
import json
import shutil
import base64
import zipfile
import urllib.request
import gc
import struct
import random
import threading
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from io import BytesIO
from typing import Optional, List, Tuple, Any, Callable, Dict

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

try:
    from PIL import Image
except Exception as e:
    print(f"  FATAL: Pillow import failed: {e}")
    _pause_exit(1)

try:
    from openai import OpenAI
except Exception as e:
    print(f"  FATAL: openai import failed: {e}")
    _pause_exit(1)

try:
    import mutagen
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except Exception:
    HAS_MUTAGEN = False

GROQ_RPM_LIMIT = 30
GROQ_RPD_LIMIT = 14400
GROQ_TPM_LIMIT = 30000
GROQ_RPM_ROTATE_AT = GROQ_RPM_LIMIT - 1
GROQ_RPD_ROTATE_AT = GROQ_RPD_LIMIT - 1
GROQ_TPM_ROTATE_AT = max(1, GROQ_TPM_LIMIT - 1)
KEY_SWITCH_DELAY_SECONDS = 600

# Official vision model: https://console.groq.com/docs/vision
GROQ_MODELS = {
    "vision": "qwen/qwen3.6-27b",
    "vision_fallbacks": [],
    "translate": "llama-3.3-70b-versatile",
    "translate_fallbacks": [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "llama-3.1-8b-instant",
    ],
    "whisper": "whisper-large-v3",
    "whisper_fallbacks": [
        "whisper-large-v3-turbo",
    ],
}

_MODEL_DEAD = set()
_LIVE_MODEL_IDS = set()

GROQ_API_KEY = ""
GROQ_KEY_MANAGER = None

MEDIA_DIR = Path(MEDIA_ROOT)
os.chdir(MEDIA_DIR)

TOOLS_DIR = Path(TOOLS_DIR_STR)
YTDLP_PATH = TOOLS_DIR / "yt-dlp.exe"
FFMPEG_PATH = TOOLS_DIR / "ffmpeg.exe"
FFPROBE_CANDIDATES = [
    TOOLS_DIR / "ffprobe.exe",
    Path(str(FFMPEG_PATH).replace("ffmpeg.exe", "ffprobe.exe")),
]
ERROR_LOG = MEDIA_DIR / "error_log.txt"

URL_PICKER_FILE   = MEDIA_DIR / "Ultimate Media Tool URL Picker.txt"
URL_PICKER_DONE   = MEDIA_DIR / "Ultimate Media Tool URL Picker Done.txt"
URL_PICKER_FAILED = MEDIA_DIR / "Ultimate Media Tool URL Picker Failed.txt"
JOB_LOG_FILE      = MEDIA_DIR / "Ultimate Media Tool Job Log.txt"

YTDLP_RELEASE_TAG = "2025.10.14"
YTDLP_DOWNLOAD_URL = (
    f"https://github.com/yt-dlp/yt-dlp/releases/download/"
    f"{YTDLP_RELEASE_TAG}/yt-dlp.exe"
)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg", ".mpg", ".m4v", ".3gp"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a"}
ALL_EXT = IMAGE_EXT | VIDEO_EXT | AUDIO_EXT

_PERMANENT_DL_HINTS = (
    "no video formats found",
    "unsupported url",
    "unable to download webpage",
    "private video",
    "login required",
    "requested content is not available",
    "404",
)

_RE_DONE_NAME = re.compile(r"(?i)^(Image|Video|Audio)(?:\s+No\.)?\s+(\d+)\s+")


class C:
    RESET = "\033[0m"
    BUILT_IN = "\033[1m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"


def print_step(icon: str, message: str, color: str = C.WHITE) -> None:
    print(f"  {color}{icon}  {message}{C.RESET}")


def log_error(msg: str):
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except Exception:
        pass


def model_chain(primary_key: str) -> List[str]:
    primary = GROQ_MODELS.get(primary_key) or ""
    fbs = GROQ_MODELS.get(f"{primary_key}_fallbacks") or []
    out = []
    for m in [primary] + list(fbs):
        m = (m or "").strip()
        if not m or m in out or m in _MODEL_DEAD:
            continue
        if _LIVE_MODEL_IDS and m not in _LIVE_MODEL_IDS and m != primary:
            continue
        out.append(m)
    if not out and primary:
        out = [primary]
    if primary_key == "vision" and _LIVE_MODEL_IDS:
        for m in sorted(_LIVE_MODEL_IDS):
            low = m.lower()
            if m in out or m in _MODEL_DEAD:
                continue
            if any(x in low for x in ("qwen3.6", "qwen/qwen3.6", "vision", "llava")):
                out.append(m)
    return out


def mark_model_dead(model_id: str, err: Exception = None):
    if not model_id:
        return
    _MODEL_DEAD.add(model_id)
    msg = f"model marked unavailable this session: {model_id}"
    if err is not None:
        msg += f" | {err}"
    log_error(msg)
    print(f"  {C.YELLOW}[model] Skipping '{model_id}' for rest of run (not found / no access){C.RESET}")


def is_model_not_found_error(e: Exception) -> bool:
    msg = str(e).lower()
    if "model_not_found" in msg:
        return True
    if "does not exist" in msg and "model" in msg:
        return True
    if "do not have access" in msg and "model" in msg:
        return True
    if "decommissioned" in msg:
        return True
    if "invalid_request_error" in msg and "model" in msg and ("404" in msg or "not found" in msg):
        return True
    status = None
    for attr in ("status_code", "status"):
        if hasattr(e, attr):
            try:
                status = int(getattr(e, attr))
            except Exception:
                pass
    if status == 404 and "model" in msg:
        return True
    return False


def strip_code_fences(text: str) -> str:
    if not text:
        return ""
    s = text.strip()
    s = re.sub(r"<think>[\s\S]*?</think>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<thinking>[\s\S]*?</thinking>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^```(?:json|JSON)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    raw = strip_code_fences(text)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    s, e = raw.find("{"), raw.rfind("}")
    if s != -1 and e > s:
        chunk = raw[s : e + 1]
        for candidate in (
            chunk,
            re.sub(r",\s*}", "}", re.sub(r",\s*]", "]", chunk)),
            chunk.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'"),
        ):
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(raw[start : i + 1])
                    if isinstance(obj, dict):
                        return obj
                except Exception:
                    return None
    return None


def normalize_english_field(original: str, english: str) -> str:
    eng = (english or "").strip()
    orig = (original or "").strip()
    if not eng:
        return "Not Required"
    if eng.lower() in ("not required", "n/a", "na", "none", "same", "-"):
        return "Not Required"
    if orig and orig.lower() == eng.lower():
        return "Not Required"
    return eng


def message_text_from_response(resp) -> str:
    try:
        msg = resp.choices[0].message
    except Exception:
        return ""
    content = getattr(msg, "content", None)
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") in ("text", "output_text") and p.get("text"):
                    parts.append(str(p.get("text")))
                elif p.get("text"):
                    parts.append(str(p.get("text")))
            else:
                t = getattr(p, "text", None)
                if t:
                    parts.append(str(t))
        if parts:
            return "\n".join(parts)
    return (content or "") if isinstance(content, str) else ""


class ApiKeyRotator:
    KEY_SWITCH_DELAY_SECONDS = KEY_SWITCH_DELAY_SECONDS

    def __init__(
        self,
        key_entries: list,
        rpm_limit: int = GROQ_RPM_LIMIT,
        rpd_limit: int = GROQ_RPD_LIMIT,
        tpm_limit: int = GROQ_TPM_LIMIT,
        provider_name: str = "Groq",
    ):
        if not key_entries:
            raise ValueError("No API keys provided to ApiKeyRotator")
        self.provider = provider_name
        self.rpm_limit = rpm_limit
        self.rpd_limit = rpd_limit
        self.tpm_limit = tpm_limit
        self.rpm_rotate_at = max(1, rpm_limit - 1)
        self.rpd_rotate_at = max(1, rpd_limit - 1)
        self.tpm_rotate_at = max(1, tpm_limit - 1)
        self._lock = threading.RLock()
        self.keys = []
        for i, entry in enumerate(key_entries):
            self.keys.append({
                "slot": entry.get("slot", i + 1),
                "index": entry.get("index", i + 1),
                "user_id": entry.get("user_id") or f"key#{i + 1}",
                "key": entry["key"],
                "req_times": deque(),
                "tok_events": deque(),
                "day_stamp": self._today(),
                "day_count": 0,
                "total_requests": 0,
                "total_tokens_est": 0,
                "cooldown_until": 0.0,
                "disabled": False,
                "last_error": "",
            })
        self.current_idx = 0
        self._clients = {}
        self._last_switched_from = None

    @staticmethod
    def _today() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _purge_windows(self, k: dict, now: float):
        cutoff = now - 60.0
        while k["req_times"] and k["req_times"][0] < cutoff:
            k["req_times"].popleft()
        while k["tok_events"] and k["tok_events"][0][0] < cutoff:
            k["tok_events"].popleft()
        today = self._today()
        if k["day_stamp"] != today:
            k["day_stamp"] = today
            k["day_count"] = 0

    def _rpm(self, k: dict, now: float) -> int:
        self._purge_windows(k, now)
        return len(k["req_times"])

    def _tpm(self, k: dict, now: float) -> int:
        self._purge_windows(k, now)
        return sum(t for _, t in k["tok_events"])

    def _rpd(self, k: dict, now: float) -> int:
        self._purge_windows(k, now)
        return k["day_count"]

    def _is_available(self, k: dict, now: float) -> bool:
        if k["disabled"] or k["cooldown_until"] > now:
            return False
        self._purge_windows(k, now)
        if self._rpm(k, now) >= self.rpm_rotate_at:
            return False
        if self._rpd(k, now) >= self.rpd_rotate_at:
            return False
        if self._tpm(k, now) >= self.tpm_rotate_at:
            return False
        return True

    def _reason_unavailable(self, k: dict, now: float) -> str:
        if k["disabled"]:
            return f"disabled ({k.get('last_error') or 'auth/permanent'})"
        if k["cooldown_until"] > now:
            return f"cooldown {k['cooldown_until'] - now:.1f}s left"
        rpm, rpd, tpm = self._rpm(k, now), self._rpd(k, now), self._tpm(k, now)
        parts = []
        if rpm >= self.rpm_rotate_at:
            parts.append(f"RPM {rpm}/{self.rpm_limit}")
        if rpd >= self.rpd_rotate_at:
            parts.append(f"RPD {rpd}/{self.rpd_limit}")
        if tpm >= self.tpm_rotate_at:
            parts.append(f"TPM~{tpm}/{self.tpm_limit}")
        return ", ".join(parts) or "unknown"

    def _advance(self, from_idx: int) -> int:
        return (from_idx + 1) % len(self.keys)

    def _apply_key_switch_delay(self, old_slot: int, new_slot: int, reason: str = "") -> None:
        delay = max(0, int(self.KEY_SWITCH_DELAY_SECONDS))
        if delay <= 0 or old_slot == new_slot:
            return
        reason_s = f" ({reason})" if reason else ""
        print(
            f"  {C.YELLOW}[{self.provider}] Waiting {delay}s before next key "
            f"#{old_slot} → #{new_slot}{reason_s}...{C.RESET}"
        )
        time.sleep(delay)

    def _pick_index(self, now: float) -> int:
        n = len(self.keys)
        idx = self.current_idx
        for _ in range(n):
            if self._is_available(self.keys[idx], now):
                return idx
            idx = self._advance(idx)
        best_idx, best_score = None, None
        for i, k in enumerate(self.keys):
            if k["disabled"]:
                continue
            wait = 0.0
            if k["cooldown_until"] > now:
                wait = k["cooldown_until"] - now
            else:
                self._purge_windows(k, now)
                if self._rpm(k, now) >= self.rpm_rotate_at and k["req_times"]:
                    wait = max(wait, max(0.0, 60.0 - (now - k["req_times"][0])) + 0.05)
                if self._tpm(k, now) >= self.tpm_rotate_at and k["tok_events"]:
                    wait = max(wait, max(0.0, 60.0 - (now - k["tok_events"][0][0])) + 0.05)
                if self._rpd(k, now) >= self.rpd_rotate_at:
                    tomorrow = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ) + timedelta(days=1)
                    wait = max(wait, (tomorrow - datetime.now()).total_seconds())
            score = (wait, k["total_requests"], i)
            if best_score is None or score < best_score:
                best_score = score
                best_idx = i
        if best_idx is None:
            return self.current_idx
        wait_needed = best_score[0]
        if wait_needed > 0.05:
            print(
                f"  {C.YELLOW}[{self.provider}] All keys at soft limit. "
                f"Waiting {wait_needed:.1f}s then using {self._label(self.keys[best_idx])}...{C.RESET}"
            )
            time.sleep(min(wait_needed, 120.0))
        return best_idx

    def _label(self, k: dict) -> str:
        uid = _mask_user_id(k.get("user_id") or "")
        short = (k["key"][:8] + "…") if len(k["key"]) > 10 else "***"
        return f"#{k['slot']} ({uid}) [{short}]"

    def get_key(self) -> str:
        with self._lock:
            now = time.time()
            prev_idx = self.current_idx
            idx = self._pick_index(now)
            if idx != prev_idx:
                old, new = self.keys[prev_idx], self.keys[idx]
                reason = self._reason_unavailable(old, now) if not self._is_available(old, now) else "round-robin"
                print(
                    f"  {C.MAGENTA}[{self.provider}] Key rotate: "
                    f"{self._label(old)} → {self._label(new)} "
                    f"(reason: {reason}){C.RESET}"
                )
                self._apply_key_switch_delay(old["slot"], new["slot"], reason)
            self.current_idx = idx
            self._last_switched_from = prev_idx
            return self.keys[idx]["key"]

    def current_label(self) -> str:
        with self._lock:
            return self._label(self.keys[self.current_idx])

    def record_success(self, tokens_est: int = 0):
        with self._lock:
            now = time.time()
            k = self.keys[self.current_idx]
            self._purge_windows(k, now)
            k["req_times"].append(now)
            k["day_count"] += 1
            k["total_requests"] += 1
            tok = max(0, int(tokens_est or 0))
            if tok:
                k["tok_events"].append((now, tok))
                k["total_tokens_est"] += tok
            if (
                self._rpm(k, now) >= self.rpm_rotate_at
                or self._rpd(k, now) >= self.rpd_rotate_at
                or self._tpm(k, now) >= self.tpm_rotate_at
            ):
                nxt = self._advance(self.current_idx)
                old_slot = k["slot"]
                print(
                    f"  {C.CYAN}[{self.provider}] Soft limit on {self._label(k)} "
                    f"→ next key #{self.keys[nxt]['slot']}{C.RESET}"
                )
                self._apply_key_switch_delay(old_slot, self.keys[nxt]["slot"], "soft limit")
                self.current_idx = nxt
                self._last_switched_from = self.current_idx

    def record_rate_limit(self, retry_after: Optional[float] = None):
        with self._lock:
            now = time.time()
            k = self.keys[self.current_idx]
            wait = float(retry_after) if retry_after and retry_after > 0 else 60.0
            wait = wait + random.uniform(0.1, 1.0)
            k["cooldown_until"] = now + wait
            k["last_error"] = f"429 cooldown {wait:.1f}s"
            old_slot = k["slot"]
            print(
                f"  {C.YELLOW}[{self.provider}] 429 on {self._label(k)} — "
                f"cooldown {wait:.1f}s, rotating...{C.RESET}"
            )
            nxt = self._advance(self.current_idx)
            self._apply_key_switch_delay(old_slot, self.keys[nxt]["slot"], "429 rate limit")
            self.current_idx = nxt

    def record_auth_error(self):
        with self._lock:
            k = self.keys[self.current_idx]
            k["disabled"] = True
            k["last_error"] = "auth 401/403"
            old_slot = k["slot"]
            print(
                f"  {C.RED}[{self.provider}] Auth failed on {self._label(k)} — "
                f"disabled for this run, rotating...{C.RESET}"
            )
            log_error(f"{self.provider} auth fail key slot #{k['slot']} user={_mask_user_id(k.get('user_id') or '')}")
            nxt = self._advance(self.current_idx)
            self._apply_key_switch_delay(old_slot, self.keys[nxt]["slot"], "auth error")
            self.current_idx = nxt

    def get_client(self) -> OpenAI:
        key = self.get_key()
        with self._lock:
            cli = self._clients.get(key)
            if cli is None:
                cli = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key)
                self._clients[key] = cli
            return cli

    def status_summary(self) -> str:
        with self._lock:
            now = time.time()
            lines = [f"  {self.provider} keys: {len(self.keys)} | active → {self._label(self.keys[self.current_idx])}"]
            for k in self.keys:
                st = "OK"
                if k["disabled"]:
                    st = "DISABLED"
                elif k["cooldown_until"] > now:
                    st = f"COOL {k['cooldown_until'] - now:.0f}s"
                elif not self._is_available(k, now):
                    st = "SOFT-LIMIT"
                lines.append(
                    f"    #{k['slot']:>2} {_mask_user_id(k.get('user_id') or '-'):<28} "
                    f"req={k['total_requests']:<5} "
                    f"RPM={self._rpm(k, now):<3} RPD={self._rpd(k, now):<6} "
                    f"[{st}]"
                )
            return "\n".join(lines)

    def balance_plain(self) -> str:
        with self._lock:
            now = time.time()
            lines = []
            for k in self.keys:
                rpm = self._rpm(k, now)
                rpd = self._rpd(k, now)
                rpm_left = max(0, self.rpm_rotate_at - rpm)
                rpd_left = max(0, self.rpd_rotate_at - rpd)
                if k["disabled"]:
                    st = "DISABLED"
                elif k["cooldown_until"] > now:
                    st = f"COOLDOWN {int(k['cooldown_until'] - now)}s"
                else:
                    st = "active"
                lines.append(
                    f"  Key #{k['slot']} ({_mask_user_id(k.get('user_id') or '')}): "
                    f"RPM {rpm}/{self.rpm_limit} (left~{rpm_left}) | "
                    f"RPD {rpd}/{self.rpd_limit} (left~{rpd_left}) | {st}"
                )
            return "\n".join(lines)


def estimate_tokens_from_text(*parts: str) -> int:
    total_chars = sum(len(str(p)) for p in parts if p)
    return max(1, total_chars // 4)


def estimate_tokens_from_response(resp) -> int:
    try:
        u = getattr(resp, "usage", None)
        if u is not None:
            pt = getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", 0) or 0
            ct = getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", 0) or 0
            tt = getattr(u, "total_tokens", None)
            if tt:
                return int(tt)
            return int(pt) + int(ct)
    except Exception:
        pass
    return 0


def chat_completions_create(client: OpenAI, **kwargs):
    kwargs = dict(kwargs)
    if "max_tokens" in kwargs and "max_completion_tokens" not in kwargs:
        kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")

    def _call(kw):
        return client.chat.completions.create(**kw)

    try:
        return _call(kwargs)
    except TypeError:
        if "max_completion_tokens" in kwargs:
            kw2 = dict(kwargs)
            kw2["max_tokens"] = kw2.pop("max_completion_tokens")
            try:
                return _call(kw2)
            except Exception:
                pass
        raise
    except Exception as e:
        msg = str(e).lower()
        if "response_format" in kwargs and (
            "response_format" in msg or "json_object" in msg or "unsupported" in msg
        ):
            kw2 = dict(kwargs)
            kw2.pop("response_format", None)
            return _call(kw2)
        if "max_completion_tokens" in msg or "max_tokens" in msg:
            kw2 = dict(kwargs)
            if "max_completion_tokens" in kw2:
                kw2["max_tokens"] = kw2.pop("max_completion_tokens")
                try:
                    return _call(kw2)
                except Exception as e2:
                    if "response_format" in kw2:
                        kw2.pop("response_format", None)
                        return _call(kw2)
                    raise e2
        raise


def call_with_key_rotation(
    operation_name: str,
    fn: Callable[[OpenAI], Any],
    tokens_hint: int = 0,
    max_attempts: int = None,
) -> Any:
    global GROQ_KEY_MANAGER
    if GROQ_KEY_MANAGER is None:
        raise RuntimeError("GROQ_KEY_MANAGER not initialized")
    n_keys = max(1, len(GROQ_KEY_MANAGER.keys))
    if max_attempts is None:
        max_attempts = max(6, n_keys * 2)
    last_err = None
    for attempt in range(max_attempts):
        client = GROQ_KEY_MANAGER.get_client()
        try:
            result = fn(client)
            tok = estimate_tokens_from_response(result) or tokens_hint
            GROQ_KEY_MANAGER.record_success(tokens_est=tok)
            return result
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            status = None
            for attr in ("status_code", "status"):
                if hasattr(e, attr):
                    try:
                        status = int(getattr(e, attr))
                    except Exception:
                        pass
            resp_obj = getattr(e, "response", None)
            if status is None and resp_obj is not None:
                try:
                    status = int(getattr(resp_obj, "status_code", 0) or 0)
                except Exception:
                    pass
            if is_model_not_found_error(e):
                log_error(f"{operation_name} model_not_found: {e}")
                raise
            is_429 = status == 429 or "429" in msg or "rate limit" in msg or "too many requests" in msg
            is_auth = (
                status in (401, 403)
                or "invalid api key" in msg
                or "authentication" in msg
                or "unauthorized" in msg
            )
            is_5xx = (status is not None and status >= 500) or "server error" in msg
            retry_after = None
            if resp_obj is not None:
                try:
                    headers = getattr(resp_obj, "headers", None) or {}
                    if hasattr(headers, "get"):
                        ra = headers.get("retry-after") or headers.get("Retry-After")
                        if ra is not None:
                            retry_after = float(ra)
                except Exception:
                    pass
            if is_auth:
                GROQ_KEY_MANAGER.record_auth_error()
                log_error(f"{operation_name} auth: {e}")
                continue
            if is_429:
                GROQ_KEY_MANAGER.record_rate_limit(retry_after=retry_after)
                time.sleep(0.3 + random.uniform(0, 0.4))
                log_error(f"{operation_name} 429: {e}")
                continue
            if is_5xx:
                wait = min(30.0, (2 ** min(attempt, 4)) + random.uniform(0, 1))
                print(
                    f"  {C.YELLOW}[{operation_name}] server error, retry in {wait:.1f}s "
                    f"(attempt {attempt + 1}/{max_attempts}){C.RESET}"
                )
                time.sleep(wait)
                log_error(f"{operation_name} 5xx: {e}")
                continue
            log_error(f"{operation_name}: {e}")
            raise
    raise Exception(f"{operation_name} failed after {max_attempts} attempts: {last_err}")


def call_with_model_fallback(
    operation_name: str,
    model_key: str,
    make_fn: Callable[[str], Callable[[OpenAI], Any]],
    tokens_hint: int = 0,
) -> Any:
    last_err = None
    chain = model_chain(model_key)
    if not chain:
        raise RuntimeError(f"No models configured for '{model_key}'")
    print(f"            {C.DIM}model chain: {' → '.join(chain)}{C.RESET}")
    for model_id in chain:
        try:
            print(f"            {C.DIM}trying model: {model_id}{C.RESET}")
            fn = make_fn(model_id)
            return call_with_key_rotation(operation_name, fn, tokens_hint=tokens_hint)
        except Exception as e:
            last_err = e
            err_s = str(e)
            print(f"            {C.YELLOW}model fail: {model_id} → {err_s[:220]}{C.RESET}")
            if is_model_not_found_error(e):
                mark_model_dead(model_id, e)
                continue
            low = err_s.lower()
            if any(x in low for x in ("image", "vision", "multimodal", "content part")):
                mark_model_dead(model_id, e)
                continue
            raise
    raise Exception(f"{operation_name}: all models failed for '{model_key}': {last_err}")


def refresh_live_models_from_groq():
    global _LIVE_MODEL_IDS
    if GROQ_KEY_MANAGER is None:
        return
    try:
        client = GROQ_KEY_MANAGER.get_client()
        try:
            models_page = client.models.list()
            ids = []
            data = getattr(models_page, "data", None) or models_page
            for m in data:
                mid = getattr(m, "id", None) or (m.get("id") if isinstance(m, dict) else None)
                if mid:
                    ids.append(mid)
        except Exception:
            key = GROQ_KEY_MANAGER.get_key()
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}", "User-Agent": "UltimateMediaTool/0.8"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            ids = [m.get("id") for m in (payload.get("data") or []) if m.get("id")]

        _LIVE_MODEL_IDS = set(ids)
        try:
            GROQ_KEY_MANAGER.record_success(tokens_est=10)
        except Exception:
            pass

        print(f"  {C.GREEN}[OK] Groq live models: {len(_LIVE_MODEL_IDS)}{C.RESET}")

        preferred_vision = ["qwen/qwen3.6-27b"]
        live_vision = [m for m in preferred_vision if m in _LIVE_MODEL_IDS]
        for m in sorted(_LIVE_MODEL_IDS):
            low = m.lower()
            if m in live_vision:
                continue
            if "qwen3.6" in low or "vision" in low:
                live_vision.append(m)

        if live_vision:
            GROQ_MODELS["vision"] = live_vision[0]
            GROQ_MODELS["vision_fallbacks"] = live_vision[1:]
            print(f"  {C.GREEN}[OK] Vision primary: {GROQ_MODELS['vision']}{C.RESET}")
            if GROQ_MODELS["vision_fallbacks"]:
                print(f"  {C.DIM}     fallbacks: {', '.join(GROQ_MODELS['vision_fallbacks'][:5])}{C.RESET}")
        else:
            print(f"  {C.YELLOW}[WARN] No vision model in live catalog — keeping qwen/qwen3.6-27b{C.RESET}")
            print(f"  {C.DIM}  sample: {', '.join(sorted(_LIVE_MODEL_IDS)[:15])}{C.RESET}")
            GROQ_MODELS["vision"] = "qwen/qwen3.6-27b"

        pref_tr = [
            "llama-3.3-70b-versatile",
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
            "llama-3.1-8b-instant",
            "qwen/qwen3.6-27b",
        ]
        live_tr = [m for m in pref_tr if m in _LIVE_MODEL_IDS]
        if not live_tr:
            live_tr = [
                m for m in sorted(_LIVE_MODEL_IDS)
                if "whisper" not in m.lower() and "tts" not in m.lower() and "guard" not in m.lower()
            ][:6]
        if live_tr:
            GROQ_MODELS["translate"] = live_tr[0]
            GROQ_MODELS["translate_fallbacks"] = live_tr[1:]
            print(f"  {C.GREEN}[OK] Translate primary: {GROQ_MODELS['translate']}{C.RESET}")

        pref_w = ["whisper-large-v3", "whisper-large-v3-turbo"]
        live_w = [m for m in pref_w if m in _LIVE_MODEL_IDS]
        if live_w:
            GROQ_MODELS["whisper"] = live_w[0]
            GROQ_MODELS["whisper_fallbacks"] = live_w[1:]
            print(f"  {C.GREEN}[OK] Whisper primary: {GROQ_MODELS['whisper']}{C.RESET}")

    except Exception as e:
        log_error(f"models.list: {e}")
        print(f"  {C.YELLOW}[WARN] Could not list Groq models: {e}{C.RESET}")
        print(f"  {C.DIM}Using hardcoded GROQ_MODELS (vision=qwen/qwen3.6-27b){C.RESET}")


def _download_file(url: str, dest: Path, timeout: int = 120) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (UltimateMediaTool/0.8)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)


def setup_tools():
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    if not YTDLP_PATH.exists() or YTDLP_PATH.stat().st_size < 100_000:
        print(f"  {C.YELLOW}Downloading yt-dlp.exe ({YTDLP_RELEASE_TAG}) -> library Tools...{C.RESET}")
        try:
            _download_file(YTDLP_DOWNLOAD_URL, YTDLP_PATH)
            if not (YTDLP_PATH.exists() and YTDLP_PATH.stat().st_size > 100_000):
                _download_file(
                    "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
                    YTDLP_PATH,
                )
            print(f"  {C.GREEN}[OK] {YTDLP_PATH}{C.RESET}\n")
        except Exception as e:
            log_error(f"yt-dlp: {e}")
            print(f"  {C.RED}yt-dlp failed: {e}{C.RESET}\n")
    else:
        print(f"  {C.GREEN}[OK] yt-dlp already present{C.RESET}")

    if not FFMPEG_PATH.exists():
        print(f"  {C.YELLOW}Downloading ffmpeg.exe -> library Tools...{C.RESET}")
        urls = [
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        ]
        zip_path = TOOLS_DIR / "ffmpeg.zip"
        downloaded, last_err = False, None
        for url in urls:
            try:
                print(f"  {C.DIM}Trying: {url}{C.RESET}")
                if zip_path.exists():
                    zip_path.unlink(missing_ok=True)
                _download_file(url, zip_path, timeout=300)
                if zip_path.exists() and zip_path.stat().st_size > 1_000_000:
                    downloaded = True
                    print(f"  {C.GREEN}Download OK{C.RESET}")
                    break
            except Exception as e:
                last_err = e
                print(f"  {C.YELLOW}  failed: {e}{C.RESET}")
        if not downloaded:
            log_error(f"ffmpeg: {last_err}")
            print(f"  {C.RED}ffmpeg failed: {last_err}{C.RESET}")
            print(f"  Put ffmpeg.exe manually in: {TOOLS_DIR}\n")
            return
        try:
            print(f"  {C.DIM}Extracting...{C.RESET}")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(TOOLS_DIR)
            found_ffmpeg = found_ffprobe = False
            for root, dirs, files in os.walk(TOOLS_DIR):
                if "ffmpeg.exe" in files and not found_ffmpeg:
                    src = Path(root) / "ffmpeg.exe"
                    if src.resolve() != FFMPEG_PATH.resolve():
                        if FFMPEG_PATH.exists():
                            FFMPEG_PATH.unlink()
                        shutil.move(str(src), str(FFMPEG_PATH))
                    found_ffmpeg = True
                if "ffprobe.exe" in files and not found_ffprobe:
                    src = Path(root) / "ffprobe.exe"
                    dest_probe = TOOLS_DIR / "ffprobe.exe"
                    if src.resolve() != dest_probe.resolve():
                        if dest_probe.exists():
                            dest_probe.unlink()
                        shutil.move(str(src), str(dest_probe))
                    found_ffprobe = True
            zip_path.unlink(missing_ok=True)
            for item in list(TOOLS_DIR.iterdir()):
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
            if found_ffmpeg and FFMPEG_PATH.exists():
                print(f"  {C.GREEN}[OK] {FFMPEG_PATH}{C.RESET}")
                if found_ffprobe:
                    print(f"  {C.GREEN}[OK] ffprobe.exe extracted{C.RESET}")
                print()
            else:
                print(f"  {C.RED}ffmpeg.exe not found after extract{C.RESET}\n")
        except Exception as e:
            log_error(f"ffmpeg extract: {e}")
            print(f"  {C.RED}ffmpeg extract failed: {e}{C.RESET}\n")
    else:
        print(f"  {C.GREEN}[OK] ffmpeg already present{C.RESET}")


# ====
# URL PICKER (same logic as forensic image/video tools)
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
    urls, seen = [], set()
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


def write_job_log(
    *,
    url: str,
    downloaded_files: List[str],
    status: str,
) -> None:
    try:
        remaining_urls = load_urls_from_picker()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        block = [
            "=" * 80,
            f"JOB COMPLETE  {stamp}",
            f"Status       : {status}",
            f"URL          : {url}",
            f"Downloaded   : {len(downloaded_files)} file(s)",
        ]
        for name in downloaded_files:
            block.append(f"  + {name}")
        block.append(f"URL picker remaining balance: {len(remaining_urls)} URL(s)")
        for u in remaining_urls:
            block.append(f"  ~ {u}")
        block.append("API key balance after job:")
        if GROQ_KEY_MANAGER is not None:
            block.append(GROQ_KEY_MANAGER.balance_plain())
        block.append("")
        with open(JOB_LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(block) + "\n")
        print_step("+", f"Job record saved → {JOB_LOG_FILE.name}", C.GREEN)
    except Exception as e:
        print_step("!", f"Could not write job log: {e}", C.YELLOW)


def quarantine_url_as_failed(url: str, reason: str = "") -> None:
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
    write_job_log(url=url, downloaded_files=[], status=f"QUARANTINED — {reason}")


def _looks_permanent_download_error(log_text: str) -> bool:
    low = (log_text or "").lower()
    return any(h in low for h in _PERMANENT_DL_HINTS)


def get_url_with_timeout(timeout_sec: float = 8.0) -> Optional[str]:
    print()
    print(f"  {C.CYAN}{C.BOLD}No URLs in {URL_PICKER_FILE.name}{C.RESET}")
    print(f"  {C.DIM}Paste social media URL, or wait {int(timeout_sec)}s / Enter → local media.{C.RESET}")
    if not HAS_MSVCRT:
        try:
            raw = input(f"  {C.YELLOW}Enter Social Media URL (or Enter skip): {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
    else:
        print(f"  {C.YELLOW}Enter Social Media URL (Auto-skips in {int(timeout_sec)}s): {C.RESET}", end="", flush=True)
        raw = ""
        start = time.time()
        while time.time() - start < timeout_sec:
            if msvcrt.kbhit():
                raw = input()
                break
            time.sleep(0.1)
        print()
    if not raw or not raw.strip():
        print_step("~", "No URL entered / timeout → using local media only", C.DIM)
        return None
    m = re.search(r"https?://[^\s<>\"'\])\}]+", raw.strip(), re.IGNORECASE)
    if not m:
        print_step("!", "No valid http(s) URL detected — using local media only", C.YELLOW)
        return None
    url = m.group(0).rstrip(".,;:)")
    print_step("+", f"Using entered URL: {url[:90]}...", C.GREEN)
    return url


def _snapshot_files(dest_folder: Path) -> Dict[str, Tuple[int, int]]:
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


def _is_already_named_output(filename: str) -> bool:
    return bool(_RE_DONE_NAME.match(filename or ""))


def _is_instagram_url(url: str) -> bool:
    low = url.lower()
    return "instagram.com" in low or "instagr.am" in low


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


def _thumbnail_group_key(path: Path) -> str:
    name = path.name
    m = re.match(r"^(.*)\.(\d+)(\.[^.]+)$", name)
    if m:
        return m.group(1).lower()
    return path.stem.lower()


def _dedupe_thumbnail_variants(images: List[Path]) -> List[Path]:
    if not images:
        return []
    groups: Dict[str, List[Path]] = {}
    for p in images:
        groups.setdefault(_thumbnail_group_key(p), []).append(p)
    kept, removed = [], 0
    for key, paths in groups.items():
        if len(paths) == 1:
            kept.append(paths[0])
            continue
        paths_sorted = sorted(
            paths,
            key=lambda x: (x.stat().st_size if x.exists() else 0, x.name),
            reverse=True,
        )
        kept.append(paths_sorted[0])
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


def _collect_new_media(dest_folder: Path, before_meta: Dict[str, Tuple[int, int]]) -> List[Path]:
    found: List[Path] = []
    try:
        for p in dest_folder.rglob("*"):
            if not p.is_file():
                continue
            if _is_already_named_output(p.name):
                continue
            # skip nested scraper output folders
            parts_lower = [x.lower() for x in p.relative_to(dest_folder).parts]
            if any("scraper by akt" in x for x in parts_lower):
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
            if p.suffix.lower() not in ALL_EXT:
                continue
            if st.st_size < 500:
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

    # Dedupe multi-quality thumbs among images only
    images = [p for p in flattened if p.suffix.lower() in IMAGE_EXT]
    others = [p for p in flattened if p.suffix.lower() not in IMAGE_EXT]
    images = _dedupe_thumbnail_variants(images)
    out = images + others
    out.sort(key=lambda x: x.name.lower())
    return out


def _gallery_dl_available() -> bool:
    return _package_present_in_target("gallery_dl", "gallery-dl")


def download_via_gallery_dl(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    if not _gallery_dl_available():
        return [], "gallery-dl not installed"
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    cmd = [
        sys.executable, "-m", "gallery_dl",
        "--dest", str(dest_folder),
        "-f", "{id}_{num}.{extension}",
        url,
    ]
    print_step("~", f"gallery-dl: {url[:80]}...", C.DIM)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300, cwd=str(dest_folder),
            env={**os.environ, "PYTHONPATH": SITE_PACKAGES + os.pathsep + os.environ.get("PYTHONPATH", "")},
        )
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for line in log.splitlines():
            low = line.lower()
            if any(x in low for x in ("download", "error", "#", "http", "writing")):
                print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
        media = _collect_new_media(dest_folder, before)
        if media:
            for p in media:
                print_step("+", f"Saved via gallery-dl → {p.name}", C.GREEN)
            return media, log
        return [], log
    except subprocess.TimeoutExpired:
        return [], "gallery-dl timed out (300s)"
    except Exception as e:
        return [], f"gallery-dl failed: {e}"


def download_via_ytdlp(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    if not YTDLP_PATH.exists():
        return [], "yt-dlp not available"
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    out_tmpl = str(dest_folder / "%(id)s_%(playlist_index|)s%(playlist_index&_)s%(title).60B.%(ext)s")

    cmd_media = [
        str(YTDLP_PATH), url,
        "-o", out_tmpl,
        "--no-mtime",
        "-f", "bv*[height<=720]+ba/b[height<=720]/best",
        "--merge-output-format", "mp4",
        "--ignore-no-formats-error",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "--retries", "3",
    ]
    cmd_thumbs = [
        str(YTDLP_PATH), url,
        "-o", out_tmpl,
        "--no-mtime",
        "--skip-download",
        "--ignore-no-formats-error",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "--retries", "3",
    ]

    combined_log = ""

    def _run(cmd: List[str], label: str) -> str:
        print_step("~", f"yt-dlp [{label}]: {url[:80]}...", C.DIM)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300,
            )
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            for line in out.splitlines():
                low = line.lower()
                if any(x in low for x in ("download", "100%", "error", "destination", "writing", "merging", "thumbnail")):
                    print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
            return out
        except subprocess.TimeoutExpired:
            return f"yt-dlp [{label}] timed out"
        except Exception as e:
            return f"yt-dlp [{label}] failed: {e}"

    combined_log += _run(cmd_media, "media+thumbs")
    media = _collect_new_media(dest_folder, before)
    if media:
        for p in media:
            print_step("+", f"Saved via yt-dlp → {p.name}", C.GREEN)
        return media, combined_log

    if _is_instagram_url(url) or "no video formats found" in combined_log.lower():
        before2 = _snapshot_files(dest_folder)
        combined_log += "\n" + _run(cmd_thumbs, "thumbs-only")
        media = _collect_new_media(dest_folder, before2)
        if media:
            for p in media:
                print_step("+", f"Saved via yt-dlp thumbnail → {p.name}", C.GREEN)
            return media, combined_log

    print_step("!", "yt-dlp finished but no new media in folder", C.YELLOW)
    return [], combined_log


def download_media_from_url(url: str, dest_folder: Path) -> Tuple[List[Path], str, bool]:
    """
    Smart social download (same logic as forensic tools):
      Instagram → gallery-dl first, then yt-dlp
      Other social → yt-dlp first, then gallery-dl
    Returns: (media_files, log, permanent_failure)
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    logs: List[str] = []

    if _is_instagram_url(url) or "pinterest.com" in url.lower() or "reddit.com" in url.lower():
        media, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if media:
            return media, "\n".join(logs), False
        print_step("~", "gallery-dl produced no media — trying yt-dlp...", C.DIM)
        media, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if media:
            return media, "\n".join(logs), False
        return [], "\n".join(logs), _looks_permanent_download_error("\n".join(logs))

    if _is_social_media_url(url) or url.startswith("http"):
        media, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if media:
            return media, "\n".join(logs), False
        media, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if media:
            return media, "\n".join(logs), False
        return [], "\n".join(logs), _looks_permanent_download_error("\n".join(logs))

    return [], "\n".join(logs), False


def finish_url_job(url: str, saved_list: List[Path], success: bool) -> None:
    names = [p.name for p in saved_list]
    if success and saved_list:
        remove_url_from_picker(url)
        archive_completed_url(url, note=f"{len(saved_list)} file(s) downloaded + scraped")
        write_job_log(url=url, downloaded_files=names, status="OK")
    else:
        print_step("!", "Download/scrape incomplete — URL kept in picker for retry", C.YELLOW)
        write_job_log(url=url, downloaded_files=names, status="FAILED — URL kept in picker")


_EXIF_DATE_TAGS = (36867, 36868, 306)
_DATE_STRING_FORMATS = (
    "%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
    "%Y:%m:%d", "%Y-%m-%d",
)
_MP4_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


def _parse_date_string(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="ignore")
        except Exception:
            return None
    if not isinstance(value, str):
        value = str(value)
    s = value.strip().strip("\x00").strip().strip('"').strip("'")
    if not s:
        return None
    for fmt in _DATE_STRING_FORMATS:
        try:
            clean_fmt = fmt.rstrip("Z") if fmt.endswith("Z") else fmt
            probe = s[:26].rstrip("Z") if ("T" in s or "Z" in s or ":" in s[:5]) else s[:19]
            dt = datetime.strptime(probe, clean_fmt if not fmt.endswith("Z") else fmt.rstrip("Z"))
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
            hh, mm, ss = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
            return datetime(y, mo, d, hh, mm, ss).timestamp()
        except Exception:
            pass
    return None


def _mp4_seconds_to_unix(seconds: int) -> Optional[float]:
    try:
        if seconds is None or seconds <= 60:
            return None
        dt = _MP4_EPOCH.timestamp() + float(seconds)
        if 0 < dt < 4102444800:
            return dt
    except Exception:
        pass
    return None


def _read_image_exif_date_created(path: Path) -> Tuple[Optional[float], str]:
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
            labels = {
                36867: "EXIF Date created (DateTimeOriginal)",
                36868: "EXIF DateTimeDigitized",
                306: "EXIF DateTime",
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
                ts = _parse_date_string(raw)
                if ts is not None:
                    return ts, labels.get(tag_id, "EXIF")
    except Exception:
        pass
    return None, ""


def _read_mp4_creation_time(path: Path) -> Optional[float]:
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
                                    return _mp4_seconds_to_unix(int(struct.unpack(">Q", data[0:8])[0]))
                            else:
                                data = f.read(8)
                                if len(data) >= 8:
                                    return _mp4_seconds_to_unix(int(struct.unpack(">I", data[0:4])[0]))
                            return None
                        if t2 in ("trak", "mdia", "minf", "stbl", "udta", "meta"):
                            inner += h2_len
                            continue
                        inner += s2
                    return None
                pos += size
    except Exception:
        pass
    return None


def _find_ffprobe() -> Optional[str]:
    for p in FFPROBE_CANDIDATES:
        try:
            if p.exists():
                return str(p)
        except Exception:
            pass
    for name in ("ffprobe.exe", "ffprobe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _read_ffprobe_creation_time(path: Path) -> Optional[float]:
    ffprobe = _find_ffprobe()
    if not ffprobe:
        return None
    try:
        cmd = [
            ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_entries", "format_tags=creation_time:stream_tags=creation_time",
            str(path),
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20,
        )
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            return None
        data = json.loads(proc.stdout)
        tags = (data.get("format") or {}).get("tags") or {}
        for key in ("creation_time", "Creation Time", "DATE", "date",
                    "com.apple.quicktime.creationdate"):
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
    except Exception:
        pass
    return None


def _read_video_media_date_created(path: Path) -> Tuple[Optional[float], str]:
    ts = _read_ffprobe_creation_time(path)
    if ts is not None:
        return ts, "Media Date created (metadata)"
    if path.suffix.lower() in {".mp4", ".m4v", ".mov", ".3gp", ".qt"}:
        ts = _read_mp4_creation_time(path)
        if ts is not None:
            return ts, "Media Date created (MP4/MOV container)"
    return None, ""


def _read_audio_tag_date(path: Path) -> Tuple[Optional[float], str]:
    if not HAS_MUTAGEN:
        return None, ""
    try:
        audio = MutagenFile(path, easy=True)
        if audio is None:
            return None, ""
        tags = getattr(audio, "tags", None) or {}
        for key in ("date", "year", "originaldate", "creation_time"):
            val = None
            try:
                if key in tags:
                    v = tags[key]
                    val = v[0] if isinstance(v, (list, tuple)) and v else v
            except Exception:
                val = None
            if val:
                s = str(val).strip()
                if re.fullmatch(r"\d{4}", s):
                    try:
                        return datetime(int(s), 1, 1).timestamp(), f"Audio tag date ({key})"
                    except Exception:
                        pass
                ts = _parse_date_string(s)
                if ts is not None:
                    return ts, f"Audio tag date ({key})"
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


def get_media_sort_timestamp(path: Path) -> Tuple[float, str, str]:
    name_key = path.name.lower()
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        ts, source = _read_image_exif_date_created(path)
        if ts is not None:
            return (ts, source, name_key)
    elif ext in VIDEO_EXT:
        ts, source = _read_video_media_date_created(path)
        if ts is not None:
            return (ts, source, name_key)
    elif ext in AUDIO_EXT:
        ts, source = _read_audio_tag_date(path)
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


def discover_media(root: Path) -> List[Path]:
    try:
        found = []
        for i in root.iterdir():
            if not i.is_file():
                continue
            if i.suffix.lower() not in ALL_EXT:
                continue
            if _is_already_named_output(i.name):
                continue
            found.append(i)
    except Exception as e:
        log_error(f"discover: {e}")
        return []
    if not found:
        return []
    print(f"  {C.DIM}Sorting media by Date created (earliest first)...{C.RESET}")
    keyed = []
    for p in found:
        ts, source, name_key = get_media_sort_timestamp(p)
        keyed.append((ts, name_key, p, source))
        print(f"      {C.DIM}{p.name}  →  {format_ts(ts)}  [{source}]{C.RESET}")
    keyed.sort(key=lambda item: (item[0], item[1]))
    sorted_paths = [item[2] for item in keyed]
    print(f"  {C.GREEN}[OK] Order locked: earliest Date created → latest ({len(sorted_paths)} file(s)){C.RESET}\n")
    return sorted_paths


def img_to_base64(img):
    try:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        log_error(f"img_to_base64: {e}")
        return None


def translate_to_english_if_needed(original_text):
    if not original_text:
        return original_text, "Not Required"
    prompt = f"""Analyze the text.
1. Return the EXACT original text unchanged in the 'original' field.
2. STRICT RULE: If the text is ALREADY IN ENGLISH, put exactly "Not Required" in the 'english' field.
3. If the text is NOT in English, translate it to English and put it in the 'english' field.
Return ONLY valid JSON (no markdown, no commentary): {{"original": "...", "english": "..."}}

Text: {json.dumps(original_text, ensure_ascii=False)}
"""
    tokens_hint = estimate_tokens_from_text(prompt) + 500
    try:
        def make_fn(model_id: str):
            def _op(client: OpenAI):
                return chat_completions_create(
                    client,
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_completion_tokens=4000,
                    timeout=45.0,
                    response_format={"type": "json_object"},
                )
            return _op
        resp = call_with_model_fallback("translate", "translate", make_fn, tokens_hint=tokens_hint)
        raw = message_text_from_response(resp)
        data = extract_json_object(raw)
        if data:
            orig = data.get("original", original_text)
            eng = normalize_english_field(str(orig), str(data.get("english", "")))
            return orig, eng
        print(f"            {C.YELLOW}translate JSON parse failed; raw[:200]={raw[:200]!r}{C.RESET}")
    except Exception as e:
        log_error(f"translate: {e}")
        print(f"            {C.YELLOW}translate error: {e}{C.RESET}")
    return original_text, "Not Required"


def get_audio_text(fp: Path):
    if not FFMPEG_PATH.exists():
        print(f"            {C.YELLOW}ffmpeg missing{C.RESET}")
        return None
    safe_stem = re.sub(r"[^\w\-]+", "_", fp.stem)[:80]
    temp_wav = MEDIA_DIR / f"temp_audio_{safe_stem}.wav"
    try:
        print(f"            {C.DIM}[1/3] Extracting audio...{C.RESET}")
        subprocess.run(
            [str(FFMPEG_PATH), "-y", "-i", str(fp), "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", "-t", "60", str(temp_wav)],
            capture_output=True, timeout=60, text=True, encoding="utf-8", errors="replace",
        )
        if not temp_wav.exists() or temp_wav.stat().st_size == 0:
            return None
        print(f"            {C.DIM}[2/3] Transcribing...{C.RESET}")
        try:
            fsz = temp_wav.stat().st_size
            tokens_hint = max(200, min(8000, fsz // 50))
        except Exception:
            tokens_hint = 1000

        def make_fn(model_id: str):
            def _op(client: OpenAI):
                with open(temp_wav, "rb") as audio_file:
                    return client.audio.transcriptions.create(
                        model=model_id, file=audio_file, response_format="json",
                    )
            return _op

        resp = call_with_model_fallback("whisper", "whisper", make_fn, tokens_hint=tokens_hint)
        text = (getattr(resp, "text", None) or "").strip()
        return text or None
    except Exception as e:
        log_error(f"audio: {e}")
        print(f"            {C.RED}audio error: {e}{C.RESET}")
        return None
    finally:
        if temp_wav.exists():
            try:
                temp_wav.unlink()
            except Exception:
                pass


EXTRACTION_PROMPT = """Extract details from this social media image/screenshot.

Return ONLY a single valid JSON object. No markdown fences. No commentary before or after.
Use exactly these keys:
{
  "author_name": "Display name or empty string",
  "author_handle": "username/handle or empty string",
  "post_text": "EXACT original on-screen post text (do not translate)",
  "post_text_english": "If post_text is already English: exactly Not Required. If not English: full English translation.",
  "date_text": "Date/time visible on screen or empty string"
}

Rules:
- post_text must be the original language text as shown.
- If no text is visible, use empty strings and post_text_english = "Not Required".
- Do not invent authors or dates that are not visible.
- Do not wrap JSON in ``` fences.
"""


def extract_text_from_image(b64: str):
    try:
        tokens_hint = estimate_tokens_from_text(EXTRACTION_PROMPT) + max(800, len(b64) // 10)

        def make_fn(model_id: str):
            def _op(client: OpenAI):
                messages = [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }]
                return chat_completions_create(
                    client,
                    model=model_id,
                    messages=messages,
                    temperature=0.1,
                    max_completion_tokens=4000,
                    timeout=90.0,
                    response_format={"type": "json_object"},
                )
            return _op

        resp = call_with_model_fallback("image OCR", "vision", make_fn, tokens_hint=tokens_hint)
        raw = message_text_from_response(resp)
        if not raw.strip():
            print(f"            {C.RED}OCR empty response from model{C.RESET}")
            log_error("image OCR: empty content")
            return None

        data = extract_json_object(raw)
        if data:
            orig = data.get("post_text", "") or ""
            eng = normalize_english_field(str(orig), str(data.get("post_text_english", "")))
            data["post_text"] = orig
            data["post_text_english"] = eng
            data.setdefault("author_name", "")
            data.setdefault("author_handle", "")
            data.setdefault("date_text", "")
            preview = (orig or "")[:120].replace("\n", " ")
            print(f"            {C.GREEN}OCR ok — author={data.get('author_name')!r} text[:120]={preview!r}{C.RESET}")
            return data

        print(f"            {C.RED}OCR JSON parse failed{C.RESET}")
        print(f"            {C.DIM}raw[:400]={raw[:400]!r}{C.RESET}")
        log_error(f"image OCR: JSON parse failed. raw[:800]={raw[:800]!r}")
    except Exception as e:
        log_error(f"image OCR: {e}\n{traceback.format_exc()}")
        print(f"            {C.RED}OCR exception: {e}{C.RESET}")
    return None


def get_formatted_text_block(data: dict) -> str:
    return f"""DOWNLOAD DATE: {datetime.now().strftime("%d %b %Y; %H:%M")}

ORIGINAL URL OF CONTENT: 

AUTHOR: {data.get('author_name', 'Unknown')} ({data.get('author_handle', '')})

AUTHOR URL : 

CONTENT PUBLISH DATE & TIME : {data.get('date_text', 'Unknown')}

Extracted text from Post(s):

Original Language Text: {data.get('post_text', '')}

English Translated Text: {data.get('post_text_english', 'Not Required')}
"""


def append_to_combine_log(data, title: str, log_path: Path):
    try:
        with open(log_path, "a", encoding="utf-8-sig") as f:
            f.write(f"{'=' * 80}\n{title}\n{'=' * 80}\n")
            f.write(get_formatted_text_block(data))
            f.write("\n\n")
    except Exception as e:
        log_error(f"append combine log: {e}")


def unique_dest(folder: Path, filename: str) -> Path:
    dest = folder / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    ext = Path(filename).suffix
    n = 1
    while True:
        cand = folder / f"{stem}_{n}{ext}"
        if not cand.exists():
            return cand
        n += 1


def _starting_counters(folders: dict) -> dict:
    counters = {"Image": 0, "Video": 0, "Audio": 0}
    for f_type, folder in folders.items():
        if not folder.exists():
            continue
        try:
            for p in folder.iterdir():
                if not p.is_file():
                    continue
                m = _RE_DONE_NAME.match(p.name)
                if m and m.group(1).lower() == f_type.lower():
                    counters[f_type] = max(counters[f_type], int(m.group(2)))
        except Exception:
            pass
    return counters


def run_scraper(only_files: Optional[List[Path]] = None) -> Tuple[int, int]:
    """
    Scrape OCR/Whisper for media in MEDIA_DIR (or only_files if given).
    Returns (success_count, fail_count).
    """
    files = only_files if only_files is not None else discover_media(MEDIA_DIR)
    if only_files is not None:
        # sort provided list by date created
        keyed = []
        for p in only_files:
            if not p.exists() or p.suffix.lower() not in ALL_EXT:
                continue
            ts, source, name_key = get_media_sort_timestamp(p)
            keyed.append((ts, name_key, p))
        keyed.sort(key=lambda item: (item[0], item[1]))
        files = [item[2] for item in keyed]

    if not files:
        print(f"\n  {C.YELLOW}No media files in media folder:\n  {MEDIA_DIR}{C.RESET}")
        return 0, 0

    folders = {
        "Image": MEDIA_DIR / "Combined Image Scraper by AKT",
        "Video": MEDIA_DIR / "Combined Video Scraper by AKT",
        "Audio": MEDIA_DIR / "Combined Audio Scraper by AKT",
    }
    logs = {
        "Image": MEDIA_DIR / "Combine Image Scraper.txt",
        "Video": MEDIA_DIR / "Combine Video Scraper.txt",
        "Audio": MEDIA_DIR / "Combine Audio Scraper.txt",
    }
    for t in folders:
        folders[t].mkdir(parents=True, exist_ok=True)
    for log_path in logs.values():
        try:
            if not log_path.exists():
                open(log_path, "w", encoding="utf-8-sig").close()
        except Exception:
            pass
    for old in ("Image Scraper.txt", "Video Scraper.txt", "Audio Scraper.txt"):
        try:
            p = MEDIA_DIR / old
            if p.exists():
                p.unlink()
        except Exception:
            pass

    print(
        f"\n{C.CYAN}{C.BUILT_IN}{'=' * 60}\n"
        f"  SUPER SCRAPER v0.8 (multi-key Groq + URL Picker)\n"
        f"  Media folder: {MEDIA_DIR}\n"
        f"  Found {len(files)} file(s)\n"
        f"  Sort: Date created FIRST (earliest → latest)\n"
        f"  Vision : {GROQ_MODELS.get('vision')}\n"
        f"  Translate: {GROQ_MODELS.get('translate')}\n"
        f"  Whisper: {GROQ_MODELS.get('whisper')}\n"
        f"  Key delay: {KEY_SWITCH_DELAY_SECONDS}s\n"
        f"  Logs: Combine Image/Video/Audio Scraper.txt\n"
        f"{'=' * 60}{C.RESET}\n"
    )
    if GROQ_KEY_MANAGER is not None:
        print(GROQ_KEY_MANAGER.status_summary())
        print()

    counters = _starting_counters(folders)
    success = 0
    failed = 0

    for fp in files:
        ext = fp.suffix.lower()
        if ext in IMAGE_EXT:
            f_type = "Image"
        elif ext in VIDEO_EXT:
            f_type = "Video"
        elif ext in AUDIO_EXT:
            f_type = "Audio"
        else:
            continue

        counters[f_type] += 1
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", fp.name)
        new_name = f"{f_type} {counters[f_type]} {safe_name}"
        print(f"  {C.BUILT_IN}[{f_type} {counters[f_type]}] {fp.name}{C.RESET}")
        if GROQ_KEY_MANAGER is not None:
            print(f"            {C.DIM}key: {GROQ_KEY_MANAGER.current_label()}{C.RESET}")

        try:
            data = {
                "author_name": "Unknown",
                "author_handle": "user",
                "post_text": "",
                "post_text_english": "Not Required",
                "date_text": "Unknown",
            }

            if f_type == "Image":
                with Image.open(fp) as im:
                    img = im.convert("RGB")
                    if max(img.size) > 1600:
                        img.thumbnail((1600, 1600))
                    b64 = img_to_base64(img)
                if not b64:
                    print(f"            {C.RED}base64 encode failed{C.RESET}")
                else:
                    approx_bytes = (len(b64) * 3) // 4
                    print(f"            {C.DIM}image payload ~{approx_bytes/1024:.1f} KB{C.RESET}")
                    if approx_bytes > 3_500_000:
                        print(f"            {C.YELLOW}image large; re-encoding smaller...{C.RESET}")
                        with Image.open(fp) as im2:
                            img2 = im2.convert("RGB")
                            img2.thumbnail((1024, 1024))
                            buf = BytesIO()
                            img2.save(buf, format="JPEG", quality=70)
                            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    result = extract_text_from_image(b64)
                    if result:
                        data = result
                    else:
                        print(f"            {C.RED}OCR returned no data — check error_log.txt{C.RESET}")
                    gc.collect()

            elif f_type in ("Video", "Audio"):
                raw_text = get_audio_text(fp)
                if raw_text:
                    print(f"            {C.DIM}[3/3] Language check...{C.RESET}")
                    o, e = translate_to_english_if_needed(raw_text)
                    data["post_text"], data["post_text_english"] = o, e
                else:
                    data["post_text"] = "Could not extract audio/text."

            if not data.get("post_text"):
                data["post_text"] = "Could not extract text."
            if not data.get("post_text_english"):
                data["post_text_english"] = "Not Required"

            append_to_combine_log(data, new_name, logs[f_type])
            dest = unique_dest(folders[f_type], new_name)
            shutil.move(str(fp), str(dest))
            print(f"            {C.GREEN}OK → {folders[f_type].name}\\{dest.name}{C.RESET}")
            success += 1
        except Exception as e:
            log_error(f"{fp}: {e}\n{traceback.format_exc()}")
            print(f"            {C.RED}FAILED: {e}{C.RESET}")
            failed += 1
        time.sleep(1)

    if GROQ_KEY_MANAGER is not None:
        print()
        print(GROQ_KEY_MANAGER.status_summary())

    print(
        f"\n{C.GREEN}{C.BUILT_IN}{'=' * 60}\n"
        f"  SCRAPING COMPLETE!\n"
        f"  Media folders (files only):\n"
        f"    {folders['Image']}\n"
        f"    {folders['Video']}\n"
        f"    {folders['Audio']}\n"
        f"  Combine logs (outside):\n"
        f"    {logs['Image'].name}\n"
        f"    {logs['Video'].name}\n"
        f"    {logs['Audio'].name}\n"
        f"{'=' * 60}{C.RESET}\n"
    )
    return success, failed


def main():
    global GROQ_API_KEY, GROQ_KEY_MANAGER

    if os.name == "nt":
        try:
            os.system("title ULTIMATE MEDIA TOOL v0.8")
        except Exception:
            pass

    print(f"  {C.BUILT_IN}LIBRARIES (only here):{C.RESET}")
    print(f"    {LIB_ROOT}")
    print(f"    {SITE_PACKAGES}")
    print(f"    {TOOLS_DIR}")
    print()
    print(f"  {C.BUILT_IN}MEDIA (script folder):{C.RESET}")
    print(f"    {MEDIA_DIR}")
    print(f"  {C.DIM}Admin: {_is_admin()}{C.RESET}")
    print(f"  {C.DIM}Sort : Date created FIRST{C.RESET}")
    print(f"  {C.DIM}Key delay: {KEY_SWITCH_DELAY_SECONDS}s between API key switches{C.RESET}")
    print(f"  {C.DIM}Default models: vision={GROQ_MODELS.get('vision')} | "
          f"translate={GROQ_MODELS.get('translate')} | "
          f"whisper={GROQ_MODELS.get('whisper')}{C.RESET}\n")

    key_entries = extract_api_keys()
    if not key_entries:
        print(f"  {C.YELLOW}No valid Groq keys in USER_CONFIG.{C.RESET}")
        print(f"  {C.CYAN}Enter one Groq API Key now (or leave empty to exit):{C.RESET}")
        print(f"  {C.DIM}Replace YOUR_GROQ_API_KEY_* placeholders at the top of this script.{C.RESET}")
        manual = input("  > ").strip()
        if not manual:
            print(f"  {C.RED}No API key provided. Exiting.{C.RESET}")
            return
        key_entries = [{"index": 1, "slot": 1, "user_id": "manual-input", "key": manual}]

    GROQ_KEY_MANAGER = ApiKeyRotator(
        key_entries,
        rpm_limit=GROQ_RPM_LIMIT,
        rpd_limit=GROQ_RPD_LIMIT,
        tpm_limit=GROQ_TPM_LIMIT,
        provider_name="Groq",
    )
    GROQ_API_KEY = GROQ_KEY_MANAGER.get_key()

    print(f"  {C.GREEN}[OK] Loaded {len(key_entries)} Groq API key(s) from USER_CONFIG{C.RESET}")
    print(
        f"  {C.DIM}Rotation: RPM@{GROQ_RPM_ROTATE_AT}/{GROQ_RPM_LIMIT} | "
        f"RPD@{GROQ_RPD_ROTATE_AT}/{GROQ_RPD_LIMIT} | "
        f"TPM@{GROQ_TPM_ROTATE_AT}/{GROQ_TPM_LIMIT} | "
        f"Key-switch delay={KEY_SWITCH_DELAY_SECONDS}s{C.RESET}"
    )
    print(GROQ_KEY_MANAGER.status_summary())
    print()

    print(f"  {C.CYAN}Refreshing live model list from Groq...{C.RESET}")
    refresh_live_models_from_groq()
    print()

    setup_tools()
    print()
    ensure_url_picker_file()
    picker_urls = load_urls_from_picker()

    total_dl_failed = 0

    if picker_urls:
        print(
            f"\n  {C.CYAN}{C.BOLD}Found {len(picker_urls)} URL(s) in "
            f"{URL_PICKER_FILE.name} — downloading & scraping them first.{C.RESET}\n"
        )
        for i, url in enumerate(picker_urls, start=1):
            print(f"  {C.BOLD}[Picker URL {i}/{len(picker_urls)}] {url}{C.RESET}")
            try:
                saved_list, dl_log, permanent = download_media_from_url(url, MEDIA_DIR)
                if not saved_list:
                    if permanent:
                        print_step("!", "Permanent download failure — URL quarantined", C.RED)
                        quarantine_url_as_failed(url, reason="permanent download failure")
                    else:
                        print_step("!", "Download failed — URL kept in picker for retry", C.YELLOW)
                    total_dl_failed += 1
                    continue
                print_step("+", f"Downloaded {len(saved_list)} media file(s) from URL", C.GREEN)
                s, f = run_scraper(only_files=saved_list)
                finish_url_job(url, saved_list, success=(s > 0))
            except Exception as e:
                print_step("!", f"Picker URL job failed (URL kept in file): {e}", C.RED)
                total_dl_failed += 1
                log_error(f"picker job: {e}\n{traceback.format_exc()}")
            print()
        # Also process any remaining local media
        remaining = discover_media(MEDIA_DIR)
        if remaining:
            print_step("~", f"Also found {len(remaining)} local media file(s) to scrape...", C.CYAN)
            run_scraper(only_files=remaining)
    else:
        manual_url = get_url_with_timeout(8.0)
        if manual_url:
            print(f"  {C.BOLD}[Manual URL] {manual_url}{C.RESET}")
            try:
                saved_list, dl_log, permanent = download_media_from_url(manual_url, MEDIA_DIR)
                if not saved_list:
                    if permanent:
                        print_step("!", "Permanent download failure — URL quarantined", C.RED)
                        quarantine_url_as_failed(manual_url, reason="permanent download failure")
                    else:
                        print_step("!", "Download failed", C.YELLOW)
                    total_dl_failed += 1
                else:
                    print_step("+", f"Downloaded {len(saved_list)} media file(s) from URL", C.GREEN)
                    s, f = run_scraper(only_files=saved_list)
                    archive_completed_url(manual_url, note="manual Enter-URL")
                    write_job_log(
                        url=manual_url,
                        downloaded_files=[p.name for p in saved_list],
                        status="COMPLETED (manual URL)",
                    )
            except Exception as e:
                print_step("!", f"Manual URL job failed: {e}", C.RED)
                total_dl_failed += 1
                log_error(f"manual url: {e}\n{traceback.format_exc()}")

        remaining = discover_media(MEDIA_DIR)
        if remaining:
            run_scraper(only_files=remaining)
        elif total_dl_failed == 0:
            print(f"\n  {C.YELLOW}No media files found.{C.RESET}")
            print(f"  Put media next to this .py, or URLs in: {URL_PICKER_FILE.name}")

    print(f"\n  URL picker (active):\n  {C.CYAN}{URL_PICKER_FILE}{C.RESET}")
    print(f"  URL picker Done:\n  {C.CYAN}{URL_PICKER_DONE}{C.RESET}")
    print(f"  Failed URLs:\n  {C.CYAN}{URL_PICKER_FAILED}{C.RESET}")
    print(f"  Job log:\n  {C.CYAN}{JOB_LOG_FILE}{C.RESET}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {C.YELLOW}Stopped by user.{C.RESET}\n")
    except Exception as e:
        _log_crash(e)
    finally:
        try:
            input("\n  Press Enter to exit...")
        except Exception:
            pass
