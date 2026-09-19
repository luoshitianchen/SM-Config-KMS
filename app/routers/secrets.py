"""密钥版本管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.secret_version import SecretCreate
from app.services.secret_version import SecretService

router = APIRouter(prefix="/api/secrets", tags=["secret-versions"])


@router.get("/{secret_name}/versions")
async def list_versions(
    secret_name: str, request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SecretService.list_versions(session, secret_name, limit=limit, offset=offset)


@router.get("/{secret_name}/active")
async def get_active(
    secret_name: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SecretService.get_active(session, secret_name)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_version(
    payload: SecretCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SecretService.create_version(session, payload, request)


@router.get("/{secret_name}/reveal")
async def reveal(
    secret_name: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await SecretService.reveal(session, secret_name, request)
