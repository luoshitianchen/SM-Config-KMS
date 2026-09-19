"""轮换策略仓储层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rotation_policy import RotationPolicy


async def get_policy(session: AsyncSession, policy_id: str) -> RotationPolicy | None:
    result = await session.execute(select(RotationPolicy).where(RotationPolicy.id == policy_id))
    return result.scalar_one_or_none()


async def get_policy_by_name(session: AsyncSession, policy_name: str) -> RotationPolicy | None:
    result = await session.execute(
        select(RotationPolicy).where(RotationPolicy.policy_name == policy_name)
    )
    return result.scalar_one_or_none()


async def get_policy_by_secret(session: AsyncSession, secret_name: str) -> RotationPolicy | None:
    result = await session.execute(
        select(RotationPolicy).where(RotationPolicy.secret_name == secret_name)
    )
    return result.scalar_one_or_none()


async def list_policies(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, secret_name: str | None = None,
) -> list[RotationPolicy]:
    stmt = select(RotationPolicy).order_by(RotationPolicy.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(RotationPolicy.status == status)
    if secret_name:
        stmt = stmt.where(RotationPolicy.secret_name == secret_name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_policies(
    session: AsyncSession, status: str | None = None, secret_name: str | None = None,
) -> int:
    stmt = select(func.count(RotationPolicy.id))
    if status:
        stmt = stmt.where(RotationPolicy.status == status)
    if secret_name:
        stmt = stmt.where(RotationPolicy.secret_name == secret_name)
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_policy(session: AsyncSession, policy: RotationPolicy) -> RotationPolicy:
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy


async def update_policy(session: AsyncSession, policy: RotationPolicy) -> RotationPolicy:
    await session.commit()
    await session.refresh(policy)
    return policy


async def delete_policy(session: AsyncSession, policy: RotationPolicy) -> None:
    await session.delete(policy)
    await session.commit()
