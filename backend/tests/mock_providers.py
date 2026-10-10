"""MOCK provider server for browser end-to-end tests without real keys or internet.

It answers with the same JSON shapes as Groq, Sarvam, Overpass and Nominatim. Every
answer is prefixed "(mock)" so it can never be mistaken for real output.
NOT used by the app itself. Real checks: scripts/verify_live.py.

    python tests/mock_providers.py 8099
    LLM_BASE_URL=http://127.0.0.1:8099/openai/v1 SARVAM_BASE_URL=http://127.0.0.1:8099 \
    OVERPASS_URL=http://127.0.0.1:8099/api/interpreter NOMINATIM_URL=http://127.0.0.1:8099/search \
    LLM_API_KEY=mock SARVAM_API_KEY=mock uvicorn app.main:app
"""
import base64
import io
import math
import struct
import sys
import wave

from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()
TRANSCRIPT = {"hi-IN": "मुझे दो दिन से खाँसी है", "en-IN": "I have had a cough for two days", "as-IN": "মোৰ দুদিন ধৰি কাহ হৈছে"}


def tone_wav(seconds=0.4, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(seconds * rate))))
    return buf.getvalue()


@app.post("/openai/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    q = body["messages"][-1]["content"]
    if isinstance(q, list):  # vision request (text + image_url parts)
        import json as _json
        return {"choices": [{"message": {"role": "assistant", "content": _json.dumps({
            "observation": "(mock) The photo shows a small red patch on the skin.",
            "possible_explanations": ["(mock) This can happen with an insect bite."],
            "follow_up_questions": ["(mock) How long has it been there?"],
            "recommended_next_steps": ["(mock) Keep it clean and dry.", "(mock) See an ASHA worker if it spreads."],
            "urgency": "see_health_worker", "image_quality": "ok"})}}]}
    tag = "EMERGENCY" if "lips are grey" in q else "ROUTINE"
    return {"choices": [{"message": {"role": "assistant", "content": f"TRIAGE: {tag}\n(mock) Answer about: {q[:60]}. See a health worker if it gets worse."}}]}


@app.post("/translate")
async def translate(req: Request):
    b = await req.json()
    return {"translated_text": f"(mock {b['target_language_code']}) {b['input']}"}


@app.post("/speech-to-text")
async def stt(req: Request):
    form = await req.form()
    return {"transcript": TRANSCRIPT.get(form.get("language_code"), "(mock) question"), "language_code": form.get("language_code")}


@app.post("/text-to-speech")
async def tts(req: Request):
    return {"audios": [base64.b64encode(tone_wav()).decode()]}


@app.get("/search")
async def nominatim(q: str = "", postalcode: str = ""):
    return [{"lat": "26.1430", "lon": "91.6600", "display_name": f"(mock) {q or postalcode}, Guwahati, Assam"}]


@app.post("/api/interpreter")
async def overpass():
    return {"elements": [
        {"type": "node", "id": 101, "lat": 26.1555, "lon": 91.7650,
         "tags": {"amenity": "hospital", "name": "(mock) Hospital A", "emergency": "yes", "phone": "+91 00000 00000"}},
        {"type": "node", "id": 102, "lat": 26.1500, "lon": 91.6650, "tags": {"amenity": "clinic", "name": "(mock) Clinic B"}},
    ]}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8099, log_level="warning")
