"""密钥轮换策略模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class RotationPolicy(Base):
    """密钥轮换策略：定义某个密钥的轮换周期与状态。"""

    __tablename__ = "rotation_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    # 受管密钥名（逻辑外键）
    secret_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    # 状态机：enabled / disabled
    status: Mapped[str] = mapped_column(String(16), default="enabled", index=True)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_rotation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
