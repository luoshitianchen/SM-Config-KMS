"""SM-Config-KMS 业务深化测试：配置项/密钥版本/轮换策略。"""
from __future__ import annotations

import uuid

H = {"X-Internal-Token": "test-internal-key-12345"}
P = {"X-Internal-Token": "wrong-token"}


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


async def _make_secret(client, name: str, plaintext: str = "value-1") -> dict:
    resp = await client.post("/api/secrets", json={
        "secret_name": name, "plaintext": plaintext,
    }, headers=H)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ═══════════════════════════════════════════════════════════
# 配置项
# ═══════════════════════════════════════════════════════════

class TestConfigItem:
    async def test_create_config_success(self, client):
        key = f"cfg.{_suffix()}"
        resp = await client.post("/api/configs", json={
            "config_key": key, "env": "dev", "value": "v1", "description": "测试",
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["config_key"] == key
        assert data["env"] == "dev"
        assert data["status"] == "active"

    async def test_create_config_requires_token(self, client):
        resp = await client.post("/api/configs", json={
            "config_key": f"cfg.{_suffix()}", "env": "dev", "value": "x",
        }, headers=P)
        assert resp.status_code in (401, 403)

    async def test_duplicate_key_env_conflict(self, client):
        key = f"cfg.{_suffix()}"
        await client.post("/api/configs", json={"config_key": key, "env": "prod", "value": "1"}, headers=H)
        resp = await client.post("/api/configs", json={"config_key": key, "env": "prod", "value": "2"}, headers=H)
        assert resp.status_code == 409

    async def test_same_key_different_env_allowed(self, client):
        key = f"cfg.{_suffix()}"
        r1 = await client.post("/api/configs", json={"config_key": key, "env": "dev", "value": "a"}, headers=H)
        r2 = await client.post("/api/configs", json={"config_key": key, "env": "prod", "value": "b"}, headers=H)
        assert r1.status_code == 201
        assert r2.status_code == 201

    async def test_list_and_filter_configs(self, client):
        key = f"cfg.{_suffix()}"
        await client.post("/api/configs", json={"config_key": key, "env": "staging", "value": "s"}, headers=H)
        resp = await client.get(f"/api/configs?env=staging&keyword={key}", headers=H)
        assert resp.status_code == 200
        assert any(c["config_key"] == key for c in resp.json()["items"])

    async def test_get_config_not_found(self, client):
        resp = await client.get("/api/configs/nope", headers=H)
        assert resp.status_code == 404

    async def test_update_config_value(self, client):
        create = await client.post("/api/configs", json={"config_key": f"cfg.{_suffix()}", "env": "dev", "value": "old"}, headers=H)
        cid = create.json()["id"]
        resp = await client.patch(f"/api/configs/{cid}", json={"value": "new"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["value"] == "new"

    async def test_archive_config(self, client):
        create = await client.post("/api/configs", json={"config_key": f"cfg.{_suffix()}", "env": "dev", "value": "a"}, headers=H)
        cid = create.json()["id"]
        resp = await client.patch(f"/api/configs/{cid}/status", json={"status": "archived"}, headers=H)
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    async def test_delete_config(self, client):
        create = await client.post("/api/configs", json={"config_key": f"cfg.{_suffix()}", "env": "dev", "value": "d"}, headers=H)
        cid = create.json()["id"]
        resp = await client.delete(f"/api/configs/{cid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


# ═══════════════════════════════════════════════════════════
# 密钥版本
# ═══════════════════════════════════════════════════════════

class TestSecretVersion:
    async def test_create_secret_first_version(self, client):
        name = f"sec-{_suffix()}"
        data = await _make_secret(client, name, "plain-1")
        assert data["version"] == 1
        assert data["status"] == "active"

    async def test_new_version_deprecates_old(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "plain-1")
        v2 = await _make_secret(client, name, "plain-2")
        assert v2["version"] == 2
        assert v2["status"] == "active"
        versions = await client.get(f"/api/secrets/{name}/versions", headers=H)
        items = versions.json()["items"]
        active = [v for v in items if v["status"] == "active"]
        deprecated = [v for v in items if v["status"] == "deprecated"]
        assert len(active) == 1
        assert len(deprecated) == 1

    async def test_reveal_roundtrip(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "supersecret-xyz")
        resp = await client.get(f"/api/secrets/{name}/reveal", headers=H)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plaintext"] == "supersecret-xyz"
        assert data["version"] == 1

    async def test_reveal_requires_token(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "x")
        resp = await client.get(f"/api/secrets/{name}/reveal", headers=P)
        assert resp.status_code in (401, 403)

    async def test_reveal_not_found(self, client):
        resp = await client.get("/api/secrets/ghost-secret/reveal", headers=H)
        assert resp.status_code == 404

    async def test_list_versions_count(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "a")
        await _make_secret(client, name, "b")
        await _make_secret(client, name, "c")
        resp = await client.get(f"/api/secrets/{name}/versions", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] == 3


# ═══════════════════════════════════════════════════════════
# 轮换策略
# ═══════════════════════════════════════════════════════════

class TestRotationPolicy:
    async def test_create_policy_success(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "init")
        resp = await client.post("/api/rotation-policies", json={
            "policy_name": f"pol-{_suffix()}", "secret_name": name, "interval_days": 30,
        }, headers=H)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "enabled"
        assert data["interval_days"] == 30
        assert data["next_rotation_at"] is not None

    async def test_create_policy_secret_not_found(self, client):
        resp = await client.post("/api/rotation-policies", json={
            "policy_name": f"pol-{_suffix()}", "secret_name": "ghost", "interval_days": 30,
        }, headers=H)
        assert resp.status_code == 400

    async def test_create_policy_duplicate_name(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "init")
        pname = f"pol-{_suffix()}"
        await client.post("/api/rotation-policies", json={"policy_name": pname, "secret_name": name}, headers=H)
        resp = await client.post("/api/rotation-policies", json={"policy_name": pname, "secret_name": name}, headers=H)
        assert resp.status_code == 409

    async def test_rotate_creates_new_version(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "v1")
        create = await client.post("/api/rotation-policies", json={
            "policy_name": f"pol-{_suffix()}", "secret_name": name, "interval_days": 30,
        }, headers=H)
        pid = create.json()["id"]
        resp = await client.post(f"/api/rotation-policies/{pid}/rotate", json={
            "new_plaintext": "v2-rotated",
        }, headers=H)
        assert resp.status_code == 200
        assert resp.json()["last_rotated_at"] is not None
        # 新版本应为 v2 且可解出新明文
        reveal = await client.get(f"/api/secrets/{name}/reveal", headers=H)
        assert reveal.json()["version"] == 2
        assert reveal.json()["plaintext"] == "v2-rotated"

    async def test_disabled_policy_cannot_rotate(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "init")
        create = await client.post("/api/rotation-policies", json={
            "policy_name": f"pol-{_suffix()}", "secret_name": name,
        }, headers=H)
        pid = create.json()["id"]
        await client.patch(f"/api/rotation-policies/{pid}/status", json={"status": "disabled"}, headers=H)
        resp = await client.post(f"/api/rotation-policies/{pid}/rotate", json={"new_plaintext": "x"}, headers=H)
        assert resp.status_code == 409

    async def test_list_policies_filter(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "init")
        await client.post("/api/rotation-policies", json={
            "policy_name": f"pol-{_suffix()}", "secret_name": name,
        }, headers=H)
        resp = await client.get(f"/api/rotation-policies?status=enabled&secret_name={name}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_delete_policy(self, client):
        name = f"sec-{_suffix()}"
        await _make_secret(client, name, "init")
        create = await client.post("/api/rotation-policies", json={
            "policy_name": f"pol-{_suffix()}", "secret_name": name,
        }, headers=H)
        pid = create.json()["id"]
        resp = await client.delete(f"/api/rotation-policies/{pid}", headers=H)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
