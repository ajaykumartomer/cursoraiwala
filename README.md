# Forensic Image-to-Prompt Engine

One-click Gemini 2.5 Flash script that turns images (local or Instagram/social URLs) into forensic reconstruction prompts.

## File

- `forensic_image_to_prompt.py` — main script (Windows-oriented; libraries under `C:\AKT Media Tools`)

## Setup

1. Paste your Gemini API keys into the `USER_CONFIG` block at the top of the script (replace `YOUR_GEMINI_API_KEY_*` placeholders).
2. **Do not commit real keys.** Rotate any key that was ever pasted into chat or committed.
3. Run the script. It installs Pillow, google-genai, and gallery-dl into `C:\AKT Media Tools\Lib\site-packages`.

## Instagram / social downloads

- **gallery-dl** is preferred for Instagram photo posts and carousels.
- **yt-dlp** is used as fallback with `--ignore-no-formats-error` + thumbnail extraction (image-only posts no longer fail with “No video formats found” and zero files).
- All downloaded stills from a carousel are processed (not just the first).
- Permanent download failures are moved to `Image to Prompt URL Picker Failed.txt` so they do not retry forever.

## Folders

| Path | Purpose |
|------|---------|
| `Image to Prompt\` | Source images + `combined_image_output.txt` |
| `Image to Prompt\Image to Prompt Done\` | Processed images |
| `Image to Prompt URL Picker.txt` | URLs to download |
| `Image to Prompt URL Picker Failed.txt` | Quarantined permanent failures |
