from fastapi import APIRouter
import os

router = APIRouter()


@router.get("/")
async def root():
    return {"status": "ok", "service": "sliick-api"}


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "ocr_backend": "google_vision" if os.getenv("GOOGLE_VISION_API_KEY") else "tesseract",
        "supabase_url": os.getenv("SUPABASE_URL", "not set"),
        "supabase_key_set": bool(os.getenv("SUPABASE_SERVICE_KEY")),
    }