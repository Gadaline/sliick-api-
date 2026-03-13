import re
from datetime import date
from typing import Optional
from models.schemas import ParsedReceipt, ReceiptItem, Currency
from services.ocr import _extract_total, _extract_date, _parse_amount

SENDER_MERCHANTS = {
    "amazon": "Amazon",
    "amzn": "Amazon",
    "apple": "Apple",
    "paypal": "PayPal",
    "zalando": "Zalando",
    "booking": "Booking.com",
    "airbnb": "Airbnb",
    "uber": "Uber",
    "deliveroo": "Deliveroo",
    "glovo": "Glovo",
    "esselunga": "Esselunga",
    "trenitalia": "Trenitalia",
    "italo": "Italo Treno",
    "ryanair": "Ryanair",
    "easyjet": "EasyJet",
}


def _html_to_text(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<(br|p|div|tr|li|h[1-6])[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace("&euro;", "€")
    html = html.replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r" {2,}", " ", html)).strip()


def _merchant_from_sender(sender: str) -> Optional[str]:
    sender_lower = sender.lower()
    for key, name in SENDER_MERCHANTS.items():
        if key in sender_lower:
            return name
    m = re.search(r"@([a-z0-9\-]+)\.", sender_lower)
    if m:
        return m.group(1).replace("-", " ").title()
    return None


def _extract_order_items_from_email(text: str) -> list[ReceiptItem]:
    items = []
    pattern = r"^(.{5,60}?)\s+x?(\d+)\s+[€$£]?\s*(\d+[.,]\d{2})"
    for line in text.split("\n"):
        m = re.match(pattern, line.strip(), re.IGNORECASE)
        if m:
            try:
                qty = float(m.group(2))
                price = _parse_amount(m.group(3))
                items.append(ReceiptItem(
                    description=m.group(1).strip(),
                    quantity=qty,
                    unit_price=price / qty if qty else price,
                    total_price=price,
                ))
            except (ValueError, ZeroDivisionError):
                continue
    return items


def process_email(sender: str, subject: str, body_text: str, body_html: Optional[str] = None) -> ParsedReceipt:
    if body_html:
        text = _html_to_text(body_html)
        text = body_text + "\n" + text
    else:
        text = body_text

    merchant = _merchant_from_sender(sender) or None
    receipt_date = _extract_date(subject + "\n" + text)
    total = _extract_total(text)
    items = _extract_order_items_from_email(text)

    if not total and items:
        total = round(sum(i.total_price for i in items), 2)

    return ParsedReceipt(
        merchant_name=merchant,
        date=receipt_date,
        items=items,
        total_amount=total or 0.0,
        currency=Currency.EUR,
        raw_text=text[:2000],
        confidence=0.75 if total else 0.3,
    )