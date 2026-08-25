"""FastAPI application for the HSE inspection analysis service."""

from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI-assisted analysis of HSE inspection media.",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}
