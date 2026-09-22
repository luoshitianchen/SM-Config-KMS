# SM-Config-KMS 运维手册（OPERATIONS）

> 服务：sm-config-kms（配置与密钥管理服务）｜ 端口：8018

## 1. 服务概述与依赖

SM-Config-KMS 是 SM 数据平台微服务集群中的 **配置与密钥管理服务** 服务。

**依赖组件：**
- PostgreSQL 主库（`sm_config_kms` 数据库）
- SM-IAM（统一身份认证）
- SM-Audit-Log-Center（审计日志转发）
- Vault（密钥管理，通过 ExternalSecret 注入）
- Prometheus + Grafana（监控）
- Loki（日志聚合）

**无状态/有状态：** 无状态服务（数据库持久化在外部 PG），支持水平扩展。

## 2. SLO 定义

| 指标 | 目标值 | 测量窗口 | 数据源 |
|---|---|---|---|
| 服务可用性 | ≥ 99.9% | 30 天滚动 | Uptime / 健康检查通过率 |
| 延迟 P99 | < 1000ms | 7 天 | Prometheus 直方图 |
| 延迟 P95 | < 500ms | 7 天 | Prometheus 直方图 |
| 错误率（5xx） | < 0.1% | 7 天 | Ingress 指标 |
| 数据一致性 | 100% | 持续 | 数据库校验任务 |

## 3. 错误预算公式与消耗跟踪

- 月度错误预算 = 30 天 × 24h × 60min × (1 - 99.9%) ≈ **43.2 分钟不可用**。
- 消耗跟踪：Grafana Dashboard "Error Budget Burn Rate" 面板实时展示。
- 消耗规则：
  - 24h 内消耗 > 5%：冻结非紧急变更。
  - 72h 内消耗 > 10%：暂停发布，启动复盘。
  - 月度预算耗尽：进入稳定性专项治理，直至预算重置或补偿措施上线。

## 4. 变更管理流程

- **变更分类**：标准变更（自动化流水线，免审批）、常规变更（技术负责人审批）、重大变更（CAB 审批 + 变更窗口）。
- **变更窗口**：
  - 生产：工作日 10:00-16:00（避开早晚高峰与月末结账）。
  - 禁止窗口：法定节假日前后 2 个工作日、大促/营销活动期间。
- **变更通知**：提前 24h 在运维群通知，附变更方案、回滚预案、影响评估。

## 5. 发布审批流程

```
dev（自动部署）
  → 单元测试 + 集成测试通过
  → staging（手动触发）
    → 端到端测试 + 回归测试通过
    → 安全扫描无 Critical/High
    → prod（人工审批 + 灰度）
      → 10% 灰度 30min 观察
      → 100% 全量
```

## 6. 回滚流程

1. **触发条件**：5xx 错误率 > 1%、P99 延迟 > 3s、核心业务不可用、数据异常。
2. **回滚命令**：
   ```bash
   helm rollback sm-config-kms -n sm-prod
   # 或指定版本
   helm rollback sm-config-kms <REVISION> -n sm-prod
   ```
3. **RTO 目标**：≤ 5 分钟。
4. **验证步骤**：
   - `kubectl rollout status deployment/sm-config-kms -n sm-prod`
   - 健康检查 `/health` 与 `/readyz` 返回 200
   - 冒烟测试核心接口通过
   - 监控面板错误率恢复基线

## 7. 值班与告警响应

- **值班模式**：7×24 主备双值班，主值班 30 分钟未响应自动升级到备值班，再 15 分钟升级到技术负责人。
- **告警分级**：
  - P1（紧急）：服务不可用、数据泄露风险 — 立即电话呼叫，15 分钟响应。
  - P2（高）：错误率突增、节点异常 — 30 分钟内处理。
  - P3（中）：资源水位告警、日志异常 — 2 小时内处理。
  - P4（低）：非紧急优化建议 — 工作日处理。
- **升级路径**：值班工程师 → 技术负责人 → 部门总监 → CTO。

## 8. 日常运维操作手册

| 操作 | 命令/步骤 | 频率 |
|---|---|---|
| 查看 Pod 状态 | `kubectl get pods -n sm-prod -l app.kubernetes.io/name=sm-config-kms` | 日常 |
| 查看日志 | `kubectl logs -n sm-prod -l app.kubernetes.io/name=sm-config-kms --tail=100` | 日常 |
| 进入 Pod 排查 | `kubectl exec -it <pod> -n sm-prod -- /bin/sh` | 按需 |
| 手动扩缩容 | `kubectl scale deployment/sm-config-kms -n sm-prod --replicas=5` | 紧急 |
| 查看 HPA | `kubectl get hpa -n sm-prod -l app.kubernetes.io/name=sm-config-kms` | 日常 |
| 配置变更 | 修改 ConfigMap 后触发滚动重启 | 变更窗口 |
| 密钥轮换 | Vault 更新 → ExternalSecret 自动同步（1h 内）→ 重启 Pod | 按计划 |
