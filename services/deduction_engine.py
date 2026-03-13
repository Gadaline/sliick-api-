from models.schemas import ParsedReceipt, DeductionResult, DeductionCategory
from typing import Optional

DEDUCTION_RULES = {
    DeductionCategory.spese_mediche: {
        "rate": 0.19,
        "franchise": 129.11,
        "cap": None,
        "tuir": "Art. 15, c.1, lett. c) TUIR",
        "notes": "Detrazione 19% sulla spesa eccedente €129,11.",
    },
    DeductionCategory.istruzione: {
        "rate": 0.19,
        "franchise": 0,
        "cap": 800.0,
        "tuir": "Art. 15, c.1, lett. e) TUIR",
        "notes": "Detrazione 19% su spese scolastiche e universitarie.",
    },
    DeductionCategory.interessi_mutuo: {
        "rate": 0.19,
        "franchise": 0,
        "cap": 4000.0,
        "tuir": "Art. 15, c.1, lett. b) TUIR",
        "notes": "Detrazione 19% sugli interessi passivi del mutuo prima casa.",
    },
    DeductionCategory.spese_veterinarie: {
        "rate": 0.19,
        "franchise": 129.11,
        "cap": 387.34,
        "tuir": "Art. 15, c.1, lett. c-bis) TUIR",
        "notes": "Detrazione 19% su spese veterinarie.",
    },
    DeductionCategory.erogazioni_liberali: {
        "rate": 0.26,
        "franchise": 0,
        "cap": 30000.0,
        "tuir": "Art. 15, c.1, lett. i-bis) TUIR",
        "notes": "Detrazione 26% per donazioni a ONLUS ed ETS.",
    },
    DeductionCategory.ristrutturazione: {
        "rate": 0.50,
        "franchise": 0,
        "cap": 96000.0,
        "tuir": "Art. 16-bis TUIR",
        "notes": "Detrazione 50% su spese di ristrutturazione.",
    },
    DeductionCategory.bonus_mobili: {
        "rate": 0.50,
        "franchise": 0,
        "cap": 8000.0,
        "tuir": "Art. 16, c.2 TUIR",
        "notes": "Detrazione 50% acquisto mobili ed elettrodomestici.",
    },
    DeductionCategory.spese_funebri: {
        "rate": 0.19,
        "franchise": 0,
        "cap": 1550.0,
        "tuir": "Art. 15, c.1, lett. d) TUIR",
        "notes": "Detrazione 19% su spese funebri.",
    },
    DeductionCategory.spese_sportive_figli: {
        "rate": 0.19,
        "franchise": 0,
        "cap": 210.0,
        "tuir": "Art. 15, c.1, lett. i-quinquies) TUIR",
        "notes": "Detrazione 19% su attività sportive figli 5-18 anni.",
    },
}

CATEGORY_KEYWORDS = {
    DeductionCategory.spese_mediche: [
        "farmacia", "farmacie", "farmaco", "medicinale", "medico", "dottore",
        "ospedale", "clinica", "dentista", "odontoiatra", "oculista", "fisioterapia",
        "laboratorio analisi", "analisi cliniche", "radiologia", "ecografia",
        "visita medica", "pronto soccorso", "asl", "ssn",
        "pharmacy", "medical", "doctor", "hospital", "dentist",
    ],
    DeductionCategory.istruzione: [
        "università", "universita", "university", "scuola", "school", "liceo",
        "istituto", "college", "tasse universitarie", "retta", "corso",
        "formazione", "libri scolastici", "materiale didattico",
    ],
    DeductionCategory.interessi_mutuo: [
        "mutuo", "banca", "interessi", "rata mutuo", "mortgage", "bank",
    ],
    DeductionCategory.spese_veterinarie: [
        "veterinario", "veterinaria", "vet", "clinica veterinaria",
        "animale", "cane", "gatto", "pet",
    ],
    DeductionCategory.erogazioni_liberali: [
        "onlus", "associazione", "donazione", "charity", "fondazione",
        "croce rossa", "caritas", "beneficenza",
    ],
    DeductionCategory.ristrutturazione: [
        "ristrutturazione", "edilizia", "muratore", "idraulico", "elettricista",
        "impresa edile", "infissi", "caldaia", "impianto",
    ],
    DeductionCategory.bonus_mobili: [
        "arredamento", "mobili", "ikea", "furniture", "elettrodomestici",
        "lavatrice", "frigorifero", "lavastoviglie",
        "media world", "unieuro", "expert",
    ],
    DeductionCategory.spese_funebri: [
        "onoranze funebri", "pompe funebri", "funerale", "cimitero",
    ],
    DeductionCategory.spese_sportive_figli: [
        "palestra", "piscina", "calcio", "tennis", "nuoto", "sport",
        "associazione sportiva", "asd", "sci", "karate", "danza",
    ],
}


def detect_category(receipt: ParsedReceipt) -> DeductionCategory:
    text_pool = " ".join(filter(None, [
        (receipt.merchant_name or "").lower(),
        (receipt.category or "").lower(),
        (receipt.raw_text or "").lower(),
        " ".join(item.description.lower() for item in receipt.items),
    ]))

    scores: dict[DeductionCategory, int] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_pool)
        if score > 0:
            scores[category] = score

    if not scores:
        return DeductionCategory.none

    return max(scores, key=lambda c: scores[c])


def calculate_deduction(category: DeductionCategory, amount: float) -> DeductionResult:
    if category == DeductionCategory.none:
        return DeductionResult(
            is_deductible=False,
            category=DeductionCategory.none,
        )

    rule = DEDUCTION_RULES[category]
    rate: float = rule["rate"]
    franchise: float = rule["franchise"]
    cap: Optional[float] = rule["cap"]

    eligible = max(0.0, amount - franchise)
    if cap is not None:
        eligible = min(eligible, cap)

    deductible_amount = round(eligible, 2)
    tax_saving = round(eligible * rate, 2)

    return DeductionResult(
        is_deductible=deductible_amount > 0,
        category=category,
        deduction_rate=rate,
        deductible_amount=deductible_amount,
        tax_saving_estimate=tax_saving,
        notes=rule["notes"],
        tuir_reference=rule["tuir"],
    )


def analyze_receipt(receipt: ParsedReceipt) -> DeductionResult:
    category = detect_category(receipt)
    return calculate_deduction(category, receipt.total_amount)