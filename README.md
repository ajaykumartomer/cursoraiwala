# Ultimate Media Tool

Windows Python media pipeline for Google Drive docs + URL picker + local files.

## Repairs in this branch

1. **Permanent-error detection** — accumulates real yt-dlp/gallery-dl/browser logs; quarantines `Suspended` / deleted / unavailable immediately; quarantines “no video” only after image recovery + browser fallback.
2. **Drive quarantine** — permanent failures are removed from the Google Doc and recorded in `Failed <Doc> URL.txt` (no infinite retry).
3. **Image-post recovery** — after the video ladder fails, runs full `gallery-dl` (and yt-dlp still/thumbnail) so image/GIF posts are not treated as total failures.
4. **X browser fallback** — tries `platform.twitter.com/embed/Tweet.html` (and syndication) before the raw `x.com` page, matching the screenshotter path that already works.

## Setup

1. Copy `Ultimate_Media_Tool.py` to your media folder.
2. Put Groq keys in the `USER_CONFIG` block (`gsk_...` or `YOUR_GROQ_API_KEY_N` placeholders).
3. Libraries install under `C:\AKT Media Tools`.
4. Google Drive uses `credentials.json` / `token.json` beside the script.
