import os
import base64
import re
from datetime import date
from typing import Optional
import httpx

from models.schemas import ParsedReceipt, ReceiptItem, Currency


async def _ocr_google_vision(image_bytes: bytes) -> str:
    api_key = os.getenv("GOOGLE_VISION_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_VISION_API_KEY not set")

    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "requests": [{
            "image": {"content": b64},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
        }]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://vision.googleapis.com/v1/images:annotate?key={api_key}",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    try:
        return data["responses"][0]["fullTextAnnotation"]["text"]
    except (KeyError, IndexError):
        return ""


def _ocr_tesseract(image_bytes: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageFilter
        import io

        img = Image.open(io.BytesIO(image_bytes))

        # Convert to grayscale
        img = img.convert("L")

        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.5)

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

        # Resize if too small
        w, h = img.size
        if w < 1000:
            scale = 1000 / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        return pytesseract.image_to_string(img, lang="ita+eng", config="--psm 4")
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed: {e}")


async def extract_text(image_bytes: bytes) -> str:
    if os.getenv("GOOGLE_VISION_API_KEY"):
        try:
            return await _ocr_google_vision(image_bytes)
        except Exception:
            pass
    return _ocr_tesseract(image_bytes)


# ── Italian RT receipt patterns ───────────────────────────────────────────────

# Total patterns — Italian RT format
TOTAL_PATTERNS = [
    r"TOTALE\s+COMPLESSIVO\s*[€E]?\s*(\d+[.,]\d{2})",
    r"TOTALE\s*[€E]?\s*(\d+[.,]\d{2})",
    r"IMPORTO\s+PAGATO\s*[€E]?\s*(\d+[.,]\d{2})",
    r"TOT(?:ALE)?\s*[:\s€E]?\s*(\d+[.,]\d{2})",
    r"TOTALE\s+EURO\s*(\d+[.,]\d{2})",
    r"(?:totale|total|tot\.?|amount due|importo)\s*[:\s€$£]?\s*(\d+[.,]\d{2})",
    r"€\s*(\d+[.,]\d{2})\s*$",
]

# Date patterns
DATE_PATTERNS = [
    r"\b(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})\b",   # DD/MM/YYYY
    r"\b(\d{4})[\/\-\.](\d{2})[\/\-\.](\d{2})\b",   # YYYY-MM-DD
    r"\b(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2})\b",   # DD/MM/YY
]

# Merchant skip words — lines that are NOT merchant names
SKIP_WORDS = [
    "documento", "commerciale", "vendita", "prestazione", "descrizione",
    "prezzo", "iva", "club", "carta", "num", "bennet", "esselunga",
    "lidl", "conad", "coop", "carrefour", "via", "corso", "piazza",
    "scontrino", "ricevuta", "fiscale",
]


def _parse_amount(s: str) -> float:
    s = s.strip().replace(" ", "")
    if "," in s and "." in s:
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def _extract_date(text: str) -> Optional[date]:
    for pattern in DATE_PATTERNS:
        m = re.search(pattern, text)
        if m:
            try:
                g = m.groups()
                if len(g[0]) == 4:
                    return date(int(g[0]), int(g[1]), int(g[2]))
                else:
                    year = int(g[2])
                    if year < 100:
                        year += 2000
                    return date(year, int(g[1]), int(g[0]))
            except ValueError:
                continue
    return None


def _extract_total(text: str) -> Optional[float]:
    text_upper = text.upper()
    for pattern in TOTAL_PATTERNS:
        m = re.search(pattern, text_upper, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                val = _parse_amount(m.group(1))
                # Sanity check — receipt total should be between €0.01 and €10000
                if 0.01 <= val <= 10000:
                    return val
            except ValueError:
                continue

    # Last resort — find all monetary amounts and return the most likely total
    amounts = re.findall(r"(\d{1,5}[.,]\d{2})", text)
    parsed = []
    for a in amounts:
        try:
            v = _parse_amount(a)
            if 0.01 <= v <= 10000:
                parsed.append(v)
        except ValueError:
            pass

    if parsed:
        # Most likely total is the largest amount that appears more than once
        # (totale + importo pagato are usually the same)
        from collections import Counter
        counts = Counter(parsed)
        repeated = [v for v, c in counts.items() if c > 1]
        if repeated:
            return max(repeated)
        return max(parsed)

    return None


def _extract_merchant(text: str) -> Optional[str]:
    """Extract merchant from Italian RT receipt — usually the first bold/large word."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Known Italian supermarkets/merchants — check first 5 lines
    KNOWN_MERCHANTS = {
        "bennet": "Bennet",
        "esselunga": "Esselunga",
        "lidl": "Lidl",
        "conad": "Conad",
        "coop": "Coop",
        "carrefour": "Carrefour",
        "penny": "Penny Market",
        "eurospin": "Eurospin",
        "aldi": "Aldi",
        "farmacia": "Farmacia",
        "ipercoop": "IperCoop",
        "mediaworld": "MediaWorld",
        "unieuro": "Unieuro",
        "ikea": "IKEA",
        "zara": "Zara",
        "h&m": "H&M",
    }

    text_lower = text.lower()
    for key, name in KNOWN_MERCHANTS.items():
        if key in text_lower[:200]:  # Only check first 200 chars
            return name

    # Fall back to first meaningful line
    for line in lines[:6]:
        line_lower = line.lower()
        if any(skip in line_lower for skip in SKIP_WORDS):
            continue
        if re.match(r"^[A-Za-zÀ-ÿ\s&'\-\.]{3,40}$", line):
            return line.title()

    return None


def _extract_items(text: str) -> list[ReceiptItem]:
    """Extract line items from Italian RT receipt."""
    items = []
    # Pattern: description followed by price and optional IVA code (B, C, D)
    pattern = r"^(.{3,35}?)\s{1,}(\d+[.,]\d{2})\s*[ABCD]?\s*$"
    for line in text.split("\n"):
        line = line.strip()
        # Skip lines that are clearly not items
        if any(skip in line.upper() for skip in [
            "TOTALE", "IVA", "PAGAMENTO", "CONTANTE", "CARTA", "RESTO",
            "SCONTO Q", "PUNTI", "SALDO", "BARCODE", "SERVER", "ECR",
            "FIRMA", "DOCUMENTO", "DESCRIZIONE", "PREZZO"
        ]):
            continue
        m = re.match(pattern, line, re.IGNORECASE)
        if m:
            try:
                price = _parse_amount(m.group(2))
                if 0.01 <= price <= 1000:  # Sanity check
                    items.append(ReceiptItem(
                        description=m.group(1).strip(),
                        unit_price=price,
                        total_price=price,
                    ))
            except ValueError:
                continue
    return items


def parse_receipt_text(raw_text: str, confidence: float = 0.8) -> ParsedReceipt:
    total = _extract_total(raw_text) or 0.0
    return ParsedReceipt(
        merchant_name=_extract_merchant(raw_text),
        date=_extract_date(raw_text),
        items=_extract_items(raw_text),
        total_amount=total,
        currency=Currency.EUR,
        raw_text=raw_text,
        confidence=confidence,
    )


async def process_image(image_bytes: bytes) -> ParsedReceipt:
    raw_text = await extract_text(image_bytes)
    return parse_receipt_text(raw_text, confidence=0.85 if raw_text else 0.0)