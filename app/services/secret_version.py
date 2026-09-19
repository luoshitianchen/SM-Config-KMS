"""密钥版本服务层：SM4 加密、版本递增与轮换。"""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed, sm4_crypt
from app.models.secret_version import SecretVersion
from app.repositories import secret_version as repo
from app.schemas.secret_version import SecretCreate
from app.services.audit import record_audit


def _secret_to_dict(s: SecretVersion) -> dict:
    return {
        "id": s.id, "secret_name": s.secret_name, "version": s.version,
        "status": s.status,
        "rotated_at": s.rotated_at.isoformat() if s.rotated_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


class SecretService:
    @staticmethod
    async def list_versions(session: AsyncSession, secret_name: str, limit: int, offset: int) -> dict:
        items = await repo.list_secret_versions(session, secret_name, limit=limit, offset=offset)
        total = await repo.count_secret_versions(session, secret_name)
        return {"total": total, "items": [_secret_to_dict(s) for s in items]}

    @staticmethod
    async def get_active(session: AsyncSession, secret_name: str) -> dict:
        item = await repo.get_active_secret(session, secret_name)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在或无活跃版本")
        return _secret_to_dict(item)

    @staticmethod
    async def create_version(session: AsyncSession, payload: SecretCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        # SM4 加密后 base64 落库，明文不出服务边界
        cipher = sm4_crypt(payload.plaintext.encode("utf-8"), encrypt=True)
        ciphertext = base64.b64encode(cipher).decode("ascii")
        next_version = await repo.get_max_version(session, payload.secret_name) + 1
        now = datetime.now(UTC)
        # 同一密钥名：新版本置 active，旧 active 降级为 deprecated
        old_active = await repo.get_active_secret(session, payload.secret_name)
        if old_active:
            old_active.status = "deprecated"
            await repo.update_secret(session, old_active)
        item = SecretVersion(
            id=str(uuid.uuid4()), secret_name=payload.secret_name, version=next_version,
            ciphertext=ciphertext, status="active", rotated_at=now,
        )
        item = await repo.create_secret(session, item)
        await record_audit(session, "secret.version_created", "internal",
                           f"secret={payload.secret_name} version={next_version}", request)
        return _secret_to_dict(item)

    @staticmethod
    async def reveal(session: AsyncSession, secret_name: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        item = await repo.get_active_secret(session, secret_name)
        if not item:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在或无活跃版本")
        cipher = base64.b64decode(item.ciphertext)
        plaintext = sm4_crypt(cipher, encrypt=False).decode("utf-8")
        await record_audit(session, "secret.revealed", "internal", f"secret={secret_name}", request)
        return {
            "secret_name": item.secret_name, "version": item.version,
            "status": item.status, "plaintext": plaintext,
        }
