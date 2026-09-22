# SM-Config-KMS 上线部署检查清单（DEPLOYMENT CHECKLIST）

> 服务：sm-config-kms（配置与密钥管理服务）｜ 目标环境：prod

## 1. 上线前检查

- [ ] 代码审查：MR/PR 至少 1 名高级工程师 approve
- [ ] 单元测试：覆盖率 ≥ 80%，全部通过
- [ ] 集成测试：CI 流水线全部绿色
- [ ] 安全扫描：Trivy 镜像扫描无 Critical/High 漏洞
- [ ] SCA 依赖扫描：无已知高危依赖
- [ ] 性能基准：压测 QPS / P99 达到 SLO 要求
- [ ] 代码冻结：上线前 4h 无新合并（紧急修复除外）

## 2. 配置检查

- [ ] ConfigMap 环境变量核对（SM_ENV=production、SM_LOG_LEVEL=warn）
- [ ] Secret 已通过 ExternalSecret 从 Vault 正确注入
  - SM_INTERNAL_API_KEY
  - SM_SM4_KEY_HEX
  - SM_DATABASE_URL
- [ ] 数据库迁移脚本已执行（alembic upgrade head）
- [ ] 数据库账号权限最小化确认
- [ ] 域名与 TLS 证书已配置（sm-config-kms.sm.example.com）
- [ ] Ingress 注解与超时参数已核对
- [ ] HPA 副本数与资源限制已按 prod values 配置

## 3. 部署步骤

```bash
# 1. 切换到目标分支并拉取最新代码
git checkout main && git pull

# 2. 渲染 Helm 模板 dry-run 验证
helm template sm-config-kms helm/sm-config-kms -f helm/sm-config-kms/values-prod.yaml --namespace sm-prod

# 3. 安装/升级
helm upgrade --install sm-config-kms helm/sm-config-kms \
  -f helm/sm-config-kms/values.yaml \
  -f helm/sm-config-kms/values-prod.yaml \
  --namespace sm-prod --wait --timeout 5m

# 4. ArgoCD 同步确认
argocd app sync sm-config-kms
```

## 4. 验证步骤

- [ ] Pod 全部 Running 且 Ready：`kubectl get pods -n sm-prod -l app.kubernetes.io/name=sm-config-kms`
- [ ] 健康检查通过：`curl https://sm-config-kms.sm.example.com/health`
- [ ] 就绪检查通过：`curl https://sm-config-kms.sm.example.com/readyz`
- [ ] 冒烟测试：核心业务接口返回 200，数据正确
- [ ] Grafana Dashboard：CPU/内存/延迟/错误率在基线范围
- [ ] Loki 日志：无 ERROR/FATAL 级别异常日志
- [ ] 审计中心：上线操作已记录

## 5. 回滚触发条件与步骤

**触发条件（任一满足即回滚）：**
- 5xx 错误率 > 1% 且持续 5 分钟
- P99 延迟 > 3s 且持续 5 分钟
- 核心业务接口不可用
- 数据不一致或数据丢失风险

**回滚步骤：**
```bash
# 查看历史版本
helm history sm-config-kms -n sm-prod

# 回滚到上一版本
helm rollback sm-config-kms -n sm-prod

# 验证
kubectl rollout status deployment/sm-config-kms -n sm-prod
```

## 6. SBOM 与供应链策略

- [ ] 每次构建生成 SPDX SBOM（sbom.json），随镜像归档
- [ ] 基础镜像使用企业内部安全基线镜像（非官方上游裸镜像）
- [ ] 依赖锁定：requirements.lock / package-lock.json 提交入库
- [ ] 镜像签名：使用 Cosign 签名，部署时验证签名
- [ ] 镜像来源：仅从 ghcr.io/luoshitianchen/ 拉取，禁止第三方 registry
- [ ] 依赖漏洞自动阻断：CI 流水线检测到 Critical 漏洞时阻止合并
