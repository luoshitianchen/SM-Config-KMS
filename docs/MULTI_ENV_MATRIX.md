# SM-Config-KMS 多环境配置矩阵（MULTI-ENV MATRIX）

> 服务：sm-config-kms（配置与密钥管理服务）｜ 端口：8018

| 配置项 | dev | staging | prod |
|---|---|---|---|
| 命名空间 | sm-dev | sm-staging | sm-prod |
| 副本数（初始） | 1 | 2 | 3 |
| HPA 最小副本 | 1 | 2 | 3 |
| HPA 最大副本 | 3 | 5 | 10 |
| 镜像 tag | dev | staging | （Chart.AppVersion） |
| 镜像拉取策略 | IfNotPresent | IfNotPresent | IfNotPresent |
| CPU requests | 50m | 100m | 200m |
| CPU limits | 200m | 500m | 1 |
| 内存 requests | 64Mi | 128Mi | 256Mi |
| 内存 limits | 128Mi | 256Mi | 512Mi |
| 日志级别 | debug | info | warn |
| 数据库 | 开发共享 PG | 预发独立 PG | 生产主从 PG |
| 数据库名 | sm_config_kms_dev | sm_config_kms_staging | sm_config_kms |
| 域名 | sm-config-kms.dev.sm.example.com | sm-config-kms.staging.sm.example.com | sm-config-kms.sm.example.com |
| TLS | 关闭 | sm-staging-tls | sm-tls |
| NetworkPolicy | 启用 | 启用 | 启用 |
| 审计日志 | 本地输出 | 转发审计中心 | 转发审计中心（保留365天） |
| 密钥来源 | .env 本地 | Vault staging | Vault prod（ExternalSecret） |
| 自动同步（ArgoCD） | 手动 | 手动 | 自动（prune + selfHeal） |
| 变更审批 | 无 | 技术负责人 | CAB 审批 |
| 备份策略 | 无 | 每日全量 | 每日全量 + WAL 实时归档 |
| 监控告警 | 本地 | 企业 IM | 电话 + IM + 邮件 |
