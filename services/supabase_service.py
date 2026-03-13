import os
import httpx
from models.schemas import SupabaseReceiptPayload

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rveaebthjocqwsdpisqr.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def insert_receipt(payload: SupabaseReceiptPayload) -> dict:
    data = payload.model_dump(mode="json")
    data = {k: v for k, v in data.items() if v is not None}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/receipts",
            headers=_headers(),
            json=data,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else {}


async def insert_receipt_items(receipt_id: str, items: list[dict]) -> list[dict]:
    if not items:
        return []
    rows = [{"receipt_id": receipt_id, **item} for item in items]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/receipt_items",
            headers=_headers(),
            json=rows,
        )
        resp.raise_for_status()
        return resp.json()