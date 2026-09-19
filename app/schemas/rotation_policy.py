"""轮换策略 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    policy_name: str = Field(min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    secret_name: str = Field(min_length=1, max_length=256)
    interval_days: int = Field(default=90, ge=1, le=3650)


class PolicyUpdate(BaseModel):
    interval_days: int | None = Field(default=None, ge=1, le=3650)


class PolicyStatusUpdate(BaseModel):
    status: Literal["enabled", "disabled"]


class PolicyResponse(BaseModel):
    id: str
    policy_name: str
    secret_name: str
    interval_days: int
    status: str
    last_rotated_at: datetime | None = None
    next_rotation_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PolicyListResponse(BaseModel):
    total: int
    items: list[PolicyResponse]
