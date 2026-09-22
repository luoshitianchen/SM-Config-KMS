# SM-Config-KMS 容灾恢复手册（DR RUNBOOK）

> 服务：sm-config-kms（配置与密钥管理服务）｜ RTO 目标：≤ 15 分钟 ｜ RPO 目标：≤ 5 分钟

## 1. 数据库备份与恢复

### 1.1 备份策略
- **全量备份**：每日凌晨 02:00 执行，保留 30 天。
- **WAL 归档**：实时持续归档至对象存储，保留 7 天。
- **备份验证**：每周自动恢复至 staging 环境验证备份可用性。

### 1.2 数据库恢复步骤

```bash
# 1. 确认当前数据库故障状态
kubectl exec -it postgres-primary-0 -n sm-prod -- psql -U postgres -c "SELECT pg_is_in_recovery();"

# 2. 停止应用流量（可选，避免恢复期间写入）
kubectl scale deployment/sm-config-kms -n sm-prod --replicas=0

# 3. 选择恢复点（RPO ≤ 5min）
#    - 全量备份：/backup/postgres/sm_config_kms_YYYYMMDD.dump
#    - WAL 归档：/archive/wal/

# 4. 执行 PITR（时间点恢复）
#    a. 恢复全量备份
pg_basebackup -D /tmp/recover -Fd -Xs -P -h <standby-host>
#    b. 配置 recovery_target_time
#    c. 启动 PostgreSQL，回放 WAL

# 5. 验证数据完整性
psql -h <recovered-host> -U postgres -d sm_config_kms -c "SELECT count(*) FROM <核心表>;"

# 6. 恢复应用流量
kubectl scale deployment/sm-config-kms -n sm-prod --replicas=3
kubectl rollout status deployment/sm-config-kms -n sm-prod
```

## 2. 服务降级方案

| 故障场景 | 降级措施 | 恢复条件 |
|---|---|---|
| 数据库主库故障 | 切换至只读从库，写接口返回 503 | 主库恢复或提升从库为主 |
| 下游依赖超时 | 熔断 + 降级缓存响应（Redis） | 下游恢复 + 熔断半开探测成功 |
| 内存溢出（OOM） | HPA 自动扩容 + 重启 Pod | 内存水位恢复正常 |
| 日志量暴增 | 采样日志（10% 采样率） | 日志量回落 |
| 全局流量突增 | 限流保护（令牌桶），拒绝低优先级请求 | 流量回落到阈值以下 |

## 3. 跨可用区 / 跨区域切换

### 3.1 跨可用区切换（同区域 AZ 故障）
1. 确认故障 AZ 不可用（节点 NotReady / 网络分区）。
2. ArgoCD 自动同步：将 `nodeSelector` / `affinity` 切换到健康 AZ。
3. 数据库自动故障切换（Patroni/Orchestrator）。
4. 验证服务在新 AZ 正常运行。
5. 预计 RTO ≤ 10 分钟。

### 3.2 跨区域切换（区域级灾难）
1. 启动区域切换应急预案，通知值班总监。
2. DNS 流量切换至备用区域（GeoDNS / 全局负载均衡）。
3. 备用区域数据库从最近的异地备份恢复（RPO ≤ 5min）。
4. 备用区域部署 ArgoCD Application 同步上线。
5. 冒烟测试通过后开放流量。
6. 预计 RTO ≤ 30 分钟（含数据恢复）。

## 4. 演练频率与记录

| 演练类型 | 频率 | 参与方 | 记录要求 |
|---|---|---|---|
| 单 Pod 故障（ChaosMesh） | 每周自动 | 无（自动验证） | 自动生成报告归档 |
| 可用区级故障切换 | 每季度 | 运维 + DBA | 演练报告 + 改进项 |
| 跨区域灾难切换 | 每半年 | 全体 SRE + 业务方 | 正式演练复盘报告 |
| 数据库 PITR 恢复 | 每月 | DBA | 恢复时间与数据一致性记录 |

> 所有演练须在 [DR 演练记录表] 中登记：日期、参与人、演练场景、RTO/RPO 实测值、发现问题、改进措施。
