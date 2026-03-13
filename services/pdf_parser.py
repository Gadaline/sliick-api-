import io
from models.schemas import ParsedReceipt
from services.ocr import parse_receipt_text, process_image


async def process_pdf(pdf_bytes: bytes) -> ParsedReceipt:
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber not installed. Run: pip install pdfplumber")

    text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    if text.strip():
        return parse_receipt_text(text.strip(), confidence=0.95)

    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=200)
        if images:
            import io as _io
            buf = _io.BytesIO()
            images[0].save(buf, format="PNG")
            return await process_image(buf.getvalue())
    except ImportError:
        pass

    return ParsedReceipt(
        total_amount=0.0,
        raw_text="",
        confidence=0.0,
    )