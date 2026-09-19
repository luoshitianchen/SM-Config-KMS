"""密钥版本仓储层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.secret_version import SecretVersion


async def get_secret(session: AsyncSession, secret_id: str) -> SecretVersion | None:
    result = await session.execute(select(SecretVersion).where(SecretVersion.id == secret_id))
    return result.scalar_one_or_none()


async def get_active_secret(session: AsyncSession, secret_name: str) -> SecretVersion | None:
    result = await session.execute(
        select(SecretVersion).where(
            SecretVersion.secret_name == secret_name, SecretVersion.status == "active"
        )
    )
    return result.scalar_one_or_none()


async def get_max_version(session: AsyncSession, secret_name: str) -> int:
    result = await session.execute(
        select(func.max(SecretVersion.version)).where(SecretVersion.secret_name == secret_name)
    )
    return result.scalar_one() or 0


async def list_secret_versions(
    session: AsyncSession, secret_name: str, limit: int = 100, offset: int = 0,
) -> list[SecretVersion]:
    stmt = (
        select(SecretVersion)
        .where(SecretVersion.secret_name == secret_name)
        .order_by(SecretVersion.version.desc())
        .limit(limit).offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_secret_versions(session: AsyncSession, secret_name: str) -> int:
    result = await session.execute(
        select(func.count(SecretVersion.id)).where(SecretVersion.secret_name == secret_name)
    )
    return result.scalar_one()


async def create_secret(session: AsyncSession, secret: SecretVersion) -> SecretVersion:
    session.add(secret)
    await session.commit()
    await session.refresh(secret)
    return secret


async def update_secret(session: AsyncSession, secret: SecretVersion) -> SecretVersion:
    await session.commit()
    await session.refresh(secret)
    return secret
