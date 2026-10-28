# API 文档

## 1. 约定

- 基础路径：`/api/v1`
- 用户认证：`Authorization: Bearer <JWT>`
- Agent 资源接口：`Authorization: Agent <TOKEN>`
- 请求和响应：JSON；文件接口使用 `multipart/form-data` 或二进制响应。
- 交互文档：平台启动后访问 `/docs`。

常见错误：`401` 未认证，`403` 无权限，`404` 资源不存在，`409` 状态冲突，`422` 参数或业务前置条件不满足。

## 2. 用户与认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 用户名密码登录并返回 JWT |
| GET | `/auth/me` | 当前用户 |
| POST | `/auth/change-password` | 修改本人密码 |
| GET | `/users` | 用户列表，管理员 |
| POST | `/users` | 创建用户，管理员 |
| PUT | `/users/{user_id}` | 修改角色、状态或密码，管理员 |

登录示例：

```bash
curl -X POST http://192.168.14.100:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"你的密码"}'
```

## 3. 测试项目对象

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/objects/projects` | 列表、创建项目 |
| GET/DELETE | `/objects/projects/{project_id}` | 详情、删除空闲项目 |
| GET | `/objects/projects/{project_id}/files` | 保持目录结构的文件列表 |
| POST | `/objects/projects/{project_id}/files/batch` | 批量上传文件 |
| PUT/DELETE | `/objects/projects/{project_id}/files/{file_id}` | 替换、删除单文件 |
| GET | `/objects/projects/{project_id}/files/{file_id}/download` | 下载单文件 |
| GET/PUT | `/objects/projects/{project_id}/members` | 项目成员列表、整体更新 |

上传相对路径必须位于允许的项目目录中，例如 `testcase/login/test_login.py`、`config/配置文件.ini`、`casedata/user.json`。绝对路径和包含 `..` 的路径会被拒绝。

## 4. 测试框架对象

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/objects/frameworks` | 框架列表、上传最新框架 |
| GET/DELETE | `/objects/frameworks/{framework_id}` | 详情、删除未使用框架 |
| GET | `/objects/frameworks/{framework_id}/download` | 下载框架归档 |

框架上传时不再依赖 `framework.json` 清单，而是在界面填写名称、操作系统、CPU 架构和执行器入口路径；后端校验入口文件真实存在、归档路径安全。平台不提供版本回退；更新后的内容以最新 SHA256 为准。

## 5. 执行器环境

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/environments` | 环境列表、创建环境 |
| GET/PUT/DELETE | `/environments/{environment_id}` | 详情、更新、删除 |
| POST | `/environments/{environment_id}/registration` | 轮换 Token 并生成 Agent 命令 |
| POST | `/environments/{environment_id}/deploy` | 创建框架部署命令 |
| GET | `/environments/{environment_id}/deployments` | 部署记录 |
| GET | `/environments/{environment_id}/deployments/{deployment_id}/logs` | 部署日志 |

创建环境请求：

```json
{
  "name": "centos-agent-01",
  "host": "192.168.14.101",
  "work_root": "/opt/kw-executor",
  "max_concurrency": 2,
  "framework_id": 1,
  "enabled": true
}
```

`host` 是便于管理员识别的主机地址；平台不会 SSH 连接该地址。注册接口返回的 Token 只出现一次，应直接使用返回的 `docker_command`。

## 6. 测试任务

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/tasks` | 任务列表、创建任务 |
| GET | `/tasks/{task_id}` | 任务详情 |
| POST | `/tasks/{task_id}/cancel` | 取消等待或运行任务 |
| POST | `/tasks/{task_id}/rerun` | 使用原项目快照重跑 |
| GET | `/tasks/{task_id}/logs` | Redis Stream 日志 |
| GET | `/tasks/{task_id}/results` | 结果摘要 |
| GET | `/tasks/{task_id}/artifacts` | 产物列表 |
| GET | `/tasks/{task_id}/artifacts/{artifact_id}/download` | 下载产物 |

创建任务请求：

```json
{
  "project_id": 3,
  "environment_id": 2,
  "testcase_path": "testcase/login/test_login.py",
  "config_content": "[server]\nbase_url=http://10.0.0.20\n",
  "timeout_seconds": 3600
}
```

创建成功时，任务快照和 `run_task` 命令在同一 PostgreSQL 事务中提交。API 返回 `201` 只表示可靠入队，状态会依次变为 `queued`、`dispatching`、`running` 和最终状态。

## 7. Agent 私有 HTTP 接口

以下接口不提供给浏览器，必须带 Agent Token，且只能访问自身环境的资源。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/agents/{environment_id}/framework` | 下载环境选择的最新框架 |
| GET | `/agents/{environment_id}/tasks/{task_id}/project` | 下载项目快照和本次 INI ZIP |
| POST | `/agents/{environment_id}/tasks/{task_id}/artifacts` | 上传日志或报告 |

## 8. Agent WebSocket 协议

连接地址：

```text
ws(s)://平台/api/v1/agents/connect?environment_id={id}&token={token}
```

### 8.1 心跳与主动拉取

Agent 建连后立即发送，之后每 15 秒发送：

```json
{
  "type": "heartbeat",
  "os_family": "centos",
  "os_version": "7",
  "arch": "x86_64",
  "max_concurrency": 2,
  "running_count": 1,
  "available_slots": 1,
  "running_commands": [
    {"command_id": 501, "lease_id": "405ebfb3-1d6d-449c-8cf3-08c46867b922"}
  ]
}
```

Backend 先续租活动命令，再使用 `FOR UPDATE SKIP LOCKED` 领取不超过空闲槽的普通命令。取消命令不占槽。

### 8.2 平台下发命令

```json
{
  "type": "command",
  "command_id": 502,
  "lease_id": "7a6e46da-e801-48b3-b681-b19feb26e07d",
  "command": "run_task",
  "payload": {"task_id": 18, "timeout_seconds": 3600, "framework": {}}
}
```

支持且仅支持：`deploy_framework`、`run_task`、`cancel_task`。

### 8.3 Agent 状态事件

开始：

```json
{"type":"command_started","command_id":502,"lease_id":"7a6e46da-e801-48b3-b681-b19feb26e07d"}
```

日志：

```json
{"type":"log","command_id":502,"lease_id":"7a6e46da-e801-48b3-b681-b19feb26e07d","level":"INFO","message":"running case"}
```

完成：

```json
{
  "type": "command_result",
  "command_id": 502,
  "lease_id": "7a6e46da-e801-48b3-b681-b19feb26e07d",
  "success": true,
  "status": "success",
  "exit_code": 0
}
```

所有命令事件必须携带当前 `lease_id`。平台忽略旧租约事件，防止断线后的迟到结果覆盖新一轮执行状态。

## 9. 健康检查

```bash
curl http://192.168.14.100:8000/health
```

响应：

```json
{"status":"ok"}
```
