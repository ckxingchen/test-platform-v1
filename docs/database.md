# 数据库与存储设计

## 1. 存储分工

| 数据 | 存储 |
|---|---|
| 用户、对象元数据、环境、部署、任务、命令租约 | PostgreSQL |
| 项目文件、框架归档、报告和日志文件 | MinIO |
| 任务与部署的短期实时日志 | Redis Stream |

PostgreSQL 是业务事实和可靠队列的唯一来源。Redis 不再承担消息队列职责；清空 Redis 只会丢失未归档的实时日志，不会丢失任务或待执行命令。

## 2. 当前业务表

第一版 ORM 共 11 张业务表。

### 2.1 `users`

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `username` | 唯一用户名 |
| `password_hash` | 密码哈希 |
| `role` | `admin/tester/viewer` |
| `enabled` | 是否可登录 |
| `created_at` | 创建时间 |

### 2.2 `object_resources`

测试项目和测试框架的统一资源主表。

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `name` | 对象名称 |
| `resource_type` | `project/framework` |
| `description` | 说明 |
| `metadata_json` | 框架入口、架构等扩展元数据 |
| `enabled` | 是否可用 |
| `created_by` | 创建人 |
| `created_at/updated_at` | 时间戳 |

### 2.3 `object_resource_files`

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `resource_id` | 所属资源 |
| `relative_path` | 原项目相对路径；同一资源内唯一 |
| `object_key` | MinIO 对象键 |
| `object_version_id` | MinIO 版本编号，可空 |
| `sha256` | 内容摘要 |
| `size` | 字节数 |
| `updated_at` | 更新时间 |

### 2.4 `object_resource_members`

项目成员关联表，联合主键为 `resource_id + user_id`，`permission` 为 `read/write`。

### 2.5 `agent_environments`

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `name` | 唯一环境名称 |
| `host` | 管理员识别用主机地址 |
| `work_root` | 远端持久化工作目录 |
| `max_concurrency` | 最大测试并发数 |
| `framework_id` | 选择的框架对象 |
| `agent_token_hash` | Agent Token 摘要 |
| `agent_status` | `pending/online/offline` |
| `deploy_status` | `not_deployed/deploying/ready/update_available/failed` |
| `os_family/os_version/arch` | 心跳上报信息 |
| `last_seen` | 最后心跳 |
| `deployed_framework_sha256` | 已部署框架摘要 |
| `deploy_error` | 最近部署错误 |
| `enabled` | 是否允许使用 |
| `updated_at` | 更新时间 |

### 2.6 `agent_deployments`

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `environment_id` | 执行器环境 |
| `framework_sha256` | 本次目标框架摘要 |
| `status` | `queued/running/success/failed` |
| `error_message` | 错误原因 |
| `created_by` | 发起人 |
| `created_at/started_at/finished_at` | 生命周期时间 |

### 2.7 `agent_tasks`

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `project_id/environment_id/framework_id` | 本次选择 |
| `framework_sha256` | 创建时的框架摘要 |
| `status` | `queued/dispatching/running/success/failed/canceled/timeout` |
| `testcase_scope` | 可选用例路径 JSON |
| `config_content` | 本次完整 INI 内容 |
| `timeout_seconds` | 用户超时 |
| `cancel_requested` | 是否请求取消 |
| `exit_code/error_message` | 运行摘要 |
| `created_by` | 创建人 |
| `created_at/started_at/finished_at` | 生命周期时间 |

### 2.8 `agent_task_files`

任务输入快照。联合主键 `task_id + relative_path`，同时保存 `object_key`、`object_version_id` 和 `sha256`，确保项目更新后仍能重跑原任务。

### 2.9 `agent_task_results`

保存任务级或用例级结果摘要：`task_id`、`case_path`、`case_name`、`status`、`error_message`。

### 2.10 `agent_task_artifacts`

保存 MinIO 产物引用：`task_id`、`artifact_type`、`object_key`、`size`。

### 2.11 `agent_commands`

平台与 Agent 之间的可靠命令队列。

| 字段 | 说明 |
|---|---|
| `id` | 命令编号，也是 Agent 幂等键 |
| `environment_id` | 目标执行器 |
| `command_type` | `deploy_framework/run_task/cancel_task` |
| `payload` | 受控 JSON 参数 |
| `status` | `queued/leased/running/success/failed/canceled` |
| `priority` | 0 取消、50 部署、100 运行 |
| `lease_id` | 本次投递 UUID |
| `lease_expires_at` | 租约到期时间 |
| `delivery_count` | 已投递次数 |
| `task_id/deployment_id` | 关联业务记录，可空 |
| `error_message` | 最终错误 |
| `created_at/started_at/finished_at` | 生命周期时间 |

核心投递索引：

```sql
CREATE INDEX ix_agent_commands_delivery
ON agent_commands (environment_id, status, priority, id);
```

领取使用事务、行锁和跳过已锁行：

```sql
SELECT *
FROM agent_commands
WHERE environment_id = :environment_id
  AND status = 'queued'
ORDER BY priority, id
FOR UPDATE SKIP LOCKED;
```

## 3. 事务边界

- 创建任务：`agent_tasks`、全部 `agent_task_files`、`run_task AgentCommand` 一次提交。
- 发起部署：`agent_deployments`、环境部署状态、`deploy_framework AgentCommand` 一次提交。
- Agent 领取：锁定命令、生成租约、增加投递次数、更新任务分发状态一次提交。
- Agent 完成：命令最终状态、任务/部署最终状态和结果摘要一次提交。

因此无需依赖跨 PostgreSQL 与 Redis 的分布式事务。

## 4. MinIO Bucket

| Bucket | 内容 |
|---|---|
| `test-projects` | `projects/{project_id}/{relative_path}` |
| `test-frameworks` | 最新框架归档 |
| `test-task-artifacts` | `tasks/{task_id}/{artifact_type}/{filename}` |

项目 Bucket 建议开启版本控制，以便任务快照使用 `object_version_id` 精确读取；框架业务上只展示最新版本。

## 5. Redis

Redis DB 0 仅保存：

```text
task:{task_id}:logs
deployment:{deployment_id}:logs
```

Stream 最多约 10000 条，并设置七天 TTL。正式报告和日志文件由 Agent 上传 MinIO。

## 6. 初始化与迁移

Backend 启动顺序：

1. SQLAlchemy 创建不存在的表。
2. 幂等增量迁移补齐 AgentCommand 租约字段和索引。
3. 清理已经取消功能的旧字段。
4. 创建 MinIO Bucket。
5. 不存在管理员时创建初始管理员。

现有数据库中不再被 ORM 使用的历史表不会自动删除，避免升级时误删业务数据。确认无回退和审计需求后，由管理员备份数据库再人工清理。

## 7. 备份与恢复

备份 PostgreSQL：

```bash
mkdir -p /opt/test-platform-backup
docker exec testplatform-pg pg_dump -U testplatform -Fc testplatform \
  > /opt/test-platform-backup/postgres-$(date +%Y%m%d-%H%M%S).dump
```

备份 MinIO 卷：

```bash
docker run --rm \
  -v testplatform_v1_minio_data:/source:ro \
  -v /opt/test-platform-backup:/backup \
  alpine sh -c 'cd /source && tar czf /backup/minio-$(date +%Y%m%d-%H%M%S).tar.gz .'
```

恢复前必须停止 Backend，防止写入：

```bash
docker compose stop backend
cat /opt/test-platform-backup/postgres.dump | \
  docker exec -i testplatform-pg pg_restore -U testplatform -d testplatform --clean --if-exists
docker compose start backend
```

恢复操作会覆盖数据库，应先再次备份并核对目标文件。
