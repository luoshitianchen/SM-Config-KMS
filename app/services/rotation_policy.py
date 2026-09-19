"""轮换策略服务层：周期管理与手动触发轮换。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.rotation_policy import RotationPolicy
from app.repositories import rotation_policy as repo
from app.repositories import secret_version as secret_repo
from app.schemas.rotation_policy import PolicyCreate, PolicyStatusUpdate, PolicyUpdate
from app.services.audit import record_audit
from app.services.secret_version import SecretService


def _policy_to_dict(p: RotationPolicy) -> dict:
    return {
        "id": p.id, "policy_name": p.policy_name, "secret_name": p.secret_name,
        "interval_days": p.interval_days, "status": p.status,
        "last_rotated_at": p.last_rotated_at.isoformat() if p.last_rotated_at else None,
        "next_rotation_at": p.next_rotation_at.isoformat() if p.next_rotation_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }


class PolicyService:
    @staticmethod
    async def list_policies(session, limit, offset, status_filter, secret_name) -> dict:
        items = await repo.list_policies(session, limit=limit, offset=offset, status=status_filter,
                                         secret_name=secret_name)
        total = await repo.count_policies(session, status=status_filter, secret_name=secret_name)
        return {"total": total, "items": [_policy_to_dict(p) for p in items]}

    @staticmethod
    async def get_policy(session: AsyncSession, policy_id: str) -> dict:
        item = await repo.get_policy(session, policy_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "轮换策略不存在")
        return _policy_to_dict(item)

    @staticmethod
    async def create_policy(session: AsyncSession, payload: PolicyCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_policy_by_name(session, payload.policy_name):
            raise HTTPException(status.HTTP_409_CONFLICT, "策略名已存在")
        # 受管密钥必须已有至少一个版本
        active = await secret_repo.get_active_secret(session, payload.secret_name)
        if not active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "受管密钥不存在，请先创建密钥版本")
        now = datetime.now(UTC)
        item = RotationPolicy(
            id=str(uuid.uuid4()), policy_name=payload.policy_name, secret_name=payload.secret_name,
            interval_days=payload.interval_days, status="enabled",
            last_rotated_at=now, next_rotation_at=now + timedelta(days=payload.interval_days),
        )
        item = await repo.create_policy(session, item)
        await record_audit(session, "policy.created", "internal",
                           f"policy={payload.policy_name} secret={payload.secret_name}", request)
        return _policy_to_dict(item)

    @staticmethod
    async def update_policy(session: AsyncSession, policy_id: str, payload: PolicyUpdate,
                            request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_policy(session, policy_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "轮换策略不存在")
        if payload.interval_days is not None:
            item.interval_days = payload.interval_days
            # 重新计算下次轮换时间
            base = item.last_rotated_at or datetime.now(UTC)
            item.next_rotation_at = base + timedelta(days=payload.interval_days)
        item = await repo.update_policy(session, item)
        await record_audit(session, "policy.updated", "internal", f"policy_id={policy_id}", request)
        return _policy_to_dict(item)

    @staticmethod
    async def change_status(session: AsyncSession, policy_id: str, payload: PolicyStatusUpdate,
                            request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_policy(session, policy_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "轮换策略不存在")
        if payload.status == item.status:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "目标状态与当前状态一致")
        item.status = payload.status
        item = await repo.update_policy(session, item)
        await record_audit(session, "policy.status_changed", "internal",
                           f"policy={item.policy_name} status={payload.status}", request)
        return _policy_to_dict(item)

    @staticmethod
    async def rotate(session: AsyncSession, policy_id: str, new_plaintext: str,
                     request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_policy(session, policy_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "轮换策略不存在")
        if item.status != "enabled":
            raise HTTPException(status.HTTP_409_CONFLICT, "策略已停用，无法轮换")
        from app.schemas.secret_version import SecretCreate
        # 委托密钥服务生成新版本（自动废弃旧 active）
        await SecretService.create_version(
            session,
            SecretCreate(secret_name=item.secret_name, plaintext=new_plaintext),
            request,
        )
        now = datetime.now(UTC)
        item.last_rotated_at = now
        item.next_rotation_at = now + timedelta(days=item.interval_days)
        item = await repo.update_policy(session, item)
        await record_audit(session, "policy.rotated", "internal",
                           f"policy={item.policy_name} secret={item.secret_name}", request)
        return _policy_to_dict(item)

    @staticmethod
    async def delete_policy(session: AsyncSession, policy_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_policy(session, policy_id)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "轮换策略不存在")
        name = item.policy_name
        await repo.delete_policy(session, item)
        await record_audit(session, "policy.deleted", "internal", f"policy={name}", request)
        return {"deleted": True, "id": policy_id}
