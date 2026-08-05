# AKT Media Tools — Forensic + Ultimate Media

One-click Windows scripts. Libraries install under `C:\AKT Media Tools`.

## Scripts

| File | Purpose |
|------|---------|
| `forensic_image_to_prompt.py` | Images → Gemini forensic reconstruction prompts |
| `forensic_video_to_prompt.py` | Videos → 1-FPS frames → Gemini pin-point prompts |
| `ultimate_media_tool.py` | Social download + OCR / Whisper / translate (Groq) |

## Shared patterns (v0.8 parity)

- URL Picker + Done / Failed / Job Log
- gallery-dl + yt-dlp downloads (Instagram-friendly)
- Multi-key rotation + **600s key-switch delay**
- Masked userIDs in logs
- Model auto-fallback
- Repo copies use **API key placeholders only**

## Setup

1. Replace `YOUR_GEMINI_API_KEY_*` or `YOUR_GROQ_API_KEY_*` placeholders locally.
2. **Do not commit real keys.** Rotate any key that was pasted into chat.
3. Put URLs in the matching `* URL Picker.txt` next to the script, or use the 8s prompt.

## Ultimate Media Tool folders

| Path | Purpose |
|------|---------|
| `Combined Image/Video/Audio Scraper by AKT\` | Renamed media (`Image 1 …`) |
| `Combine Image/Video/Audio Scraper.txt` | Extraction logs |
| `Ultimate Media Tool URL Picker.txt` | Active URL queue |
| `Ultimate Media Tool URL Picker Done.txt` | Completed URLs |
| `Ultimate Media Tool URL Picker Failed.txt` | Quarantined failures |
| `Ultimate Media Tool Job Log.txt` | Download + key balance records |
