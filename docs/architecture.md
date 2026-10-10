# Architecture

```
Browser (phone or laptop, HTTPS)
  microphone ─► MediaRecorder ─► 16 kHz mono WAV ─┐            typed text ─┐
                                                  ▼                        ▼
FastAPI  /api/conversations/{id}/speech ─► STT (Sarvam Saaras v3, or Groq Whisper)
                                            │
                                            ▼  /ask
         translate → English (Sarvam Translate)          [skipped for English]
                                            │
         SAFETY RULES on native + English text (triage.py), BEFORE any AI
            ├─ emergency / crisis ─► fixed script + first-aid line (prompts.py), no LLM
            │                          └─► "Find a nearby hospital" (location only on request)
            └─ routine ─► LLM (Groq, openai/gpt-oss-120b) with short history + reference notes
                           ├─ TRIAGE tag: EMERGENCY can upgrade to the emergency script (second net)
                           ├─ dose filter (medicine.py): sentences stating amounts are removed
                           └─► translate back ─► TTS (Sarvam Bulbul; MMS or Parler for as/ne/brx/mni)
                                                    └─► audio served from memory, played in the browser
```

## Honesty rules in code
- No scripted routine answers exist. A missing key, quota, timeout or outage returns a
  `ProviderError` with a `kind` (`not_configured`, `auth`, `rate_limited`, `timeout`,
  `unavailable`, `bad_response`, `unsupported`) that the UI shows in plain words.
- An answer that could not be translated is shown in English **with a label saying so**.
- A language with no voice gets a text answer and a note, never another language's voice.
- The language picker is built from `languages.capability()`: what providers document,
  what is configured, and what `scripts/verify_live.py` has passed.
- Facility emergency capability is only what the data says (`emergency=yes` in OSM or a
  verified row). Unknown stays "unknown". Nothing is ever sent to a hospital.

## Facilities (facilities.py)
- OpenStreetMap via Overpass, searched at 10, 30 and then 80 km. Hospitals come first in an emergency.
- Cached in SQLite (`DB_PATH`) for 7 days. `scripts/import_osm_facilities.py` pre-loads an area.
- `data/verified_facilities.csv`: rows checked by phone, used only with a `verified_on` date.
- Place text goes to Nominatim (max 1 request/s, cached). When OpenStreetMap is off, a built-in
  approximate list of NE towns, Guwahati localities and PIN codes is used, and labelled as such.

## Privacy
Conversations, history and audio live in memory and expire after inactivity. Location is
sent only when the user taps a button, is used for one search, and is not stored. Logs hold
ids and error kinds, never health text.

## Tests
`backend/tests/` uses **mocked HTTP** for every provider (no keys, no network).
`backend/tests/mock_providers.py` is a mock server for browser end-to-end runs.
Real-provider checks: `scripts/verify_live.py` (needs keys and internet).
