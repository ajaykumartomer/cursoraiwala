# Ultimate Media Tool FINAL

Single-file **ULTIMATE MEDIA TOOL FINAL - GOOGLE DRIVE + DOC CLEANUP** (`Ultimate_Media_Tool.py`).

## What it does

1. **Google Drive first** (hard gate): scans docs in the configured Drive folder, downloads media, screenshots social posts, OCR/Whisper on **original media only**, then removes each URL from the Doc after success and archives it locally.
2. **URL Picker** (`Ultimate Media Tool URL Picker.txt`): successful URLs are erased and archived to `Completed Ultimate Media Tool URL.txt`; permanent failures go to `Ultimate Media Tool URL Picker Failed.txt`.
3. If the picker is empty: **8s manual URL** prompt, then **local media** in the script folder.

Screenshots (S24 Ultra Playwright for Instagram/X, timestamp `Post_Saved_On:…`, green-screen only when video is visible) are saved under `Screenshots/` and **never** sent to OCR/Whisper. Video downloads use a **cookie-independent** yt-dlp ladder.

## Setup

1. Replace placeholder Groq keys in `USER_CONFIG` (`gsk_YOUR_GROQ_API_KEY_01` … `_12`). Do not commit real keys.
2. Place Google OAuth desktop `credentials.json` next to the script (scopes: Drive readonly + Documents). First run creates `token.json`.
3. Libraries install under `C:\AKT Media Tools` (`Lib\site-packages`, `Tools`, `GoogleLibs`). Media/output stays beside the `.py` file.

## Outputs

- `Combined Ultimate Media Tool/` — per-job and per-Doc folders (`{DocTitle} Image/Video Scraper`, `Screenshots/`)
- Default Combined Image/Video/Audio Scraper folders + Combine `*.txt` logs when not in Drive-doc mode
- `Ultimate Media Tool Job Log.txt`

## Run

```bash
python Ultimate_Media_Tool.py
```
