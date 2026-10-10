"""Curated health-information cards used to ground every LLM answer.

The LLM is told to answer ONLY from the retrieved cards. Content is general
public-health guidance written in plain language, aligned with widely
published WHO / Government of India messaging. No drug doses are included on
purpose. Every card must be reviewed by a qualified health professional before
any real deployment.
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
        ("blood pressure", "bp", "sugar", "diabetes", "old age", "elderly", "grandmother", "grandfather", "headache"),
        (
            "Adults over 30 can get free BP and sugar checks at Ayushman Arogya Mandir (health and wellness centres).",
            "Less salt, regular walking, and avoiding tobacco and alcohol help keep blood pressure healthy.",
            "If you already take medicine for BP or sugar, do not stop or change it without your doctor.",
        ),
        ("Sudden severe headache, chest pain, weakness on one side, or confusion is an emergency.",),
        "National Programme for Prevention and Control of NCDs (public guidance)",
    ),
    Card(
        "medicine_safety", "Medicine safety",
        ("medicine", "tablet", "antibiotic", "dose", "injection", "drug", "overdose", "painkiller"),
        (
            "Take medicines only as advised by a doctor or health worker.",
            "Do not share medicines or use leftover antibiotics. Wrong use makes future infections harder to treat.",
            "Keep all medicines and pesticides locked away from children.",
        ),
        ("If someone swallowed too many tablets or a chemical, go to a hospital immediately.",),
        "WHO / MoHFW rational medicine use guidance",
    ),
]

_word = re.compile(r"[a-z0-9]+")


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
        return "NO MATCHING CARD. You do not have vetted information for this question."
    parts = []
    for c in cards:
        parts.append(
            f"[CARD {c.id}] {c.title}\nFacts:\n- " + "\n- ".join(c.facts)
            + "\nSeek care when:\n- " + "\n- ".join(c.seek_care) + f"\nSource: {c.source}"
        )
    return "\n\n".join(parts)


def card_answer(cards: list[Card], simpler: bool = False) -> str:
    """Deterministic answer built from cards (demo mode / LLM outage)."""
    if not cards:
        return ("I do not have reliable information on that. Please speak to your ASHA worker or visit the "
                "nearest health centre. If it feels serious, call 112.")
    c = cards[0]
    n = 2 if simpler else 3
    facts = " ".join(c.facts[:n])
    care = c.seek_care[0]
    return f"{facts} See a health worker or doctor if: {care[0].lower() + care[1:]}"
