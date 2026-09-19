"""配置项 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConfigCreate(BaseModel):
    config_key: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_.:/-]+$")
    env: Literal["dev", "staging", "prod"] = "dev"
    value: str = Field(default="", max_length=65536)
    description: str = Field(default="", max_length=512)


class ConfigUpdate(BaseModel):
    value: str | None = Field(default=None, max_length=65536)
    description: str | None = Field(default=None, max_length=512)


class ConfigStatusUpdate(BaseModel):
    status: Literal["active", "archived"]


class ConfigResponse(BaseModel):
    id: str
    config_key: str
    env: str
    value: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


class ConfigListResponse(BaseModel):
    total: int
    items: list[ConfigResponse]
