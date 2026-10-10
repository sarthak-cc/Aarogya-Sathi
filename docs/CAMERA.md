# Camera prototype (photo check)

A prototype that turns the Nokia handset around to its back, previews the rear camera, lights a
simulated flash, and sends one confirmed photo to Groq vision (`qwen/qwen3.8-27b`). The answer comes
back in the selected language and is read aloud with the existing TTS. It is not a diagnostic tool,
not a real phone call, and it never stores photos.

## How to use it
- **Key 6** on the handset (or the **Camera (key 6)** button under the phone, or `6` on the keyboard) flips the phone.
- Rear controls (below the phone): **Flash**, **Capture**, **Upload photo**, **Switch** (when there are 2+ cameras),
  **Retake**, **Analyze**, **Back to phone / Cancel**. An optional text box takes a few words of context.
- **END** / `Esc` cancels at any point (including during analysis) and flips back. `*` returns to the main menu.
  While the camera is open, CALL and the dash softkey do nothing, so recording cannot start behind it.
- Existing mappings are unchanged: 1 Hindi, 2 English, 3 Assamese, 4 Hospitals, 5 simpler, 0 emergency,
  dash = record, CALL, END, `*` menu, `#` (unchanged).

Flow: `Open → request permission → live preview → Capture (or Upload) → review → Analyze or Retake → result on the LCD,
call-log card, voice → front`.

## What is real and what is simulated
| Part | Status |
|---|---|
| Flip animation | CSS 3D (`perspective`, `preserve-3d`, `backface-visibility`). Instant swap with `prefers-reduced-motion`. |
| Camera | Browser `getUserMedia`, rear camera preferred (`facingMode: environment`). Starts only on request, stops on capture, cancel, result, END, `*` or when the tab is hidden. |
| Flash | **Simulated**: LED glow, light cone and a lit hand/surface in the viewfinder. If the camera reports `torch` support, the real torch is also switched (progressive enhancement); the UI says which. |
| Analysis | Real Groq API call (`POST /chat/completions`, `image_url` data URL). Not verified live from the build container, which cannot reach Groq; run `scripts/verify_vision_live.py`. |

## Backend: `POST /api/vision/analyze`
Multipart form: `image` (JPEG/PNG/WebP, up to `VISION_MAX_UPLOAD_MB`, default 8 MB), `language` (e.g. `hi-IN`), optional `note` (≤300 chars).

```
{ "ok": true, "language": "hi-IN",
  "vision":  { observation, possible_explanations[], follow_up_questions[], recommended_next_steps[],
               urgency: routine|see_health_worker|urgent|emergency, image_quality: ok|insufficient, disclaimer },
  "english": { ...same fields in English },
  "answer":  { text (spoken summary), lang, source: "vision"|"emergency_script", model, language_note },
  "triage":  { level, blocking, source: rules|vision_ai|null, matches[] },
  "offer_facilities": bool, "voice": { audio_url, provider, note, error },
  "error": null | { provider, kind, message, retry_after }, "timings_ms": {...}, "privacy": "..." }
```
`answer`, `triage` and `voice` follow the same shapes as a normal turn. On any failure `ok` is false,
`vision` is null and `error.kind` is one of `invalid_image`, `not_configured`, `auth`, `rate_limited`,
`timeout`, `unavailable`, `model_unavailable`, `bad_response`. Nothing is guessed, and there is no
fallback to a different model.

Pipeline (`backend/app/photo.py`):
1. If a note is given, the **existing deterministic safety rules run first**. An emergency phrase returns the fixed
   112 script immediately and the photo is **not sent**.
2. The image is decoded with Pillow, made upright, resized to ≤1280 px and re-encoded as JPEG, which **drops EXIF/GPS metadata**.
3. Groq vision is called with a cautious JSON-only prompt: describe, never diagnose, never dose, and say when the photo is insufficient.
4. Doses are stripped from every field (`medicine.strip_doses`). The model's urgency can only **raise** caution: `emergency` adds the 112 line and the hospital finder. It never lowers a rule-based level.
5. Fields are translated with the existing Sarvam translation (English kept and labelled if that fails), then spoken with the
   existing TTS. Assamese uses the cloned voice when `SARVAM_VOICE_ID` is set.

## Privacy
Photos are processed in memory and discarded. They are never written to disk or logged (only `ok` and the error
kind are logged). Nothing is uploaded until **Analyze** is pressed, and the screen says the photo goes to Groq.

## Setup
```bash
pip install -r requirements.txt          # adds pillow
# .env: GROQ_API_KEY=...  (VISION_MODEL defaults to qwen/qwen3.8-27b)
cd backend && uvicorn app.main:app --reload
# open http://localhost:8000 → pick a language (1/2/3) → press 6
```
Browsers allow the camera only on **https://** or **http://localhost**. On a deployed site, use HTTPS
(Render and similar hosts provide it). Without camera access, **Upload photo** still works.

## Tests
- `backend/tests/test_vision.py`: 28 tests, **mocked Groq** (schema, languages, cloned voice, EXIF stripping and resizing,
  invalid/empty/oversized uploads, missing key, 401/404/429/503, timeout, malformed replies, `<think>` tags,
  reasoning-param retry on the same model, emergency-first behaviour, urgency can't be lowered).
- `frontend/tests/camera_e2e.js`: 37 browser checks against the mock provider server with Chromium's fake camera
  (flip and inert faces, preview, flash ×3, capture/retake, one request despite repeated clicks, cancel during analysis,
  END/Escape, tracks stopped, denied/unavailable/upload fallback, network failure, Hindi/Assamese labels,
  keypad still working, 390/768/1360 px, reduced motion).
- `scripts/verify_vision_live.py`: the **real** API check (needs a key and internet).
