"""SM Config KMS 领域测试：密钥生命周期、信封加密、轮换、吊销与解密失败。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _create(client, name="master"):
    return client.post("/api/kms/keys", json={"name": name, "algorithm": "SM4"}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION
    assert r.headers["X-Frame-Options"] == "DENY"


def test_key_lifecycle_and_states(client):
    key_id = _create(client)
    assert client.get(f"/api/kms/keys/{key_id}").json()["state"] == "enabled"
    assert client.post(f"/api/kms/keys/{key_id}/disable").json()["state"] == "disabled"
    assert client.post(f"/api/kms/keys/{key_id}/enable").json()["state"] == "enabled"
    assert client.post(f"/api/kms/keys/{key_id}/rotate").json()["state"] == "enabled"
    # 未吊销不可删除
    assert client.delete(f"/api/kms/keys/{key_id}").status_code == 409
    assert client.post(f"/api/kms/keys/{key_id}/revoke").json()["state"] == "revoked"
    assert client.delete(f"/api/kms/keys/{key_id}").json()["deleted"] is True
    assert client.get("/api/kms/status").json()["revoked"] == 0


def test_duplicate_key_name(client):
    _create(client, name="dup")
    assert client.post("/api/kms/keys", json={"name": "dup"}).status_code == 409


def test_envelope_encrypt_decrypt_roundtrip(client):
    key_id = _create(client)
    enc = client.post(f"/api/kms/keys/{key_id}/encrypt", json={"value": "机密数据"}).json()["ciphertext"]
    assert enc.startswith("kms$")
    dec = client.post(f"/api/kms/keys/{key_id}/decrypt", json={"value": enc}).json()["plaintext"]
    assert dec == "机密数据"


def test_tampered_ciphertext_rejected(client):
    key_id = _create(client)
    enc = client.post(f"/api/kms/keys/{key_id}/encrypt", json={"value": "secret"}).json()["ciphertext"]
    tampered = enc[:-2] + ("00" if not enc.endswith("00") else "11")
    assert client.post(f"/api/kms/keys/{key_id}/decrypt", json={"value": tampered}).status_code == 400


def test_disabled_key_cannot_decrypt(client):
    key_id = _create(client)
    enc = client.post(f"/api/kms/keys/{key_id}/encrypt", json={"value": "secret"}).json()["ciphertext"]
    client.post(f"/api/kms/keys/{key_id}/disable")
    assert client.post(f"/api/kms/keys/{key_id}/decrypt", json={"value": enc}).status_code == 423


def test_manifest_and_baseline(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    assert client.get("/api/security/baseline").json()["controls"]["sm4_integrity_mac"] is True


def test_crypto_base_endpoints(client):
    enc = client.post("/api/crypto/encrypt", json={"value": "hello"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "hello"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/kms/keys", json={"name": "x"}).status_code == 401


def test_kms_crypto_and_list_require_auth(client):
    key_id = _create(client)
    enc = client.post(f"/api/kms/keys/{key_id}/encrypt", json={"value": "secret"}).json()["ciphertext"]
    del client.headers["X-Internal-Token"]
    # 无令牌：密钥列表、密钥详情、加密、解密一律 fail-closed
    assert client.get("/api/kms/keys").status_code in (401, 403)
    assert client.get(f"/api/kms/keys/{key_id}").status_code in (401, 403)
    assert client.post(f"/api/kms/keys/{key_id}/encrypt", json={"value": "x"}).status_code in (401, 403)
    assert client.post(f"/api/kms/keys/{key_id}/decrypt", json={"value": enc}).status_code in (401, 403)
