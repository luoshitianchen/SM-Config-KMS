"""轮换策略管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.rotation_policy import PolicyCreate, PolicyStatusUpdate, PolicyUpdate
from app.services.rotation_policy import PolicyService

router = APIRouter(prefix="/api/rotation-policies", tags=["rotation-policies"])


class RotateRequest(BaseModel):
    new_plaintext: str = Field(min_length=1, max_length=4096)


@router.get("")
async def list_policies(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    secret_name: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PolicyService.list_policies(session, limit=limit, offset=offset,
                                            status_filter=status_filter, secret_name=secret_name)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: PolicyCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PolicyService.create_policy(session, payload, request)


@router.get("/{policy_id}")
async def get_policy(
    policy_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PolicyService.get_policy(session, policy_id)


@router.patch("/{policy_id}")
async def update_policy(
    policy_id: str, payload: PolicyUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PolicyService.update_policy(session, policy_id, payload, request)


@router.patch("/{policy_id}/status")
async def change_policy_status(
    policy_id: str, payload: PolicyStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PolicyService.change_status(session, policy_id, payload, request)


@router.post("/{policy_id}/rotate")
async def rotate_policy(
    policy_id: str, payload: RotateRequest, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PolicyService.rotate(session, policy_id, payload.new_plaintext, request)


@router.delete("/{policy_id}")
async def delete_policy(
    policy_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await PolicyService.delete_policy(session, policy_id, request)
