"""Reference notes passed to the LLM as extra context.

The LLM answers any health question; when a question matches one of these
notes (North East specific topics such as malaria, JE, scrub typhus, snakebite),
the note is added to the prompt so the answer reflects local public-health
guidance. Content follows widely published WHO / Government of India messaging,
contains no drug doses, and must be reviewed by a health professional.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    id: str
    title: str
    keywords: tuple[str, ...]
    facts: tuple[str, ...]
    seek_care: tuple[str, ...]
    source: str


CARDS: list[Card] = [
    Card(
        "fever", "Fever (general)",
        ("fever", "temperature", "hot body", "bukhar", "jor", "jwar"),
        (
            "Fever is the body fighting an infection. Rest and drink plenty of clean water.",
            "In the North East, fever can be a sign of malaria, dengue, Japanese encephalitis or scrub typhus, so a blood test at the health centre is often needed.",
            "Do not take leftover medicines or injections from a shop without advice.",
            "A wet cloth on the forehead can help the person feel more comfortable.",
        ),
        (
            "Fever lasting more than 2 to 3 days.",
            "Fever with shivering, severe headache, stiff neck, rash, confusion, bleeding, or a black scab on the skin.",
            "Any fever in a baby younger than 3 months, a pregnant woman, or an elderly person.",
        ),
        "General guidance consistent with WHO / MoHFW public messaging",
    ),
    Card(
        "malaria", "Malaria",
        ("malaria", "mosquito", "chills", "shivering", "shivers"),
        (
            "Malaria spreads through mosquito bites and is common in parts of the North East.",
            "Fever with chills and shivering, which may come and go, can be malaria.",
            "A quick blood test can confirm it. ASHA workers and government health centres can test for malaria.",
            "Sleeping under an insecticide-treated mosquito net every night protects the whole family.",
        ),
        ("Any fever with chills should be tested the same day if possible.", "Confusion, drowsiness, or fits with fever is an emergency."),
        "National Center for Vector Borne Diseases Control (NCVBDC) public guidance",
    ),
    Card(
        "dengue", "Dengue",
        ("dengue", "rash", "joint pain", "body pain", "platelet"),
        (
            "Dengue spreads through day-biting mosquitoes that breed in clean stagnant water, such as in pots, tyres and coolers.",
            "It causes high fever, body and joint pain, headache and sometimes a rash.",
            "Do not take painkillers like aspirin or ibuprofen for fever without a doctor's advice, because they can increase bleeding risk in dengue.",
            "Empty and cover water containers every week to stop mosquitoes breeding.",
        ),
        ("Bleeding from gums or nose, black stools, severe stomach pain, repeated vomiting, or feeling very weak and cold.",),
        "NCVBDC / WHO dengue public guidance",
    ),
    Card(
        "japanese_encephalitis", "Japanese Encephalitis (brain fever)",
        ("encephalitis", "brain fever", "je", "japanese"),
        (
            "Japanese encephalitis is a brain infection spread by mosquitoes. Cases rise in Assam and nearby areas during the monsoon.",
            "The JE vaccine is given free to children in affected districts under the national immunisation programme.",
            "Use mosquito nets and cover the body at dusk.",
        ),
        ("Fever with headache, confusion, fits, or unusual sleepiness, especially in children. Go to a hospital immediately.",),
        "MoHFW Universal Immunisation Programme / NCVBDC public guidance",
    ),
    Card(
        "scrub_typhus", "Scrub typhus",
        ("scrub typhus", "black scab", "mite", "eschar", "bushes", "jungle", "field work"),
        (
            "Scrub typhus is spread by tiny mite bites in bushes, fields and grassy areas. It is seen in hilly states like Mizoram, Manipur, Nagaland and Meghalaya.",
            "It causes fever, headache and body ache. Sometimes a small black scab appears where the mite bit.",
            "It is treatable with the correct medicine from a doctor, so early testing matters.",
            "Wear full sleeves and long trousers when working in fields or bushes.",
        ),
        ("Fever after working in fields or bushes, especially with a black scab, needs a doctor's check soon.",),
        "Public guidance from Indian state health departments / ICMR",
    ),
    Card(
        "diarrhoea", "Diarrhoea and ORS",
        ("diarrhoea", "diarrhea", "loose motion", "loose stool", "dast", "vomiting", "ors", "dehydration", "stomach upset"),
        (
            "Diarrhoea makes the body lose water and salt. The main danger is dehydration.",
            "Give ORS (oral rehydration solution). Mix one ORS packet in clean water exactly as written on the packet.",
            "Zinc tablets for children with diarrhoea are given free at government health centres; ask the ASHA or health worker.",
            "Keep breastfeeding babies and keep giving food.",
        ),
        (
            "Blood in stool, very little urine, sunken eyes, very weak or drowsy, or unable to drink.",
            "Diarrhoea lasting more than 2 days, or in a baby.",
        ),
        "WHO / UNICEF ORS and zinc guidance; MoHFW",
    ),
    Card(
        "safe_water", "Safe drinking water and hygiene",
        ("water", "drinking water", "boil", "hygiene", "wash hands", "handwashing", "sanitation", "toilet", "prevent diarrhoea", "prevent diarrhea"),
        (
            "Boil drinking water for at least one minute, or use a trusted filter or chlorine tablets.",
            "Store water in a clean covered container and take it out with a ladle, not hands.",
            "Wash hands with soap before eating, before cooking, and after using the toilet.",
            "Use a toilet, and keep food covered from flies.",
        ),
        ("If several people in a village get diarrhoea at the same time, inform the ASHA or health centre.",),
        "WHO water, sanitation and hygiene guidance",
    ),
    Card(
        "child_cough", "Child cough and pneumonia warning signs",
        ("cough", "cold", "child cough", "baby cough", "pneumonia", "fast breathing", "khansi"),
        (
            "Most coughs and colds in children get better in a few days with rest, fluids and continued feeding.",
            "Keep the child warm and keep breastfeeding.",
            "Do not give cough medicines to small children without a doctor's advice.",
        ),
        (
            "Fast breathing, the chest pulling in while breathing, or a grunting sound.",
            "Unable to drink or breastfeed, vomits everything, very sleepy, or has fits. These are danger signs and need a hospital now.",
            "Cough lasting more than 2 weeks.",
        ),
        "WHO Integrated Management of Childhood Illness (IMCI) danger signs",
    ),
    Card(
        "tb", "Long cough and tuberculosis (TB)",
        ("tuberculosis", "tb", "two weeks", "2 weeks", "long cough", "weight loss", "night sweats", "coughing blood"),
        (
            "A cough lasting 2 weeks or more can be TB, especially with fever, weight loss or night sweats.",
            "TB testing and full treatment are free at government health centres.",
            "TB can be cured if the full course of medicine is completed.",
        ),
        ("Cough for 2 weeks or more, or coughing blood, needs a test at the health centre.",),
        "National TB Elimination Programme public guidance",
    ),
    Card(
        "pregnancy", "Pregnancy care and danger signs",
        ("pregnant", "pregnancy", "garbh", "antenatal", "delivery", "baby kick", "expecting"),
        (
            "Register the pregnancy early with the ASHA or health centre and attend all check-ups.",
            "Eat a variety of foods and take the iron and folic acid tablets given at the health centre.",
            "Plan to deliver at a hospital or health centre. Government schemes support free institutional delivery and transport.",
        ),
        (
            "Bleeding, severe headache, blurred vision, fits, high fever, severe stomach pain, swelling of the face or hands, or the baby moving less. These are danger signs: go to a hospital immediately.",
        ),
        "MoHFW maternal health guidance (JSSK / PMSMA public information)",
    ),
    Card(
        "snakebite", "Snakebite first aid",
        ("snake", "snakebite", "bite", "saanp", "xaap"),
        (
            "Keep the person calm and still. Movement spreads venom faster.",
            "Remove rings, bangles and tight clothing near the bite.",
            "Do not cut the wound, suck it, tie a tight band, or use herbs or a traditional healer. This wastes precious time.",
            "Take the person to a hospital immediately. Anti-snake venom is the only proven treatment.",
        ),
        ("Every snakebite is an emergency, even if the person feels fine at first.",),
        "WHO snakebite guidance / MoHFW",
    ),
    Card(
        "nutrition_hydration", "Hydration and nutrition",
        ("food", "diet", "nutrition", "eat", "weak", "weakness", "hydration", "thirst", "anaemia", "anemia"),
        (
            "Drink enough clean water through the day, more in hot weather or when you have fever or diarrhoea.",
            "Eat a mix of rice or other grains, dal or beans, green leafy vegetables, fruits, and eggs, fish or meat if you eat them.",
            "Tiredness and pale skin can be signs of anaemia. A simple blood test at the health centre can check this.",
        ),
        ("Weakness that does not improve, fainting, or breathlessness on small effort.",),
        "MoHFW / ICMR-NIN dietary guidance (general)",
    ),
    Card(
        "elderly_bp", "Healthy ageing, blood pressure and sugar",
        ("blood pressure", "bp", "sugar", "diabetes", "old age", "elderly", "grandmother", "grandfather"),
        (
            "Adults over 30 can get free BP and sugar checks at Ayushman Arogya Mandir (health and wellness centres).",
            "Less salt, regular walking, and avoiding tobacco and alcohol help keep blood pressure healthy.",
            "If you already take medicine for BP or sugar, do not stop or change it without your doctor.",
        ),
        ("Sudden severe headache, chest pain, weakness on one side, or confusion is an emergency.",),
        "National Programme for Prevention and Control of NCDs (public guidance)",
    ),
    Card(
        "headache", "Headache and tension",
        ("headache", "head pain", "head ache", "head hurts", "sardard", "sir dard", "muror bikh", "matha betha"),
        (
            "Most headaches are tension headaches or due to tiredness, dehydration, eye strain or lack of sleep.",
            "Resting in a quiet, dark room and drinking clean water often helps ease routine headaches.",
            "Avoid taking repeated unprescribed painkillers from shops, as overuse can cause rebound headaches and harm the stomach.",
        ),
        (
            "Sudden thunderclap headache (worst headache of your life).",
            "Headache with fever, stiff neck, vomiting, or confusion.",
            "Headache accompanied by weakness on one side of the body, slurred speech, or vision changes.",
            "Headache following a head injury or in a pregnant woman.",
        ),
        "WHO / NHS public guidance on headache assessment",
    ),
    Card(
        "poisoning", "Suspected poisoning and chemical safety",
        ("poison", "poisoning", "toxic", "pesticide", "insecticide", "kerosene", "chemical", "zahar", "keetnashak"),
        (
            "Any ingestion of poison, agricultural pesticides, kerosene, or overdose of medicines is a critical emergency.",
            "Do NOT induce vomiting unless specifically instructed by a medical doctor, as vomiting caustic chemicals can burn the food pipe or enter lungs.",
            "Do not give home remedies, raw eggs, or large volumes of water or salt.",
            "Keep all agricultural chemicals, pesticides, and medicines in locked containers away from children.",
        ),
        (
            "Take the person to the nearest emergency hospital immediately and bring the bottle, packet, or chemical container along.",
        ),
        "WHO / AIIMS National Poisons Information Centre guidance",
    ),
    Card(
        "medicine_safety", "Medicine safety",
        ("medicine", "medicines", "medication", "tablet", "tablets", "antibiotic", "dose", "dosage", "injection",
         "drug", "overdose", "painkiller", "prescription", "pharmacy", "syrup", "paracetamol", "dawai"),
        (
            "Take medicines only as advised by a doctor or health worker. Only they can choose a medicine and the amount after seeing you.",
            "If you already have a prescription, follow it, and ask the pharmacist to explain how and when to take it.",
            "Do not share medicines or use leftover antibiotics. Wrong use makes future infections harder to treat.",
            "Tell the doctor if you are pregnant, breastfeeding, or already taking other medicines.",
            "Painkillers bought at a shop can harm the stomach, liver or kidneys if taken often. Ask before using them regularly.",
            "Check the expiry date, and keep all medicines and pesticides locked away from children.",
        ),
        ("If someone swallowed too many tablets or a chemical, go to a hospital immediately.",
         "If a medicine causes a rash, swelling of the face, or trouble breathing, stop and get help at once."),
        "WHO / MoHFW rational medicine use guidance",
    ),
]

_word = re.compile(r"[a-z0-9]+")
_BY_ID = {c.id: c for c in CARDS}


def by_id(card_id: str) -> Card:
    return _BY_ID[card_id]


def retrieve(english_text: str, k: int = 2) -> list[Card]:
    """Tiny keyword retriever: good enough for a 15-card knowledge base and
    fully explainable to judges. Swap for embeddings when the base grows."""
    text = english_text.lower()
    tokens = set(_word.findall(text))
    scored = []
    for card in CARDS:
        score = 0
        for kw in card.keywords:
            if " " in kw:
                score += 3 if kw in text else 0
            elif kw in tokens:
                score += 2
            elif len(kw) > 4 and kw in text:
                score += 1
        if score:
            scored.append((score, card))
    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:k]]


def render_for_prompt(cards: list[Card]) -> str:
    if not cards:
        return "(No specific notes for this question.)"
    parts = []
    for c in cards:
        parts.append(
            f"[NOTE {c.id}] {c.title}\nFacts:\n- " + "\n- ".join(c.facts)
            + "\nSeek care when:\n- " + "\n- ".join(c.seek_care) + f"\nSource: {c.source}"
        )
    return "\n\n".join(parts)
