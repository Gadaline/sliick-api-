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
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img, lang="ita+eng")
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed: {e}")


async def extract_text(image_bytes: bytes) -> str:
    if os.getenv("GOOGLE_VISION_API_KEY"):
        try:
            return await _ocr_google_vision(image_bytes)
        except Exception:
            pass
    return _ocr_tesseract(image_bytes)


DATE_PATTERNS = [
    r"\b(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{4})\b",
    r"\b(\d{4})[\/\-\.](\d{2})[\/\-\.](\d{2})\b",
    r"\b(\d{2})[\/\-\.](\d{2})[\/\-\.](\d{2})\b",
]

TOTAL_PATTERNS = [
    r"(?:totale|total|tot\.?|amount due|importo)\s*[:\s€$£]?\s*(\d+[.,]\d{2})",
    r"(?:da pagare|to pay|zu zahlen|à payer)\s*[:\s€$£]?\s*(\d+[.,]\d{2})",
    r"€\s*(\d+[.,]\d{2})\s*$",
]


def _parse_amount(s: str) -> float:
    s = s.strip()
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
    for pattern in TOTAL_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                return _parse_amount(m.group(1))
            except ValueError:
                continue
    amounts = re.findall(r"€?\s*(\d{1,5}[.,]\d{2})", text)
    parsed = []
    for a in amounts:
        try:
            parsed.append(_parse_amount(a))
        except ValueError:
            pass
    return max(parsed) if parsed else None


def _extract_merchant(text: str) -> Optional[str]:
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        if re.match(r"^[A-Za-zÀ-ÿ\s&'\-\.]{4,50}$", line):
            return line.title()
    return None


def _extract_items(text: str) -> list[ReceiptItem]:
    items = []
    pattern = r"^(.{3,40}?)\s{2,}(\d+[.,]\d{2})\s*$"
    for line in text.split("\n"):
        m = re.match(pattern, line.strip(), re.IGNORECASE)
        if m:
            try:
                price = _parse_amount(m.group(2))
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