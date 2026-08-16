# Tweet screenshotter

Capture a complete, high-quality screenshot of an X/Twitter post: profile picture and username through the like, view, bookmark, and share bar.

The script uses Playwright to screenshot the tweet `<article>` element, so the crop matches the post itself instead of the whole browser window.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
python tweet_screenshotter.py
```

When prompted, paste a URL such as:

`https://x.com/nehruwaad/status/2088937530028937559?s=20`

Or pass the URL directly:

```bash
python tweet_screenshotter.py "https://x.com/nehruwaad/status/2088937530028937559?s=20"
```

The PNG is saved next to the script as `tweet_<id>.png`. Use `-o` to choose another path.

X sometimes shows a login wall. If the tweet element cannot be found, the script writes a full-page `_page.png` debug capture.
