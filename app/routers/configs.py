"""配置项管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.config_item import ConfigCreate, ConfigStatusUpdate, ConfigUpdate
from app.services.config_item import ConfigService

router = APIRouter(prefix="/api/configs", tags=["config-items"])


@router.get("")
async def list_configs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    env: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ConfigService.list_configs(session, limit=limit, offset=offset, env=env,
                                          status_filter=status_filter, keyword=keyword)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_config(
    payload: ConfigCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ConfigService.create_config(session, payload, request)


@router.get("/{config_id}")
async def get_config(
    config_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ConfigService.get_config(session, config_id)


@router.patch("/{config_id}")
async def update_config(
    config_id: str, payload: ConfigUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ConfigService.update_config(session, config_id, payload, request)


@router.patch("/{config_id}/status")
async def change_config_status(
    config_id: str, payload: ConfigStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ConfigService.change_status(session, config_id, payload, request)


@router.delete("/{config_id}")
async def delete_config(
    config_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ConfigService.delete_config(session, config_id, request)
