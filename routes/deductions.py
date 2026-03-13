from fastapi import APIRouter
from models.schemas import ParsedReceipt, DeductionResult, DeductionCategory
from services.deduction_engine import analyze_receipt, calculate_deduction, DEDUCTION_RULES

router = APIRouter()


@router.post("/analyze", response_model=DeductionResult)
async def analyze(receipt: ParsedReceipt):
    """Analyze a parsed receipt for Italian tax deductions."""
    return analyze_receipt(receipt)


@router.get("/categories")
async def list_categories():
    """List all supported Italian deduction categories with TUIR references."""
    return [
        {
            "category": cat.value,
            "rate": rule["rate"],
            "franchise": rule["franchise"],
            "cap": rule["cap"],
            "tuir_reference": rule["tuir"],
            "notes": rule["notes"],
        }
        for cat, rule in DEDUCTION_RULES.items()
    ]


@router.get("/calculate")
async def calculate(category: DeductionCategory, amount: float):
    """Calculate deduction for a given category and amount."""
    return calculate_deduction(category, amount)