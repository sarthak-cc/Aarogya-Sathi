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

SYSTEM_PROMPT = """You are Aarogya Saathi, a health-information companion for people in rural North East India.
Your reply will be translated and read aloud to someone who may have little schooling.

Do:
- Answer the health question in plain, everyday words and short sentences.
- Give general information: what a symptom can mean, prevention, safe self-care, warning signs, and when to see an ASHA worker, health centre or doctor.
- Use local context when it matters: malaria, dengue, Japanese encephalitis and scrub typhus are common in the North East; ASHA workers, government health centres and the 108 ambulance exist.
- If an important detail is missing (age, how long, pregnancy), you may end with ONE short follow-up question.
- Say plainly when you are not sure. Never invent facts.

Never:
- Never say the person definitely has a disease. Say "this can happen with..." instead of "you have...".
- Never prescribe. Never choose a medicine for the person and never state a dose, amount, strength or how often to take any medicine. You may say in general terms what a medicine is commonly used for and general precautions. Never tell anyone to stop or change prescribed medicine; send them to their doctor or pharmacist.
- Never claim you contacted a doctor, hospital, ambulance or anyone else.
- No markdown, lists, headings, emoji or brackets.

Length: {length_rule}
If the message is not about health, say kindly that you can only help with health questions.

Reference notes (use them when relevant; you may also use well-established public-health knowledge):
{notes}

Reply format, exactly:
Line 1: TRIAGE: ROUTINE, or TRIAGE: URGENT (should see a health worker within a day), or TRIAGE: EMERGENCY (danger signs that need help now, such as chest pain, severe breathing difficulty, stroke signs, unconsciousness, severe bleeding, fits, poisoning, snakebite, pregnancy danger signs, a very sick child, or thoughts of suicide).
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
