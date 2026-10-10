"""Care Handoff Slip: a consent-gated, deterministic summary a caller can show
(or read the code of) to an ASHA worker or doctor. Built from rules, not the
LLM, so it never invents symptoms. Contains no diagnosis."""
from __future__ import annotations

import re
import secrets
import time
from datetime import datetime, timedelta, timezone

from . import languages
from .triage import SEVERITY, Level

IST = timezone(timedelta(hours=5, minutes=30))
SLIP_TTL_SECONDS = 24 * 3600
_slips: dict[str, tuple[float, dict]] = {}

ACTION = {
    Level.CRISIS.value: "Possible self-harm risk. Caller was given Tele-MANAS 14416 and 112. Please follow up today.",
    Level.EMERGENCY.value: "Emergency red flag reported. Caller was told to seek emergency care / call 112 immediately.",
    Level.URGENT.value: "Needs assessment by a health worker or doctor within 24 hours.",
    Level.NONE.value: "General health information given. Routine follow-up if symptoms continue.",
}

DURATION = re.compile(
    r"(since (?:yesterday|last night|this morning|\w+ days?|\w+ weeks?)|for (?:\w+|\d+) (?:days?|weeks?|months?)|every (?:evening|night|morning|day))",
    re.I,
)


def build(session) -> dict:
    lang = languages.get(session.language or "en-IN")
    concerns, flags, cards = [], [], []
    top = Level.NONE.value
    for t in session.turns:
        if t.get("rephrase_of") is not None:
            continue  # "explain simpler" repeats are not new concerns
        concerns.append({"said": t.get("transcript"), "english": t.get("english"),
                         "duration": _duration(t.get("english") or t.get("transcript") or "")})
        tri = t.get("triage") or {}
        for m in tri.get("matches", []):
            if m["label"] not in flags:
                flags.append(m["label"])
        if SEVERITY[Level(tri.get("level", "none"))] > SEVERITY[Level(top)]:
            top = tri.get("level", "none")
        for c in t.get("cards", []):
            if c["title"] not in cards:
                cards.append(c["title"])

    code = secrets.token_hex(3).upper()
    slip = {
        "code": code,
        "created_ist": datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST"),
        "language": f"{lang.name} ({lang.native_name})" if lang else session.language,
        "concerns": concerns,
        "red_flags": flags,
        "urgency": top,
        "recommended_action": ACTION[top],
        "topics_covered": cards,
        "disclaimer": "Caller-reported information from an automated health-information line. "
                      "Not a diagnosis. Verify all details with the patient.",
    }
    _slips[code] = (time.time(), slip)
    return slip


def lookup(code: str) -> dict | None:
    cutoff = time.time() - SLIP_TTL_SECONDS
    for k in [k for k, (ts, _) in _slips.items() if ts < cutoff]:
        _slips.pop(k, None)
    item = _slips.get(code.upper())
    return item[1] if item else None


def delete(code: str) -> bool:
    return _slips.pop(code.upper(), None) is not None


def _duration(text: str) -> str | None:
    m = DURATION.search(text or "")
    return m.group(0) if m else None
