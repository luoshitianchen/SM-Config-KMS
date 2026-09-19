"""密钥版本模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class SecretVersion(Base):
    """密钥版本：同一密钥名存在多个历史版本，仅一个 active。"""

    __tablename__ = "secret_versions"
    __table_args__ = (
        UniqueConstraint("secret_name", "version", name="uq_secret_name_version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    secret_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # SM4 加密后的 base64 密文，绝不存储明文
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    # 状态机：active -> deprecated（同一密钥名仅一个 active）
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
