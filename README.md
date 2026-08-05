# Instagram Media Downloader

Fast, max-quality downloader for Instagram posts, reels, carousels, stories, and profiles.

Uses **gallery-dl** (photos / carousels / stories) + **yt-dlp** (reels / best video bitrate) with browser cookies so Instagram auth works.

## Setup

```bash
pip install -r requirements.txt
```

Optional but recommended for video merges: install [FFmpeg](https://ffmpeg.org/) and put it on your `PATH`.

## Usage

Interactive:

```bash
python instagram_downloader.py --cookies-from-browser chrome
```

Single URL:

```bash
python instagram_downloader.py --cookies-from-browser chrome "https://www.instagram.com/reel/XXXX/"
```

Batch file (`urls.txt`, one URL per line):

```bash
python instagram_downloader.py --cookies-from-browser chrome urls.txt
```

Cookie file instead of browser:

```bash
python instagram_downloader.py --cookie-file cookies.txt "https://www.instagram.com/p/XXXX/"
```

Force one engine:

```bash
python instagram_downloader.py --engine gallery-dl --cookies-from-browser chrome URL
python instagram_downloader.py --engine yt-dlp --cookies-from-browser chrome URL
```

Files land in `~/Downloads/Instagram_Archives/Insta_<shortcode>/`.

## Why cookies matter

Instagram blocks most anonymous downloads. Log into Instagram in Chrome/Firefox, then pass `--cookies-from-browser chrome` (or `firefox`, `edge`, `brave`).

## Why the old script failed

| Problem | Fix here |
|---|---|
| `-f best` crashes on photo posts | Format `bv*+ba/b` + gallery-dl for images |
| No login session | `--cookies-from-browser` / `--cookie-file` |
| Subprocess + hard 180s timeout | Native Python APIs, retries, concurrent fragments |
| Carousels / stories flaky on yt-dlp alone | gallery-dl primary, yt-dlp for reels |
