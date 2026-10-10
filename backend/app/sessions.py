"""Call sessions and the conversation state machine.

Sessions live in memory only. Ending a call wipes transcripts and audio
unless the caller consented to a handoff slip (which keeps only the slip).
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from . import audio_store, config


class State(str, Enum):
    INCOMING_CALL = "INCOMING_CALL"
    LANGUAGE_SELECTION = "LANGUAGE_SELECTION"
    READY_TO_LISTEN = "READY_TO_LISTEN"
    CONFIRMING = "CONFIRMING"  # read-back: "I heard X, press 1 if right"
    ANSWERED = "ANSWERED"  # answer spoken, post-answer menu active
    EMERGENCY = "EMERGENCY"
    CONSENT = "CONSENT"
    CALL_ENDED = "CALL_ENDED"


ALLOWED: dict[State, set[State]] = {
    State.INCOMING_CALL: {State.LANGUAGE_SELECTION, State.CALL_ENDED},
    State.LANGUAGE_SELECTION: {State.READY_TO_LISTEN, State.LANGUAGE_SELECTION, State.CALL_ENDED},
    State.READY_TO_LISTEN: {State.CONFIRMING, State.ANSWERED, State.EMERGENCY, State.READY_TO_LISTEN,
                            State.LANGUAGE_SELECTION, State.CONSENT, State.CALL_ENDED},
    State.CONFIRMING: {State.ANSWERED, State.EMERGENCY, State.READY_TO_LISTEN, State.CALL_ENDED},
    State.ANSWERED: {State.READY_TO_LISTEN, State.ANSWERED, State.CONFIRMING, State.EMERGENCY,
                     State.LANGUAGE_SELECTION, State.CONSENT, State.CALL_ENDED},
    State.EMERGENCY: {State.READY_TO_LISTEN, State.CONSENT, State.LANGUAGE_SELECTION, State.CALL_ENDED},
    State.CONSENT: {State.CALL_ENDED},
    State.CALL_ENDED: set(),
}


class InvalidTransition(Exception):
    pass


@dataclass
class Session:
    id: str
    channel: str = "simulator"  # simulator (web voice); a phone channel can be added later
    state: State = State.INCOMING_CALL
    language: Optional[str] = None
    literacy: str = "standard"  # standard | simple
    history: list[dict] = field(default_factory=list)  # English turns for LLM context
    turns: list[dict] = field(default_factory=list)  # full turn records (in memory only)
    pending: Optional[dict] = None  # utterance awaiting read-back confirmation
    audio_keys: list[str] = field(default_factory=list)
    seen_events: set[str] = field(default_factory=set)  # webhook idempotency
    consent_slip: bool = False
    slip: Optional[dict] = None
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    retries: int = 0
    location: Optional[dict] = None  # approximate place for facility search; wiped when the call ends

    def transition(self, new: State) -> None:
        if new not in ALLOWED[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {new.value} not allowed")
        self.state = new
        self.updated = time.time()

    @property
    def last_answer(self) -> Optional[dict]:
        for t in reversed(self.turns):
            if t.get("answer"):
                return t
        return None

    def public(self) -> dict:
        return {"id": self.id, "channel": self.channel, "state": self.state.value, "language": self.language,
                "literacy": self.literacy, "turns": len(self.turns), "consent_slip": self.consent_slip}


_sessions: dict[str, Session] = {}
unsupported_language_requests: dict[str, int] = {}  # demand signal for future data collection


def create(channel: str = "simulator", session_id: Optional[str] = None) -> Session:
    _purge()
    sid = session_id or ("AS-" + secrets.token_hex(4).upper())
    s = Session(id=sid, channel=channel)
    _sessions[sid] = s
    return s


def get(session_id: str) -> Optional[Session]:
    _purge()
    return _sessions.get(session_id)


def get_or_create(session_id: str, channel: str) -> Session:
    return get(session_id) or create(channel, session_id)


def end(session: Session) -> dict:
    """End the call and wipe everything except a consented slip."""
    if session.state != State.CALL_ENDED:
        session.state = State.CALL_ENDED
    audio_store.drop_many(session.audio_keys)
    session.audio_keys.clear()
    session.turns.clear()
    session.history.clear()
    session.pending = None
    session.location = None
    if not session.consent_slip:
        session.slip = None
    return {"ended": True, "data_cleared": True, "slip_kept": session.slip is not None}


def delete(session_id: str) -> bool:
    s = _sessions.pop(session_id, None)
    if s:
        audio_store.drop_many(s.audio_keys)
    return s is not None


def _purge() -> None:
    cutoff = time.time() - config.settings.session_ttl_seconds
    for sid in [k for k, v in _sessions.items() if v.updated < cutoff]:
        delete(sid)
