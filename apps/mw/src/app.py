# filename: apps/mw/src/app.py
from fastapi import FastAPI

from .health import get_health_payload

app = FastAPI(title="MasterMobile MW")


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple health-check endpoint used by smoke tests."""
    return get_health_payload()
