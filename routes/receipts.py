from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional

from models.schemas import (
    ManualReceiptInput, EmailReceiptInput,
    ReceiptWithDeduction, SupabaseReceiptPayload,
)
from services import ocr, pdf_parser, email_parser
from services.deduction_engine import analyze_receipt
from services.supabase_service import insert_receipt, insert_receipt_items

router = APIRouter()


def _build_payload(user_id: str, receipt, deduction) -> SupabaseReceiptPayload:
    return SupabaseReceiptPayload(
        user_id=user_id,
        merchant_name=receipt.merchant_name,
        total_amount=receipt.total_amount,
        currency=receipt.currency.value,
        date=receipt.date,
        category=receipt.category,
        raw_text=receipt.raw_text,
        is_deductible=deduction.is_deductible,
        deduction_category=deduction.category.value if deduction.is_deductible else None,
        deduction_rate=deduction.deduction_rate if deduction.is_deductible else None,
        deductible_amount=deduction.deductible_amount if deduction.is_deductible else None,
        tax_saving_estimate=deduction.tax_saving_estimate if deduction.is_deductible else None,
    )


@router.post("/upload/image", response_model=ReceiptWithDeduction)
async def upload_image(
    file: UploadFile = File(...),
    user_id: str = Header(..., alias="X-User-Id"),
    save_to_db: bool = True,
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "File must be an image (JPEG or PNG)")
    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 10MB)")
    try:
        receipt = await ocr.process_image(image_bytes)
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {e}")
    deduction = analyze_receipt(receipt)
    result = ReceiptWithDeduction(receipt=receipt, deduction=deduction)
    if save_to_db:
        try:
            payload = _build_payload(user_id, receipt, deduction)
            db_row = await insert_receipt(payload)
            if receipt.items and db_row.get("id"):
                items_data = [item.model_dump(mode="json") for item in receipt.items]
                await insert_receipt_items(db_row["id"], items_data)
        except Exception as e:
            print(f"[WARN] DB write failed: {e}")
    return result


@router.post("/upload/pdf", response_model=ReceiptWithDeduction)
async def upload_pdf(
    file: UploadFile = File(...),
    user_id: str = Header(..., alias="X-User-Id"),
    save_to_db: bool = True,
):
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(400, "File must be a PDF")
    pdf_bytes = await file.read()
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise HTTPException(413, "PDF too large (max 20MB)")
    try:
        receipt = await pdf_parser.process_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(500, f"PDF parsing failed: {e}")
    deduction = analyze_receipt(receipt)
    result = ReceiptWithDeduction(receipt=receipt, deduction=deduction)
    if save_to_db:
        try:
            payload = _build_payload(user_id, receipt, deduction)
            db_row = await insert_receipt(payload)
            if receipt.items and db_row.get("id"):
                items_data = [item.model_dump(mode="json") for item in receipt.items]
                await insert_receipt_items(db_row["id"], items_data)
        except Exception as e:
            print(f"[WARN] DB write failed: {e}")
    return result


@router.post("/upload/email", response_model=ReceiptWithDeduction)
async def upload_email(
    body: EmailReceiptInput,
    save_to_db: bool = True,
):
    try:
        receipt = email_parser.process_email(
            sender=body.sender,
            subject=body.subject,
            body_text=body.body_text,
            body_html=body.body_html,
        )
    except Exception as e:
        raise HTTPException(500, f"Email parsing failed: {e}")
    deduction = analyze_receipt(receipt)
    result = ReceiptWithDeduction(receipt=receipt, deduction=deduction)
    if save_to_db:
        try:
            payload = _build_payload(body.user_id, receipt, deduction)
            db_row = await insert_receipt(payload)
            if receipt.items and db_row.get("id"):
                items_data = [item.model_dump(mode="json") for item in receipt.items]
                await insert_receipt_items(db_row["id"], items_data)
        except Exception as e:
            print(f"[WARN] DB write failed: {e}")
    return result


@router.post("/manual", response_model=ReceiptWithDeduction)
async def manual_entry(
    body: ManualReceiptInput,
    save_to_db: bool = True,
):
    from models.schemas import ParsedReceipt
    receipt = ParsedReceipt(
        merchant_name=body.merchant_name,
        date=body.date,
        total_amount=body.total_amount,
        currency=body.currency,
        category=body.category,
        items=body.items,
        confidence=1.0,
    )
    deduction = analyze_receipt(receipt)
    result = ReceiptWithDeduction(receipt=receipt, deduction=deduction)
    if save_to_db:
        try:
            payload = _build_payload(body.user_id, receipt, deduction)
            db_row = await insert_receipt(payload)
            if receipt.items and db_row.get("id"):
                items_data = [item.model_dump(mode="json") for item in receipt.items]
                await insert_receipt_items(db_row["id"], items_data)
        except Exception as e:
            print(f"[WARN] DB write failed: {e}")
    return result
