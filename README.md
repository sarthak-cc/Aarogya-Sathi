# Aarogya Saathi

**A voice health companion for rural North East India: answers in your language, and points you to real care when it matters.**
Built for CodeWar 8.0, problem statement 2: Multilingual AI Health Companion for Rural and Remote NER.

Open the website on any phone or laptop, press **CALL**, pick a language and speak. Aarogya Saathi
answers everyday health questions in simple words. If the caller describes a possible emergency,
such as chest pain, a snakebite or a pregnancy danger sign, it switches immediately: emergency
guidance first, then it asks where they are and lists the nearest suitable hospitals with 108/112.
It gives general information only. It never diagnoses, never prescribes, and never claims to have
called anyone.

## Three core features

| Feature | How it works | Why judges should care |
|---|---|---|
| **1. Multilingual health companion** | Voice in, voice out. Read-back confirmation ("I heard: fever since yesterday. Press 1 if right"). Answers grounded on 14 vetted health cards. Press 5 for simpler words. | Wrong speech recognition never turns into confident advice. Different literacy levels are handled. |
| **2. Emergency detection and assistance** | A rule-based safety engine runs **before** any AI, in English, Hindi, Assamese and Bengali. Emergencies skip the AI, speak a fixed 112 script and a first-aid line, then ask for the location (GPS, spoken or typed place, or a PIN typed on the keypad). | Guidance never waits for a database query or an LLM. |
| **3. Healthcare navigation and medicine safety** | Facility search over a seeded hospital database (all eight NE states, dense around Guwahati) plus free OpenStreetMap. Prescription requests are refused safely, and any AI answer that states a dose is blocked. | Clear referrals to a clinician instead of pretending to be one. |

## Honest scope

| Channel | Status |
|---|---|
| Web voice (browser microphone over HTTPS, phone or laptop) | **Live** |
| Keypad phone line (IVR) | **Planned.** Needs a paid telephony provider such as Twilio or Exotel, plus an Indian number with KYC. That isn't free, so it is out of the hackathon build. The pipeline is channel-agnostic, so a phone adapter plugs into the same backend later. |
| Automatically notifying a hospital or ambulance | **Not built.** Needs an authorised integration with confirmation. Today the caller gets contact details and is told nobody has been contacted. |

The Network tab in the app shows the same table, plus which languages really have voice support right now.

## Quick start (local)

```bash
cd Aarogya-Sathi
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env               # add GROQ + SARVAM keys for live AI (optional)
cd backend
uvicorn app.main:app --reload
```

Open http://localhost:8000 and press **CALL**. API docs are at http://localhost:8000/docs.
Run the tests from `backend/` with `python -m pytest -q` (63 tests).
Without keys, everything runs in labelled demo mode, including emergencies, facility search and the care slip.

## Deploy for free (judges open a link on their phones)

The microphone and GPS only work over **HTTPS**, and every host below gives you HTTPS automatically.

**Render (recommended):** push this repo to GitHub, then on render.com choose *New → Blueprint* and pick
the repo. `render.yaml` creates a free Docker web service. Add `LLM_API_KEY`, `GROQ_API_KEY` and
`SARVAM_API_KEY` as secret environment variables in the Render dashboard. Free instances sleep
after about 15 minutes idle, so open the link a minute before judging.

**Hugging Face Spaces / Koyeb / Railway:** create a Docker app from this repo. The `Dockerfile` reads
`$PORT` (use 7860 on Hugging Face). Add the same secrets.

Never commit `.env`. It is already in `.gitignore` and `.dockerignore`.

## Demo script for judges (about 3 minutes, from Assam Engineering College)

1. On a phone, open the link, press **CALL**, then **1** for Assamese.
2. Tap **Fever since yesterday**: grounded answer, its card source, and a latency waterfall in the Call log. Press **5** for simpler words.
3. Tap **Heart attack signs (emergency)**: the screen flashes amber, the AI is skipped, and the 112 script plus "make the person sit and rest" plays straight away.
4. Press **Hospital** (right softkey) then **GPS**, or tap the demo location **Assam Engineering College, Jalukbari**. The nearest listed hospitals appear with distances, 108/112, map links and "not yet verified" labels. Key **1** opens the first one.
5. Press **4** again and type **786001** on the keypad: that's how a caller without GPS works (Dibrugarh, Assam Medical College).
6. Tap **Asks for a medicine dose**: a safe refusal plus general precautions. With live AI, a draft that names a dose is blocked, and the Call log says so.
7. Press **9**, then **1**. The **Care slip** tab shows what the ASHA worker sees.
8. Open **Network**: web voice is live, the phone line is planned (paid provider), hospital alerts aren't built. Then the honest language gaps for Khasi, Garo, Mizo and Kokborok.

## Modes

| Mode | What you need | What works |
|---|---|---|
| **Demo** (default) | Nothing | Full flow. Six scripted scenarios in English, Hindi and Assamese, labelled "Demo answer". Safety check, facility search, slip and simpler words all work. |
| **Live AI** | `LLM_API_KEY` (Groq, free tier) + `SARVAM_API_KEY` | Any question in Assamese, Bodo, Manipuri, Nepali, Bengali, Hindi or English, answered from vetted cards. Hindi, Bengali and English voice. |
| **Live voice for NER languages** | `PARLER_TTS_URL` | Assamese, Bodo, Manipuri and Nepali spoken answers via self-hosted Indic Parler-TTS (see below). |
| **Live map data** | Network access (`OSM_ENABLED=true`, default) | OpenStreetMap hospitals near the caller, shown alongside the seed list. |

### Running Parler-TTS on a free GPU
In a Kaggle or Colab notebook with a T4 GPU:
```bash
pip install git+https://github.com/huggingface/parler-tts.git fastapi uvicorn soundfile pyngrok
python tts_server/parler_server.py   # then: ngrok http 8001
```
Put the ngrok https URL in `PARLER_TTS_URL`. Then pre-render the fixed prompts so menus play instantly:
`cd backend && python ../scripts/prerender_prompts.py`.

## Before showing real users: verify the hospital list

`backend/app/data/facilities.csv` lists public medical colleges and district hospitals in every NE state,
plus a denser Guwahati set (Jalukbari, Maligaon, Boragaon, Dispur and around). Coordinates are approximate
and **no phone numbers are filled in**, because a wrong emergency number is worse than none. To verify a row,
phone the facility, confirm its 24×7 emergency service, then fill in `phone` and `verified_on`
(for example `2026-10-12`). The app then shows it as verified, with that date.

## Project layout
```
backend/app/
  main.py            REST API + serves the web phone
  pipeline.py        STT → read-back → translate → triage → cards → LLM → dose filter → translate → TTS
  triage.py          multilingual red-flag rules (runs before any AI)
  facilities.py      hospital search: SQLite seed list + OpenStreetMap, PIN/town/landmark resolver
  medicine.py        prescription-request detector and dose filter
  knowledge.py       vetted health cards + retriever
  languages.py       capability registry
  prompts.py         fixed prompts (Hindi/Assamese hand-written)
  handoff.py         consent-gated care slip
  sessions.py        state machine, in-memory sessions
  demo.py            offline scenarios
  providers/         sarvam / groq / parler adapters
  data/              facilities.csv, places.csv
backend/tests/       63 tests (call flow, live mocks, triage, navigation, medicine safety)
frontend/            retro keypad phone (HTML/CSS/vanilla JS), installable as a PWA
tts_server/          Indic Parler-TTS GPU server
Dockerfile, render.yaml   free deployment
docs/                architecture.md, DESIGN.md
```

## Known limitations (say these to the judges)
- Health cards, triage rules, the hospital list and the Hindi/Assamese text are **not clinically validated or verified**. They need review by a doctor, native speakers, and a phone check of each facility.
- No voice support yet for Khasi, Garo, Mizo, Kokborok or Nagamese, because no reliable public models exist.
- Distances are straight-line. Road distance in the hills can be much longer.
- Sessions are in memory, so a server restart ends calls. Use Redis or Postgres for production.
- Provider language coverage was checked against public docs in October 2026.

## Sources
- Sarvam AI models and languages: https://docs.sarvam.ai/api/getting-started/models
- AI4Bharat Indic Parler-TTS: https://huggingface.co/ai4bharat/indic-parler-tts
- Groq models: https://console.groq.com/docs/models
- OpenStreetMap Nominatim and Overpass usage policies: https://operations.osmfoundation.org/policies/
