# Architecture

## One pipeline, one front door today (a phone line plugs in later)

```
 Phone or laptop browser (mic over HTTPS) ──► REST API ──► FastAPI session + state machine ──► pipeline
 Keypad phone line (planned) ──► telephony adapter ──┘   needs a paid provider (Twilio, Exotel...)

 pipeline (backend/app/pipeline.py)

  audio ─► STT (Sarvam Saaras v4, medical keyterms) ─► READ-BACK "I heard X, press 1"
         ─► translate → English (Sarvam Translate)
         ─► SAFETY TRIAGE (rules on native + English text)
               ├─ emergency / crisis ─► fixed script + first-aid line, LLM never called
               │      └─► ask location (GPS, or village / town / PIN / landmark, or keypad PIN)
               │             ─► seed hospital list (SQLite) + OpenStreetMap ─► nearest help + 108/112
               └─ otherwise ─► retrieve vetted cards ─► LLM in English (Groq)
                      ─► DOSE FILTER (any amount/frequency → vetted card instead) ─► translate back
         ─► TTS (Parler for as/brx/mni/ne, Sarvam Bulbul for hi/bn/en; fixed prompts pre-rendered)
```

## Why English in the middle
Open LLMs on free tiers write weak Assamese/Bodo/Manipuri but reason well in English.
Sarvam Translate covers all NER scheduled languages, so the LLM thinks in English and
the caller hears their own language. The triage rules also get an English copy,
while native-language keywords still catch red flags if translation fails.

## Latency budget (target, live mode)
| Step | Typical | How it is kept down |
|---|---|---|
| Fixed prompts (menus, read-back frame, emergency) | ~0 ms | Pre-rendered audio (`scripts/prerender_prompts.py`) |
| STT | 0.5–1.5 s | Short utterances, 16 kHz, Sarvam REST |
| Translate ×2 | 0.2–0.5 s each | Cached |
| Triage + retrieval | <5 ms | Pure Python |
| LLM | 0.3–1 s | Groq LPU, max 220 tokens, ≤4 sentences |
| TTS | 1–3 s | GPU Parler / Sarvam Bulbul |

Each turn returns `timings_ms`, shown as a waterfall in the UI.

## State machine (backend/app/sessions.py)

```
INCOMING_CALL → LANGUAGE_SELECTION → READY_TO_LISTEN → CONFIRMING ─┬─► ANSWERED ──┐
                       ▲                     ▲          (read-back) └─► EMERGENCY ─┤
                       └──── press 3 ────────┴──────── press 1 ◄──────────────────┘
                                                                  press 9 → CONSENT → CALL_ENDED
```
Invalid transitions raise and return HTTP 409. Location search does not change state:
it can run from ANSWERED or EMERGENCY (keypad 4) and never delays the emergency script.

## Healthcare navigation (backend/app/facilities.py)
- `data/facilities.csv`: public medical colleges and district hospitals in all eight NE states,
  plus a denser Guwahati list. Loaded into SQLite at start-up. Every row says "not yet verified"
  and has no phone number until someone has phoned it and filled in `verified_on`.
- `data/places.csv`: towns, Guwahati localities, Assamese/Hindi spellings and PIN codes, so
  "Jalukbari", "781014" or "মালিগাঁও" all resolve without any network.
- Optional free OpenStreetMap lookups (Nominatim, Overpass), always labelled as community data.
- Nothing is ever sent to a hospital. The response always says so.

## Medicine safety (backend/app/medicine.py)
- Prescription requests ("which medicine", "what dose", "how many tablets") pull the
  medicine-safety card to the front and add an explicit refusal rule to the prompt.
- Any generated answer stating an amount, strength or frequency is discarded and replaced by
  vetted card text. The call log shows when this happened.

## Privacy
- Sessions, transcripts and audio live in memory only and are wiped when the call ends.
- The care slip exists only with explicit consent (keypad 1), expires after 24 h, and can be deleted.
- Logs contain session ids and states, never health text or provider error bodies.
- A caller's location is kept only for the current call and wiped at hang-up.

## Extending to a new language
Add a `Language(...)` entry in `backend/app/languages.py` with the providers that
really support it. The capability table, keypad menu and fallbacks update automatically.
