"""Webapp auth routes — login, logout, whoami."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, schemas
from app.auth import (
    current_user,
    issue_session_token,
    verify_password,
)
from app.config import Settings, get_settings
from app.database import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=schemas.UserOut)
async def login(
    body: schemas.LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.UserOut:
    user = (await db.execute(
        select(models.User).where(models.User.email == body.email.lower())
    )).scalar_one_or_none()
    # Constant-time-ish: always verify against SOME hash to avoid timing leaks
    # that could enumerate valid emails.
    ok = verify_password(user.password_hash, body.password) if user else False
    if not user or not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"ok": False, "code": "invalid_credentials"},
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    token = issue_session_token(user.id, settings)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        domain=settings.cookie_domain,
        path="/",
    )
    return schemas.UserOut(id=user.id, email=user.email, display_name=user.display_name)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: Settings = Depends(get_settings)) -> Response:
    # Mirror the attributes set in /auth/login so browsers match and clear
    # the cookie rather than creating a second one with different scope.
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=schemas.UserOut)
async def me(user: models.User = Depends(current_user)) -> schemas.UserOut:
    return schemas.UserOut(id=user.id, email=user.email, display_name=user.display_name)
