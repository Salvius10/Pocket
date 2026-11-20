"""Auth. Public routes: Firebase ID token (demo) or X-Dev-User (local only). Internal routes: shared token."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from core_api import models as m
from core_api.config import get_settings
from core_api.db import get_session
from core_api.ledger.context import Ctx, load_ctx

Session = Annotated[AsyncSession, Depends(get_session)]


def _verify_firebase(token: str, project_id: str) -> str:
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    claims = id_token.verify_firebase_token(token, g_requests.Request(), audience=project_id)  # type: ignore[no-untyped-call]
    if not claims or not claims.get("sub"):
        raise ValueError("invalid token")
    return str(claims["sub"])


async def _uid_from_request(authorization: str | None, x_dev_user: str | None) -> str:
    settings = get_settings()
    if settings.auth_mode == "dev":
        if not x_dev_user or len(x_dev_user) > 100:
            raise HTTPException(401, "X-Dev-User header required in dev auth mode")
        return f"dev:{x_dev_user}"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "sign-in required")
    try:
        return await run_in_threadpool(_verify_firebase, authorization[7:].strip(), settings.firebase_project_id)
    except Exception as exc:  # any verification failure is a 401, never a 500
        raise HTTPException(401, "sign-in expired or invalid") from exc


async def get_or_create_user(session: AsyncSession, uid: str) -> m.User:
    user = (await session.execute(select(m.User).where(m.User.firebase_uid == uid))).scalars().first()
    if user is None:
        user = m.User(firebase_uid=uid)
        session.add(user)
        await session.flush()
        session.add(m.UserSettings(user_id=user.id))
        await session.commit()
    return user


async def current_user(
    session: Session,
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user: Annotated[str | None, Header()] = None,
) -> m.User:
    return await get_or_create_user(session, await _uid_from_request(authorization, x_dev_user))


CurrentUser = Annotated[m.User, Depends(current_user)]


async def user_ctx(session: Session, user: CurrentUser) -> Ctx:
    return await load_ctx(session, user)


UserCtx = Annotated[Ctx, Depends(user_ctx)]


def require_internal(x_internal_token: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().internal_token
    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(403, "internal endpoint")


async def internal_user(
    session: Session,
    _: Annotated[None, Depends(require_internal)],
    x_pocket_user_id: Annotated[str | None, Header()] = None,
) -> m.User:
    user = await session.get(m.User, x_pocket_user_id) if x_pocket_user_id else None
    if user is None:
        raise HTTPException(404, "user not found")
    return user


InternalUser = Annotated[m.User, Depends(internal_user)]


async def resolve_token_user(session: AsyncSession, token: str | None, dev_user: str | None) -> m.User:
    """Used by the agent to turn the phone's hello token into a user id."""
    return await get_or_create_user(session, await _uid_from_request(f"Bearer {token}" if token else None, dev_user))
