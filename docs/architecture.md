# Architecture

## One pipeline, two front doors

```
 Feature phone ──► Twilio IVR webhooks ─┐
                                        ├──► FastAPI session + state machine ──► pipeline
 Browser simulator ──► REST API ────────┘

 pipeline (backend/app/pipeline.py)

  audio ─► STT (Sarvam Saaras v4, medical keyterms) ─► READ-BACK "I heard X, press 1"
         ─► translate → English (Sarvam Translate)
         ─► SAFETY TRIAGE (rules on native + English text)
               ├─ emergency / crisis ─► fixed script + first-aid line, LLM never called
               └─ otherwise ─► retrieve vetted cards ─► LLM in English (Groq) ─► translate back
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
Invalid transitions raise and return HTTP 409. Twilio retries are de-duplicated with
the `I-Twilio-Idempotency-Token` header.

## Privacy
- Sessions, transcripts and audio live in memory only and are wiped when the call ends.
- The care slip exists only with explicit consent (keypad 1), expires after 24 h, and can be deleted.
- Logs contain session ids and states, never health text or provider error bodies.
- Twilio webhooks are HMAC-SHA1 signature-checked.

## Extending to a new language
Add a `Language(...)` entry in `backend/app/languages.py` with the providers that
really support it. The capability table, IVR menu and fallbacks update automatically.
