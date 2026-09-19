"""配置项模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class ConfigItem(Base):
    """配置项：按环境隔离的键值配置。"""

    __tablename__ = "config_items"
    __table_args__ = (
        UniqueConstraint("config_key", "env", name="uq_config_key_env"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    # 环境：dev / staging / prod
    env: Mapped[str] = mapped_column(String(32), nullable=False, default="dev", index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(String(512), default="")
    # 状态机：active -> archived
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
