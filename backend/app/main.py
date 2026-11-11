from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.services import router as services_router
from backend.app.core.config import PROJECT_ROOT

app = FastAPI(title="Service Business API", version="0.1.0")
app.include_router(services_router, prefix="/api/v1")
app.mount(
    "/onboarding",
    StaticFiles(directory=PROJECT_ROOT / "mobile" / "public", html=True),
    name="onboarding",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Service Business API"}


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
