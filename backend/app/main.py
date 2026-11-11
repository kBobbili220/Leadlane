from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.services import router as services_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.core.config import PROJECT_ROOT

app = FastAPI(title="Service Business API", version="0.1.0")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(services_router, prefix="/api/v1")
app.mount(
    "/onboarding",
    StaticFiles(directory=PROJECT_ROOT / "mobile" / "public", html=True),
    name="onboarding",
)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    if request.url.path.startswith("/api/v1/auth/"):
        # Pydantic errors can include the original input. Never echo passwords.
        details = [{key: value for key, value in item.items() if key in ("type", "loc", "msg")}
                   for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(details)})
    return await request_validation_exception_handler(request, error)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Service Business API"}


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
