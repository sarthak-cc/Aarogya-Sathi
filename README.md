# Aarogya Saathi

**A voice health-information line for rural North East India that works on any phone.**
Built for CodeWar 8.0, problem statement 2: Multilingual AI Health Companion for Rural and Remote NER.

A caller picks a language on the keypad, says their health concern, confirms what was heard,
and hears a short, simple answer in their own language. A rule-based safety check runs before
any AI, so emergencies get an immediate "call 112" script instead of a chat. It gives general
information only. It never diagnoses and does not replace a health worker.

## What is new compared with a plain voice chatbot

| Feature | Why it matters for the problem statement |
|---|---|
| **Read-back confirmation**: "I heard: fever since yesterday. Press 1 if right." | Speech recognition makes mistakes in noisy villages. Wrong input should never turn into confident advice. |
| **Safety triage before the LLM**: rules in English, Hindi, Assamese and Bengali, including NER-specific red flags (snakebite, pregnancy danger signs, child danger signs, self-harm). | The AI never decides whether something is an emergency. Emergencies skip the AI and add one first-aid line. |
| **Grounded answers**: the LLM may only use 14 vetted health cards (malaria, Japanese encephalitis, scrub typhus, dengue, ORS, TB and more), each with a source. | No invented medical facts and no doses. Off-topic questions get "ask your ASHA worker". |
| **Literacy dial**: press 5 to hear it again in simpler words. | Adapts to different health-literacy levels, as the PS asks. |
| **Care handoff slip** (consent-gated): a code the caller gives the ASHA worker or doctor, showing symptoms, duration, red flags and urgency. | Carries the symptoms clearly to the professional instead of replacing them. |
| **Honest language capability table** and a demand counter for unsupported languages. | Khasi, Garo, Mizo, Kokborok and Nagamese have no public voice AI yet, and the app says so. |
| **Latency waterfall** for every answer, plus pre-rendered fixed prompts. | Shows judges exactly where the time goes. |

## Quick start (Windows PowerShell)

```powershell
cd aarogya-saathi
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env        # optional: add keys for live AI
cd backend
uvicorn app.main:app --reload
```

Open http://localhost:8000 and press **Call**. API docs are at http://localhost:8000/docs.
Run the tests from `backend/` with `python -m pytest -q` (40 tests).

On macOS/Linux, use `source .venv/bin/activate` and `cp` instead.

## Modes

| Mode | What you need | What works |
|---|---|---|
| **Demo** (default) | Nothing | Full call flow. Six scripted scenarios in English, Hindi and Assamese, labelled "Demo answer". Safety check, slip and simpler words all work. Browser speech for Hindi/English where Chrome supports it. |
| **Live AI** | `LLM_API_KEY` (Groq, free) + `SARVAM_API_KEY` | Any question in Assamese, Bodo, Manipuri, Nepali, Bengali, Hindi or English, answered from vetted cards. Hindi/Bengali/English voice. |
| **Live voice for NER languages** | `PARLER_TTS_URL` | Assamese, Bodo, Manipuri and Nepali spoken answers via self-hosted Indic Parler-TTS. |
| **Real phone line** | Twilio number + `PUBLIC_BASE_URL` | Call from a basic keypad phone. |

### Running Parler-TTS on a free GPU
In a Kaggle or Colab notebook with a T4 GPU:
```bash
pip install git+https://github.com/huggingface/parler-tts.git fastapi uvicorn soundfile pyngrok
python tts_server/parler_server.py   # then: ngrok http 8001
```
Put the ngrok https URL in `PARLER_TTS_URL`. Then pre-render the fixed prompts so menus play instantly:
```powershell
cd backend; python ..\scripts\prerender_prompts.py
```

### Real phone calls (Twilio)
1. Run `ngrok http 8000` and set `PUBLIC_BASE_URL` to the https URL.
2. On your Twilio number, set the Voice webhook to `POST {PUBLIC_BASE_URL}/telephony/twilio/voice`
   and the status callback to `/telephony/twilio/status`.
3. Call the number. Keys: 1–7 choose a language, 8 means "my language is not listed".
   After an answer: 1 asks again, 2 repeats, 5 gives simpler words, 3 changes language, 9 ends with the slip offer.

An Indian inbound number needs KYC and regulatory approval from the provider. For the hackathon,
use a trial number and say so.

## Demo script (3 minutes)
1. Press Call, then 1 for Assamese. Ask **Fever since yesterday**: you get a grounded answer, its card source, and the latency breakdown.
2. Press 5 to hear it in simpler words.
3. Ask **Snakebite in the paddy field**: the emergency script runs, the AI is skipped, and the caller hears "do not cut, suck or tie".
4. Hang up with 9, then press 1. Open the **Care slip** tab: this is what the ASHA worker sees.
5. Open the **Languages** tab and point out the honest gaps for Khasi, Garo, Mizo and Kokborok.

## Project layout
```
backend/app/
  main.py            REST API + serves the frontend
  telephony.py       Twilio IVR webhooks (signature-checked, idempotent)
  pipeline.py        STT → read-back → translate → triage → cards → LLM → translate → TTS
  triage.py          multilingual red-flag rules
  knowledge.py       vetted health cards + retriever
  languages.py       capability registry
  prompts.py         fixed IVR prompts (Hindi/Assamese hand-written)
  handoff.py         consent-gated care slip
  sessions.py        state machine, in-memory sessions
  demo.py            offline scenarios
  providers/         sarvam / groq / parler adapters
backend/tests/       40 tests (demo flow, mocked live flow, triage, Twilio)
frontend/            phone simulator (HTML/CSS/vanilla JS)
tts_server/          Indic Parler-TTS GPU server
scripts/             prompt pre-rendering
docs/architecture.md
```

## Known limitations (say these to the judges)
- Health cards, triage rules and the Hindi/Assamese text are **not clinically validated**. They need review by a doctor and native speakers before real use.
- No voice support yet for Khasi, Garo, Mizo, Kokborok or Nagamese, because no reliable public models exist.
- Manipuri output script (Bengali vs Meitei Mayek) needs checking with native users.
- Sessions are in memory, so a server restart ends calls. Use Redis for production.
- Provider language coverage was checked against public docs in October 2026.

## Sources
- Sarvam AI models and languages: https://docs.sarvam.ai/api/getting-started/models
- AI4Bharat Indic Parler-TTS: https://huggingface.co/ai4bharat/indic-parler-tts
- Groq models: https://console.groq.com/docs/models
