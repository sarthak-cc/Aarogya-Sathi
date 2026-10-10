"""Grounded answer generation through any OpenAI-compatible chat API
(Groq by default; OpenRouter, Ollama or vLLM work by changing LLM_BASE_URL)."""
from __future__ import annotations

import re

import httpx

from .. import config, knowledge
from . import ProviderError, ProviderUnavailable, client, raise_for

SYSTEM_PROMPT = """You are Aarogya Saathi, a voice health-information companion for rural North East India.
Your answer will be translated and SPOKEN on a phone call to someone who may have little schooling.

Hard rules:
1. Use ONLY the facts in the CARDS below. If the cards do not cover the question, say you do not have reliable information and advise the ASHA worker or nearest health centre.
2. Never diagnose. Say "this can happen with..." not "you have...".
3. Never prescribe. Never choose a medicine for the caller and never state a dose, amount, strength or how often to take anything. You may say in general terms what a medicine is commonly used for and the precautions on the cards. Never tell anyone to stop or change prescribed medicine; send them to their doctor or pharmacist.
4. Always end with one sentence on when to see a health worker or doctor, taken from the card's "Seek care when" list.
5. Never claim you contacted a doctor, ambulance or anyone else.
6. Plain spoken English: no lists, no markdown, no brackets, no abbreviations except ORS, ASHA and 112.
7. {length_rule}
8. If an important detail is missing (age, how many days), you may ask ONE short question at the end instead of guessing.
{urgent_rule}{medicine_rule}
CARDS:
{cards}"""

LENGTH = {
    "standard": "At most 4 short sentences, each under 15 words.",
    "simple": "At most 3 very short sentences, each under 10 words, using words a 10-year-old knows. Explain like talking to a grandparent.",
}


def build_messages(question_en: str, cards: list[knowledge.Card], level: str = "standard",
                   urgent: bool = False, history: list[dict] | None = None,
                   medicine_request: bool = False) -> list[dict]:
    urgent_rule = ("9. The safety check flagged this as URGENT: clearly say to see a health worker or doctor "
                   "within a day.\n") if urgent else ""
    medicine_rule = ("10. The caller is asking which medicine or how much to take. Say clearly that only a doctor, nurse or "
                     "pharmacist can decide that after seeing them, then give the general safety points from the cards.\n"
                     ) if medicine_request else ""
    system = SYSTEM_PROMPT.format(length_rule=LENGTH.get(level, LENGTH["standard"]), urgent_rule=urgent_rule,
                                  medicine_rule=medicine_rule,
                                  cards=knowledge.render_for_prompt(cards))
    msgs = [{"role": "system", "content": system}]
    for turn in (history or [])[-4:]:  # short memory keeps latency and cost low
        msgs.append({"role": turn["role"], "content": turn["content"]})
    msgs.append({"role": "user", "content": question_en})
    return msgs


def _clean(text: str) -> str:
    text = re.sub(r"[*_#`>\[\]]", "", text)
    text = re.sub(r"^\s*[-•\d]+[.)]?\s+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


async def answer(question_en: str, cards: list[knowledge.Card], level: str = "standard",
                 urgent: bool = False, history: list[dict] | None = None, medicine_request: bool = False) -> str:
    s = config.settings
    if not s.has_llm:
        raise ProviderUnavailable("LLM not configured")
    payload = {
        "model": s.llm_model,
        "messages": build_messages(question_en, cards, level, urgent, history, medicine_request),
        "temperature": 0.2,
        "max_tokens": 220,
    }
    try:
        async with client() as c:
            resp = await c.post(f"{s.llm_base_url}/chat/completions",
                                headers={"Authorization": f"Bearer {s.llm_api_key}"}, json=payload)
    except httpx.HTTPError as exc:
        raise ProviderError(f"llm network error: {type(exc).__name__}") from exc
    raise_for(resp, "llm")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise ProviderError("llm returned an unexpected payload") from exc
    return _clean(content or "")
