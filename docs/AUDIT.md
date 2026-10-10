# Audit and implementation plan (October 2026)

## What the audit found

| Area | Finding | Verdict |
|---|---|---|
| Routine answers | `demo.py` fuzzy-matches six scripted questions to canned answers. When the LLM is missing or fails, `knowledge.card_answer()` returns card text labelled "Vetted card text (AI not available)". | **Scripted. Removed.** A missing or failed LLM now shows an honest error. |
| LLM prompt | The model was told to answer ONLY from 14 keyword-retrieved cards and to refuse anything else, so arbitrary questions were mostly refused. | **Too narrow. Rewritten.** The cards become optional reference notes, and the model answers any health question within safety rules. |
| LLM model | Default `llama-3.3-70b-versatile` was shut down by Groq on 16 Aug 2026. Live mode would fail even with a valid key. | **Broken. Fixed:** `openai/gpt-oss-120b` (configurable), low reasoning effort. |
| Translation fallback | `demo.english_for()` "translated" only the six scripted questions. | **Fake. Removed.** |
| STT | Sarvam call sent an undocumented `keyterms` field with `saaras:v4`. Browser sent webm. | **Unverified. Fixed:** documented `saaras:v3` + `mode=transcribe`. The browser now sends 16 kHz mono WAV. |
| TTS | Sarvam payload used `language_code`. Bulbul v3 has no Assamese, Bodo, Manipuri or Nepali voice. | Field changed to `target_language_code`. Assamese voice comes from optional open-source Meta MMS-TTS (CPU) or self-hosted Parler. |
| Telephony look | CALL/END keys, "Calling…", ring-back and DTMF tones imply a phone call that does not exist. | **Misleading. Replaced** with one big "Tap to speak" button. The colours and LCD-style answer card stay. |
| Care slip | `handoff.py`, `/api/slips`, consent state, slip tab. | **Not requested. Removed.** |
| Network tab | Language table, channel list, unsupported-language counter. | **Not requested. Removed.** Language support now shows in the language picker itself. |
| Read-back / keypad state machine | IVR-style CONFIRMING/CONSENT states. | **Removed.** The transcript is shown on screen with a "Not what I said? Speak again" action. |
| Hospital data | `facilities.csv` held hospitals with coordinates from memory and "emergency expected" guessed from the facility type. | **Not documented data. Removed.** Replaced by OpenStreetMap (ODbL, documented) and an optional verified CSV your team fills in. |
| Emergency rules | Independent rules in English, Hindi, Assamese, Bengali and Nepali run before the LLM. | **Kept and extended.** The LLM also returns a triage tag as a second net, never the only one. |
| Keys | `.env` holds Groq and Sarvam keys and is gitignored. This build container cannot reach Groq, Sarvam or OpenStreetMap (network policy). | Live calls are verified with `scripts/verify_live.py` on a machine with internet. |

## Language reality (from provider documentation, October 2026)

| Language | Speech to text | Translation | LLM | Speech output | Plan |
|---|---|---|---|---|---|
| Hindi | Sarvam Saaras | Sarvam Translate | via English pivot | Sarvam Bulbul v3 | **First end-to-end target** |
| English | Sarvam / Groq Whisper | n/a | direct | Sarvam Bulbul v3 | End-to-end |
| Bengali | Sarvam | Sarvam | pivot | Bulbul v3 | End-to-end |
| Assamese | Sarvam | Sarvam | pivot | **not in Bulbul**; MMS-TTS (local, optional) or Parler | Voice in; voice out only if TTS configured |
| Nepali | Sarvam | Sarvam | pivot | not in Bulbul; MMS or Parler | Same as Assamese |
| Bodo | Sarvam | Sarvam | pivot | Parler only | Voice in, text answer |
| Manipuri | Sarvam | Sarvam (script must be checked with native speakers) | pivot | Parler only | Voice in, text answer, script flagged |
| Khasi, Garo, Mizo, Kokborok, Nagamese | none | none reliable | n/a | none | **Not offered.** Shown as unavailable, with the reason |

A language is shown as "verified" only after `scripts/verify_live.py` has passed for it with real keys.

## Order of work
1. P0: remove scripted answers, slip and network; fix the LLM model and prompt; honest provider errors.
2. P0: sequential voice pipeline (WAV upload → STT → triage → LLM → dose check → translate → TTS) and a simple UI.
3. P0: independent emergency layer first in the pipeline, with an instant emergency button.
4. P1: OpenStreetMap facility finder with SQLite cache, verified-CSV support, honest labels.
5. P1: language capability matrix plus the live verification script; tests; docs.
