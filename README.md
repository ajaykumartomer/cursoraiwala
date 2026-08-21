# Ultimate Media Tool FINAL

Single-file **ULTIMATE MEDIA TOOL FINAL - GOOGLE DRIVE + DOC CLEANUP** (`Ultimate_Media_Tool.py`).

## What it does

1. **Google Drive first** (hard gate): scans Docs in the configured Drive folder, downloads original media (cookie-independent), saves timestamp/green Screenshots separately, runs OCR/Whisper on **original media only**, then removes each URL from the Doc only after a successful scrape and archives it under `{DocTitle}/Completed {DocTitle} URL.txt`.
2. **URL Picker** (`Ultimate Media Tool URL Picker.txt`): continues after Drive. Successful URLs are erased and archived to `Completed Ultimate Media Tool URL.txt`; permanent download failures go to `Ultimate Media Tool URL Picker Failed.txt`.
3. If the picker is empty: **8s manual URL** prompt, then **local media** in the script folder (local media also runs after picker jobs).

Screenshots (S24 Ultra Playwright for Instagram/X, `Post_Saved_On:…` auto-fit timestamp, green-screen only when video is visible) are saved under `Screenshots/` and **never** sent to OCR/Whisper. YouTube is video-only (no social screenshot). Video downloads use a **cookie-independent** yt-dlp ladder.

## Setup

1. Replace placeholder Groq keys in `USER_CONFIG` (`gsk_YOUR_GROQ_API_KEY_01` … `_12`). Do not commit real keys; rotate any key that was previously pasted into chat.
2. Place Google OAuth desktop `credentials.json` next to the script (scopes: Drive readonly + Documents). First run creates `token.json`.
3. Libraries install under `C:\AKT Media Tools` (`Lib\site-packages`, `Tools`, `GoogleLibs`). Media/output stays beside the `.py` file.

## Outputs

- `{DocTitle}/` — Drive jobs: `{DocTitle} Image/Video Scraper`, matching `.txt` logs, `Screenshots/`, `Completed {DocTitle} URL.txt`
- `Combined Ultimate Media Tool/` — picker/manual downloads + `Screenshots/`
- Default Combined Image/Video/Audio Scraper folders + Combine `*.txt` logs for local/non-Drive mode
- `Ultimate Media Tool Job Log.txt`

## Run

```bash
python Ultimate_Media_Tool.py
```
