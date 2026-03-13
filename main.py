from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import receipts, deductions, health
import os

app = FastAPI(
    title="Sliick API",
    description="Receipt parsing, deduction detection and price mapping for Sliick",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
app.include_router(deductions.router, prefix="/deductions", tags=["deductions"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)