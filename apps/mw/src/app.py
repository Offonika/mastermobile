from fastapi import FastAPI

from .api.routes import returns as returns_routes
from .api.routes import system as system_routes
from .api.schemas.returns import Health
from .db.session import init_db
from .health import get_health_payload

app = FastAPI(title="MasterMobile MW")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health", response_model=Health)
async def health() -> Health:
    """Simple health-check endpoint used by smoke tests."""

    return Health.model_validate(get_health_payload())


app.include_router(system_routes.router)
app.include_router(returns_routes.router)
