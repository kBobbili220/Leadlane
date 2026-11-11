from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from backend.app.api.dependencies import BearerToken, CurrentOwner, DatabaseSession
from backend.app.core.config import Settings, get_settings
from backend.app.schemas.auth import AuthIdentityRead, AuthTokenRead, LoginRequest, RegisterRequest
from backend.app.services import auth

router = APIRouter(prefix="/auth", tags=["authentication"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post("/register", response_model=AuthTokenRead, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, session: DatabaseSession, settings: AppSettings) -> AuthTokenRead:
    response.headers["Cache-Control"] = "no-store"
    ip = request.client.host if request.client else "unknown"
    auth.enforce_rate_limits(session, [("register_ip", ip, 5, 3600)])
    return auth.register(session, payload, settings)


@router.post("/login", response_model=AuthTokenRead)
def login(payload: LoginRequest, request: Request, response: Response, session: DatabaseSession, settings: AppSettings) -> AuthTokenRead:
    response.headers["Cache-Control"] = "no-store"
    ip = request.client.host if request.client else "unknown"
    auth.enforce_rate_limits(session, [("login_email", str(payload.email), 10, 900), ("login_ip", ip, 60, 900)])
    return auth.login(session, str(payload.email), payload.password.get_secret_value(), settings)


@router.get("/me", response_model=AuthIdentityRead)
def me(owner: CurrentOwner, response: Response) -> AuthIdentityRead:
    response.headers["Cache-Control"] = "no-store"
    return auth.identity(owner)


@router.post("/logout", status_code=204)
def logout(token: BearerToken, session: DatabaseSession) -> Response:
    auth.logout(session, token)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
