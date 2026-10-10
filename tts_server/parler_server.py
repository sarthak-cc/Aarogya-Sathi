"""Self-hosted AI4Bharat Indic Parler-TTS server (Assamese, Bodo, Manipuri, Nepali...).

Run on a free GPU (Kaggle / Colab T4):
    pip install git+https://github.com/huggingface/parler-tts.git fastapi uvicorn soundfile pyngrok
    python parler_server.py            # serves on :8001
    ngrok http 8001                    # put the https URL in PARLER_TTS_URL

POST /tts  {"text": "...", "language": "as-IN"}  ->  audio/wav
Model card: https://huggingface.co/ai4bharat/indic-parler-tts (Apache-2.0).
Speaker names below are taken from the model card's recommendations; adjust after listening.
"""
import io

import soundfile as sf
import torch
from fastapi import FastAPI
from fastapi.responses import Response
from parler_tts import ParlerTTSForConditionalGeneration
from pydantic import BaseModel
from transformers import AutoTokenizer

MODEL_ID = "ai4bharat/indic-parler-tts"
device = "cuda:0" if torch.cuda.is_available() else "cpu"
model = ParlerTTSForConditionalGeneration.from_pretrained(MODEL_ID).to(device)
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
description_tokenizer = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)

SPEAKER = {"as-IN": "Sita", "brx-IN": "Maya", "mni-IN": "Laishram", "ne-IN": "Amrita",
           "bn-IN": "Aditi", "hi-IN": "Divya", "en-IN": "Mary"}

app = FastAPI(title="Indic Parler-TTS")


class TTSIn(BaseModel):
    text: str
    language: str = "as-IN"


@app.post("/tts")
def tts(body: TTSIn):
    speaker = SPEAKER.get(body.language, "")
    description = (f"{speaker} speaks slowly and clearly in a warm, calm voice. "
                   "The recording is very high quality with no background noise.").strip()
    desc = description_tokenizer(description, return_tensors="pt").to(device)
    prompt = tokenizer(body.text, return_tensors="pt").to(device)
    with torch.inference_mode():
        audio = model.generate(input_ids=desc.input_ids, attention_mask=desc.attention_mask,
                               prompt_input_ids=prompt.input_ids, prompt_attention_mask=prompt.attention_mask)
    buf = io.BytesIO()
    sf.write(buf, audio.cpu().numpy().squeeze(), model.config.sampling_rate, format="WAV")
    return Response(buf.getvalue(), media_type="audio/wav")


@app.get("/health")
def health():
    return {"ok": True, "device": device}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
