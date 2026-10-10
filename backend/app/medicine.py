"""Medicine-safety guard.

The assistant may explain what a medicine is generally for, common precautions,
and how to follow an existing prescription. It must never choose a medicine for
someone or state a dose. Two deterministic checks enforce that around the LLM:

* `is_prescription_request` spots "which medicine / how much should I take"
  questions so the answer is steered to the medicine-safety card and a referral.
* `contains_dose` rejects any generated answer that states an amount, frequency
  or strength; the vetted card text is used instead.
"""
from __future__ import annotations

import re

_REQUEST = re.compile(
    r"(which|what) (medicine|medication|tablet|drug|antibiotic|syrup|injection)s?\b"
    r"|\b(dose|dosage|how many (tablet|pill|capsule)s?|how much (medicine|syrup|paracetamol))\b"
    r"|\bprescri(be|ption for)\b|\bgive me (a )?(medicine|tablet)\b"
    r"|\bshould i take\b.*\b(medicine|tablet|pill|antibiotic|paracetamol|ibuprofen|aspirin)\b",
    re.I,
)
_REQUEST_NATIVE = ("कौन सी दवा", "कौनसी दवा", "कितनी गोली", "दवा बताइए", "दवाई बताओ",
                   "কোনটো ঔষধ", "কিমান টেবলেট", "ঔষধ কওক", "কোন ওষুধ", "কত ডোজ")

_DOSE = re.compile(
    r"\b\d+(\.\d+)?\s?(mg|mcg|µg|g|gm|ml|iu|units?|tablets?|tabs?|pills?|capsules?|drops?|puffs?|teaspoons?|spoons?)\b"
    r"|\b(once|twice|thrice|\d+ times) (a|per|every) (day|daily|night)\b"
    r"|\bevery \d+ hours\b",
    re.I,
)


def is_prescription_request(*texts: str) -> bool:
    for t in texts:
        if not t:
            continue
        if _REQUEST.search(t) or any(k in t for k in _REQUEST_NATIVE):
            return True
    return False


def contains_dose(text: str) -> bool:
    return bool(text and _DOSE.search(text))
