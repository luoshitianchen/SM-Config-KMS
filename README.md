# SM Config KMS

统一配置与密钥中心：KMS/HSM、密钥轮换、证书和动态配置。

```powershell
git clone https://github.com/luoshitianchen/SM-Config-KMS.git
cd SM-Config-KMS
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8400
```

接口：`/health`、`/readyz`、`/api/overview`、`/api/items`、`/api/ops/metrics`、`/api/crypto/status`。

内置 TrustedHost、安全响应头、CSP、国密状态接口和容器加固。
