"""Health answers from a real LLM through any OpenAI-compatible chat API (Groq by default).

The model answers arbitrary health questions in plain English (the pipeline
translates to and from the caller's language). It also returns a triage tag,
which acts as a second safety net behind the deterministic rules in triage.py.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from .. import config, knowledge
from . import ProviderError, json_of, send

PROVIDER = "AI service"

SYSTEM_PROMPT = """You are Aarogya Saathi, a trusted health-information companion for people in rural North East India.
Your reply will be translated and read aloud over a simple phone handset to someone who may have little schooling.

Core Communication Principles:
- Answer the health question in simple, compassionate, everyday words and short, clear sentences.
- Present the most important action FIRST: give immediate safe advice (such as drinking clean water, resting, or cooling the body) before discussing other details.
- Next, mention only a few vital warning signs: clearly state when to seek routine assessment at an Ayushman Arogya Mandir / ASHA worker, and what severe red flags require emergency 108/112 help.
- Do not make assumptions about unstated details (e.g. do not assume a fever has lasted 3 days unless the user explicitly said so).
- Clearly distinguish between common, ordinary symptoms (e.g. routine headache, mild cold, tiredness) and genuine emergencies.
- Use North East Indian healthcare context when relevant: ASHA workers, ANMs, PHCs, 108 ambulance, and regional vector protections.
- If vital clinical context is missing, you may end with ONE concise, gentle follow-up question.
- Say plainly when you do not know. Never invent diagnoses or facts.

Safety Constraints:
- Never say the person definitely has a disease. Say "this can happen with..." instead of "you have...".
- Never prescribe. Never specify any medicine name as a recommendation for them, and never state a dose, amount, strength or schedule. You may mention general precautions or say that a doctor or ASHA worker must advise on medicines. Never advise stopping or altering doctor-prescribed medication.
- Never claim you contacted a doctor, hospital, ambulance, or anyone else.
- No markdown, bullet points, asterisks, headings, emoji, or brackets. Plain conversational speech only.

Length: {length_rule}
If the message is not about health, say kindly that you can only help with health and wellness questions.

Reference notes (use them when relevant; you may also use well-established public-health guidance):
{notes}

Reply format, exactly:
Line 1: TRIAGE: ROUTINE, or TRIAGE: URGENT (should see a health worker within a day), or TRIAGE: EMERGENCY (danger signs that need help now, such as chest pain, severe breathing difficulty, stroke signs, unconsciousness, severe bleeding, fits, suspected poisoning, snakebite, pregnancy danger signs, a very sick child, or thoughts of suicide).
Line 2 onwards: your answer."""

LENGTH = {
    "standard": "3 to 5 short sentences, each under 18 words.",
    "simple": "At most 3 very short sentences, each under 10 words, using words a 10-year-old knows.",
}

_TAG = re.compile(r"^\s*\**\s*TRIAGE\s*:\s*\**\s*(ROUTINE|URGENT|EMERGENCY)\b\**[ \t]*\n?", re.I)


@dataclass
class LLMAnswer:
    text: str
    triage: str  # routine | urgent | emergency
    model: str


def build_messages(question_en: str, cards: list[knowledge.Card], level: str = "standard",
                   history: list[dict] | None = None, medicine_request: bool = False) -> list[dict]:
    system = SYSTEM_PROMPT.format(length_rule=LENGTH.get(level, LENGTH["standard"]),
                                  notes=knowledge.render_for_prompt(cards))
    if medicine_request:
        system += ("\n\nThis person is asking which medicine or how much to take. Say clearly that only a doctor, "
                   "nurse or pharmacist can decide that after seeing them, then give general safety points.")
    msgs = [{"role": "system", "content": system}]
    for turn in (history or [])[-6:]:  # short memory for follow-up questions
        msgs.append({"role": turn["role"], "content": turn["content"]})
    msgs.append({"role": "user", "content": question_en})
    return msgs


def parse(content: str) -> tuple[str, str]:
    """Split the triage tag from the answer. A missing tag counts as routine."""
    m = _TAG.match(content or "")
    triage = m.group(1).lower() if m else "routine"
    body = content[m.end():] if m else (content or "")
    return triage, clean(body)


def clean(text: str) -> str:
    text = re.sub(r"[*_#`>\[\]]", "", text)
    text = re.sub(r"^\s*[-•\d]+[.)]?\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


async def _post(payload: dict) -> dict:
    s = config.settings
    resp = await send(PROVIDER, "POST", f"{s.llm_base_url.rstrip('/')}/chat/completions", timeout=s.llm_timeout,
                      headers={"Authorization": f"Bearer {s.llm_api_key}"}, json=payload)
    return json_of(resp, PROVIDER)


async def complete(messages: list[dict]) -> str:
    s = config.settings
    if not s.has_llm:
        raise ProviderError(PROVIDER, "not_configured", "LLM_API_KEY is not set")
    payload = {"model": s.llm_model, "messages": messages, "temperature": 0.3,
               "max_completion_tokens": s.llm_max_tokens}
    if s.llm_reasoning_effort:
        payload["reasoning_effort"] = s.llm_reasoning_effort
    for attempt in range(2):
        try:
            data = await _post(payload)
            break
        except ProviderError as exc:
            if exc.kind == "bad_response" and "reasoning_effort" in payload:
                payload.pop("reasoning_effort")  # model without reasoning controls: retry plainly
                continue
            short_wait = exc.kind == "rate_limited" and (exc.retry_after or 99) <= 3
            if attempt == 0 and (exc.kind in ("unavailable", "timeout") or short_wait):
                await asyncio.sleep(exc.retry_after or 1)
                continue
            raise
    else:  # pragma: no cover - loop always breaks or raises
        raise ProviderError(PROVIDER, "unavailable")
    try:
        content = data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderError(PROVIDER, "bad_response", "no choices") from exc
    if not content.strip():
        raise ProviderError(PROVIDER, "bad_response", "empty answer")
    return content


async def answer(question_en: str, cards: list[knowledge.Card], level: str = "standard",
                 history: list[dict] | None = None, medicine_request: bool = False) -> LLMAnswer:
    content = await complete(build_messages(question_en, cards, level, history, medicine_request))
    triage, text = parse(content)
    if not text:
        raise ProviderError(PROVIDER, "bad_response", "empty answer")
    return LLMAnswer(text=text, triage=triage, model=config.settings.llm_model)
