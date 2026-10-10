"""Photo analysis through a Groq vision-capable chat model (default qwen/qwen3.8-27b).

Separate from the text LLM in llm.py. The image is validated, re-encoded as a
small JPEG (which also drops EXIF metadata such as GPS location) and sent once
as a base64 data URL in an OpenAI-style `image_url` content part, as documented
by Groq. Nothing is stored. The model writes in English; the pipeline translates.
"""
from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass, field

from .. import config
from . import ProviderError, json_of, send

PROVIDER = "Groq vision"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIDE = 1280  # px; plenty for a skin or wound photo, keeps the request well under Groq's 4 MB base64 cap
URGENCY = ("routine", "see_health_worker", "urgent", "emergency")

SYSTEM_PROMPT = """You are the photo helper of Aarogya Saathi, a health-information companion for people in rural North East India.
Someone has sent a photo (often skin, a wound, a rash, a bite, a burn, eyes, nails, or a medicine strip).
Your words will be translated and read aloud to a person who may have little schooling. Keep the entire response very short (~25-45 words).

Core structure:
- What I see: exactly one short sentence describing only visible features (e.g. "The photo shows a small red patch on the skin.").
- What to do: one or two simple practical actions (e.g. "Keep it clean and dry.").
- Warning: clear signs that require urgent help when relevant (e.g. "If it spreads or you develop a fever, contact an ASHA worker.").
- Question: at most one short follow-up question, only if useful (e.g. "How long has it been there?").

Rules:
- Describe only what is visible. Say "the photo shows" or "it looks like", never "you have".
- Never give a diagnosis. In possible_explanations, provide at most 2 brief possibilities as "this can happen with...".
- If the photo is blurry, dark, too far, or unclear, say so plainly in 1 short sentence and set image_quality to "insufficient".
- A normal-looking photo never proves someone is healthy.
- Never prescribe and never name a medicine dose, amount, strength, or schedule.
- If there are emergency signs (deep wound, heavy bleeding, large burn, snakebite, severe swelling, eye injury), set urgency to "emergency" or "urgent" and advise getting emergency help immediately.
- Use simple words and short sentences. No markdown, no bullet points.

Reply with ONLY a JSON object, no other text:
{"observation": "one short sentence on what is visible",
 "possible_explanations": ["..."],
 "follow_up_questions": ["..."],
 "recommended_next_steps": ["1-2 simple actions with warning signs if relevant"],
 "urgency": "routine" | "see_health_worker" | "urgent" | "emergency",
 "image_quality": "ok" | "insufficient"}"""


@dataclass
class PreparedImage:
    data_url: str
    width: int
    height: int
    bytes_sent: int


@dataclass
class VisionResult:
    observation: str
    possible_explanations: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    recommended_next_steps: list[str] = field(default_factory=list)
    urgency: str = "see_health_worker"
    image_quality: str = "ok"
    model: str = ""


class InvalidImage(ValueError):
    """The upload is not a usable image (wrong type, empty, corrupt, too large)."""


def prepare(data: bytes, content_type: str) -> PreparedImage:
    """Validate and shrink the image. Raises InvalidImage with a user-facing reason."""
    max_bytes = int(config.settings.vision_max_upload_mb * 1024 * 1024)
    if not data:
        raise InvalidImage("The photo is empty. Please take or choose the photo again.")
    if len(data) > max_bytes:
        raise InvalidImage(f"The photo is too large. Please use one under {config.settings.vision_max_upload_mb:g} MB.")
    if (content_type or "").split(";")[0].strip().lower() not in ALLOWED_TYPES:
        raise InvalidImage("Please send a JPEG, PNG or WebP photo.")
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - listed in requirements.txt
        raise ProviderError(PROVIDER, "not_configured", "pip install pillow") from exc
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in ("JPEG", "PNG", "WEBP"):
                raise InvalidImage("Please send a JPEG, PNG or WebP photo.")
            img = ImageOps.exif_transpose(img)  # keep the photo upright, then drop all metadata
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            rgb = img.convert("RGB")
            out = io.BytesIO()
            rgb.save(out, format="JPEG", quality=85, optimize=True)  # no exif= argument: metadata is discarded
            w, h = rgb.size
    except InvalidImage:
        raise
    except Exception as exc:  # PIL raises many types for corrupt files
        raise InvalidImage("The photo could not be read. Please take it again.") from exc
    jpeg = out.getvalue()
    return PreparedImage("data:image/jpeg;base64," + base64.b64encode(jpeg).decode(), w, h, len(jpeg))


def build_messages(image: PreparedImage, note: str = "") -> list[dict]:
    text = "Please look at this photo and reply with the JSON object."
    if note:
        text += f" The person says: \"{note[:300]}\""
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [{"type": "text", "text": text},
                                         {"type": "image_url", "image_url": {"url": image.data_url}}]}]


_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def _strings(value, limit: int) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:limit]


def parse(content: str, model: str) -> VisionResult:
    """Parse the model's JSON. A reply we cannot read is an error, never a guessed result."""
    text = _THINK.sub("", content or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ProviderError(PROVIDER, "bad_response", "no JSON in reply")
    try:
        data = json.loads(m.group(0))
    except ValueError as exc:
        raise ProviderError(PROVIDER, "bad_response", "invalid JSON") from exc
    observation = str(data.get("observation") or "").strip()
    if not observation:
        raise ProviderError(PROVIDER, "bad_response", "empty observation")
    urgency = str(data.get("urgency") or "").strip().lower()
    quality = str(data.get("image_quality") or "ok").strip().lower()
    return VisionResult(
        observation=observation,
        possible_explanations=_strings(data.get("possible_explanations"), 3),
        follow_up_questions=_strings(data.get("follow_up_questions"), 2),
        recommended_next_steps=_strings(data.get("recommended_next_steps"), 4),
        urgency=urgency if urgency in URGENCY else "see_health_worker",  # unknown label: lean cautious
        image_quality="insufficient" if quality == "insufficient" else "ok",
        model=model,
    )


async def analyze(image: PreparedImage, note: str = "") -> VisionResult:
    s = config.settings
    key = s.vision_api_key
    if not key:
        raise ProviderError(PROVIDER, "not_configured", "GROQ_API_KEY is not set")
    payload: dict = {"model": s.vision_model, "messages": build_messages(image, note),
                     "temperature": 0.2, "max_completion_tokens": 700}
    if s.vision_reasoning_effort:
        payload["reasoning_effort"] = s.vision_reasoning_effort
    url = f"{s.vision_base_url.rstrip('/')}/chat/completions"
    for _ in range(2):
        try:
            resp = await send(PROVIDER, "POST", url, timeout=s.vision_timeout,
                              headers={"Authorization": f"Bearer {key}"}, json=payload)
            break
        except ProviderError as exc:
            if exc.kind == "bad_response" and "reasoning_effort" in payload:
                payload.pop("reasoning_effort")  # parameter rejected: retry once, same model
                continue
            if exc.detail == "HTTP 404":
                raise ProviderError(PROVIDER, "model_unavailable", s.vision_model) from exc
            raise
    else:  # pragma: no cover
        raise ProviderError(PROVIDER, "unavailable")
    data = json_of(resp, PROVIDER)
    try:
        content = data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError(PROVIDER, "bad_response", "no choices") from exc
    return parse(content, s.vision_model)
