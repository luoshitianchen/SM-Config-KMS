"""配置项仓储层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_item import ConfigItem


async def get_config(session: AsyncSession, config_id: str) -> ConfigItem | None:
    result = await session.execute(select(ConfigItem).where(ConfigItem.id == config_id))
    return result.scalar_one_or_none()


async def get_config_by_key_env(
    session: AsyncSession, config_key: str, env: str,
) -> ConfigItem | None:
    result = await session.execute(
        select(ConfigItem).where(ConfigItem.config_key == config_key, ConfigItem.env == env)
    )
    return result.scalar_one_or_none()


async def list_configs(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    env: str | None = None, status: str | None = None, keyword: str | None = None,
) -> list[ConfigItem]:
    stmt = select(ConfigItem).order_by(ConfigItem.created_at.desc()).limit(limit).offset(offset)
    if env:
        stmt = stmt.where(ConfigItem.env == env)
    if status:
        stmt = stmt.where(ConfigItem.status == status)
    if keyword:
        stmt = stmt.where(ConfigItem.config_key.like(f"%{keyword}%"))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_configs(
    session: AsyncSession, env: str | None = None,
    status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(ConfigItem.id))
    if env:
        stmt = stmt.where(ConfigItem.env == env)
    if status:
        stmt = stmt.where(ConfigItem.status == status)
    if keyword:
        stmt = stmt.where(ConfigItem.config_key.like(f"%{keyword}%"))
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_config(session: AsyncSession, item: ConfigItem) -> ConfigItem:
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_config(session: AsyncSession, item: ConfigItem) -> ConfigItem:
    await session.commit()
    await session.refresh(item)
    return item


async def delete_config(session: AsyncSession, item: ConfigItem) -> None:
    await session.delete(item)
    await session.commit()
