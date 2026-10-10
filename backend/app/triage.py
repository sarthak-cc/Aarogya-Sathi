"""Deterministic red-flag triage.

Runs on BOTH the native transcript and its English translation, before any
LLM call. If anything matches at EMERGENCY or CRISIS level the LLM is skipped
entirely and a short pre-written message is spoken. Rules deliberately
over-trigger: a false alarm costs seconds, a missed emergency costs a life.

Rules follow common public-health danger-sign lists (WHO IMCI child danger
signs, standard stroke/chest-pain/breathing red flags, pregnancy danger signs,
snakebite first-aid guidance). They are NOT clinically validated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Level(str, Enum):
    NONE = "none"
    URGENT = "urgent"  # see a health worker / doctor within ~24h
    EMERGENCY = "emergency"  # go now / call 112
    CRISIS = "crisis"  # self-harm risk


SEVERITY = {Level.NONE: 0, Level.URGENT: 1, Level.EMERGENCY: 2, Level.CRISIS: 3}


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    level: Level
    # Each alternative is a tuple of fragments that must ALL appear.
    any_of: tuple[tuple[str, ...], ...]


def _alts(*items) -> tuple[tuple[str, ...], ...]:
    return tuple(i if isinstance(i, tuple) else (i,) for i in items)


CHILD = ("baby", "child", "infant", "my son", "my daughter", "बच्चा", "बच्चे", "शिशु", "শিশু", "কেঁচুৱা", "লৰা")

RULES: list[Rule] = [
    Rule("crisis_self_harm", "Thoughts of self-harm", Level.CRISIS, _alts(
        "kill myself", "suicide", "want to die", "end my life", "harm myself", "hurt myself",
        "आत्महत्या", "मरना चाहत", "मर जाना चाह", "আত্মহত্যা", "মৰিব বিচাৰো", "মরতে চাই",
    )),
    Rule("breathing", "Severe breathing difficulty", Level.EMERGENCY, _alts(
        "can't breathe", "cannot breathe", "can not breathe", "unable to breathe", "difficulty breathing",
        "difficulty in breathing", "trouble breathing", "shortness of breath", "short of breath",
        "breathless", "not breathing", "gasping", "choking", "lips turning blue", "blue lips",
        "साँस नहीं", "सांस नहीं", "साँस लेने में", "सांस लेने में", "सांस फूल", "साँस फूल",
        "উশাহ ল'ব নোৱা", "উশাহ লব নোৱা", "উশাহত কষ্ট", "উশাহ-নিশাহ", "শ্বাস নিতে কষ্ট", "শ্বাসকষ্ট",
        "सास फेर्न", "सास लिन गाह्रो",
    )),
    Rule("chest_pain", "Chest pain or pressure", Level.EMERGENCY, _alts(
        "chest pain", "pain in chest", "pain in my chest", "chest pressure", "chest tightness", "heart attack",
        "सीने में दर्द", "छाती में दर्द", "বুকুৰ বিষ", "বুকু বিষ", "বুকে ব্যথা", "छाती दुख",
    )),
    Rule("stroke", "Possible stroke signs", Level.EMERGENCY, _alts(
        "stroke", "face drooping", "face droop", "slurred speech", "speech is slurred", "can't speak",
        "cannot speak", "one side weak", "weakness on one side", "one side of the body", "paralysis",
        "paralysed", "paralyzed", "लकवा", "पक्षाघात", "মুখ বেঁকা", "পক্ষাঘাত",
    )),
    Rule("unconscious", "Unconscious or not responding", Level.EMERGENCY, _alts(
        "unconscious", "not waking", "won't wake", "will not wake", "fainted", "passed out", "unresponsive",
        "not responding", "बेहोश", "होश नहीं", "অজ্ঞান", "অচেতন", "बेहोस",
    )),
    Rule("bleeding", "Severe bleeding", Level.EMERGENCY, _alts(
        "heavy bleeding", "bleeding a lot", "won't stop bleeding", "not stop bleeding", "not stopping bleeding",
        "severe bleeding", "vomiting blood", "blood vomit", "बहुत खून", "खून नहीं रुक", "खून की उल्टी",
        "বহুত তেজ", "তেজ বন্ধ হোৱা নাই", "অনেক রক্ত",
    )),
    Rule("seizure", "Fits / seizure", Level.EMERGENCY, _alts(
        "seizure", "convulsion", "having fits", "had fits", "fitting", "दौरा पड़", "मिर्गी", "মৃগী", "খিচুনি",
    )),
    Rule("snakebite", "Snakebite", Level.EMERGENCY, _alts(
        "snake bite", "snakebite", "bitten by a snake", "snake bit", "snake has bitten",
        "साँप ने काट", "सांप ने काट", "साँप काट", "सांप काट", "সাপে কামোৰ", "সাপে কাম", "সাপে কামড়",
        "सर्पले टोक", "सापले टोक",
    )),
    Rule("poisoning", "Poisoning", Level.EMERGENCY, _alts(
        "drank poison", "swallowed poison", "ate poison", "poisoned", "pesticide", "insecticide", "overdose", "drank kerosene", "swallowed kerosene",
        "ज़हर", "जहर", "কীটনাশক", "বিহ খা", "বিষ খে",
    )),
    Rule("pregnancy_danger", "Pregnancy danger sign", Level.EMERGENCY, _alts(
        ("pregnan", "bleeding"), ("pregnan", "fits"), ("pregnan", "seizure"), ("pregnan", "blurred vision"),
        ("pregnan", "severe headache"), ("pregnan", "severe pain"), ("pregnan", "baby not moving"),
        ("pregnan", "baby is not moving"), ("गर्भ", "खून"), ("गर्भवती", "खून"), ("গৰ্ভ", "তেজ"), ("গর্ভ", "রক্ত"),
    )),
    Rule("child_danger", "Child danger sign", Level.EMERGENCY, tuple(
        (c, s) for c in CHILD for s in (
            "not feeding", "unable to drink", "can't drink", "cannot drink", "not drinking", "not breastfeeding",
            "vomits everything", "vomiting everything", "very sleepy", "hard to wake", "lethargic", "fits",
            "दूध नहीं पी", "कुछ नहीं पी", "খাব পৰা নাই", "গাখীৰ খোৱা নাই",
        )
    )),
    # --- URGENT: needs a health worker/doctor soon, but not an ambulance ---
    Rule("fever_persistent", "Fever lasting 3+ days or very high fever", Level.URGENT, _alts(
        "fever for 3 days", "fever for three days", "fever for 4 days", "fever for four days",
        "fever for a week", "fever for 5 days", "fever for five days", "high fever", "very high fever",
        "तीन दिन से बुखार", "तेज़ बुखार", "तेज बुखार", "তিনিদিন ধৰি জ্বৰ", "বেছি জ্বৰ",
    )),
    Rule("fever_chills", "Fever with chills/shivering (needs malaria test)", Level.URGENT, _alts(
        "fever with chills", "fever with shivering", ("fever", "shiver"), ("fever", "chills"),
        "कंपकंपी", "কঁপনি",
    )),
    Rule("stiff_neck", "Fever with stiff neck or confusion", Level.EMERGENCY, _alts(
        ("fever", "stiff neck"), ("fever", "confus"), ("fever", "neck is stiff"),
    )),
    Rule("dehydration", "Signs of dehydration", Level.URGENT, _alts(
        "no urine", "not passing urine", "sunken eyes", "very thirsty", "severe dehydration", "dehydrated",
        "blood in stool", "bloody diarrh", "blood in motion", "पेशाब नहीं", "दस्त में खून",
    )),
    Rule("long_cough", "Cough for two weeks or more / coughing blood", Level.URGENT, _alts(
        "cough for 2 weeks", "cough for two weeks", "cough for 3 weeks", "cough for a month", "coughing blood",
        "blood in cough", "दो हफ्ते से खांसी", "खांसी में खून",
    )),
    Rule("animal_bite", "Dog or animal bite (rabies risk)", Level.URGENT, _alts(
        "dog bite", "dog bit", "bitten by a dog", "monkey bite", "animal bite", "bat bite",
        "कुत्ते ने काट", "কুকুৰে কামোৰ", "কুকুরে কামড়",
    )),
    Rule("jaundice", "Yellow eyes / jaundice", Level.URGENT, _alts(
        "jaundice", "yellow eyes", "eyes are yellow", "पीलिया", "জণ্ডিচ",
    )),
    Rule("eschar", "Black scab with fever (possible scrub typhus)", Level.URGENT, _alts(
        ("fever", "black scab"), ("fever", "black spot"), ("fever", "eschar"),
    )),
    Rule("severe_abdominal", "Severe abdominal pain", Level.URGENT, _alts(
        "severe stomach pain", "severe abdominal pain", "severe pain in stomach", "पेट में तेज दर्द",
    )),
]


@dataclass
class TriageResult:
    level: Level = Level.NONE
    matches: list[dict] = field(default_factory=list)

    @property
    def is_blocking(self) -> bool:
        """Emergency/crisis short-circuits the LLM."""
        return self.level in (Level.EMERGENCY, Level.CRISIS)

    def to_dict(self) -> dict:
        return {"level": self.level.value, "blocking": self.is_blocking, "matches": self.matches}


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", text)


def assess(*texts: str) -> TriageResult:
    """Assess one or more texts (native transcript, English translation)."""
    haystack = " || ".join(_normalise(t) for t in texts if t)
    result = TriageResult()
    for rule in RULES:
        for alternative in rule.any_of:
            if all(frag.lower() in haystack for frag in alternative):
                result.matches.append({"rule": rule.id, "label": rule.label, "level": rule.level.value,
                                       "matched": " + ".join(alternative)})
                if SEVERITY[rule.level] > SEVERITY[result.level]:
                    result.level = rule.level
                break
    return result
