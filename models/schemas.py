from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"


class ReceiptStatus(str, Enum):
    pending = "pending"
    processed = "processed"
    failed = "failed"


class ReceiptItem(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    total_price: float
    category: Optional[str] = None


class ParsedReceipt(BaseModel):
    merchant_name: Optional[str] = None
    merchant_address: Optional[str] = None
    merchant_vat: Optional[str] = None
    date: Optional[date] = None
    time: Optional[str] = None
    items: List[ReceiptItem] = []
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: float
    currency: Currency = Currency.EUR
    category: Optional[str] = None
    raw_text: Optional[str] = None
    confidence: float = 0.0


class DeductionCategory(str, Enum):
    spese_mediche = "spese_mediche"
    istruzione = "istruzione"
    interessi_mutuo = "interessi_mutuo"
    spese_veterinarie = "spese_veterinarie"
    erogazioni_liberali = "erogazioni_liberali"
    ristrutturazione = "ristrutturazione"
    bonus_mobili = "bonus_mobili"
    spese_funebri = "spese_funebri"
    spese_sportive_figli = "spese_sportive_figli"
    none = "none"


class DeductionResult(BaseModel):
    is_deductible: bool
    category: DeductionCategory
    deduction_rate: float = 0.0
    deductible_amount: float = 0.0
    tax_saving_estimate: float = 0.0
    notes: Optional[str] = None
    tuir_reference: Optional[str] = None


class ReceiptWithDeduction(BaseModel):
    receipt: ParsedReceipt
    deduction: DeductionResult


class ManualReceiptInput(BaseModel):
    merchant_name: str
    date: date
    total_amount: float
    currency: Currency = Currency.EUR
    category: Optional[str] = None
    items: List[ReceiptItem] = []
    user_id: str


class EmailReceiptInput(BaseModel):
    sender: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    user_id: str


class SupabaseReceiptPayload(BaseModel):
    user_id: str
    merchant_name: Optional[str]
    total_amount: float
    currency: str = "EUR"
    date: Optional[date]
    category: Optional[str]
    status: ReceiptStatus = ReceiptStatus.processed
    raw_text: Optional[str]
    is_deductible: bool = False
    deduction_category: Optional[str] = None
    deduction_rate: Optional[float] = None
    deductible_amount: Optional[float] = None
    tax_saving_estimate: Optional[float] = None