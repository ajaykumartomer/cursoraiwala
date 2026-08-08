# Instagram Media Downloader

Windows-friendly Instagram downloader that **scans C: for browser cookies** (Firefox first), then downloads.

## Main script (use this)

`ig_archiver.py` — matches the Firefox → Chrome → other browsers cookie-try flow.

```bat
pip install -r requirements.txt

:: 1) Open Firefox → instagram.com → log in → CLOSE Firefox
:: 2) Run:
python ig_archiver.py
python ig_archiver.py "https://www.instagram.com/reel/XXXX/"
python ig_archiver.py --scan-only
python ig_archiver.py --deep-scan
```

Or double-click `run_instagram_downloader.bat`.

### What it does
1. Scans `C:\Users\*\AppData\...` for browsers (**Firefox → Chrome → Edge → Brave → …**)
2. If Firefox has Instagram `sessionid`, exports `cookies.txt`
3. Tries cookie file, then each browser via `--cookies-from-browser`
4. Downloads reel / post / carousel with live yt-dlp output

Saves to `%USERPROFILE%\Downloads\Instagram_Archives\`.

## Other files
| File | Role |
|---|---|
| `ig_archiver.py` | **Primary** Windows archiver (your cookie-try logic + C: scan) |
| `browser_cookie_scanner.py` | Discovers/export Firefox/Chrome cookie DBs on C: |
| `instagram_downloader.py` | Dual engine (gallery-dl + yt-dlp) advanced option |
| `run_instagram_downloader.bat` | Double-click launcher |

## Tip
Close Firefox before running so `cookies.sqlite` is not locked. The script copies the DB when possible, but closed browser is most reliable.
