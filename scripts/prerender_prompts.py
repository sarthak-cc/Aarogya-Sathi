"""Pre-render every fixed IVR prompt to audio for each voice-ready language.

Fixed prompts are most of what a caller hears; rendering them once removes
TTS latency from those turns entirely and keeps the demo working offline.

    cd backend && python ../scripts/prerender_prompts.py
Outputs frontend/prompts/<lang>/<key>.wav plus an index.json.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import languages, prompts  # noqa: E402
from app.providers import ProviderError, ProviderUnavailable, tts  # noqa: E402

OUT = ROOT / "frontend" / "prompts"


async def main():
    index = {}
    for lang in languages.REGISTRY.values():
        if not lang.keypad:
            continue
        for key in prompts.EN:
            if key == "readback":
                continue  # contains the caller's words, rendered live
            p = await prompts.get(key, lang.code)
            if p["lang"] != lang.code:
                continue
            try:
                audio, provider = await tts.synthesize(p["text"], lang.code)
            except (ProviderUnavailable, ProviderError) as exc:
                print(f"skip {lang.code}/{key}: {exc}")
                break
            path = OUT / lang.code / f"{key}.wav"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(audio)
            index.setdefault(lang.code, {})[key] = {"url": f"/static/prompts/{lang.code}/{key}.wav", "text": p["text"]}
            print(f"ok   {lang.code}/{key} via {provider}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
