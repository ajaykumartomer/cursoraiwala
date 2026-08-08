# Instagram Media Downloader

Fast, max-quality Instagram downloader with **automatic browser cookie scanning**.

## How auth works (important)

Instagram blocks anonymous downloads. On start, the script:

1. Scans **C:** user profiles for browsers in this order: **Firefox → Chrome → Edge → Brave → others**
2. Checks Firefox `cookies.sqlite` for Instagram `sessionid`
3. Exports those cookies to a Netscape `cookies.txt` (most reliable)
4. Downloads the post/reel/carousel with gallery-dl + yt-dlp

## Setup (Windows)

```bash
pip install -r requirements.txt
```

Optional: install [FFmpeg](https://ffmpeg.org/) for video merges.

**Before first run:** open **Firefox**, log into [instagram.com](https://www.instagram.com/), then close Firefox.

## Usage

```bash
# Auto-scan C: for Firefox cookies, then interactive download
python instagram_downloader.py

# One URL
python instagram_downloader.py "https://www.instagram.com/reel/XXXX/"

# Scan cookies only (no download)
python instagram_downloader.py --scan-only

# Deep-scan portable browsers under Users / Program Files
python instagram_downloader.py --deep-scan --scan-only

# Force a browser / skip auto-scan
python instagram_downloader.py --cookies-from-browser chrome URL
python instagram_downloader.py --cookie-file cookies.txt URL
```

Standalone cookie scanner:

```bash
python browser_cookie_scanner.py
python browser_cookie_scanner.py --deep
python browser_cookie_scanner.py --export cookies.txt
```

Files save to `~/Downloads/Instagram_Archives/` (Windows: `C:\Users\<you>\Downloads\Instagram_Archives\`).

## Files

| File | Role |
|---|---|
| `instagram_downloader.py` | Main downloader (auto cookie scan + download) |
| `browser_cookie_scanner.py` | C: browser cookie discovery (Firefox first) |
| `requirements.txt` | yt-dlp + gallery-dl |
