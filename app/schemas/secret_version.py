"""密钥版本 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SecretCreate(BaseModel):
    secret_name: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_.-]+$")
    plaintext: str = Field(min_length=1, max_length=4096)


class SecretRevealResponse(BaseModel):
    secret_name: str
    version: int
    status: str
    plaintext: str


class SecretVersionResponse(BaseModel):
    id: str
    secret_name: str
    version: int
    status: str
    rotated_at: datetime | None = None
    created_at: datetime


class SecretVersionListResponse(BaseModel):
    total: int
    items: list[SecretVersionResponse]
