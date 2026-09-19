"""配置项服务层：按环境隔离的键值管理。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.config_item import ConfigItem
from app.repositories import config_item as repo
from app.schemas.config_item import ConfigCreate, ConfigStatusUpdate, ConfigUpdate
from app.services.audit import record_audit


def _config_to_dict(c: ConfigItem) -> dict:
    return {
        "id": c.id, "config_key": c.config_key, "env": c.env,
        "value": c.value or "", "description": c.description or "", "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


class ConfigService:
    @staticmethod
    async def list_configs(session, limit, offset, env, status_filter, keyword) -> dict:
        items = await repo.list_configs(session, limit=limit, offset=offset, env=env,
                                        status=status_filter, keyword=keyword)
        total = await repo.count_configs(session, env=env, status=status_filter, keyword=keyword)
        return {"total": total, "items": [_config_to_dict(c) for c in items]}

    @staticmethod
    async def get_config(session: AsyncSession, config_id: str) -> dict:
        item = await repo.get_config(session, config_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        return _config_to_dict(item)

    @staticmethod
    async def create_config(session: AsyncSession, payload: ConfigCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_config_by_key_env(session, payload.config_key, payload.env):
            raise HTTPException(status.HTTP_409_CONFLICT, "该环境下配置键已存在")
        item = ConfigItem(
            id=str(uuid.uuid4()), config_key=payload.config_key, env=payload.env,
            value=payload.value, description=payload.description, status="active",
        )
        item = await repo.create_config(session, item)
        await record_audit(session, "config.created", "internal",
                           f"key={payload.config_key} env={payload.env}", request)
        return _config_to_dict(item)

    @staticmethod
    async def update_config(session: AsyncSession, config_id: str, payload: ConfigUpdate,
                            request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_config(session, config_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        if payload.value is not None:
            item.value = payload.value
        if payload.description is not None:
            item.description = payload.description
        item = await repo.update_config(session, item)
        await record_audit(session, "config.updated", "internal", f"config_id={config_id}", request)
        return _config_to_dict(item)

    @staticmethod
    async def change_status(session: AsyncSession, config_id: str, payload: ConfigStatusUpdate,
                            request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_config(session, config_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        if payload.status == item.status:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "目标状态与当前状态一致")
        item.status = payload.status
        item = await repo.update_config(session, item)
        await record_audit(session, "config.status_changed", "internal",
                           f"key={item.config_key} status={payload.status}", request)
        return _config_to_dict(item)

    @staticmethod
    async def delete_config(session: AsyncSession, config_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_config(session, config_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "配置项不存在")
        key = item.config_key
        await repo.delete_config(session, item)
        await record_audit(session, "config.deleted", "internal", f"key={key}", request)
        return {"deleted": True, "id": config_id}
