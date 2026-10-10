"""Offline demo phrasebook.

Lets the full conversation run with NO API keys: six scripted scenarios in
English, Hindi and Assamese. Every answer produced here is labelled
`source: demo` so it is never mistaken for live AI output. Hindi/Assamese
text is a draft for native-speaker review.
"""
from __future__ import annotations

import difflib
import re

SCENARIOS: list[dict] = [
    {
        "id": "fever",
        "title": "Fever since yesterday",
        "q": {
            "en-IN": "I have had a fever since yesterday. What should I do?",
            "hi-IN": "मुझे कल से बुखार है। मुझे क्या करना चाहिए?",
            "as-IN": "মোৰ কালিৰ পৰা জ্বৰ হৈছে। মই কি কৰিম?",
        },
        "a": {
            "en-IN": "Fever is the body fighting an infection. Rest and drink plenty of clean water. In the North East, fever can be malaria or dengue, so a blood test at the health centre may be needed. See a health worker if the fever lasts more than 2 to 3 days, or comes with shivering, a rash or confusion.",
            "hi-IN": "बुखार शरीर का संक्रमण से लड़ना है। आराम करें और खूब साफ़ पानी पिएँ। पूर्वोत्तर में बुखार मलेरिया या डेंगू भी हो सकता है, इसलिए स्वास्थ्य केंद्र पर खून की जाँच ज़रूरी हो सकती है। बुखार 2-3 दिन से ज़्यादा रहे, या कंपकंपी, दाने या उलझन हो, तो स्वास्थ्य कार्यकर्ता से मिलें।",
            "as-IN": "জ্বৰ মানে শৰীৰে সংক্ৰমণৰ বিৰুদ্ধে যুঁজি আছে। জিৰণি লওক আৰু বেছিকৈ পৰিষ্কাৰ পানী খাওক। উত্তৰ-পূবত জ্বৰ মেলেৰিয়া বা ডেংগুও হ'ব পাৰে, সেয়েহে স্বাস্থ্য কেন্দ্ৰত তেজ পৰীক্ষা লাগিব পাৰে। জ্বৰ ২-৩ দিনতকৈ বেছি থাকিলে, বা কঁপনি, ফোঁহা বা বিভ্ৰান্তি হ'লে স্বাস্থ্য কৰ্মীক লগ কৰক।",
        },
    },
    {
        "id": "diarrhoea_prevention",
        "title": "Preventing diarrhoea",
        "q": {
            "en-IN": "How can I prevent diarrhoea in my family?",
            "hi-IN": "मैं अपने परिवार को दस्त से कैसे बचाऊँ?",
            "as-IN": "মোৰ পৰিয়ালক ডায়েৰিয়াৰ পৰা কেনেকৈ ৰক্ষা কৰিম?",
        },
        "a": {
            "en-IN": "Boil drinking water for at least one minute, or use a trusted filter. Wash hands with soap before eating and after using the toilet. Keep food covered from flies. If several people in your village get diarrhoea at the same time, tell your ASHA worker.",
            "hi-IN": "पीने का पानी कम से कम एक मिनट उबालें, या भरोसेमंद फ़िल्टर इस्तेमाल करें। खाने से पहले और शौच के बाद साबुन से हाथ धोएँ। खाने को मक्खियों से ढककर रखें। गाँव में कई लोगों को एक साथ दस्त हों, तो आशा कार्यकर्ता को बताएँ।",
            "as-IN": "খোৱা পানী অন্ততঃ এক মিনিট উতলাওক, বা বিশ্বাসযোগ্য ফিল্টাৰ ব্যৱহাৰ কৰক। খোৱাৰ আগতে আৰু শৌচালয় ব্যৱহাৰৰ পিছত চাবোনেৰে হাত ধুওক। খাদ্য মাখিৰ পৰা ঢাকি ৰাখক। গাঁৱৰ বহুতৰ একেলগে পেটৰ অসুখ হ'লে আশা কৰ্মীক জনাওক।",
        },
    },
    {
        "id": "child_cough",
        "title": "Child with a cough",
        "q": {
            "en-IN": "My child has had a cough for two days.",
            "hi-IN": "मेरे बच्चे को दो दिन से खांसी है।",
            "as-IN": "মোৰ কেঁচুৱাটোৰ দুদিনৰ পৰা কাহ হৈছে।",
        },
        "a": {
            "en-IN": "Most coughs in children get better in a few days with rest, fluids and feeding. Keep the child warm and keep breastfeeding. Do not give cough medicine to small children without a doctor. Go to a hospital now if the child breathes fast, the chest pulls in, or the child cannot drink. How old is your child?",
            "hi-IN": "ज़्यादातर बच्चों की खांसी आराम, तरल और खाने से कुछ दिनों में ठीक हो जाती है। बच्चे को गर्म रखें और स्तनपान जारी रखें। डॉक्टर की सलाह के बिना छोटे बच्चों को खांसी की दवा न दें। बच्चा तेज़ साँस ले, छाती अंदर धँसे, या कुछ पी न सके तो तुरंत अस्पताल जाएँ। आपके बच्चे की उम्र क्या है?",
            "as-IN": "বেছিভাগ শিশুৰ কাহ জিৰণি, পানীয় আৰু খাদ্যৰে কেইদিনমানতে ভাল হয়। শিশুটোক গৰমে ৰাখক আৰু পিয়াহ খুওৱাই থাকক। চিকিৎসকৰ পৰামৰ্শ অবিহনে সৰু শিশুক কাহৰ দৰব নিদিব। শিশুৱে বেগাবেগিকৈ উশাহ ল'লে, বুকু ভিতৰলৈ সোমাই গ'লে, বা একো খাব নোৱাৰিলে এতিয়াই হাস্পতাললৈ যাওক। আপোনাৰ শিশুটোৰ বয়স কিমান?",
        },
    },
    {
        "id": "malaria",
        "title": "Fever with shivering (urgent)",
        "q": {
            "en-IN": "I get fever with shivering every evening.",
            "hi-IN": "मुझे हर शाम कंपकंपी के साथ बुखार आता है।",
            "as-IN": "মোৰ প্ৰতি সন্ধিয়া কঁপনিৰে সৈতে জ্বৰ আহে।",
        },
        "a": {
            "en-IN": "Fever with shivering that comes and goes can be malaria, which is common in parts of the North East. A quick blood test can confirm it, and your ASHA worker or health centre can do it. Sleep under a mosquito net every night. Please get tested today, because this needs a health worker within a day.",
            "hi-IN": "आती-जाती कंपकंपी के साथ बुखार मलेरिया हो सकता है, जो पूर्वोत्तर के कई हिस्सों में आम है। एक जल्दी होने वाली खून की जाँच से पता चल जाता है, और आशा कार्यकर्ता या स्वास्थ्य केंद्र यह जाँच कर सकते हैं। हर रात मच्छरदानी में सोएँ। कृपया आज ही जाँच कराएँ, क्योंकि इसमें एक दिन के अंदर स्वास्थ्य कार्यकर्ता से मिलना ज़रूरी है।",
            "as-IN": "আহ-যাহ কৰা কঁপনিৰ সৈতে জ্বৰ মেলেৰিয়া হ'ব পাৰে, যিটো উত্তৰ-পূবৰ বহু ঠাইত সাধাৰণ। এটা সোনকালে হোৱা তেজ পৰীক্ষাই ইয়াক নিশ্চিত কৰিব পাৰে, আৰু আশা কৰ্মী বা স্বাস্থ্য কেন্দ্ৰই এই পৰীক্ষা কৰিব পাৰে। প্ৰতি ৰাতি মহজালৰ তলত শুওক। অনুগ্ৰহ কৰি আজিয়েই পৰীক্ষা কৰাওক, কাৰণ এক দিনৰ ভিতৰত স্বাস্থ্য কৰ্মীক লগ কৰাটো প্ৰয়োজন।",
        },
    },
    {
        "id": "breathing_emergency",
        "title": "Breathing difficulty + chest pain (emergency)",
        "q": {
            "en-IN": "My father cannot breathe properly and has chest pain.",
            "hi-IN": "मेरे पिताजी को सांस लेने में तकलीफ़ है और सीने में दर्द है।",
            "as-IN": "মোৰ দেউতাৰ উশাহ ল'ব নোৱাৰা হৈছে আৰু বুকুৰ বিষ হৈছে।",
        },
        "a": {},  # handled by triage, never by an answer
    },
    {
        "id": "snakebite",
        "title": "Snakebite in the paddy field (emergency)",
        "q": {
            "en-IN": "A snake bit my brother in the paddy field.",
            "hi-IN": "खेत में मेरे भाई को सांप ने काट लिया।",
            "as-IN": "পথাৰত মোৰ ভাইটিক সাপে কামোৰিলে।",
        },
        "a": {},
    },
]

EMERGENCY_TIPS_HAND: dict[str, dict[str, str]] = {
    "hi-IN": {
        "snakebite": "व्यक्ति को स्थिर रखें। काटे हुए स्थान को न काटें, न चूसें, न बाँधें।",
        "breathing": "व्यक्ति को सीधा बैठाएँ और तंग कपड़े ढीले करें।",
        "chest_pain": "व्यक्ति को बैठाकर आराम कराएँ। चलने न दें।",
    },
    "as-IN": {
        "snakebite": "মানুহজনক স্থিৰ কৰি ৰাখক। কামোৰা ঠাই কাটিব, চুহিব বা বান্ধিব নালাগে।",
        "breathing": "মানুহজনক পোন হৈ বহিবলৈ দিয়ক আৰু টান কাপোৰ ঢিলা কৰক।",
        "chest_pain": "মানুহজনক বহুৱাই জিৰণি ল'বলৈ দিয়ক। খোজ কাঢ়িবলৈ নিদিব।",
    },
}


def _norm(text: str) -> str:
    return re.sub(r"[\s।.,?!'’\"]+", " ", text.lower()).strip()


def match(text: str, lang_code: str) -> dict | None:
    """Fuzzy-match a typed/heard question to a scripted scenario."""
    best, best_score = None, 0.0
    t = _norm(text)
    for sc in SCENARIOS:
        for code, q in sc["q"].items():
            if code != lang_code and lang_code != "en-IN" and code != "en-IN":
                continue
            score = difflib.SequenceMatcher(None, t, _norm(q)).ratio()
            if score > best_score:
                best, best_score = sc, score
    return best if best_score >= 0.6 else None


def english_for(text: str, lang_code: str) -> str | None:
    sc = match(text, lang_code)
    return sc["q"]["en-IN"] if sc else None


def answer_for(scenario_id: str, lang_code: str, simple: bool = False) -> str | None:
    for sc in SCENARIOS:
        if sc["id"] == scenario_id:
            text = sc["a"].get(lang_code)
            if not text:
                return None
            if simple:
                sentences = [s for s in re.split(r"(?<=[.।?])\s+", text) if s]
                text = " ".join([sentences[0], sentences[-1]]) if len(sentences) > 1 else text
            return text
    return None
