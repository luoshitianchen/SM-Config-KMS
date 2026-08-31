"""SM Config KMS —— 密钥管理与加密服务：密钥生命周期、信封加密、轮换与吊销。

数据密钥通过主密钥（SM4_KEY_HEX）信封加密后落库，密钥明文不落盘。
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-config-kms"
VERSION = "2.0.0"
NAME = "SM Config KMS"
DESCRIPTION = "密钥管理与加密服务（KMS）：密钥生命周期、信封加密、轮换与吊销"
PORT = 8400


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS keys (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, algorithm TEXT NOT NULL DEFAULT 'SM4',
                state TEXT NOT NULL DEFAULT 'enabled', wrapped_key TEXT NOT NULL,
                created_at TEXT NOT NULL, rotated_at TEXT NOT NULL, expires_at TEXT
            );
            CREATE TABLE IF NOT EXISTS key_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, key_id TEXT NOT NULL,
                action TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_keys_state ON keys(state);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-audit-log-center"],
    events=["key.created", "key.rotated", "key.revoked", "key.used"],
    overview_fn=lambda _r: {
        "summary": {
            "keys": base.get_db().execute("SELECT COUNT(*) FROM keys").fetchone()[0],
            "enabled": base.get_db().execute("SELECT COUNT(*) FROM keys WHERE state='enabled'").fetchone()[0],
            "revoked": base.get_db().execute("SELECT COUNT(*) FROM keys WHERE state='revoked'").fetchone()[0],
        }
    },
)
_init()


class KeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9._-]+$")
    algorithm: str = Field(default="SM4", pattern=r"^(SM4|AES-256)$")
    expires_in_days: int = Field(default=365, ge=1, le=3650)


class CryptoIn(BaseModel):
    value: str = Field(min_length=1, max_length=10000)


def _unwrap(row: Any) -> bytes:
    """解封数据密钥（信封解密）。"""
    if row["state"] != "enabled":
        raise HTTPException(status.HTTP_423_LOCKED, "密钥不可用")
    return base.sm4_decrypt(row["wrapped_key"], label="kms-wrap")


def _kms_encrypt(data_key: bytes, value: bytes) -> str:
    from gmssl.sm4 import SM4_ENCRYPT, CryptSM4
    mac_key = base.sm3_hex(data_key + b"mac").encode()[:16]
    iv = secrets.token_bytes(16)
    cipher = CryptSM4()
    cipher.set_key(data_key, SM4_ENCRYPT)
    ciphertext = cipher.crypt_cbc(iv, value)
    mac = base.sm3_hex(mac_key + iv + ciphertext)
    return f"kms${iv.hex()}${ciphertext.hex()}${mac}"


def _kms_decrypt(data_key: bytes, token: str) -> bytes:
    from gmssl.sm4 import SM4_DECRYPT, CryptSM4
    if not token.startswith("kms$"):
        raise ValueError("密文格式无效")
    _, iv_hex, ct_hex, mac = token.split("$", 3)
    mac_key = base.sm3_hex(data_key + b"mac").encode()[:16]
    iv, ciphertext = bytes.fromhex(iv_hex), bytes.fromhex(ct_hex)
    if not secrets.compare_digest(base.sm3_hex(mac_key + iv + ciphertext), mac):
        raise ValueError("密文完整性校验失败")
    cipher = CryptSM4()
    cipher.set_key(data_key, SM4_DECRYPT)
    return cipher.crypt_cbc(iv, ciphertext)


def _row_to_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    item.pop("wrapped_key", None)
    return item


@app.get("/api/kms/keys")
def list_keys() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
    return {"items": [_row_to_dict(r) for r in rows], "total": len(rows)}


@app.post("/api/kms/keys", status_code=status.HTTP_201_CREATED)
def create_key(payload: KeyIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    key_id = str(uuid.uuid4())
    data_key = secrets.token_bytes(16)
    wrapped = base.sm4_encrypt(data_key, label="kms-wrap")
    expires = (datetime.now(UTC) + timedelta(days=payload.expires_in_days)).isoformat()
    with base.db_ctx() as conn:
        try:
            conn.execute(
                "INSERT INTO keys (id, name, algorithm, state, wrapped_key, created_at, rotated_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                (key_id, payload.name, payload.algorithm, "enabled", wrapped, _now(), _now(), expires),
            )
            conn.execute("INSERT INTO key_events (key_id, action, created_at) VALUES (?,?,?)", (key_id, "created", _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "密钥名已存在") from exc
        base.record_audit("key.created", "internal", f"key={key_id} name={payload.name}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": key_id, "name": payload.name, "state": "enabled"}


@app.get("/api/kms/keys/{key_id}")
def get_key(key_id: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM keys WHERE id=?", (key_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在")
    return _row_to_dict(row)


@app.post("/api/kms/keys/{key_id}/rotate")
def rotate_key(key_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM keys WHERE id=?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在")
        if row["state"] == "revoked":
            raise HTTPException(status.HTTP_423_LOCKED, "已吊销密钥不可轮换")
        new_key = base.sm4_encrypt(secrets.token_bytes(16), label="kms-wrap")
        conn.execute("UPDATE keys SET wrapped_key=?, state='enabled', rotated_at=? WHERE id=?", (new_key, _now(), key_id))
        conn.execute("INSERT INTO key_events (key_id, action, created_at) VALUES (?,?,?)", (key_id, "rotated", _now()))
        base.record_audit("key.rotated", "internal", f"key={key_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": key_id, "state": "enabled", "rotated_at": _now()}


@app.post("/api/kms/keys/{key_id}/disable")
def disable_key(key_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    return _set_state(key_id, "disabled", request)


@app.post("/api/kms/keys/{key_id}/enable")
def enable_key(key_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    return _set_state(key_id, "enabled", request)


@app.post("/api/kms/keys/{key_id}/revoke")
def revoke_key(key_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    return _set_state(key_id, "revoked", request)


def _set_state(key_id: str, state: str, request: Request) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if conn.execute("UPDATE keys SET state=? WHERE id=?", (state, key_id)).rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在")
        conn.execute("INSERT INTO key_events (key_id, action, created_at) VALUES (?,?,?)", (key_id, state, _now()))
        base.record_audit(f"key.{state}", "internal", f"key={key_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": key_id, "state": state}


@app.delete("/api/kms/keys/{key_id}")
def delete_key(key_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM keys WHERE id=?", (key_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在")
        if row["state"] != "revoked":
            raise HTTPException(status.HTTP_409_CONFLICT, "仅已吊销密钥可删除")
        conn.execute("DELETE FROM keys WHERE id=?", (key_id,))
        base.record_audit("key.deleted", "internal", f"key={key_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": key_id, "deleted": True}


@app.post("/api/kms/keys/{key_id}/encrypt")
def encrypt_value(key_id: str, payload: CryptoIn, request: Request) -> dict[str, Any]:
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM keys WHERE id=?", (key_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在")
    data_key = _unwrap(row)
    return {"key_id": key_id, "algorithm": row["algorithm"], "ciphertext": _kms_encrypt(data_key, payload.value.encode("utf-8"))}


@app.post("/api/kms/keys/{key_id}/decrypt")
def decrypt_value(key_id: str, payload: CryptoIn, request: Request) -> dict[str, Any]:
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM keys WHERE id=?", (key_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "密钥不存在")
    data_key = _unwrap(row)
    try:
        plaintext = _kms_decrypt(data_key, payload.value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"key_id": key_id, "algorithm": row["algorithm"], "plaintext": plaintext.decode("utf-8")}


@app.get("/api/kms/status")
def kms_status() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        return {
            "enabled": _count("SELECT COUNT(*) FROM keys WHERE state='enabled'"),
            "disabled": _count("SELECT COUNT(*) FROM keys WHERE state='disabled'"),
            "revoked": _count("SELECT COUNT(*) FROM keys WHERE state='revoked'"),
            "expiring_soon": _count("SELECT COUNT(*) FROM keys WHERE expires_at IS NOT NULL AND expires_at < datetime('now', '+30 day')"),
            "key_events": _count("SELECT COUNT(*) FROM key_events"),
            "key_source": "SM4_KEY_HEX environment",
        }
