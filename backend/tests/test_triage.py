import pytest

from app import triage
from app.triage import Level


@pytest.mark.parametrize("text,level,rule", [
    ("My father cannot breathe properly", Level.EMERGENCY, "breathing"),
    ("he has severe chest pain", Level.EMERGENCY, "chest_pain"),
    ("her face drooping and slurred speech", Level.EMERGENCY, "stroke"),
    ("A snake bit my brother in the paddy field.", Level.EMERGENCY, "snakebite"),
    ("I am pregnant and there is bleeding", Level.EMERGENCY, "pregnancy_danger"),
    ("my baby is not feeding and very sleepy", Level.EMERGENCY, "child_danger"),
    ("I want to kill myself", Level.CRISIS, "crisis_self_harm"),
    ("fever with shivering every evening", Level.URGENT, "fever_chills"),
    ("cough for two weeks", Level.URGENT, "long_cough"),
    ("a dog bit my son", Level.URGENT, "animal_bite"),
])
def test_english_red_flags(text, level, rule):
    r = triage.assess(text)
    assert r.level == level
    assert rule in [m["rule"] for m in r.matches]


@pytest.mark.parametrize("text,rule", [
    ("পথাৰত মোৰ ভাইটিক সাপে কামোৰিলে।", "snakebite"),            # Assamese
    ("মোৰ দেউতাৰ উশাহ ল'ব নোৱাৰা হৈছে", "breathing"),              # Assamese
    ("मेरे पिताजी को सीने में दर्द है", "chest_pain"),                # Hindi
    ("खेत में मेरे भाई को सांप ने काट लिया", "snakebite"),           # Hindi
    ("সাপে কামড়েছে", "snakebite"),                                  # Bengali
])
def test_native_red_flags_work_without_translation(text, rule):
    r = triage.assess(text)
    assert r.is_blocking
    assert rule in [m["rule"] for m in r.matches]


def test_crisis_outranks_emergency():
    r = triage.assess("I swallowed pesticide because I want to die")
    assert r.level == Level.CRISIS


def test_routine_question_not_flagged():
    for q in ["How can I prevent diarrhoea?", "What should I eat for good health?", "I have a mild cold"]:
        assert triage.assess(q).level == Level.NONE


def test_food_poisoning_is_not_an_emergency_trigger():
    assert triage.assess("I think I have food poisoning").level != Level.EMERGENCY


def test_ordinary_headache_is_not_emergency():
    # Routine headache questions must be Level.NONE
    for q in [
        "I have a slight headache today",
        "मुझे सुबह से हल्का सिरदर्द है",
        "মোৰ মূৰৰ বিষ হৈছে, কি কৰিম?",  # Assamese headache
        "মাথা বিষ খেতে কি করব",
        "mere sar me dard hai",
    ]:
        res = triage.assess(q)
        assert res.level == Level.NONE, f"Expected NONE for '{q}', got {res.level}"


def test_dangerous_headache_is_emergency():
    # Thunderclap / severe headache with red flags
    for q in [
        "worst headache of my life and I am vomiting",
        "sudden severe headache and blurred vision",
        "अचानक बहुत तेज सिरदर्द और उल्टी हो रही है",
    ]:
        res = triage.assess(q)
        assert res.level == Level.EMERGENCY
        assert "headache_danger" in [m["rule"] for m in res.matches]


def test_cannot_speak_language_does_not_trigger_stroke():
    # Innocent language capability statements should not trigger stroke emergency
    for q in [
        "I cannot speak English well",
        "I can't speak Hindi",
        "मैं अंग्रेजी बोल नहीं पाता",
        "মই ভালকৈ ক'ব নোৱাৰোঁ",
    ]:
        res = triage.assess(q)
        assert res.level != Level.EMERGENCY, f"Unexpected emergency for '{q}'"


def test_poisoning_distinguishes_real_ingestion_from_headache():
    # Poisoning rule should catch actual toxic ingestion
    assert triage.assess("He drank pesticide by accident").level == Level.EMERGENCY
    assert triage.assess("उसने ज़हर पी लिया").level == Level.EMERGENCY
    assert triage.assess("সি বিহ খালে").level == Level.EMERGENCY
    # But ordinary pain relief or mild questions should NOT trigger poisoning
    assert triage.assess("মূৰৰ বিষ খেদিবলৈ কি কৰিম?").level == Level.NONE
