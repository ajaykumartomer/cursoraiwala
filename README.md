# Forensic Media-to-Prompt Engines

One-click Gemini Flash scripts that turn local or Instagram/social media into forensic reconstruction prompts (Windows-oriented; libraries under `C:\AKT Media Tools`).

## Files

| Script | Purpose |
|--------|---------|
| `forensic_image_to_prompt.py` | Images → master + forensic prompts |
| `forensic_video_to_prompt.py` | Videos → 1-FPS frames → pin-point master + shot list + forensic prompts |

## Setup

1. Paste Gemini API keys into the `USER_CONFIG` block at the top of the script (replace `YOUR_GEMINI_API_KEY_*` placeholders).
2. **Do not commit real keys.** Rotate any key that was ever pasted into chat or committed.
3. Run the script. Packages install into `C:\AKT Media Tools\Lib\site-packages`.
   - Image: Pillow, google-genai, gallery-dl
   - Video: Pillow, opencv-python, google-genai, gallery-dl (+ yt-dlp.exe under Tools)

## Shared behavior (both scripts)

- Gemini model auto-fallback: `3.6-flash` → `3.5` → `3.1-flash-lite` → `2.5` → `2.0`
- 12-key rotation with RPM/RPD thresholds + 600s key-switch delay
- 10-minute active / 10-minute pause loop
- URL Picker + Done / Failed / Job Log (Ultimate Media Tool style)
- Blank thematic overrides → pure original reconstruction
- Naming: `Image 1 …` / `Video 1 …` (legacy `No.` still counted)

## Image engine

- **gallery-dl** preferred for Instagram photo / carousel posts
- **yt-dlp** fallback with `--ignore-no-formats-error` + one thumbnail per slide
- Folders: `Image to Prompt\`, URL picker files named `Image to Prompt URL Picker*.txt`

## Video engine

- OpenCV **1-FPS** frame extraction (max 60 frames, resized ≤768px)
- Pin-point second-by-second direction / face / object tracking in the prompt
- **yt-dlp** preferred for reels/posts (actual video), gallery-dl fallback
- Sort: Media/EXIF date created first (earliest first)
- Folders: `Video to Prompt\`, URL picker files named `Video to Prompt URL Picker*.txt`
- Output: `combined_video_output.txt` (master prompt + timestamped shot list + forensic analysis)
