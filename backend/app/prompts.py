"""Fixed safety texts: the ONLY pre-written content the user hears.

Routine health answers always come from the LLM. These messages exist because
emergency guidance must be instant and must not depend on an AI service. Hindi,
Assamese and Bengali are hand-written (flagged for native-speaker review);
other languages are translated by Sarvam when configured, else English is
returned and labelled as English.
"""
from __future__ import annotations

from .providers import ProviderError

EN: dict[str, str] = {
    "emergency": "This may be an emergency. Call 112 now, or ask someone near you to take the person to the nearest hospital. Do not wait.",
    "crisis": "You matter, and help is available right now. Please call Tele-MANAS on 14416, or 112 if you are in danger. If you can, stay with someone you trust.",
    "ask_location": "To find the nearest hospital, share your location or type your village, town, PIN code or a nearby landmark.",
    "not_heard": "Sorry, I could not hear that clearly. Please try again, or type your question.",
}

# One-line first aid spoken after the emergency message, per triage rule.
TIPS_EN: dict[str, str] = {
    "chest_pain": "Make the person sit and rest. Do not let them walk. Loosen tight clothing.",
    "breathing": "Help the person sit upright and loosen tight clothing.",
    "stroke": "Note the time the symptoms started. Do not give food or water.",
    "unconscious": "Turn the person on their side and check they are breathing.",
    "bleeding": "Press firmly on the wound with a clean cloth and keep pressing.",
    "seizure": "Do not put anything in the mouth. Move hard objects away and turn the person on their side.",
    "snakebite": "Keep the person still. Do not cut, suck or tie the bite.",
    "poisoning": "Do not make the person vomit. Take the container with you to the hospital.",
    "pregnancy_danger": "Keep her lying on her left side and go to the hospital now.",
    "child_danger": "Keep the child warm and take the child to a hospital now.",
    "stiff_neck": "Go to a hospital now. This needs a doctor today.",
    "burns": "Cool the burn under clean running water for 20 minutes. Do not put oil, toothpaste or ice on it.",
    "injury": "Do not move the person if the head, neck or back may be hurt, unless they are in danger. Press on any bleeding.",
    "drowning": "If the person is not breathing, call 112 and start chest compressions if you know how.",
    "electric": "Switch off the power or move the wire with dry wood before touching the person.",
}

HAND: dict[str, dict[str, str]] = {
    "hi-IN": {
        "emergency": "यह आपातकाल हो सकता है। अभी 112 पर कॉल करें, या पास के किसी व्यक्ति से तुरंत नज़दीकी अस्पताल ले जाने को कहें। इंतज़ार न करें।",
        "crisis": "आप महत्वपूर्ण हैं, और मदद अभी उपलब्ध है। टेली-मानस को 14416 पर कॉल करें, या खतरा हो तो 112 पर। हो सके तो किसी भरोसेमंद व्यक्ति के साथ रहें।",
        "ask_location": "नज़दीकी अस्पताल ढूँढने के लिए अपनी लोकेशन साझा करें, या अपना गाँव, शहर, पिन कोड या पास की कोई पहचान वाली जगह लिखें।",
        "not_heard": "माफ़ कीजिए, मैं ठीक से सुन नहीं पाया। दोबारा बोलिए, या अपना सवाल लिखिए।",
        "tip_chest_pain": "व्यक्ति को बैठाकर आराम कराएँ। चलने न दें। तंग कपड़े ढीले करें।",
        "tip_breathing": "व्यक्ति को सीधा बैठाएँ और तंग कपड़े ढीले करें।",
        "tip_snakebite": "व्यक्ति को स्थिर रखें। काटे हुए स्थान को न काटें, न चूसें, न बाँधें।",
        "tip_unconscious": "व्यक्ति को करवट से लिटाएँ और देखें कि साँस चल रही है।",
        "tip_bleeding": "घाव पर साफ़ कपड़े से ज़ोर से दबाकर रखें।",
    },
    "as-IN": {
        "emergency": "এইটো জৰুৰী অৱস্থা হ'ব পাৰে। এতিয়াই 112 নম্বৰত ফোন কৰক, বা ওচৰৰ কাৰোবাক মানুহজনক তৎক্ষণাত ওচৰৰ হাস্পতাললৈ লৈ যাবলৈ কওক। অপেক্ষা নকৰিব।",
        "crisis": "আপুনি মূল্যৱান, আৰু সহায় এতিয়াই উপলব্ধ। টেলি-মানছক 14416 নম্বৰত ফোন কৰক, বিপদ হ'লে 112 ত। পাৰিলে বিশ্বাসী কাৰোবাৰ লগত থাকক।",
        "ask_location": "ওচৰৰ হাস্পতাল বিচাৰিবলৈ আপোনাৰ লোকেশ্বন শ্বেয়াৰ কৰক, বা আপোনাৰ গাঁও, চহৰ, পিন ক'ড বা ওচৰৰ চিনাকি ঠাইৰ নাম লিখক।",
        "not_heard": "ক্ষমা কৰিব, মই ভালদৰে শুনিব নোৱাৰিলোঁ। আকৌ কওক, বা আপোনাৰ প্ৰশ্নটো লিখক।",
        "tip_chest_pain": "মানুহজনক বহুৱাই জিৰণি ল'বলৈ দিয়ক। খোজ কাঢ়িবলৈ নিদিব। টান কাপোৰ ঢিলা কৰক।",
        "tip_breathing": "মানুহজনক পোন হৈ বহিবলৈ দিয়ক আৰু টান কাপোৰ ঢিলা কৰক।",
        "tip_snakebite": "মানুহজনক স্থিৰ কৰি ৰাখক। কামোৰা ঠাই কাটিব, চুহিব বা বান্ধিব নালাগে।",
    },
    "bn-IN": {
        "emergency": "এটি জরুরি অবস্থা হতে পারে। এখনই 112 নম্বরে ফোন করুন, বা কাছের কাউকে বলুন রোগীকে এখনই কাছের হাসপাতালে নিয়ে যেতে। দেরি করবেন না।",
        "crisis": "আপনি মূল্যবান, এবং সাহায্য এখনই পাওয়া যায়। টেলি-মানসে 14416 নম্বরে ফোন করুন, বিপদ হলে 112 নম্বরে। পারলে বিশ্বস্ত কারও সঙ্গে থাকুন।",
        "ask_location": "কাছের হাসপাতাল খুঁজতে আপনার লোকেশন শেয়ার করুন, বা আপনার গ্রাম, শহর, পিন কোড বা কাছের কোনো পরিচিত জায়গার নাম লিখুন।",
        "not_heard": "দুঃখিত, আমি ঠিকমতো শুনতে পাইনি। আবার বলুন, বা প্রশ্নটি লিখুন।",
    },
}

_machine_cache: dict[tuple[str, str], str] = {}


async def get(key: str, lang_code: str) -> dict:
    """Return {'text', 'lang', 'source'}; source = hand | machine | english_fallback."""
    english = EN[key] if key in EN else TIPS_EN[key.removeprefix("tip_")]
    if lang_code == "en-IN":
        return {"text": english, "lang": "en-IN", "source": "hand"}
    hand = HAND.get(lang_code, {})
    if key in hand:
        return {"text": hand[key], "lang": lang_code, "source": "hand"}
    if (key, lang_code) not in _machine_cache:
        from .providers import translate  # local import avoids a cycle

        try:
            _machine_cache[(key, lang_code)] = await translate.from_english(english, lang_code)
        except ProviderError:
            return {"text": english, "lang": "en-IN", "source": "english_fallback"}
    return {"text": _machine_cache[(key, lang_code)], "lang": lang_code, "source": "machine"}


async def emergency_message(level: str, rule_ids: list[str], lang_code: str) -> dict:
    """Fixed emergency script plus the most relevant first-aid line."""
    msg = await get("crisis" if level == "crisis" else "emergency", lang_code)
    if level == "crisis":
        return msg
    rule = next((r for r in rule_ids if r in TIPS_EN), None)
    if rule:
        tip = await get(f"tip_{rule}", lang_code)
        if tip["lang"] == msg["lang"]:
            msg = {**msg, "text": f"{msg['text']} {tip['text']}"}
    return msg
