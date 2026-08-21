# AKT Social Media Tools

## Complete all-in-one script

**[`AKT_Universal_Video_Downloader.py`](./AKT_Universal_Video_Downloader.py)** — single file. No other project files required.

Includes:
- **Cookie/browser-independent** universal video download (any http(s) URL → `.mp4` when available)
- Social Media Snapshotter (X/Twitter + Instagram S24 Ultra screenshots)
- yt-dlp ladder: API → CLI → gallery-dl → streamlink/direct (no `--cookies-from-browser`)
- YouTube player-client ladder (`android`/`ios`/`web_embedded`/…) without reading browser cookie DBs

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

### Video download notes

- Video extraction **never** scrapes Chrome/Firefox/Edge cookie stores and never uses `--cookies-from-browser`.
- Screenshot sessions may still reuse browser cookies for Instagram/X login walls only.
- Age-restricted or bot-gated videos can still fail on some networks; keep `yt-dlp` updated (the script auto-checks about every 12 hours).
