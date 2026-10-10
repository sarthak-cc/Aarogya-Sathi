"""REAL Groq vision check (not mocked). Needs GROQ_API_KEY and internet.

    cd backend && python ../scripts/verify_vision_live.py                 # synthetic test image, en + hi + as
    cd backend && python ../scripts/verify_vision_live.py photo.jpg hi-IN

Prints the parsed result for each language. It does not store the image anywhere.
Exit code 0 only if every analysis succeeded.
"""
from __future__ import annotations

import asyncio
import io
import json
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import config, photo  # noqa: E402


def synthetic() -> tuple[bytes, str]:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (640, 480), (150, 110, 80))
    d = ImageDraw.Draw(img)
    d.ellipse((220, 120, 420, 380), fill=(205, 160, 130))  # a palm-like shape
    d.ellipse((300, 230, 340, 262), fill=(185, 70, 60))     # a red patch
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue(), "image/jpeg"


async def main(args: list[str]) -> int:
    config.reload_settings()
    s = config.settings
    print(f"Vision model: {s.vision_model}  key set: {bool(s.vision_api_key)}  base: {s.vision_base_url}")
    path = next((a for a in args if Path(a).is_file()), None)
    langs = [a for a in args if a != path] or ["en-IN", "hi-IN", "as-IN"]
    data, ctype = (Path(path).read_bytes(), mimetypes.guess_type(path)[0] or "image/jpeg") if path else synthetic()
    ok = True
    for lang in langs:
        r = await photo.analyze(data, ctype, lang)
        print(f"\n== {lang}: {'OK' if r['ok'] else 'FAILED'}  ({r['timings_ms']})")
        if r["ok"]:
            print(json.dumps(r["vision"], ensure_ascii=False, indent=1))
            print("voice:", r["voice"]["provider"] or r["voice"]["note"])
        else:
            print("error:", r["error"])
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
