#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FORENSIC IMAGE-TO-PROMPT ENGINE
Gemini Flash image-to-prompt workflow for local folders and URL pickup.

Pipeline:
- Download: direct image via urllib | Instagram via yt-dlp + browser cookies (Firefox→Chrome→…; MEDIA ONLY) then gallery-dl | other social via gallery-dl + yt-dlp
- Sort: EXIF capture time first, filesystem time second
- Analyze: Gemini Flash with rotating API keys and model fallback
- Archive: prompts and source images into Image to Prompt Done
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as _dt
import hashlib
import imghdr
import json
import mimetypes
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover - optional runtime dependency
    Image = None  # type: ignore
    ImageOps = None  # type: ignore

APP_TITLE = "FORENSIC IMAGE-TO-PROMPT ENGINE"
APP_VERSION = "FINAL / Gemini Flash"
KEY_SWITCH_DELAY_SECONDS = 600
RPM_SOFT_LIMIT = 9
RPM_HARD_LIMIT = 10
RPD_SOFT_LIMIT = 249
RPD_HARD_LIMIT = 250
ACTIVE_WINDOW_SECONDS = 10 * 60
PAUSE_WINDOW_SECONDS = 10 * 60
URL_INPUT_TIMEOUT_SECONDS = 8
DEFAULT_IMAGE_FOLDER_NAME = "Image to Prompt"
DONE_FOLDER_NAME = "Image to Prompt Done"
URL_PICKER_FILENAME = "Image to Prompt URL Picker.txt"
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif", ".heic", ".heif"}
DIRECT_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
SOCIAL_DOMAINS = (
    "instagram.com", "www.instagram.com", "instagr.am", "pinterest.com", "pin.it",
    "reddit.com", "www.reddit.com", "x.com", "twitter.com", "tiktok.com",
    "facebook.com", "threads.net", "tumblr.com", "flickr.com", "deviantart.com",
)
MODEL_FALLBACK_ORDER = [
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
TOOLS_DIR = Path.home() / ".forensic_image_to_prompt" / "tools"
SITE_PACKAGES = str(TOOLS_DIR / "site-packages")
YTDLP_PATH = TOOLS_DIR / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
GALLERY_DL_PATH = TOOLS_DIR / ("gallery-dl.exe" if os.name == "nt" else "gallery-dl")


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
    WHITE = "\033[37m"


USER_CONFIG = r"""
1. Enter Gemini API Key (userID: your_email_1@example.com):	AQ.YOUR_GEMINI_API_KEY_01
2. Enter Gemini API Key (userID: your_email_2@example.com):	AQ.YOUR_GEMINI_API_KEY_02
3. Enter Gemini API Key (userID: your_email_3@example.com):	AQ.YOUR_GEMINI_API_KEY_03
4. Enter Gemini API Key (userID: your_email_4@example.com):	AQ.YOUR_GEMINI_API_KEY_04
5. Enter Gemini API Key (userID: your_email_5@example.com):	AQ.YOUR_GEMINI_API_KEY_05
6. Enter Gemini API Key (userID: your_email_6@example.com):	AQ.YOUR_GEMINI_API_KEY_06
7. Enter Gemini API Key (userID: your_email_7@example.com):	AQ.YOUR_GEMINI_API_KEY_07
8. Enter Gemini API Key (userID: your_email_8@example.com):	AQ.YOUR_GEMINI_API_KEY_08
9. Enter Gemini API Key (userID: your_email_9@example.com):	AQ.YOUR_GEMINI_API_KEY_09
10. Enter Gemini API Key (userID: your_email_10@example.com):	AQ.YOUR_GEMINI_API_KEY_10
11. Enter Gemini API Key (userID: your_email_11@example.com):	AQ.YOUR_GEMINI_API_KEY_11
12. Enter Gemini API Key (userID: your_email_12@example.com):	AQ.YOUR_GEMINI_API_KEY_12
"""
FORENSIC_SYSTEM_PROMPT = """
FORENSIC IMAGE-TO-PROMPT ENGINE SYSTEM PROMPT
You are a forensic image-to-prompt analyst. Convert visible image evidence into a precise prompt for faithful regeneration.
Preserve factual observations, lighting, lens behavior, materials, composition, and negative constraints without inventing hidden context.

- Forensic directive 0001: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0002: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0003: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0004: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0005: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0006: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0007: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0008: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0009: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0010: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0011: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0012: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0013: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0014: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0015: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0016: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0017: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0018: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0019: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0020: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0021: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0022: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0023: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0024: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0025: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0026: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0027: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0028: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0029: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0030: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0031: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0032: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0033: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0034: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0035: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0036: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0037: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0038: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0039: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0040: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0041: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0042: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0043: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0044: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0045: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0046: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0047: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0048: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0049: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0050: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0051: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0052: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0053: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0054: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0055: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0056: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0057: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0058: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0059: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0060: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0061: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0062: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0063: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0064: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0065: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0066: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0067: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0068: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0069: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0070: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0071: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0072: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0073: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0074: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0075: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0076: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0077: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0078: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0079: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0080: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0081: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0082: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0083: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0084: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0085: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0086: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0087: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0088: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0089: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0090: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0091: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0092: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0093: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0094: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0095: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0096: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0097: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0098: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0099: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0100: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0101: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0102: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0103: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0104: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0105: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0106: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0107: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0108: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0109: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0110: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0111: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0112: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0113: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0114: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0115: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0116: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0117: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0118: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0119: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0120: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0121: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0122: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0123: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0124: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0125: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0126: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0127: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0128: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0129: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0130: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0131: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0132: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0133: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0134: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0135: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0136: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0137: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0138: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0139: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0140: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0141: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0142: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0143: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0144: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0145: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0146: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0147: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0148: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0149: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0150: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0151: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0152: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0153: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0154: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0155: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0156: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0157: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0158: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0159: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0160: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0161: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0162: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0163: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0164: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0165: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0166: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0167: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0168: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0169: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0170: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0171: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0172: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0173: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0174: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0175: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0176: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0177: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0178: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0179: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0180: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0181: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0182: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0183: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0184: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0185: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0186: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0187: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0188: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0189: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0190: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0191: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0192: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0193: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0194: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0195: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0196: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0197: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0198: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0199: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0200: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0201: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0202: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0203: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0204: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0205: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0206: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0207: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0208: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0209: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0210: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0211: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0212: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0213: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0214: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0215: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0216: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0217: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0218: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0219: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0220: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0221: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0222: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0223: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0224: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0225: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0226: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0227: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0228: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0229: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0230: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0231: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0232: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0233: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0234: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0235: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0236: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0237: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0238: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0239: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0240: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0241: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0242: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0243: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0244: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0245: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0246: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0247: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0248: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0249: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0250: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0251: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0252: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0253: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0254: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0255: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0256: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0257: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0258: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0259: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0260: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0261: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0262: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0263: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0264: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0265: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0266: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0267: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0268: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0269: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0270: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0271: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0272: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0273: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0274: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0275: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0276: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0277: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0278: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0279: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0280: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0281: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0282: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0283: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0284: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0285: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0286: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0287: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0288: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0289: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0290: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0291: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0292: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0293: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0294: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0295: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0296: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0297: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0298: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0299: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0300: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0301: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0302: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0303: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0304: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0305: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0306: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0307: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0308: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0309: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0310: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0311: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0312: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0313: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0314: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0315: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0316: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0317: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0318: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0319: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0320: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0321: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0322: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0323: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0324: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0325: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0326: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0327: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0328: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0329: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0330: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0331: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0332: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0333: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0334: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0335: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0336: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0337: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0338: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0339: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0340: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0341: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0342: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0343: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0344: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0345: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0346: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0347: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0348: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0349: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0350: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0351: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0352: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0353: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0354: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0355: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0356: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0357: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0358: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0359: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0360: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0361: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0362: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0363: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0364: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0365: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0366: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0367: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0368: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0369: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0370: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0371: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0372: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0373: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0374: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0375: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0376: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0377: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0378: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0379: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0380: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0381: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0382: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0383: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0384: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0385: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0386: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0387: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0388: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0389: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0390: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0391: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0392: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0393: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0394: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0395: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0396: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0397: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0398: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0399: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0400: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0401: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0402: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0403: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0404: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0405: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0406: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0407: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0408: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0409: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0410: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0411: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0412: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0413: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0414: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0415: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0416: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0417: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0418: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0419: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0420: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0421: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0422: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0423: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0424: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0425: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0426: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0427: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0428: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0429: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0430: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0431: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0432: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0433: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0434: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0435: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0436: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0437: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0438: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0439: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0440: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0441: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0442: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0443: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0444: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0445: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0446: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0447: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0448: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0449: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0450: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0451: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0452: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0453: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0454: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0455: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0456: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0457: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0458: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0459: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0460: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0461: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0462: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0463: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0464: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0465: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0466: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0467: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0468: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0469: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0470: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0471: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0472: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0473: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0474: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0475: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0476: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0477: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0478: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0479: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0480: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0481: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0482: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0483: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0484: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0485: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0486: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0487: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0488: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0489: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0490: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0491: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0492: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0493: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0494: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0495: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0496: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0497: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0498: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0499: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0500: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0501: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0502: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0503: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0504: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0505: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0506: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0507: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0508: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0509: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0510: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0511: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0512: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0513: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0514: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0515: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0516: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0517: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0518: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0519: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0520: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0521: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0522: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0523: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0524: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0525: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0526: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0527: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0528: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0529: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0530: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0531: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0532: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0533: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0534: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0535: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0536: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0537: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0538: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0539: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0540: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0541: inspect subject identity and count; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0542: inspect pose and gesture; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0543: inspect facial expression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0544: inspect wardrobe material; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0545: inspect object placement; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0546: inspect background geometry; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0547: inspect foreground occlusion; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0548: inspect lighting direction; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0549: inspect shadow hardness; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0550: inspect color temperature; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0551: inspect camera height; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0552: inspect lens compression; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0553: inspect depth of field; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0554: inspect texture evidence; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0555: inspect surface reflectivity; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0556: inspect weather and atmosphere; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0557: inspect time-of-day clues; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0558: inspect social-media crop behavior; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0559: inspect image artifact inspection; describe only visible evidence, rank confidence, and avoid unstated identity claims.
- Forensic directive 0560: inspect prompt safety boundary; describe only visible evidence, rank confidence, and avoid unstated identity claims.

Output format:
1. FORENSIC CAPTION: concise literal description of the scene.
2. GENERATION PROMPT: a complete image prompt preserving subject, composition, lens, light, palette, and atmosphere.
3. NEGATIVE PROMPT: visible exclusions, artifacts to avoid, and style drift to suppress.
4. TECHNICAL NOTES: EXIF/crop/quality observations when inferable from the pixels.
"""

USER_THEMATIC_OVERRIDES: Dict[str, str] = {
    "theme_001": (
        "Thematic override 001: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_002": (
        "Thematic override 002: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_003": (
        "Thematic override 003: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_004": (
        "Thematic override 004: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_005": (
        "Thematic override 005: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_006": (
        "Thematic override 006: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_007": (
        "Thematic override 007: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_008": (
        "Thematic override 008: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_009": (
        "Thematic override 009: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_010": (
        "Thematic override 010: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_011": (
        "Thematic override 011: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_012": (
        "Thematic override 012: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_013": (
        "Thematic override 013: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_014": (
        "Thematic override 014: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_015": (
        "Thematic override 015: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_016": (
        "Thematic override 016: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_017": (
        "Thematic override 017: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_018": (
        "Thematic override 018: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_019": (
        "Thematic override 019: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_020": (
        "Thematic override 020: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_021": (
        "Thematic override 021: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_022": (
        "Thematic override 022: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_023": (
        "Thematic override 023: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_024": (
        "Thematic override 024: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_025": (
        "Thematic override 025: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_026": (
        "Thematic override 026: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_027": (
        "Thematic override 027: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_028": (
        "Thematic override 028: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_029": (
        "Thematic override 029: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_030": (
        "Thematic override 030: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_031": (
        "Thematic override 031: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_032": (
        "Thematic override 032: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_033": (
        "Thematic override 033: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_034": (
        "Thematic override 034: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_035": (
        "Thematic override 035: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_036": (
        "Thematic override 036: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_037": (
        "Thematic override 037: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_038": (
        "Thematic override 038: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_039": (
        "Thematic override 039: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_040": (
        "Thematic override 040: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_041": (
        "Thematic override 041: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_042": (
        "Thematic override 042: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_043": (
        "Thematic override 043: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_044": (
        "Thematic override 044: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_045": (
        "Thematic override 045: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_046": (
        "Thematic override 046: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_047": (
        "Thematic override 047: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_048": (
        "Thematic override 048: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_049": (
        "Thematic override 049: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_050": (
        "Thematic override 050: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_051": (
        "Thematic override 051: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_052": (
        "Thematic override 052: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_053": (
        "Thematic override 053: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_054": (
        "Thematic override 054: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_055": (
        "Thematic override 055: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_056": (
        "Thematic override 056: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_057": (
        "Thematic override 057: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_058": (
        "Thematic override 058: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_059": (
        "Thematic override 059: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_060": (
        "Thematic override 060: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_061": (
        "Thematic override 061: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_062": (
        "Thematic override 062: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_063": (
        "Thematic override 063: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_064": (
        "Thematic override 064: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_065": (
        "Thematic override 065: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_066": (
        "Thematic override 066: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_067": (
        "Thematic override 067: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_068": (
        "Thematic override 068: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_069": (
        "Thematic override 069: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_070": (
        "Thematic override 070: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_071": (
        "Thematic override 071: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_072": (
        "Thematic override 072: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_073": (
        "Thematic override 073: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_074": (
        "Thematic override 074: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_075": (
        "Thematic override 075: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_076": (
        "Thematic override 076: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_077": (
        "Thematic override 077: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_078": (
        "Thematic override 078: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_079": (
        "Thematic override 079: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_080": (
        "Thematic override 080: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_081": (
        "Thematic override 081: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_082": (
        "Thematic override 082: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_083": (
        "Thematic override 083: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_084": (
        "Thematic override 084: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_085": (
        "Thematic override 085: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_086": (
        "Thematic override 086: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_087": (
        "Thematic override 087: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_088": (
        "Thematic override 088: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_089": (
        "Thematic override 089: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_090": (
        "Thematic override 090: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_091": (
        "Thematic override 091: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_092": (
        "Thematic override 092: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_093": (
        "Thematic override 093: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_094": (
        "Thematic override 094: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_095": (
        "Thematic override 095: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_096": (
        "Thematic override 096: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_097": (
        "Thematic override 097: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_098": (
        "Thematic override 098: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_099": (
        "Thematic override 099: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "theme_100": (
        "Thematic override 100: preserve the original forensic observation order; "
        "emphasize concrete visible details, camera perspective, and environmental cues; "
        "do not add brands, names, locations, or story events unless they are visible in the image."
    ),
    "instagram_still_image": (
        "When the source came from Instagram, treat the downloaded media as still-image evidence only. "
        "Do not describe reels, captions, likes, comments, account metadata, or surrounding page chrome."
    ),
    "direct_url_image": (
        "When the source was a direct image URL, prioritize the pixels and file characteristics over page context."
    ),
}

FORENSIC_DETAIL_CANON: Tuple[str, ...] = (
    "Canon note 0001: verify silhouette separation before composing the final prompt.",
    "Canon note 0002: verify specular highlight map before composing the final prompt.",
    "Canon note 0003: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0004: verify fabric weave before composing the final prompt.",
    "Canon note 0005: verify edge acuity before composing the final prompt.",
    "Canon note 0006: verify motion blur vector before composing the final prompt.",
    "Canon note 0007: verify background vanishing point before composing the final prompt.",
    "Canon note 0008: verify reflected color cast before composing the final prompt.",
    "Canon note 0009: verify ambient occlusion before composing the final prompt.",
    "Canon note 0010: verify compression block pattern before composing the final prompt.",
    "Canon note 0011: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0012: verify scene scale cue before composing the final prompt.",
    "Canon note 0013: verify crop boundary intent before composing the final prompt.",
    "Canon note 0014: verify visible text handling before composing the final prompt.",
    "Canon note 0015: verify transparent object behavior before composing the final prompt.",
    "Canon note 0016: verify fine hair detail before composing the final prompt.",
    "Canon note 0017: verify silhouette separation before composing the final prompt.",
    "Canon note 0018: verify specular highlight map before composing the final prompt.",
    "Canon note 0019: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0020: verify fabric weave before composing the final prompt.",
    "Canon note 0021: verify edge acuity before composing the final prompt.",
    "Canon note 0022: verify motion blur vector before composing the final prompt.",
    "Canon note 0023: verify background vanishing point before composing the final prompt.",
    "Canon note 0024: verify reflected color cast before composing the final prompt.",
    "Canon note 0025: verify ambient occlusion before composing the final prompt.",
    "Canon note 0026: verify compression block pattern before composing the final prompt.",
    "Canon note 0027: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0028: verify scene scale cue before composing the final prompt.",
    "Canon note 0029: verify crop boundary intent before composing the final prompt.",
    "Canon note 0030: verify visible text handling before composing the final prompt.",
    "Canon note 0031: verify transparent object behavior before composing the final prompt.",
    "Canon note 0032: verify fine hair detail before composing the final prompt.",
    "Canon note 0033: verify silhouette separation before composing the final prompt.",
    "Canon note 0034: verify specular highlight map before composing the final prompt.",
    "Canon note 0035: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0036: verify fabric weave before composing the final prompt.",
    "Canon note 0037: verify edge acuity before composing the final prompt.",
    "Canon note 0038: verify motion blur vector before composing the final prompt.",
    "Canon note 0039: verify background vanishing point before composing the final prompt.",
    "Canon note 0040: verify reflected color cast before composing the final prompt.",
    "Canon note 0041: verify ambient occlusion before composing the final prompt.",
    "Canon note 0042: verify compression block pattern before composing the final prompt.",
    "Canon note 0043: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0044: verify scene scale cue before composing the final prompt.",
    "Canon note 0045: verify crop boundary intent before composing the final prompt.",
    "Canon note 0046: verify visible text handling before composing the final prompt.",
    "Canon note 0047: verify transparent object behavior before composing the final prompt.",
    "Canon note 0048: verify fine hair detail before composing the final prompt.",
    "Canon note 0049: verify silhouette separation before composing the final prompt.",
    "Canon note 0050: verify specular highlight map before composing the final prompt.",
    "Canon note 0051: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0052: verify fabric weave before composing the final prompt.",
    "Canon note 0053: verify edge acuity before composing the final prompt.",
    "Canon note 0054: verify motion blur vector before composing the final prompt.",
    "Canon note 0055: verify background vanishing point before composing the final prompt.",
    "Canon note 0056: verify reflected color cast before composing the final prompt.",
    "Canon note 0057: verify ambient occlusion before composing the final prompt.",
    "Canon note 0058: verify compression block pattern before composing the final prompt.",
    "Canon note 0059: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0060: verify scene scale cue before composing the final prompt.",
    "Canon note 0061: verify crop boundary intent before composing the final prompt.",
    "Canon note 0062: verify visible text handling before composing the final prompt.",
    "Canon note 0063: verify transparent object behavior before composing the final prompt.",
    "Canon note 0064: verify fine hair detail before composing the final prompt.",
    "Canon note 0065: verify silhouette separation before composing the final prompt.",
    "Canon note 0066: verify specular highlight map before composing the final prompt.",
    "Canon note 0067: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0068: verify fabric weave before composing the final prompt.",
    "Canon note 0069: verify edge acuity before composing the final prompt.",
    "Canon note 0070: verify motion blur vector before composing the final prompt.",
    "Canon note 0071: verify background vanishing point before composing the final prompt.",
    "Canon note 0072: verify reflected color cast before composing the final prompt.",
    "Canon note 0073: verify ambient occlusion before composing the final prompt.",
    "Canon note 0074: verify compression block pattern before composing the final prompt.",
    "Canon note 0075: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0076: verify scene scale cue before composing the final prompt.",
    "Canon note 0077: verify crop boundary intent before composing the final prompt.",
    "Canon note 0078: verify visible text handling before composing the final prompt.",
    "Canon note 0079: verify transparent object behavior before composing the final prompt.",
    "Canon note 0080: verify fine hair detail before composing the final prompt.",
    "Canon note 0081: verify silhouette separation before composing the final prompt.",
    "Canon note 0082: verify specular highlight map before composing the final prompt.",
    "Canon note 0083: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0084: verify fabric weave before composing the final prompt.",
    "Canon note 0085: verify edge acuity before composing the final prompt.",
    "Canon note 0086: verify motion blur vector before composing the final prompt.",
    "Canon note 0087: verify background vanishing point before composing the final prompt.",
    "Canon note 0088: verify reflected color cast before composing the final prompt.",
    "Canon note 0089: verify ambient occlusion before composing the final prompt.",
    "Canon note 0090: verify compression block pattern before composing the final prompt.",
    "Canon note 0091: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0092: verify scene scale cue before composing the final prompt.",
    "Canon note 0093: verify crop boundary intent before composing the final prompt.",
    "Canon note 0094: verify visible text handling before composing the final prompt.",
    "Canon note 0095: verify transparent object behavior before composing the final prompt.",
    "Canon note 0096: verify fine hair detail before composing the final prompt.",
    "Canon note 0097: verify silhouette separation before composing the final prompt.",
    "Canon note 0098: verify specular highlight map before composing the final prompt.",
    "Canon note 0099: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0100: verify fabric weave before composing the final prompt.",
    "Canon note 0101: verify edge acuity before composing the final prompt.",
    "Canon note 0102: verify motion blur vector before composing the final prompt.",
    "Canon note 0103: verify background vanishing point before composing the final prompt.",
    "Canon note 0104: verify reflected color cast before composing the final prompt.",
    "Canon note 0105: verify ambient occlusion before composing the final prompt.",
    "Canon note 0106: verify compression block pattern before composing the final prompt.",
    "Canon note 0107: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0108: verify scene scale cue before composing the final prompt.",
    "Canon note 0109: verify crop boundary intent before composing the final prompt.",
    "Canon note 0110: verify visible text handling before composing the final prompt.",
    "Canon note 0111: verify transparent object behavior before composing the final prompt.",
    "Canon note 0112: verify fine hair detail before composing the final prompt.",
    "Canon note 0113: verify silhouette separation before composing the final prompt.",
    "Canon note 0114: verify specular highlight map before composing the final prompt.",
    "Canon note 0115: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0116: verify fabric weave before composing the final prompt.",
    "Canon note 0117: verify edge acuity before composing the final prompt.",
    "Canon note 0118: verify motion blur vector before composing the final prompt.",
    "Canon note 0119: verify background vanishing point before composing the final prompt.",
    "Canon note 0120: verify reflected color cast before composing the final prompt.",
    "Canon note 0121: verify ambient occlusion before composing the final prompt.",
    "Canon note 0122: verify compression block pattern before composing the final prompt.",
    "Canon note 0123: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0124: verify scene scale cue before composing the final prompt.",
    "Canon note 0125: verify crop boundary intent before composing the final prompt.",
    "Canon note 0126: verify visible text handling before composing the final prompt.",
    "Canon note 0127: verify transparent object behavior before composing the final prompt.",
    "Canon note 0128: verify fine hair detail before composing the final prompt.",
    "Canon note 0129: verify silhouette separation before composing the final prompt.",
    "Canon note 0130: verify specular highlight map before composing the final prompt.",
    "Canon note 0131: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0132: verify fabric weave before composing the final prompt.",
    "Canon note 0133: verify edge acuity before composing the final prompt.",
    "Canon note 0134: verify motion blur vector before composing the final prompt.",
    "Canon note 0135: verify background vanishing point before composing the final prompt.",
    "Canon note 0136: verify reflected color cast before composing the final prompt.",
    "Canon note 0137: verify ambient occlusion before composing the final prompt.",
    "Canon note 0138: verify compression block pattern before composing the final prompt.",
    "Canon note 0139: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0140: verify scene scale cue before composing the final prompt.",
    "Canon note 0141: verify crop boundary intent before composing the final prompt.",
    "Canon note 0142: verify visible text handling before composing the final prompt.",
    "Canon note 0143: verify transparent object behavior before composing the final prompt.",
    "Canon note 0144: verify fine hair detail before composing the final prompt.",
    "Canon note 0145: verify silhouette separation before composing the final prompt.",
    "Canon note 0146: verify specular highlight map before composing the final prompt.",
    "Canon note 0147: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0148: verify fabric weave before composing the final prompt.",
    "Canon note 0149: verify edge acuity before composing the final prompt.",
    "Canon note 0150: verify motion blur vector before composing the final prompt.",
    "Canon note 0151: verify background vanishing point before composing the final prompt.",
    "Canon note 0152: verify reflected color cast before composing the final prompt.",
    "Canon note 0153: verify ambient occlusion before composing the final prompt.",
    "Canon note 0154: verify compression block pattern before composing the final prompt.",
    "Canon note 0155: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0156: verify scene scale cue before composing the final prompt.",
    "Canon note 0157: verify crop boundary intent before composing the final prompt.",
    "Canon note 0158: verify visible text handling before composing the final prompt.",
    "Canon note 0159: verify transparent object behavior before composing the final prompt.",
    "Canon note 0160: verify fine hair detail before composing the final prompt.",
    "Canon note 0161: verify silhouette separation before composing the final prompt.",
    "Canon note 0162: verify specular highlight map before composing the final prompt.",
    "Canon note 0163: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0164: verify fabric weave before composing the final prompt.",
    "Canon note 0165: verify edge acuity before composing the final prompt.",
    "Canon note 0166: verify motion blur vector before composing the final prompt.",
    "Canon note 0167: verify background vanishing point before composing the final prompt.",
    "Canon note 0168: verify reflected color cast before composing the final prompt.",
    "Canon note 0169: verify ambient occlusion before composing the final prompt.",
    "Canon note 0170: verify compression block pattern before composing the final prompt.",
    "Canon note 0171: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0172: verify scene scale cue before composing the final prompt.",
    "Canon note 0173: verify crop boundary intent before composing the final prompt.",
    "Canon note 0174: verify visible text handling before composing the final prompt.",
    "Canon note 0175: verify transparent object behavior before composing the final prompt.",
    "Canon note 0176: verify fine hair detail before composing the final prompt.",
    "Canon note 0177: verify silhouette separation before composing the final prompt.",
    "Canon note 0178: verify specular highlight map before composing the final prompt.",
    "Canon note 0179: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0180: verify fabric weave before composing the final prompt.",
    "Canon note 0181: verify edge acuity before composing the final prompt.",
    "Canon note 0182: verify motion blur vector before composing the final prompt.",
    "Canon note 0183: verify background vanishing point before composing the final prompt.",
    "Canon note 0184: verify reflected color cast before composing the final prompt.",
    "Canon note 0185: verify ambient occlusion before composing the final prompt.",
    "Canon note 0186: verify compression block pattern before composing the final prompt.",
    "Canon note 0187: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0188: verify scene scale cue before composing the final prompt.",
    "Canon note 0189: verify crop boundary intent before composing the final prompt.",
    "Canon note 0190: verify visible text handling before composing the final prompt.",
    "Canon note 0191: verify transparent object behavior before composing the final prompt.",
    "Canon note 0192: verify fine hair detail before composing the final prompt.",
    "Canon note 0193: verify silhouette separation before composing the final prompt.",
    "Canon note 0194: verify specular highlight map before composing the final prompt.",
    "Canon note 0195: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0196: verify fabric weave before composing the final prompt.",
    "Canon note 0197: verify edge acuity before composing the final prompt.",
    "Canon note 0198: verify motion blur vector before composing the final prompt.",
    "Canon note 0199: verify background vanishing point before composing the final prompt.",
    "Canon note 0200: verify reflected color cast before composing the final prompt.",
    "Canon note 0201: verify ambient occlusion before composing the final prompt.",
    "Canon note 0202: verify compression block pattern before composing the final prompt.",
    "Canon note 0203: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0204: verify scene scale cue before composing the final prompt.",
    "Canon note 0205: verify crop boundary intent before composing the final prompt.",
    "Canon note 0206: verify visible text handling before composing the final prompt.",
    "Canon note 0207: verify transparent object behavior before composing the final prompt.",
    "Canon note 0208: verify fine hair detail before composing the final prompt.",
    "Canon note 0209: verify silhouette separation before composing the final prompt.",
    "Canon note 0210: verify specular highlight map before composing the final prompt.",
    "Canon note 0211: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0212: verify fabric weave before composing the final prompt.",
    "Canon note 0213: verify edge acuity before composing the final prompt.",
    "Canon note 0214: verify motion blur vector before composing the final prompt.",
    "Canon note 0215: verify background vanishing point before composing the final prompt.",
    "Canon note 0216: verify reflected color cast before composing the final prompt.",
    "Canon note 0217: verify ambient occlusion before composing the final prompt.",
    "Canon note 0218: verify compression block pattern before composing the final prompt.",
    "Canon note 0219: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0220: verify scene scale cue before composing the final prompt.",
    "Canon note 0221: verify crop boundary intent before composing the final prompt.",
    "Canon note 0222: verify visible text handling before composing the final prompt.",
    "Canon note 0223: verify transparent object behavior before composing the final prompt.",
    "Canon note 0224: verify fine hair detail before composing the final prompt.",
    "Canon note 0225: verify silhouette separation before composing the final prompt.",
    "Canon note 0226: verify specular highlight map before composing the final prompt.",
    "Canon note 0227: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0228: verify fabric weave before composing the final prompt.",
    "Canon note 0229: verify edge acuity before composing the final prompt.",
    "Canon note 0230: verify motion blur vector before composing the final prompt.",
    "Canon note 0231: verify background vanishing point before composing the final prompt.",
    "Canon note 0232: verify reflected color cast before composing the final prompt.",
    "Canon note 0233: verify ambient occlusion before composing the final prompt.",
    "Canon note 0234: verify compression block pattern before composing the final prompt.",
    "Canon note 0235: verify natural vs artificial light before composing the final prompt.",
    "Canon note 0236: verify scene scale cue before composing the final prompt.",
    "Canon note 0237: verify crop boundary intent before composing the final prompt.",
    "Canon note 0238: verify visible text handling before composing the final prompt.",
    "Canon note 0239: verify transparent object behavior before composing the final prompt.",
    "Canon note 0240: verify fine hair detail before composing the final prompt.",
    "Canon note 0241: verify silhouette separation before composing the final prompt.",
    "Canon note 0242: verify specular highlight map before composing the final prompt.",
    "Canon note 0243: verify skin-tone lighting bias before composing the final prompt.",
    "Canon note 0244: verify fabric weave before composing the final prompt.",
    "Canon note 0245: verify edge acuity before composing the final prompt.",
    "Canon note 0246: verify motion blur vector before composing the final prompt.",
    "Canon note 0247: verify background vanishing point before composing the final prompt.",
    "Canon note 0248: verify reflected color cast before composing the final prompt.",
    "Canon note 0249: verify ambient occlusion before composing the final prompt.",
    "Canon note 0250: verify compression block pattern before composing the final prompt.",
)
@dataclasses.dataclass
class GeminiApiKey:
    index: int
    user_id: str
    api_key: str
    requests_today: int = 0
    request_timestamps: List[float] = dataclasses.field(default_factory=list)
    last_used_at: float = 0.0
    disabled_until: float = 0.0
    consecutive_errors: int = 0

    @property
    def label(self) -> str:
        return f"#{self.index} {self.user_id}"


class GeminiApiKeyRotator:
    """Rotate Gemini keys with 600s key switch delay, RPM 9/10, and RPD 249/250 limits."""

    def __init__(
        self,
        keys: Sequence[GeminiApiKey],
        key_switch_delay_seconds: int = KEY_SWITCH_DELAY_SECONDS,
        rpm_soft_limit: int = RPM_SOFT_LIMIT,
        rpm_hard_limit: int = RPM_HARD_LIMIT,
        rpd_soft_limit: int = RPD_SOFT_LIMIT,
        rpd_hard_limit: int = RPD_HARD_LIMIT,
    ) -> None:
        self.keys = list(keys)
        self.key_switch_delay_seconds = key_switch_delay_seconds
        self.rpm_soft_limit = rpm_soft_limit
        self.rpm_hard_limit = rpm_hard_limit
        self.rpd_soft_limit = rpd_soft_limit
        self.rpd_hard_limit = rpd_hard_limit
        self._lock = threading.RLock()
        self._cursor = 0
        self._day = _dt.date.today()

    def _roll_day_if_needed(self) -> None:
        today = _dt.date.today()
        if today == self._day:
            return
        self._day = today
        for key in self.keys:
            key.requests_today = 0
            key.request_timestamps.clear()
            key.consecutive_errors = 0
            key.disabled_until = 0.0

    def _clean_recent(self, key: GeminiApiKey, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        key.request_timestamps[:] = [t for t in key.request_timestamps if now - t < 60.0]

    def _key_usable(self, key: GeminiApiKey, now: Optional[float] = None) -> Tuple[bool, str]:
        if now is None:
            now = time.time()
        self._clean_recent(key, now)
        if key.disabled_until > now:
            return False, f"disabled for {int(key.disabled_until - now)}s"
        if key.requests_today >= self.rpd_soft_limit:
            return False, "daily soft quota reached"
        if len(key.request_timestamps) >= self.rpm_soft_limit:
            return False, "minute soft quota reached"
        if key.last_used_at and now - key.last_used_at < self.key_switch_delay_seconds:
            return False, f"switch delay {int(self.key_switch_delay_seconds - (now - key.last_used_at))}s"
        return True, "ready"

    def _least_wait_seconds(self, now: Optional[float] = None) -> float:
        if now is None:
            now = time.time()
        waits: List[float] = []
        for key in self.keys:
            self._clean_recent(key, now)
            if key.requests_today >= self.rpd_soft_limit:
                continue
            if key.disabled_until > now:
                waits.append(key.disabled_until - now)
            if key.request_timestamps:
                waits.append(max(0.0, 60.0 - (now - min(key.request_timestamps))))
            if key.last_used_at:
                waits.append(max(0.0, self.key_switch_delay_seconds - (now - key.last_used_at)))
        return min([w for w in waits if w > 0.0], default=30.0)

    def wait_for_available_key(self) -> GeminiApiKey:
        if not self.keys:
            raise RuntimeError("No Gemini API keys configured. Fill USER_CONFIG with real keys before running.")
        while True:
            with self._lock:
                self._roll_day_if_needed()
                now = time.time()
                for offset in range(len(self.keys)):
                    pos = (self._cursor + offset) % len(self.keys)
                    key = self.keys[pos]
                    usable, _reason = self._key_usable(key, now)
                    if usable:
                        self._cursor = (pos + 1) % len(self.keys)
                        return key
                wait_s = min(max(self._least_wait_seconds(now), 1.0), 60.0)
            print_step("~", f"All Gemini keys cooling down; waiting {int(wait_s)}s", C.YELLOW)
            time.sleep(wait_s)

    def record_success(self, key: GeminiApiKey) -> None:
        now = time.time()
        with self._lock:
            self._roll_day_if_needed()
            self._clean_recent(key, now)
            key.request_timestamps.append(now)
            key.requests_today += 1
            key.last_used_at = now
            key.consecutive_errors = 0

    def mark_error(self, key: GeminiApiKey, error_text: str) -> None:
        low = error_text.lower()
        with self._lock:
            key.consecutive_errors += 1
            if any(token in low for token in ("quota", "resource_exhausted", "429", "rate limit")):
                key.disabled_until = time.time() + 10 * 60
            elif key.consecutive_errors >= 3:
                key.disabled_until = time.time() + 3 * 60

    def status_lines(self) -> List[str]:
        now = time.time()
        rows = []
        with self._lock:
            self._roll_day_if_needed()
            for key in self.keys:
                self._clean_recent(key, now)
                usable, reason = self._key_usable(key, now)
                rows.append(
                    f"{key.label}: rpm={len(key.request_timestamps)}/{self.rpm_hard_limit} "
                    f"rpd={key.requests_today}/{self.rpd_hard_limit} usable={usable} {reason}"
                )
        return rows


def print_step(prefix: str, message: str, color: str = C.WHITE) -> None:
    print(f"{color}[{prefix}] {message}{C.RESET}", flush=True)


def parse_user_config(config_text: str = USER_CONFIG) -> List[GeminiApiKey]:
    keys: List[GeminiApiKey] = []
    pattern = re.compile(r"^\s*(\d+)\.\s*Enter Gemini API Key \(userID:\s*([^)]*?)\):\s*(\S+)\s*$")
    placeholder_markers = (
        "YOUR_GEMINI_API_KEY",
        "YOUR_API_KEY",
        "PASTE_GEMINI",
        "PASTE_API_KEY",
        "REPLACE_ME",
        "EXAMPLE",
        "<",
        ">",
    )
    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            continue
        index = int(match.group(1))
        user_id = match.group(2).strip() or f"user_{index}"
        api_key = match.group(3).strip()
        if any(marker in api_key for marker in placeholder_markers):
            continue
        if api_key.upper().startswith("AQ.YOUR_"):
            continue
        keys.append(GeminiApiKey(index=index, user_id=user_id, api_key=api_key))
    return keys


def banner() -> None:
    print(f"{C.BOLD}{C.CYAN}{APP_TITLE}{C.RESET}")
    print(f"{C.DIM}{APP_VERSION}{C.RESET}")
    print("Download: direct image via urllib | Instagram via yt-dlp + browser cookies (Firefox→Chrome→…; MEDIA ONLY) then gallery-dl | other social via gallery-dl + yt-dlp")
    print(f"Gemini keys: switch delay {KEY_SWITCH_DELAY_SECONDS}s, RPM {RPM_SOFT_LIMIT}/{RPM_HARD_LIMIT}, RPD {RPD_SOFT_LIMIT}/{RPD_HARD_LIMIT}")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_slug(value: str, max_len: int = 96) -> str:
    value = urllib.parse.unquote(value)
    value = re.sub(r"https?://", "", value, flags=re.I)
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return (value[:max_len] or "image")


def _hash_file(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _snapshot_files(folder: Path) -> Set[Path]:
    if not folder.exists():
        return set()
    return {p.resolve() for p in folder.rglob("*") if p.is_file()}


def _is_valid_image(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_EXTS:
        return False
    if Image is not None:
        try:
            with Image.open(path) as img:  # type: ignore[union-attr]
                img.verify()
            return True
        except Exception:
            return False
    try:
        return imghdr.what(path) is not None
    except Exception:
        return suffix in DIRECT_IMAGE_EXTS


def _collect_new_valid_images(dest_folder: Path, before: Set[Path]) -> List[Path]:
    found: List[Path] = []
    if not dest_folder.exists():
        return found
    for path in sorted(dest_folder.rglob("*"), key=lambda p: (p.stat().st_mtime if p.exists() else 0, str(p))):
        if not path.is_file():
            continue
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved in before:
            continue
        if _is_valid_image(path):
            found.append(path)
    return found


def _module_available(module_name: str) -> bool:
    if SITE_PACKAGES not in sys.path:
        sys.path.insert(0, SITE_PACKAGES)
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _pip_install(package_name: str) -> bool:
    _ensure_dir(Path(SITE_PACKAGES))
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", "--target", SITE_PACKAGES, package_name]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            print_step("!", f"pip install {package_name} failed: {(proc.stderr or proc.stdout).strip()[:400]}", C.YELLOW)
            return False
        return True
    except Exception as exc:
        print_step("!", f"pip install {package_name} failed: {exc}", C.YELLOW)
        return False


def _write_python_module_wrapper(path: Path, module_name: str) -> bool:
    try:
        _ensure_dir(path.parent)
        body = (
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            f"site = {SITE_PACKAGES!r}\n"
            "if site and site not in sys.path:\n"
            "    sys.path.insert(0, site)\n"
            f"from {module_name}.__main__ import main\n"
            "raise SystemExit(main())\n"
        )
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return True
    except Exception as exc:
        print_step("!", f"Could not write tool wrapper {path}: {exc}", C.YELLOW)
        return False


def _ensure_ytdlp() -> bool:
    if YTDLP_PATH.exists():
        return True
    if _module_available("yt_dlp") or _pip_install("yt-dlp"):
        return _write_python_module_wrapper(YTDLP_PATH, "yt_dlp")
    return shutil.which("yt-dlp") is not None


def _ensure_gallery_dl() -> bool:
    if GALLERY_DL_PATH.exists():
        return True
    if _module_available("gallery_dl") or _pip_install("gallery-dl"):
        return _write_python_module_wrapper(GALLERY_DL_PATH, "gallery_dl")
    return shutil.which("gallery-dl") is not None


def _gallery_dl_cmd(url: str, dest_folder: Path) -> List[str]:
    if _ensure_gallery_dl() and GALLERY_DL_PATH.exists():
        return [str(GALLERY_DL_PATH), "-D", str(dest_folder), url]
    exe = shutil.which("gallery-dl")
    if exe:
        return [exe, "-D", str(dest_folder), url]
    return [sys.executable, "-m", "gallery_dl", "-D", str(dest_folder), url]


def _looks_permanent_download_error(log_text: str) -> bool:
    low = log_text.lower()
    permanent_markers = (
        "404 not found",
        "not found",
        "does not exist",
        "private",
        "login required",
        "permission denied",
        "forbidden",
        "unavailable",
        "no longer available",
        "unsupported url",
        "unsupported site",
        "age-restricted",
    )
    transient_markers = (
        "timed out",
        "timeout",
        "temporary failure",
        "connection reset",
        "connection aborted",
        "429",
        "too many requests",
        "rate limit",
    )
    if any(marker in low for marker in transient_markers):
        return False
    return any(marker in low for marker in permanent_markers)


def _is_instagram_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return host.endswith("instagram.com") or host.endswith("instagr.am")


def _is_probably_direct_image_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in DIRECT_IMAGE_EXTS:
        return True
    ctype, _ = mimetypes.guess_type(parsed.path)
    return bool(ctype and ctype.startswith("image/"))


def download_direct_image(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    dest_folder.mkdir(parents=True, exist_ok=True)
    before = _snapshot_files(dest_folder)
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or f"download_{int(time.time())}.jpg"
    if not Path(name).suffix:
        name += ".jpg"
    target = dest_folder / _safe_slug(name, max_len=120)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=45) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read()
        if not data:
            return [], "urllib downloaded zero bytes"
        if "image" not in content_type.lower() and not _is_probably_direct_image_url(url):
            return [], f"urllib response was not image content: {content_type}"
        target.write_bytes(data)
        images = _collect_new_valid_images(dest_folder, before)
        if images:
            print_step("+", f"Saved direct image → {images[0].name}", C.GREEN)
        return images, f"urllib saved {target} ({len(data)} bytes; {content_type})"
    except Exception as exc:
        return [], f"urllib direct image failed: {exc}"


BROWSERS = ["firefox", "chrome", "edge", "brave", "opera", "chromium", "vivaldi"]


def _ytdlp_bin() -> Optional[str]:
    if _ensure_ytdlp() and YTDLP_PATH.exists():
        return str(YTDLP_PATH)
    return None


def _instagram_ytdlp_base_cmd(url: str, out_tmpl: str) -> List[str]:
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
    Instagram download (archiver logic):
      Cookie auth: Firefox → Chrome → Edge → Brave → Opera → Chromium → Vivaldi
      Then public (no cookies).
      MEDIA ONLY. Success = new valid still images via _collect_new_valid_images.
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
                if any(x in low for x in (
                    "download", "100%", "error", "destination", "writing",
                    "merging", "cookie", "extract", "warning",
                )):
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
        images = _collect_new_valid_images(dest_folder, before)
        if images:
            for p in images:
                print_step("+", f"Saved via Instagram yt-dlp ({browser}) → {p.name}", C.GREEN)
            print_step("+", f"Download finished via {browser.upper()} cookies!", C.GREEN)
            return images, "\n".join(combined_log)
        print_step("!", f"{browser} cookies produced no new images — next...", C.YELLOW)

    before = _snapshot_files(dest_folder)
    print_step("~", "Final Instagram attempt without cookies (public only)...", C.DIM)
    log = _run(_instagram_ytdlp_base_cmd(url, out_tmpl), "public")
    combined_log.append(f"=== public ===\n{log}")
    images = _collect_new_valid_images(dest_folder, before)
    if images:
        for p in images:
            print_step("+", f"Saved via Instagram yt-dlp (public) → {p.name}", C.GREEN)
        print_step("+", "Download finished (public / no cookies)!", C.GREEN)
        return images, "\n".join(combined_log)

    print_step("!", "Instagram yt-dlp finished but no new still image in folder", C.YELLOW)
    print_step("!", "FIX: Firefox → instagram.com → log in → CLOSE Firefox → re-run", C.YELLOW)
    return [], "\n".join(combined_log)


def download_via_gallery_dl(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    dest_folder.mkdir(parents=True, exist_ok=True)
    if not _ensure_gallery_dl():
        return [], "gallery-dl not available"
    before = _snapshot_files(dest_folder)
    env = {
        **os.environ,
        "PYTHONPATH": SITE_PACKAGES + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    cmd = _gallery_dl_cmd(url, dest_folder) + [
        "--no-part",
        "--no-skip",
        "--write-metadata",
        "--write-tags",
        "--write-info-json",
    ]
    print_step("~", f"gallery-dl: {url[:90]}...", C.DIM)
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
            if any(token in low for token in ("download", "error", "warning", "skip", "extract", "http")):
                print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
        images = _collect_new_valid_images(dest_folder, before)
        for p in images:
            print_step("+", f"Saved via gallery-dl → {p.name}", C.GREEN)
        return images, out
    except subprocess.TimeoutExpired:
        return [], "gallery-dl timed out (600s)"
    except Exception as exc:
        return [], f"gallery-dl failed: {exc}"


def download_via_ytdlp(url: str, dest_folder: Path) -> Tuple[List[Path], str]:
    dest_folder.mkdir(parents=True, exist_ok=True)
    if not _ensure_ytdlp():
        return [], "yt-dlp not available"
    before = _snapshot_files(dest_folder)
    ytdlp = str(YTDLP_PATH) if YTDLP_PATH.exists() else (shutil.which("yt-dlp") or sys.executable)
    if ytdlp == sys.executable:
        cmd = [sys.executable, "-m", "yt_dlp", url]
    else:
        cmd = [ytdlp, url]
    out_tmpl = str(dest_folder / "%(id)s_%(title).80B.%(ext)s")
    cmd += [
        "-o", out_tmpl,
        "--skip-download",
        "--write-thumbnail",
        "--convert-thumbnails", "jpg",
        "--ignore-errors",
        "--no-warnings",
        "--retries", "3",
    ]
    env = {
        **os.environ,
        "PYTHONPATH": SITE_PACKAGES + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }
    print_step("~", f"yt-dlp thumbnail path: {url[:90]}...", C.DIM)
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
            if any(token in low for token in ("download", "thumbnail", "error", "warning", "destination")):
                print(f"      {C.DIM}{line.strip()[:120]}{C.RESET}")
        images = _collect_new_valid_images(dest_folder, before)
        for p in images:
            print_step("+", f"Saved via yt-dlp thumbnail path → {p.name}", C.GREEN)
        return images, out
    except subprocess.TimeoutExpired:
        return [], "yt-dlp thumbnail path timed out (600s)"
    except Exception as exc:
        return [], f"yt-dlp thumbnail path failed: {exc}"


def download_image_from_url(url: str, dest_folder: Path) -> Tuple[List[Path], str, bool]:
    logs: List[str] = []
    url = url.strip()
    if not url:
        return [], "empty URL", True

    if _is_probably_direct_image_url(url):
        imgs, log = download_direct_image(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False

    # ---- Instagram: archiver cookie / media-only logic ----
    if _is_instagram_url(url):
        imgs, log = download_via_instagram_ytdlp(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        print_step("~", "Instagram cookie/yt-dlp produced no images — trying gallery-dl...", C.DIM)
        imgs, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        # last resort: existing yt-dlp thumbs path
        print_step("~", "gallery-dl produced no images — trying yt-dlp thumbnail path...", C.DIM)
        imgs, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        permanent = _looks_permanent_download_error("\n".join(logs))
        return [], "\n".join(logs), permanent

    # ---- Pinterest / Reddit: gallery-dl first ----
    if "pinterest.com" in url.lower() or "reddit.com" in url.lower():
        imgs, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        print_step("~", "gallery-dl produced no images — trying yt-dlp thumbnail path...", C.DIM)
        imgs, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        permanent = _looks_permanent_download_error("\n".join(logs))
        return [], "\n".join(logs), permanent

    host = urllib.parse.urlparse(url).netloc.lower()
    if any(host.endswith(domain) for domain in SOCIAL_DOMAINS):
        imgs, log = download_via_gallery_dl(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False
        imgs, log = download_via_ytdlp(url, dest_folder)
        logs.append(log)
        if imgs:
            return imgs, "\n".join(logs), False

    imgs, log = download_direct_image(url, dest_folder)
    logs.append(log)
    permanent = _looks_permanent_download_error("\n".join(logs))
    return imgs, "\n".join(logs), permanent


def _load_google_genai(api_key: str) -> Any:
    if SITE_PACKAGES not in sys.path:
        sys.path.insert(0, SITE_PACKAGES)
    try:
        import google.generativeai as genai  # type: ignore
    except Exception:
        if not _pip_install("google-generativeai"):
            raise
        import google.generativeai as genai  # type: ignore
    genai.configure(api_key=api_key)
    return genai


def _image_mime_type(path: Path) -> str:
    ctype, _ = mimetypes.guess_type(str(path))
    if ctype and ctype.startswith("image/"):
        return ctype
    return "image/jpeg"


def _read_image_part(path: Path) -> Dict[str, Any]:
    data = path.read_bytes()
    return {"mime_type": _image_mime_type(path), "data": data}


def _build_user_prompt(path: Path, theme: Optional[str] = None, source_url: Optional[str] = None) -> str:
    theme_text = ""
    if theme:
        theme_text = USER_THEMATIC_OVERRIDES.get(theme, theme)
    source_text = f"\nSource URL: {source_url}" if source_url else ""
    return textwrap.dedent(
        f"""
        Analyze the attached image as forensic visual evidence and produce the requested image-to-prompt output.
        File name: {path.name}{source_text}
        Optional user thematic override: {theme_text or 'none'}

        Preserve the scene faithfully. If a detail is uncertain, state it as uncertain rather than inventing it.
        """
    ).strip()


def _is_retryable_gemini_error(text: str) -> bool:
    low = text.lower()
    return any(token in low for token in ("timeout", "temporarily", "overloaded", "unavailable", "429", "quota", "rate", "resource_exhausted"))


def _extract_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    parts: List[str] = []
    try:
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                value = getattr(part, "text", None)
                if value:
                    parts.append(str(value))
    except Exception:
        pass
    return "\n".join(parts).strip()


def call_gemini_with_retry(
    image_path: Path,
    rotator: GeminiApiKeyRotator,
    theme: Optional[str] = None,
    source_url: Optional[str] = None,
    max_attempts_per_model: int = 2,
) -> Tuple[str, str, str]:
    last_error = ""
    for model_name in MODEL_FALLBACK_ORDER:
        for attempt in range(1, max_attempts_per_model + 1):
            key = rotator.wait_for_available_key()
            print_step("~", f"Gemini {model_name} attempt {attempt} using {key.label}", C.CYAN)
            try:
                genai = _load_google_genai(key.api_key)
                generation_config = {
                    "temperature": 0.22,
                    "top_p": 0.92,
                    "top_k": 32,
                    "max_output_tokens": 8192,
                }
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=FORENSIC_SYSTEM_PROMPT,
                    generation_config=generation_config,
                )
                image_part = _read_image_part(image_path)
                response = model.generate_content([
                    _build_user_prompt(image_path, theme=theme, source_url=source_url),
                    image_part,
                ])
                text = _extract_response_text(response)
                if not text:
                    raise RuntimeError("Gemini returned an empty response")
                rotator.record_success(key)
                return text, model_name, key.label
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                rotator.mark_error(key, last_error)
                print_step("!", f"Gemini error on {model_name}: {last_error[:220]}", C.YELLOW)
                if not _is_retryable_gemini_error(last_error):
                    break
                time.sleep(min(15 * attempt, 45))
        print_step("~", f"Falling back from {model_name}", C.DIM)
    raise RuntimeError(f"All Gemini model fallbacks failed. Last error: {last_error}")


def _exif_datetime(path: Path) -> Optional[_dt.datetime]:
    if Image is None:
        return None
    try:
        with Image.open(path) as img:  # type: ignore[union-attr]
            exif = img.getexif()
            for tag in (36867, 36868, 306):
                value = exif.get(tag)
                if not value:
                    continue
                if isinstance(value, bytes):
                    value = value.decode("utf-8", "ignore")
                value = str(value).strip()
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return _dt.datetime.strptime(value, fmt)
                    except ValueError:
                        continue
    except Exception:
        return None
    return None


def sort_images_by_exif(paths: Iterable[Path]) -> List[Path]:
    def key(path: Path) -> Tuple[float, str]:
        exif_dt = _exif_datetime(path)
        if exif_dt:
            return (exif_dt.timestamp(), str(path).lower())
        try:
            return (path.stat().st_mtime, str(path).lower())
        except Exception:
            return (0.0, str(path).lower())

    return sorted([p for p in paths if p.exists() and _is_valid_image(p)], key=key)


def discover_local_images(image_folder: Path) -> List[Path]:
    if not image_folder.exists():
        return []
    paths = [p for p in image_folder.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS]
    return sort_images_by_exif(paths)


def _prompt_path_for_image(done_folder: Path, image_path: Path) -> Path:
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = _safe_slug(image_path.stem, max_len=80)
    return done_folder / f"{stamp}_{base}_prompt.txt"


def _unique_destination(folder: Path, name: str) -> Path:
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(1, 10000):
        trial = folder / f"{stem}_{i:03d}{suffix}"
        if not trial.exists():
            return trial
    return folder / f"{stem}_{int(time.time())}{suffix}"


def archive_image_and_prompt(
    image_path: Path,
    prompt_text: str,
    done_folder: Path,
    model_name: str,
    key_label: str,
    source_url: Optional[str] = None,
) -> Tuple[Path, Path]:
    done_folder.mkdir(parents=True, exist_ok=True)
    prompt_path = _prompt_path_for_image(done_folder, image_path)
    metadata = {
        "source_image": str(image_path),
        "source_url": source_url,
        "model": model_name,
        "key": key_label,
        "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "sha256": _hash_file(image_path) if image_path.exists() else None,
    }
    prompt_path.write_text(
        "# FORENSIC IMAGE-TO-PROMPT ENGINE\n\n"
        + json.dumps(metadata, indent=2, ensure_ascii=False)
        + "\n\n"
        + prompt_text.strip()
        + "\n",
        encoding="utf-8",
    )
    destination = _unique_destination(done_folder, image_path.name)
    try:
        shutil.move(str(image_path), str(destination))
    except Exception:
        shutil.copy2(str(image_path), str(destination))
    print_step("+", f"Archived prompt → {prompt_path.name}", C.GREEN)
    print_step("+", f"Archived image → {destination.name}", C.GREEN)
    return destination, prompt_path


class ActivePauseTimer:
    """Enforce the original 10min active / 10min pause cadence."""

    def __init__(self, active_seconds: int = ACTIVE_WINDOW_SECONDS, pause_seconds: int = PAUSE_WINDOW_SECONDS) -> None:
        self.active_seconds = active_seconds
        self.pause_seconds = pause_seconds
        self.window_started = time.time()

    def checkpoint(self) -> None:
        elapsed = time.time() - self.window_started
        if elapsed < self.active_seconds:
            return
        print_step("~", f"Active window reached {self.active_seconds // 60}min; pausing {self.pause_seconds // 60}min", C.YELLOW)
        time.sleep(self.pause_seconds)
        self.window_started = time.time()


def _read_urls_from_picker(picker_path: Path) -> List[str]:
    if not picker_path.exists():
        picker_path.write_text(
            "# Paste image/social URLs here, one per line. Processed URLs are commented out.\n",
            encoding="utf-8",
        )
        return []
    urls: List[str] = []
    for line in picker_path.read_text(encoding="utf-8", errors="replace").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if re.match(r"https?://", value, flags=re.I):
            urls.append(value)
    return urls


def _mark_url_processed(picker_path: Path, url: str, permanent: bool = False) -> None:
    if not picker_path.exists():
        return
    old = picker_path.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines: List[str] = []
    marker = "DONE" if not permanent else "SKIP/PERMANENT"
    for line in old:
        if line.strip() == url:
            new_lines.append(f"# {marker} {time.strftime('%Y-%m-%d %H:%M:%S')} {line}")
        else:
            new_lines.append(line)
    picker_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def input_with_timeout(prompt: str, timeout_seconds: int) -> str:
    result: "queue.Queue[str]" = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result.put(input(prompt))
        except Exception:
            result.put("")

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        return result.get(timeout=timeout_seconds).strip()
    except queue.Empty:
        print()
        return ""


def gather_urls(args: argparse.Namespace, image_folder: Path) -> List[str]:
    urls: List[str] = []
    if args.url:
        urls.extend(args.url)
    picker_path = image_folder / URL_PICKER_FILENAME
    picker_urls = _read_urls_from_picker(picker_path)
    if picker_urls:
        print_step("~", f"Loaded {len(picker_urls)} URL(s) from {picker_path.name}", C.CYAN)
        urls.extend(picker_urls)
    if not args.no_prompt:
        pasted = input_with_timeout(f"Paste image/social URL now ({URL_INPUT_TIMEOUT_SECONDS}s timeout, Enter to skip): ", URL_INPUT_TIMEOUT_SECONDS)
        if pasted:
            urls.append(pasted)
    seen: Set[str] = set()
    unique: List[str] = []
    for url in urls:
        if url not in seen:
            unique.append(url)
            seen.add(url)
    return unique


def process_one_image(
    image_path: Path,
    rotator: GeminiApiKeyRotator,
    done_folder: Path,
    timer: ActivePauseTimer,
    theme: Optional[str] = None,
    source_url: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[Path]:
    timer.checkpoint()
    print_step("~", f"Analyzing {image_path.name}", C.CYAN)
    if dry_run:
        print_step("~", f"Dry run: would analyze {image_path}", C.DIM)
        return None
    prompt_text, model_name, key_label = call_gemini_with_retry(
        image_path,
        rotator,
        theme=theme,
        source_url=source_url,
    )
    _image_archive, prompt_path = archive_image_and_prompt(
        image_path,
        prompt_text,
        done_folder,
        model_name,
        key_label,
        source_url=source_url,
    )
    return prompt_path


def process_urls(
    urls: Sequence[str],
    image_folder: Path,
    done_folder: Path,
    rotator: GeminiApiKeyRotator,
    timer: ActivePauseTimer,
    theme: Optional[str] = None,
    dry_run: bool = False,
) -> None:
    picker_path = image_folder / URL_PICKER_FILENAME
    download_folder = image_folder / "Downloaded URL Images"
    for url in urls:
        timer.checkpoint()
        print_step("~", f"Downloading URL: {url}", C.CYAN)
        imgs, log, permanent = download_image_from_url(url, download_folder)
        log_path = download_folder / f"download_{int(time.time())}.log"
        try:
            log_path.write_text(log, encoding="utf-8", errors="replace")
        except Exception:
            pass
        if not imgs:
            print_step("!", f"No images downloaded for URL (permanent={permanent})", C.YELLOW)
            if permanent:
                _mark_url_processed(picker_path, url, permanent=True)
            continue
        for img in sort_images_by_exif(imgs):
            process_one_image(
                img,
                rotator,
                done_folder,
                timer,
                theme=theme,
                source_url=url,
                dry_run=dry_run,
            )
        _mark_url_processed(picker_path, url, permanent=False)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FORENSIC IMAGE-TO-PROMPT ENGINE")
    parser.add_argument("--image-folder", default=DEFAULT_IMAGE_FOLDER_NAME, help="Folder containing images to process")
    parser.add_argument("--done-folder", default=DONE_FOLDER_NAME, help="Archive/output folder")
    parser.add_argument("--url", action="append", help="Image or social URL to download and process")
    parser.add_argument("--theme", help="Optional USER_THEMATIC_OVERRIDES key or freeform instruction")
    parser.add_argument("--limit", type=int, default=0, help="Maximum local images to process after URL downloads")
    parser.add_argument("--dry-run", action="store_true", help="Discover/sort/download without calling Gemini")
    parser.add_argument("--no-prompt", action="store_true", help="Skip the 8 second URL paste prompt")
    parser.add_argument("--status", action="store_true", help="Print parsed key status and exit")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    banner()
    root = Path.cwd()
    image_folder = _ensure_dir((root / args.image_folder).resolve())
    done_folder = _ensure_dir((root / args.done_folder).resolve())
    print_step("~", f"Image folder: {image_folder}", C.DIM)
    print_step("~", f"Done folder: {done_folder}", C.DIM)
    print_step("~", f"URL picker: {image_folder / URL_PICKER_FILENAME}", C.DIM)

    keys = parse_user_config(USER_CONFIG)
    rotator = GeminiApiKeyRotator(keys)
    if args.status:
        for line in rotator.status_lines():
            print(line)
        if not keys:
            print_step("!", "No usable Gemini API keys configured; placeholders are intentionally ignored.", C.YELLOW)
        return 0
    if not keys and not args.dry_run:
        print_step("!", "No usable Gemini API keys configured in USER_CONFIG. Replace placeholders before live analysis.", C.RED)
        return 2

    timer = ActivePauseTimer()
    urls = gather_urls(args, image_folder)
    if urls:
        process_urls(urls, image_folder, done_folder, rotator, timer, theme=args.theme, dry_run=args.dry_run)

    local_images = discover_local_images(image_folder)
    if args.limit and args.limit > 0:
        local_images = local_images[: args.limit]
    if not local_images:
        print_step("~", "No local images waiting in Image to Prompt", C.DIM)
        return 0
    print_step("~", f"Processing {len(local_images)} local image(s) sorted by EXIF/filesystem time", C.CYAN)
    for image_path in local_images:
        process_one_image(
            image_path,
            rotator,
            done_folder,
            timer,
            theme=args.theme,
            source_url=None,
            dry_run=args.dry_run,
        )
    print_step("+", "FORENSIC IMAGE-TO-PROMPT ENGINE complete", C.GREEN)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print_step("!", "Interrupted by user", C.YELLOW)
        raise SystemExit(130)
    except Exception as exc:
        print_step("!", f"Fatal error: {exc}", C.RED)
        traceback.print_exc()
        raise SystemExit(1)
