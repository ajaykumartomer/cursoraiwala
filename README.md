# AKT Social Media Tools

## Complete all-in-one script (use this)

**[`AKT_Universal_Video_Downloader.py`](./AKT_Universal_Video_Downloader.py)** — single file (~2700 lines).  
No other project files required.

Includes:
- Universal video download (any http(s) URL → `.mp4` when available)
- Social Media Snapshotter (X/Twitter + Instagram S24 Ultra screenshots)
- Full yt-dlp ladder (API → CLI → browser cookies → gallery-dl → streamlink/direct)

### Run

```bash
python AKT_Universal_Video_Downloader.py
python AKT_Universal_Video_Downloader.py "https://example.com/video"
```

Or put URLs in `Social Media SnapShottter URL Picker.txt` (one per line).

### Outputs

- `Social Media Videos/`
- `Social Media Screenshots/`

Windows tools install to `C:\AKT Media Tools`. Other OS: `.akt_media_tools/` next to the script.

## Modular copies (optional)

- `social_media_screenshotter.py` + `video_download_engine.py` — same logic split into two modules
