# Aarogya Saathi

**Your health. Your language. Your companion.**
A voice-first, multilingual AI health-information companion for rural and remote North East India.

You pick a language, tap one big button and ask a health question out loud (or type it).
Aarogya Saathi transcribes it with a real speech service, checks for emergency danger signs
**before** any AI is involved, answers routine questions with a real LLM in simple words,
translates the answer back and speaks it. For a possible emergency it gives instant fixed guidance
(call 112, plus one first-aid line) and helps find nearby hospitals from OpenStreetMap.
It gives general information only. It never diagnoses, never prescribes, never gives doses,
and never claims to have contacted anyone.

## What is real, and what has been verified

| Part | Implementation | Status |
|---|---|---|
| Answers | Groq API, `openai/gpt-oss-120b` (configurable), with conversation history | Real API integration. Tested with mocked HTTP. **Verify live** with `scripts/verify_live.py` |
| Speech to text | Sarvam Saaras v3 (`mode=transcribe`), Groq Whisper as a second option | Real integration. Browser → WAV → backend path tested end to end against a mock server |
| Translation | Sarvam Translate (`sarvam-translate:v1`), English as the pivot | Real integration |
| Voice | Sarvam Bulbul v3 (hi, bn, en). Optional local MMS-TTS or Parler for Assamese/Nepali | Real integration. Assamese voice needs the optional extra |
| Emergency safety | Deterministic multilingual rules before the LLM, plus the LLM's own triage tag as a second net | Tested (en, hi, as, bn), including with the AI and translation down |
| Nearby facilities | OpenStreetMap (Overpass + Nominatim), SQLite cache, optional team-verified CSV | Real integration. Tested with mocked HTTP |

This code was built in a container that could not reach Groq, Sarvam or OpenStreetMap. Every
provider call is therefore tested against mocks, not live. **Nothing is marked "verified" until you run
`scripts/verify_live.py` with real keys.** It writes `docs/VERIFICATION.md` and the "Verified live" badges
in the language picker.

### Languages

| Language | Speak | Answer | Hear the answer |
|---|---|---|---|
| Hindi | Sarvam | LLM via translation | Sarvam Bulbul: **first end-to-end target** |
| English | Sarvam / Whisper | LLM | Sarvam Bulbul |
| Bengali | Sarvam / Whisper | LLM via translation | Sarvam Bulbul |
| Assamese | Sarvam | LLM via translation | Not in Bulbul. Text only, unless MMS-TTS or Parler is set up |
| Nepali | Sarvam / Whisper | LLM via translation | Same as Assamese |
| Bodo | Sarvam | LLM via translation | Parler server only |
| Manipuri (Meitei) | Sarvam | LLM via translation (**script, Bengali vs Meitei Mayek, not verified**) | Parler server only |
| Khasi, Garo, Mizo, Kokborok, Nagamese | – | – | – **Not offered.** No reliable public speech or translation service. The app lists them as unavailable, with the reason |

Native speakers still need to review answer quality in every language. Machine checks can't judge it.

## Camera prototype (photo check)
Press **6** on the handset to flip it around: the rear camera previews, a simulated flash lights the scene, and one
confirmed photo is analyzed by Groq vision (`qwen/qwen3.8-27b`) and explained, cautiously, in the selected language with
voice. Photos are never stored. Details, API and tests: [`docs/CAMERA.md`](docs/CAMERA.md).

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                   # then put your keys in .env
cd backend
uvicorn app.main:app --reload
```

Open http://localhost:8000. The microphone and location also work on `localhost`. Anywhere else they need HTTPS.

Keys (all have free starting tiers; check the current limits):
- `LLM_API_KEY`: Groq, https://console.groq.com/keys. Required for answers.
- `SARVAM_API_KEY`: https://dashboard.sarvam.ai. Required for any language other than English, and for voice.

Without keys the app still loads. It shows exactly which key is missing and offers no language it can't serve.

### Check the real providers
```bash
cd backend
python ../scripts/verify_live.py                 # Hindi, English, Assamese
python ../scripts/verify_live.py bn-IN ne-IN     # others
```
For each language it runs a question that isn't in any dataset through the real pipeline. It also checks
an emergency phrase, a real voice → real speech-recognition round trip, and a real OpenStreetMap
search near Jalukbari, Guwahati.

### Optional: Assamese / Nepali voice
```bash
pip install -r requirements-tts.txt     # Meta MMS-TTS on CPU, CC-BY-NC 4.0 (non-commercial)
# .env:  MMS_TTS_LANGS=as-IN,ne-IN
```
Or run `tts_server/parler_server.py` on a free Kaggle/Colab GPU and set `PARLER_TTS_URL`.

### Optional: offline facility data
```bash
cd backend && python ../scripts/import_osm_facilities.py 26.14 91.66 40000   # Guwahati area
```
Facilities your team has checked by phone go in `backend/app/data/verified_facilities.csv`, with a `verified_on` date.

## Tests
```bash
cd backend && python -m pytest -q
```
There are 57 tests. All provider calls in them are **mocked** (no keys, no network). They cover: arbitrary
questions reaching the LLM, history for follow-ups, the translation pivot and its failure, missing keys,
bad keys, rate limits, outages, malformed replies, speech upload and its validation, honest
language capabilities, emergencies in four languages (including with the AI down), the AI backup triage,
dose removal, and facility search, caching and labels.

`backend/tests/mock_providers.py` is a mock server with the same API shapes. Use it to drive the full browser
flow without keys (every mock answer starts with "(mock)").

## Deploy (free tier)
`render.yaml` and the `Dockerfile` deploy one small service on Render's free plan. Add the keys as secret
environment variables in the dashboard, never in the repo. Free instances sleep after about 15 minutes idle.

## Project layout
```
backend/app/
  main.py          API: conversations, speech, emergency, facilities, audio
  pipeline.py      STT → translate → safety rules → LLM → dose filter → translate → TTS
  triage.py        multilingual emergency rules (run before any AI)
  prompts.py       the only fixed texts: emergency, crisis, first aid, location request
  medicine.py      prescription-request detection, dose removal
  knowledge.py     reference notes added to the LLM prompt (NE-specific topics)
  languages.py     capability matrix (documented support + configuration + live verification)
  facilities.py    OpenStreetMap search, SQLite cache, verified CSV
  providers/       groq (llm.py), sarvam/whisper (stt.py), sarvam (translate.py), bulbul/mms/parler (tts.py)
frontend/          one-page web app (HTML/CSS/vanilla JS), installable on phones
scripts/           verify_live.py, import_osm_facilities.py
docs/              AUDIT.md (what changed and why), architecture.md
```

## Known limitations
- Health guidance, emergency rules and the hand-written Hindi/Assamese/Bengali texts need review by clinicians and native speakers.
- Free tiers are rate limited and can change. When a quota runs out, the app says so.
- OpenStreetMap coverage in rural NE India is incomplete. Phone numbers and emergency departments are listed only where mappers added them.
- No telephone (keypad-phone) access. It would need a paid telephony provider, and it isn't part of this build.
