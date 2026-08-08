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
  - Download: Instagram via yt-dlp + browser cookies (Firefox→Chrome→…; MEDIA ONLY)
               Other social via gallery-dl + yt-dlp (ignore-no-formats + media)
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

1. Enter Groq API Key (userID: your_email_1@example.com):	gsk_YOUR_GROQ_API_KEY_01

2. Enter Groq API Key (userID: your_email_2@example.com):	gsk_YOUR_GROQ_API_KEY_02

3. Enter Groq API Key (userID: your_email_3@example.com):	gsk_YOUR_GROQ_API_KEY_03

4. Enter Groq API Key (userID: your_email_4@example.com):	gsk_YOUR_GROQ_API_KEY_04

5. Enter Groq API Key (userID: your_email_5@example.com):	gsk_YOUR_GROQ_API_KEY_05

6. Enter Groq API Key (userID: your_email_6@example.com):	gsk_YOUR_GROQ_API_KEY_06

7. Enter Groq API Key (userID: your_email_7@example.com):	gsk_YOUR_GROQ_API_KEY_07

8. Enter Groq API Key (userID: your_email_8@example.com):	gsk_YOUR_GROQ_API_KEY_08

9. Enter Groq API Key (userID: your_email_9@example.com):	gsk_YOUR_GROQ_API_KEY_09

10. Enter Groq API Key (userID: your_email_10@example.com):	gsk_YOUR_GROQ_API_KEY_10

11. Enter Groq API Key (userID: your_email_11@example.com):	gsk_YOUR_GROQ_API_KEY_11

12. Enter Groq API Key (userID: your_email_12@example.com):	gsk_YOUR_GROQ_API_KEY_12

"""
# ====
# END USER CONFIG
# ====

import base64
import ctypes
import datetime as _dt
import importlib
import json
import mimetypes
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


VERSION = "0.8"
LIB_ROOT = Path(r"C:\AKT Media Tools")
LIB_DIR = LIB_ROOT / "Lib"
SITE_PACKAGES_PATH = LIB_DIR / "site-packages"
SITE_PACKAGES = str(SITE_PACKAGES_PATH)
BIN_ROOT = LIB_ROOT / "bin"
YTDLP_PATH = BIN_ROOT / "yt-dlp.exe"

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent

PICKER_FILE = SCRIPT_DIR / "Ultimate Media Tool URL Picker.txt"
PICKER_DONE_FILE = SCRIPT_DIR / "Ultimate Media Tool URL Picker Done.txt"
PICKER_FAILED_FILE = SCRIPT_DIR / "Ultimate Media Tool URL Picker Failed.txt"
JOB_LOG_FILE = SCRIPT_DIR / "Ultimate Media Tool Job Log.txt"

COMBINED_IMAGE_DIR = SCRIPT_DIR / "Combined Image Scraper by AKT"
COMBINED_VIDEO_DIR = SCRIPT_DIR / "Combined Video Scraper by AKT"
COMBINED_AUDIO_DIR = SCRIPT_DIR / "Combined Audio Scraper by AKT"

COMBINE_IMAGE_LOG = SCRIPT_DIR / "Combine Image Scraper.txt"
COMBINE_VIDEO_LOG = SCRIPT_DIR / "Combine Video Scraper.txt"
COMBINE_AUDIO_LOG = SCRIPT_DIR / "Combine Audio Scraper.txt"

DOWNLOAD_ROOT = SCRIPT_DIR / "Downloaded Media Scraper by AKT"

GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_RPM_LIMIT = 30
GROQ_ROTATE_AT_RPM = 29
GROQ_KEY_SWITCH_DELAY_SECONDS = 600
GROQ_REQUEST_TIMEOUT = 120
VISION_MODELS = [
    "qwen/qwen3.6-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.2-90b-vision-preview",
]
TRANSLATE_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]
WHISPER_MODEL = "whisper-large-v3"

REQUIRED_PACKAGES = [
    ("requests", "requests"),
    ("PIL", "Pillow"),
    ("mutagen", "mutagen"),
    ("yt_dlp", "yt-dlp"),
    ("gallery_dl", "gallery-dl"),
]

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".heic", ".heif", ".avif",
}
VIDEO_EXTS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".mpeg", ".mpg", ".3gp",
}
AUDIO_EXTS = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wma", ".aiff", ".aif",
}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS | AUDIO_EXTS
SIDECAR_EXTS = {
    ".json", ".info.json", ".description", ".comments", ".part", ".ytdl", ".url", ".txt",
}


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def _use_color() -> bool:
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def color(text: str, code: str) -> str:
    if not _use_color():
        return text
    return f"{code}{text}{C.RESET}"


def print_step(prefix: str, message: str, code: str = "") -> None:
    marker = color(prefix, code) if code else prefix
    print(f"{marker} {message}", flush=True)


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def file_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        try:
            if stream and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def is_windows() -> bool:
    return os.name == "nt"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def append_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", errors="replace") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def read_text_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def write_text_lines(path: Path, lines: Sequence[str]) -> None:
    ensure_dir(path.parent)
    path.write_text("\n".join(lines).rstrip() + ("\n" if lines else ""), encoding="utf-8")


def is_writable_folder(path: Path) -> bool:
    try:
        ensure_dir(path)
        probe = path / f".write_test_{os.getpid()}_{int(time.time())}.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def soft_uac_if_needed() -> None:
    """
    Elevates only when C:\\AKT Media Tools cannot be written by the current user.
    If elevation is unavailable or declined, the script continues and pip will show
    the real install error instead of forcing an early exit.
    """
    if not is_windows():
        ensure_dir(SITE_PACKAGES_PATH)
        ensure_dir(BIN_ROOT)
        return
    if is_writable_folder(LIB_ROOT):
        ensure_dir(SITE_PACKAGES_PATH)
        ensure_dir(BIN_ROOT)
        return
    if os.environ.get("AKT_UMT_ELEVATED") == "1":
        return
    print_step("!", f"{LIB_ROOT} is not writable. Requesting soft UAC elevation...", C.YELLOW)
    params = " ".join([f'"{arg}"' for arg in sys.argv])
    env_cmd = f'/c set AKT_UMT_ELEVATED=1&& "{sys.executable}" {params}'
    try:
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", env_cmd, None, 1)
        if rc > 32:
            sys.exit(0)
    except Exception as exc:
        print_step("!", f"UAC request skipped: {exc}", C.YELLOW)


def add_site_packages_to_path() -> None:
    ensure_dir(SITE_PACKAGES_PATH)
    site = str(SITE_PACKAGES_PATH)
    if site not in sys.path:
        sys.path.insert(0, site)
    current = os.environ.get("PYTHONPATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    if site not in parts:
        os.environ["PYTHONPATH"] = site + (os.pathsep + current if current else "")
    if is_windows():
        scripts = SITE_PACKAGES_PATH.parent / "Scripts"
        os.environ["PATH"] = str(scripts) + os.pathsep + str(BIN_ROOT) + os.pathsep + os.environ.get("PATH", "")
    else:
        os.environ["PATH"] = str(BIN_ROOT) + os.pathsep + os.environ.get("PATH", "")


def import_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def pip_install_target(pip_name: str) -> bool:
    ensure_dir(SITE_PACKAGES_PATH)
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(SITE_PACKAGES_PATH),
        "--no-warn-script-location",
        pip_name,
    ]
    print_step("~", f"Installing/updating {pip_name} into {SITE_PACKAGES_PATH}", C.DIM)
    try:
        subprocess.check_call(cmd)
        importlib.invalidate_caches()
        return True
    except Exception as exc:
        print_step("!", f"Package install failed for {pip_name}: {exc}", C.YELLOW)
        return False


def install_required_packages() -> None:
    add_site_packages_to_path()
    for module_name, pip_name in REQUIRED_PACKAGES:
        if import_available(module_name):
            continue
        pip_install_target(pip_name)
    add_site_packages_to_path()


def bootstrap_environment() -> None:
    soft_uac_if_needed()
    ensure_dir(LIB_ROOT)
    ensure_dir(LIB_DIR)
    ensure_dir(SITE_PACKAGES_PATH)
    ensure_dir(BIN_ROOT)
    add_site_packages_to_path()
    install_required_packages()
    ensure_dir(COMBINED_IMAGE_DIR)
    ensure_dir(COMBINED_VIDEO_DIR)
    ensure_dir(COMBINED_AUDIO_DIR)
    ensure_dir(DOWNLOAD_ROOT)
    ensure_picker_file()


def mask_user_id(user_id: str) -> str:
    user_id = (user_id or "").strip()
    if "@" not in user_id:
        return user_id[:2] + "***" if user_id else "unknown"
    local, domain = user_id.split("@", 1)
    masked_local = (local[:2] + "***") if len(local) > 2 else "***"
    domain_parts = domain.split(".")
    if domain_parts:
        domain_parts[0] = (domain_parts[0][:1] + "***") if domain_parts[0] else "***"
    return masked_local + "@" + ".".join(domain_parts)


def is_placeholder_key(api_key: str) -> bool:
    return "YOUR_GROQ_API_KEY" in api_key or api_key.endswith("_PLACEHOLDER")


def parse_user_config() -> List[Dict[str, str]]:
    accounts: List[Dict[str, str]] = []
    pattern = re.compile(
        r"Enter\s+Groq\s+API\s+Key\s*\(userID:\s*([^)]+)\)\s*:\s*(gsk_[A-Za-z0-9_\-]+)",
        re.IGNORECASE,
    )
    for match in pattern.finditer(USER_CONFIG):
        user_id = match.group(1).strip()
        api_key = match.group(2).strip()
        if not api_key.startswith("gsk_"):
            continue
        if is_placeholder_key(api_key):
            continue
        accounts.append({"user_id": user_id, "api_key": api_key})
    return accounts


class GroqKeyRotator:
    def __init__(self, accounts: Sequence[Dict[str, str]]):
        self.accounts: List[Dict[str, object]] = []
        self.index = 0
        self.last_switch_at = 0.0
        for account in accounts:
            self.accounts.append(
                {
                    "user_id": account.get("user_id", "unknown"),
                    "api_key": account.get("api_key", ""),
                    "rpm_count": 0,
                    "rpm_window": time.time(),
                    "rpd_count": 0,
                    "disabled_until": 0.0,
                    "errors": 0,
                }
            )

    def has_keys(self) -> bool:
        return bool(self.accounts)

    def _refresh_window(self, account: Dict[str, object]) -> None:
        now = time.time()
        if now - float(account["rpm_window"]) >= 60:
            account["rpm_window"] = now
            account["rpm_count"] = 0

    def _available(self, account: Dict[str, object]) -> bool:
        self._refresh_window(account)
        if time.time() < float(account["disabled_until"]):
            return False
        return int(account["rpm_count"]) < GROQ_ROTATE_AT_RPM

    def current_account(self) -> Optional[Dict[str, object]]:
        if not self.accounts:
            return None
        for offset in range(len(self.accounts)):
            idx = (self.index + offset) % len(self.accounts)
            account = self.accounts[idx]
            if self._available(account):
                if idx != self.index:
                    self._switch_to(idx)
                return account
        wait_until = min(float(account["disabled_until"]) for account in self.accounts)
        sleep_for = max(0.0, min(60.0, wait_until - time.time()))
        if sleep_for:
            print_step("~", f"All Groq keys cooling down. Sleeping {sleep_for:.0f}s...", C.DIM)
            time.sleep(sleep_for)
        for account in self.accounts:
            self._refresh_window(account)
        return self.accounts[self.index]

    def _switch_to(self, idx: int) -> None:
        now = time.time()
        if self.last_switch_at and now - self.last_switch_at < GROQ_KEY_SWITCH_DELAY_SECONDS:
            delay = GROQ_KEY_SWITCH_DELAY_SECONDS - (now - self.last_switch_at)
            print_step("~", f"Groq key switch delay: sleeping {delay:.0f}s", C.DIM)
            time.sleep(delay)
        self.index = idx
        self.last_switch_at = time.time()
        account = self.accounts[self.index]
        print_step("~", f"Switched Groq key to {mask_user_id(str(account['user_id']))}", C.CYAN)

    def mark_request(self, account: Dict[str, object]) -> None:
        self._refresh_window(account)
        account["rpm_count"] = int(account["rpm_count"]) + 1
        account["rpd_count"] = int(account["rpd_count"]) + 1
        if int(account["rpm_count"]) >= GROQ_ROTATE_AT_RPM:
            account["disabled_until"] = max(float(account["disabled_until"]), time.time() + 60)
            next_idx = (self.accounts.index(account) + 1) % len(self.accounts)
            if next_idx != self.index and len(self.accounts) > 1:
                self._switch_to(next_idx)

    def mark_error(self, account: Dict[str, object], status: Optional[int] = None) -> None:
        account["errors"] = int(account["errors"]) + 1
        if status in (401, 403):
            account["disabled_until"] = time.time() + 24 * 3600
        elif status in (429, 503):
            account["disabled_until"] = time.time() + 600
        elif int(account["errors"]) >= 3:
            account["disabled_until"] = time.time() + 300

    def balance_report(self) -> str:
        if not self.accounts:
            return "Groq keys: none configured (USER_CONFIG placeholders only)"
        rows = []
        for i, account in enumerate(self.accounts, 1):
            self._refresh_window(account)
            rows.append(
                f"{i}. {mask_user_id(str(account['user_id']))} "
                f"RPM {account['rpm_count']}/{GROQ_RPM_LIMIT} "
                f"(rotate at {GROQ_ROTATE_AT_RPM}) RPD {account['rpd_count']}"
            )
        return "\n".join(rows)


def groq_json_request(rotator: GroqKeyRotator, method: str, endpoint: str, payload: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    if not rotator.has_keys():
        raise RuntimeError("No usable Groq API keys in USER_CONFIG")
    account = rotator.current_account()
    if not account:
        raise RuntimeError("No Groq API key available")
    data = None
    headers = {
        "Authorization": f"Bearer {account['api_key']}",
        "Content-Type": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(GROQ_API_BASE + endpoint, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=GROQ_REQUEST_TIMEOUT) as response:
            rotator.mark_request(account)
            body = response.read().decode("utf-8", errors="replace")
            return json.loads(body or "{}")
    except urllib.error.HTTPError as exc:
        rotator.mark_error(account, exc.code)
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq HTTP {exc.code}: {body[:500]}")
    except Exception:
        rotator.mark_error(account)
        raise


def groq_multipart_request(rotator: GroqKeyRotator, endpoint: str, fields: Dict[str, str], file_field: str, file_path: Path) -> Dict[str, object]:
    if not rotator.has_keys():
        raise RuntimeError("No usable Groq API keys in USER_CONFIG")
    account = rotator.current_account()
    if not account:
        raise RuntimeError("No Groq API key available")
    boundary = "----AKTUMTBoundary" + str(int(time.time() * 1000))
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    filename = file_path.name
    mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
    body.extend(file_path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    headers = {
        "Authorization": f"Bearer {account['api_key']}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    request = urllib.request.Request(GROQ_API_BASE + endpoint, data=bytes(body), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=GROQ_REQUEST_TIMEOUT) as response:
            rotator.mark_request(account)
            return json.loads(response.read().decode("utf-8", errors="replace") or "{}")
    except urllib.error.HTTPError as exc:
        rotator.mark_error(account, exc.code)
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Groq HTTP {exc.code}: {body_text[:500]}")
    except Exception:
        rotator.mark_error(account)
        raise


def discover_models(rotator: GroqKeyRotator) -> Dict[str, str]:
    chosen = {
        "vision": VISION_MODELS[0],
        "translate": TRANSLATE_MODELS[0],
        "whisper": WHISPER_MODEL,
    }
    if not rotator.has_keys():
        return chosen
    try:
        data = groq_json_request(rotator, "GET", "/models")
        ids = {str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict)}
        for model in VISION_MODELS:
            if model in ids:
                chosen["vision"] = model
                break
        for model in TRANSLATE_MODELS:
            if model in ids:
                chosen["translate"] = model
                break
        if WHISPER_MODEL in ids:
            chosen["whisper"] = WHISPER_MODEL
    except Exception as exc:
        print_step("!", f"Groq /models discovery skipped: {exc}", C.YELLOW)
    return chosen


def data_url_for_image(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def groq_vision_ocr(rotator: GroqKeyRotator, model: str, path: Path) -> str:
    prompt = (
        "Extract all visible text from this image. Then briefly describe the scene, "
        "people, objects, logos, labels, and any important visual context. Return plain text."
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url_for_image(path)}},
                ],
            }
        ],
        "temperature": 0,
    }
    data = groq_json_request(rotator, "POST", "/chat/completions", payload)
    choices = data.get("choices", [])
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        if isinstance(message, dict):
            return str(message.get("content", "")).strip()
    return ""


def groq_translate_cleanup(rotator: GroqKeyRotator, model: str, text: str) -> str:
    if not text.strip() or not rotator.has_keys():
        return text
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Clean OCR/transcript text, preserve facts, translate non-English to English when helpful.",
            },
            {"role": "user", "content": text[:12000]},
        ],
        "temperature": 0,
    }
    try:
        data = groq_json_request(rotator, "POST", "/chat/completions", payload)
        choices = data.get("choices", [])
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                return str(message.get("content", text)).strip() or text
    except Exception as exc:
        print_step("!", f"Translate cleanup skipped: {exc}", C.YELLOW)
    return text


def groq_whisper(rotator: GroqKeyRotator, model: str, path: Path) -> str:
    data = groq_multipart_request(
        rotator,
        "/audio/transcriptions",
        {"model": model, "response_format": "json", "temperature": "0"},
        "file",
        path,
    )
    return str(data.get("text", "")).strip()


def which_tool(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    if is_windows() and not name.lower().endswith(".exe"):
        found = shutil.which(name + ".exe")
        if found:
            return found
    return None


def extract_audio_for_whisper(video_path: Path) -> Optional[Path]:
    ffmpeg = which_tool("ffmpeg")
    if not ffmpeg:
        return None
    tmp_dir = Path(tempfile.mkdtemp(prefix="umt_audio_"))
    out_path = tmp_dir / (video_path.stem[:80] + ".mp3")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(out_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path
    except Exception:
        pass
    return None


def classify_media(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in VIDEO_EXTS:
        return "video"
    if suffix in AUDIO_EXTS:
        return "audio"
    return "other"


def is_media_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in MEDIA_EXTS and not path.name.startswith(".")


def sidecar_or_temp(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name.endswith(".info.json"):
        return True
    return suffix in SIDECAR_EXTS or name.endswith(".part")


def safe_filename(text: str, limit: int = 120) -> str:
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = "media"
    return text[:limit].rstrip(" .")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def parse_datetime_text(value: object) -> Optional[_dt.datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    candidates = [
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%a %b %d %H:%M:%S %z %Y",
    ]
    for fmt in candidates:
        try:
            dt = _dt.datetime.strptime(text[:32], fmt)
            if dt.tzinfo:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except Exception:
            continue
    try:
        dt = _dt.datetime.fromisoformat(text)
        if dt.tzinfo:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def exif_datetime(path: Path) -> Optional[_dt.datetime]:
    try:
        from PIL import ExifTags, Image
    except Exception:
        return None
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None
            tags = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
            for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                dt = parse_datetime_text(tags.get(key))
                if dt:
                    return dt
    except Exception:
        return None
    return None


def sidecar_datetime(path: Path) -> Optional[_dt.datetime]:
    candidates = [
        path.with_suffix(path.suffix + ".json"),
        path.with_suffix(".info.json"),
        path.parent / (path.stem + ".info.json"),
    ]
    fields = [
        "date",
        "created_at",
        "created_time",
        "upload_date",
        "timestamp",
        "release_timestamp",
        "modified_date",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for field in fields:
            value = data.get(field)
            if isinstance(value, (int, float)):
                try:
                    return _dt.datetime.fromtimestamp(float(value))
                except Exception:
                    continue
            if field == "upload_date" and isinstance(value, str) and re.fullmatch(r"\d{8}", value):
                try:
                    return _dt.datetime.strptime(value, "%Y%m%d")
                except Exception:
                    continue
            dt = parse_datetime_text(value)
            if dt:
                return dt
    return None


def mutagen_datetime(path: Path) -> Optional[_dt.datetime]:
    try:
        import mutagen
    except Exception:
        return None
    try:
        media = mutagen.File(str(path), easy=True)
        if not media:
            return None
        for key in ("date", "originaldate", "year", "creationdate"):
            values = media.get(key)
            if not values:
                continue
            if isinstance(values, (list, tuple)):
                values = values[0]
            dt = parse_datetime_text(values)
            if dt:
                return dt
    except Exception:
        return None
    return None


def file_datetime(path: Path) -> _dt.datetime:
    try:
        stat = path.stat()
        ts = getattr(stat, "st_birthtime", None) or stat.st_mtime
        return _dt.datetime.fromtimestamp(ts)
    except Exception:
        return _dt.datetime.now()


def media_datetime(path: Path) -> _dt.datetime:
    for getter in (exif_datetime, sidecar_datetime, mutagen_datetime):
        dt = getter(path)
        if dt:
            return dt
    return file_datetime(path)


def media_sort_key(path: Path) -> Tuple[_dt.datetime, str]:
    return media_datetime(path), path.name.lower()


def scrape_media_file(path: Path, rotator: GroqKeyRotator, models: Dict[str, str]) -> str:
    kind = classify_media(path)
    if not rotator.has_keys():
        return "Scraper skipped: USER_CONFIG contains placeholders only."
    try:
        if kind == "image":
            text = groq_vision_ocr(rotator, models["vision"], path)
            return groq_translate_cleanup(rotator, models["translate"], text)
        if kind == "audio":
            text = groq_whisper(rotator, models["whisper"], path)
            return groq_translate_cleanup(rotator, models["translate"], text)
        if kind == "video":
            audio = extract_audio_for_whisper(path)
            if not audio:
                return "Whisper skipped: ffmpeg not found or audio extraction failed."
            text = groq_whisper(rotator, models["whisper"], audio)
            return groq_translate_cleanup(rotator, models["translate"], text)
    except Exception as exc:
        return f"Scraper error: {exc}"
    return ""


def combined_target(kind: str) -> Tuple[Path, Path, str]:
    if kind == "image":
        return COMBINED_IMAGE_DIR, COMBINE_IMAGE_LOG, "Image"
    if kind == "video":
        return COMBINED_VIDEO_DIR, COMBINE_VIDEO_LOG, "Video"
    if kind == "audio":
        return COMBINED_AUDIO_DIR, COMBINE_AUDIO_LOG, "Audio"
    return SCRIPT_DIR, JOB_LOG_FILE, "Media"


def copy_to_combined(path: Path, index: int, kind: str) -> Path:
    folder, _log, label = combined_target(kind)
    ensure_dir(folder)
    dt = media_datetime(path)
    date_prefix = dt.strftime("%Y-%m-%d_%H-%M-%S")
    base = safe_filename(path.stem, 80)
    target = unique_path(folder / f"{label} {index} {date_prefix} {base}{path.suffix.lower()}")
    shutil.copy2(str(path), str(target))
    return target


def scrape_and_combine(files: Sequence[Path], rotator: GroqKeyRotator, models: Dict[str, str], job_name: str) -> Dict[str, List[Path]]:
    grouped: Dict[str, List[Path]] = {"image": [], "video": [], "audio": []}
    for file_path in files:
        kind = classify_media(file_path)
        if kind in grouped:
            grouped[kind].append(file_path)
    results: Dict[str, List[Path]] = {"image": [], "video": [], "audio": []}
    for kind, paths in grouped.items():
        paths = sorted([p for p in paths if p.exists()], key=media_sort_key)
        for idx, source in enumerate(paths, 1):
            target = copy_to_combined(source, idx, kind)
            results[kind].append(target)
            dt = media_datetime(source)
            _folder, log_path, label = combined_target(kind)
            print_step("+", f"{label} {idx}: {target.name}", C.GREEN)
            scraped = scrape_media_file(target, rotator, models)
            log_entry = [
                "=" * 72,
                f"{label} {idx}",
                f"Job: {job_name}",
                f"Time: {now_stamp()}",
                f"Media date: {dt.isoformat(sep=' ')}",
                f"Source: {source}",
                f"Combined: {target}",
                "",
                scraped.strip() or "(no OCR/transcript text)",
                "",
            ]
            append_text(log_path, "\n".join(log_entry))
    return results


def _snapshot_files(folder: Path) -> Dict[Path, Tuple[int, int]]:
    snapshot: Dict[Path, Tuple[int, int]] = {}
    if not folder.exists():
        return snapshot
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
            snapshot[path.resolve()] = (stat.st_size, stat.st_mtime_ns)
        except Exception:
            continue
    return snapshot


def _collect_new_media(folder: Path, before: Dict[Path, Tuple[int, int]]) -> List[Path]:
    found: List[Path] = []
    if not folder.exists():
        return found
    for path in folder.rglob("*"):
        if not is_media_file(path) or sidecar_or_temp(path):
            continue
        try:
            resolved = path.resolve()
            stat = path.stat()
            old = before.get(resolved)
            if old is None or old != (stat.st_size, stat.st_mtime_ns):
                if stat.st_size > 0:
                    found.append(path)
        except Exception:
            continue
    return sorted(found, key=lambda p: p.name.lower())


BROWSERS = ["firefox", "chrome", "edge", "brave", "opera", "chromium", "vivaldi"]


def _ytdlp_bin() -> Optional[str]:
    """Prefer bundled yt-dlp.exe; fall back to python -m yt_dlp."""
    try:
        if YTDLP_PATH.exists() and YTDLP_PATH.stat().st_size > 1000:
            return str(YTDLP_PATH)
    except Exception:
        pass
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
    Uses before/after file snapshot so leftover files never count as success.
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    if _ytdlp_bin() is None:
        # Ensure python module path can see target site-packages
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "--upgrade", "--target", SITE_PACKAGES, "yt-dlp"]
                )
                importlib.invalidate_caches()
            except Exception as e:
                return [], f"yt-dlp not available: {e}"

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

    # Try each browser's cookies
    for browser in BROWSERS:
        before = _snapshot_files(dest_folder)
        cmd = _instagram_ytdlp_base_cmd(url, out_tmpl) + ["--cookies-from-browser", browser]
        print_step("~", f"Trying {browser.upper()} cookies...", C.DIM)
        log = _run(cmd, f"cookies:{browser}")
        combined_log.append(f"=== cookies:{browser} ===\n{log}")
        media = _collect_new_media(dest_folder, before)
        if media:
            for p in media:
                print_step("+", f"Saved via Instagram yt-dlp ({browser}) → {p.name}", C.GREEN)
            print_step("+", f"Download finished via {browser.upper()} cookies!", C.GREEN)
            return media, "\n".join(combined_log)
        print_step("!", f"{browser} cookies produced no new media — next...", C.YELLOW)

    # Final attempt: public / no cookies
    before = _snapshot_files(dest_folder)
    print_step("~", "Final Instagram attempt without cookies (public only)...", C.DIM)
    log = _run(_instagram_ytdlp_base_cmd(url, out_tmpl), "public")
    combined_log.append(f"=== public ===\n{log}")
    media = _collect_new_media(dest_folder, before)
    if media:
        for p in media:
            print_step("+", f"Saved via Instagram yt-dlp (public) → {p.name}", C.GREEN)
        print_step("+", "Download finished (public / no cookies)!", C.GREEN)
        return media, "\n".join(combined_log)

    print_step("!", "Instagram yt-dlp finished but no new media in folder", C.YELLOW)
    print_step(
        "!",
        "FIX: Firefox → instagram.com → log in → CLOSE Firefox → re-run",
        C.YELLOW,
    )
    return [], "\n".join(combined_log)


def downloader_env() -> Dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": SITE_PACKAGES + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }


def _run_downloader(cmd: List[str], dest_folder: Path, timeout: int = 600) -> str:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(dest_folder),
            env=downloader_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        for line in out.splitlines():
            low = line.lower()
            if any(x in low for x in ("download", "100%", "error", "warning", "destination", "merging", "extract")):
                print(f"      {C.DIM}{line.strip()[:150]}{C.RESET}")
        return out
    except subprocess.TimeoutExpired:
        return f"Downloader timed out after {timeout}s"
    except Exception as exc:
        return f"Downloader failed: {exc}"


def download_via_gallery_dl(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    cmd = [
        sys.executable,
        "-m",
        "gallery_dl",
        "--ignore-config",
        "--directory",
        str(dest_folder),
        "--filename",
        "{category}_{id}_{num}.{extension}",
        url,
    ]
    print_step("~", f"gallery-dl: {url[:90]}...", C.DIM)
    log = _run_downloader(cmd, dest_folder, timeout=600)
    media = _collect_new_media(dest_folder, before)
    for path in media:
        print_step("+", f"Saved via gallery-dl → {path.name}", C.GREEN)
    return media, log


def download_via_ytdlp(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    out_tmpl = str(dest_folder / "%(extractor)s_%(id)s_%(playlist_index|)s%(playlist_index&_)s%(title).80B.%(ext)s")
    ytdlp = _ytdlp_bin()
    if ytdlp:
        cmd = [ytdlp, url, "-o", out_tmpl]
    else:
        cmd = [sys.executable, "-m", "yt_dlp", url, "-o", out_tmpl]
    cmd += [
        "--yes-playlist",
        "--ignore-errors",
        "--ignore-no-formats-error",
        "--no-mtime",
        "-f",
        "bv*+ba/b/best",
        "--format-sort",
        "res,br,size",
        "--concurrent-fragments",
        "8",
        "--write-info-json",
        "--write-thumbnail",
        "--convert-thumbnails",
        "jpg",
        "--write-description",
        "--write-comments",
        "--retries",
        "3",
    ]
    print_step("~", f"yt-dlp: {url[:90]}...", C.DIM)
    log = _run_downloader(cmd, dest_folder, timeout=600)
    media = _collect_new_media(dest_folder, before)
    for path in media:
        print_step("+", f"Saved via yt-dlp → {path.name}", C.GREEN)
    return media, log


def _is_instagram_url(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        host = url.lower()
    return "instagram.com" in host or "instagr.am" in host


def _is_social_media_url(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        host = url.lower()
    social_hosts = [
        "instagram.com",
        "instagr.am",
        "facebook.com",
        "fb.watch",
        "tiktok.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "youtu.be",
        "reddit.com",
        "pinterest.com",
        "pin.it",
        "threads.net",
        "snapchat.com",
        "vimeo.com",
        "dailymotion.com",
        "soundcloud.com",
        "tumblr.com",
    ]
    return any(host.endswith(domain) or domain in host for domain in social_hosts)


def _looks_permanent_download_error(log: str) -> bool:
    low = (log or "").lower()
    permanent_markers = [
        "404 not found",
        "not found",
        "does not exist",
        "unavailable",
        "private video",
        "this account is private",
        "login required",
        "requested content is not available",
        "no video formats found",
        "unsupported url",
        "unable to extract",
    ]
    return any(marker in low for marker in permanent_markers)


def download_media_from_url(url: str, dest_folder: Path) -> Tuple[List[Path], str, bool]:
    """
    Smart social download:
      Instagram → yt-dlp + browser cookies (Firefox first; MEDIA ONLY)  [archiver logic]
                  then gallery-dl fallback if still empty
      Pinterest/Reddit → gallery-dl first, then yt-dlp
      Other social → yt-dlp first, then gallery-dl
    Returns: (media_files, log, permanent_failure)
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    logs: List[str] = []

    # ---- Instagram: archiver cookie / media-only logic ----
    if _is_instagram_url(url):
        media, log = download_via_instagram_ytdlp(url, dest_folder)
        logs.append(log)
        if media:
            return media, "\n".join(logs), False
        print_step("~", "Instagram cookie/yt-dlp produced no media — trying gallery-dl...", C.DIM)
        media, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if media:
            return media, "\n".join(logs), False
        return [], "\n".join(logs), _looks_permanent_download_error("\n".join(logs))

    # ---- Pinterest / Reddit: gallery-dl first ----
    if "pinterest.com" in url.lower() or "reddit.com" in url.lower():
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


def ensure_picker_file() -> None:
    if not PICKER_FILE.exists():
        PICKER_FILE.write_text(
            "# Paste one URL per line. Lines starting with # are ignored.\n",
            encoding="utf-8",
        )
    for path in (PICKER_DONE_FILE, PICKER_FAILED_FILE, JOB_LOG_FILE):
        if not path.exists():
            path.write_text("", encoding="utf-8")


def normalize_url_line(line: str) -> str:
    line = line.strip()
    if not line or line.startswith("#"):
        return ""
    return line


def picker_urls() -> List[str]:
    ensure_picker_file()
    urls: List[str] = []
    for line in read_text_lines(PICKER_FILE):
        url = normalize_url_line(line)
        if url:
            urls.append(url)
    return urls


def remove_url_from_picker(done_url: str) -> None:
    lines = read_text_lines(PICKER_FILE)
    new_lines: List[str] = []
    removed = False
    for line in lines:
        if not removed and normalize_url_line(line) == done_url:
            removed = True
            continue
        new_lines.append(line)
    write_text_lines(PICKER_FILE, new_lines)


def archive_url(path: Path, url: str, reason: str = "") -> None:
    suffix = f"  # {reason}" if reason else ""
    append_text(path, f"{now_stamp()}\t{url}{suffix}")


def prompt_url_timeout(seconds: int = 8) -> str:
    print()
    print_step("~", f"Enter URL now (auto-skip in {seconds}s for local media): ", C.CYAN)
    q: "queue.Queue[str]" = queue.Queue()

    def reader() -> None:
        try:
            q.put(input().strip())
        except Exception:
            q.put("")

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        return q.get(timeout=seconds)
    except queue.Empty:
        print_step("~", "No URL entered. Continuing with local media.", C.DIM)
        return ""


def local_media_files() -> List[Path]:
    blocked = {
        LIB_ROOT.resolve() if LIB_ROOT.exists() else LIB_ROOT,
        COMBINED_IMAGE_DIR.resolve(),
        COMBINED_VIDEO_DIR.resolve(),
        COMBINED_AUDIO_DIR.resolve(),
        DOWNLOAD_ROOT.resolve(),
    }
    found: List[Path] = []
    for path in SCRIPT_DIR.rglob("*"):
        try:
            resolved = path.resolve()
        except Exception:
            continue
        if any(str(resolved).startswith(str(root)) for root in blocked):
            continue
        if is_media_file(path):
            found.append(path)
    return sorted(found, key=media_sort_key)


def job_folder_for_url(url: str) -> Path:
    parsed = urllib.parse.urlparse(url)
    host = safe_filename(parsed.netloc or "url", 50)
    slug_source = parsed.path.strip("/").replace("/", "_") or "media"
    slug = safe_filename(slug_source, 60)
    return ensure_dir(DOWNLOAD_ROOT / f"{file_stamp()}_{host}_{slug}")


def log_job(
    job_name: str,
    source: str,
    media_files: Sequence[Path],
    combined: Dict[str, List[Path]],
    download_log: str,
    rotator: GroqKeyRotator,
    permanent_failure: bool = False,
) -> None:
    lines = [
        "=" * 88,
        f"Time: {now_stamp()}",
        f"Job: {job_name}",
        f"Source: {source}",
        f"Permanent failure: {permanent_failure}",
        f"Downloaded/local media: {len(media_files)}",
        f"Combined images: {len(combined.get('image', []))}",
        f"Combined videos: {len(combined.get('video', []))}",
        f"Combined audio: {len(combined.get('audio', []))}",
        "",
        "Files:",
    ]
    lines.extend(f"  - {path}" for path in media_files)
    lines.extend(["", "Groq key balance:", rotator.balance_report(), "", "Download log:", download_log.strip(), ""])
    append_text(JOB_LOG_FILE, "\n".join(lines))


def run_url_job(url: str, rotator: GroqKeyRotator, models: Dict[str, str]) -> bool:
    job_folder = job_folder_for_url(url)
    print_step("~", f"URL job folder: {job_folder}", C.CYAN)
    media_files, download_log, permanent_failure = download_media_from_url(url, job_folder)
    if media_files:
        combined = scrape_and_combine(media_files, rotator, models, url)
        log_job(url, url, media_files, combined, download_log, rotator, permanent_failure=False)
        archive_url(PICKER_DONE_FILE, url)
        remove_url_from_picker(url)
        return True
    log_job(url, url, [], {"image": [], "video": [], "audio": []}, download_log, rotator, permanent_failure)
    if permanent_failure:
        archive_url(PICKER_FAILED_FILE, url, "permanent download failure")
        remove_url_from_picker(url)
    return False


def run_local_job(rotator: GroqKeyRotator, models: Dict[str, str]) -> bool:
    files = local_media_files()
    if not files:
        print_step("!", f"No local media found in {SCRIPT_DIR}", C.YELLOW)
        return False
    print_step("~", f"Found {len(files)} local media file(s)", C.CYAN)
    combined = scrape_and_combine(files, rotator, models, "local media")
    log_job("local media", str(SCRIPT_DIR), files, combined, "local media - no download", rotator)
    return True


def print_banner(models: Optional[Dict[str, str]] = None) -> None:
    print()
    print(color("=" * 72, C.CYAN))
    print(color(f"ULTIMATE MEDIA TOOL v{VERSION}", C.BOLD + C.CYAN))
    print(color("=" * 72, C.CYAN))
    print(f"Libraries/tools: {LIB_ROOT}")
    print(f"Media/script folder: {SCRIPT_DIR}")
    print(f"URL picker: {PICKER_FILE}")
    if models:
        print(f"Vision: {models['vision']}")
        print(f"Translate: {models['translate']}")
        print(f"Whisper: {models['whisper']}")
    print()


def main() -> None:
    ensure_utf8_stdio()
    try:
        bootstrap_environment()
        accounts = parse_user_config()
        rotator = GroqKeyRotator(accounts)
        models = discover_models(rotator)
        print_banner(models)
        if not rotator.has_keys():
            print_step("!", "USER_CONFIG contains only placeholder Groq keys; downloads still work, OCR/Whisper will be skipped.", C.YELLOW)

        urls = picker_urls()
        if urls:
            print_step("~", f"URL picker has {len(urls)} URL(s). Processing first unfinished URL(s).", C.CYAN)
            for url in list(urls):
                print_step("~", f"Processing URL: {url}", C.BLUE)
                run_url_job(url, rotator, models)
            return

        entered = prompt_url_timeout(8)
        if entered:
            run_url_job(entered, rotator, models)
            return

        run_local_job(rotator, models)
    except KeyboardInterrupt:
        print_step("!", "Interrupted by user.", C.YELLOW)
    except Exception as exc:
        print_step("!", f"Fatal error: {exc}", C.RED)
        append_text(JOB_LOG_FILE, f"\n{now_stamp()} FATAL ERROR\n{traceback.format_exc()}\n")
        raise


if __name__ == "__main__":
    main()
