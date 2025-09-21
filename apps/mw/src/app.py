from fastapi import FastAPI

from .health import get_health_payload, get_ping_payload

app = FastAPI(title="MasterMobile MW")


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple health-check endpoint used by smoke tests."""
    return get_health_payload()


@app.get("/api/v1/system/ping")
async def system_ping() -> dict[str, str]:
    """Return the middleware status along with a UTC timestamp."""
    return get_ping_payload()
