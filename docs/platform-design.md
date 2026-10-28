# 自动化测试平台设计方案

## 1. 目标与第一版范围

平台集中管理用户、测试对象、执行器环境和测试任务，最终调用 `TestFramework_kw` 框架执行用例。第一版强调目录清晰、操作简单、可离线部署和远程横向扩展。

第一版包含：

- 用户管理：管理员、测试人员、查看人员。
- 对象管理：测试项目文件和最新测试框架。
- 环境管理：人工部署在 Linux 主机上的 Agent 执行器。
- 任务管理：运行前编辑 INI、选择项目和执行器、并发运行、取消、重跑、日志与报告。

第一版不包含被测环境管理、框架版本回退、平台自动 SSH 安装 Agent、离线包管理和定时任务。它们可以在现有边界上增量增加。

## 2. 总体架构

```text
浏览器
  │ HTTP / WebSocket
  ▼
Frontend（Vue + Nginx）
  │ /api/v1
  ▼
Backend（FastAPI，唯一平台业务进程）
  ├── PostgreSQL：业务数据、任务快照元数据、持久化 AgentCommand 队列
  ├── Redis：任务/部署实时日志 Stream
  └── MinIO：项目文件、框架包、任务产物

                 仅主动出站连接
远端 Linux A ── Agent ── Docker runtime ── 打包后的 driver/可执行程序
远端 Linux B ── Agent ── Docker runtime ── python cli.py
平台服务器 ─── Agent ── Docker runtime    （可选，同样独立部署）
```

平台固定运行 5 个容器：`backend`、`frontend`、`postgres`、`redis`、`minio`。每台执行器主机额外运行一个 Agent；测试任务在短生命周期 runtime 容器中隔离运行。

不再使用 Celery、Celery Beat 和 Flower。此前 Celery 只把业务任务转换成 `AgentCommand`，与 PostgreSQL 持久化命令队列重复。现在 API 在同一数据库事务内同时创建业务记录和命令，链路更短且不会丢失中间消息。

## 3. 设计原则

1. 平台不直接执行测试：Backend 只管理状态和文件，Agent/runtime 执行框架。
2. 执行器只需出站访问平台：不开放 SSH，不直连 PostgreSQL、Redis、MinIO。
3. 数据库是唯一可靠命令源：Redis 丢失不会导致任务记录和待执行命令丢失。
4. 文件保持原结构：MinIO 对象键保留测试项目相对路径，便于 GUI 单文件和批量维护。
5. 框架只认最新内容：上传覆盖后环境显示待更新，重新部署即可，不维护版本列表。
6. API 和 Agent 协议分离：新增执行器只需部署相同 Agent 并注册，不增加平台进程。

## 4. 模块职责

| 模块 | 职责 | 不负责 |
|---|---|---|
| 用户管理 | 登录、JWT、角色、启停和改密 | 外部组织同步 |
| 对象管理 | 项目文件、项目成员、框架包、MinIO 元数据 | 执行测试 |
| 环境管理 | 执行器配置、注册命令、在线状态、框架部署 | SSH 和 Docker 自动安装 |
| 任务管理 | 项目快照、INI、运行命令、取消、结果和产物 | 直接启动框架进程 |
| Agent 通信 | 认证、心跳、命令租约、资源下载、结果回传 | 用户侧业务接口 |
| 后台维护 | 离线判定、租约回收、超时回收、日志 TTL | 长耗时测试执行 |
| Agent | 主动拉取、并发控制、幂等、runtime 生命周期 | 用户和项目权限 |
| runtime | 单任务隔离并调用框架入口 | 平台通信和任务调度 |

## 5. 代码目录

```text
test-platform/
├── backend/
│   ├── app/
│   │   ├── app.py                    # FastAPI 唯一入口
│   │   ├── api/
│   │   │   ├── deps.py               # 当前用户、权限依赖
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── endpoints/        # 各资源 API 及直观业务逻辑
│   │   ├── core/                     # 配置、认证、MinIO、Redis
│   │   ├── crud/                     # 可复用的基础数据库操作
│   │   ├── db/                       # Base、Session、初始化、增量迁移
│   │   ├── models/                   # SQLAlchemy ORM
│   │   ├── schemas/                  # Pydantic 请求/响应
│   │   ├── jobs/                     # 生命周期和轻量维护循环
│   │   └── utils/                    # 归档、INI、路径、摘要工具
│   ├── Dockerfile
│   └── requirements.txt
├── agent/
│   ├── app.py                        # Agent 入口
│   ├── core/                         # 配置和幂等状态
│   ├── protocol/                     # 心跳、租约事件协议
│   ├── services/                     # 客户端、调度器、runtime Runner
│   ├── utils/                        # 安全解压
│   ├── Dockerfile
│   └── runtime.Dockerfile
├── frontend/                         # Vue 页面与通用主题
├── docs/                             # 设计、API、数据库、部署
├── scripts/deploy-docker.sh
├── docker-compose.yml
└── docker-compose.centos7.yml
```

Endpoint 中保留与单一接口强相关的业务逻辑；只有跨接口复用且稳定的数据库操作进入 `crud`。这样没有额外 service 转发层，调用路径保持直观。

## 6. 对象与 MinIO

### 6.1 测试项目

测试项目按文件对象保存，不打成单一 ZIP。对象键结构为：

```text
test-projects/
└── projects/{project_id}/
    ├── testcase/...
    ├── business/...
    ├── config/配置文件.ini
    └── casedata/...
```

平台允许单文件上传、批量上传、替换、下载和删除。任务创建时把当前 `object_key + version_id + sha256` 写入 `agent_task_files`，后续项目更新不会改变已创建任务的输入。

### 6.2 测试框架

框架作为一个可部署归档保存到 `test-frameworks`，同一框架对象只保留最新逻辑版本。归档不再包含 `framework.json`，关键信息在页面填写：

| 字段 | 来源 |
|---|---|
| 名称 | 上传界面填写 |
| OS / 架构 | 上传界面下拉 |
| 入口路径 `runner_path` | 上传界面填写（相对归档根目录） |
| `archive_root` | 后端自动探测（唯一顶层目录判定） |
| `file_count` | 后端统计 |

框架统一采用**打包执行**方式，`runner_path` 指向归档内的可执行程序（如 `driver/自动化测试框架`）；Agent 部署时 `chmod +x` 后直接运行，不再支持 `python cli.py` 源码执行。

框架内容变化后 SHA256 改变，关联环境从 `ready` 变为 `update_available`，管理员重新点击部署。

### 6.3 任务产物

报告和日志归档到：

```text
test-task-artifacts/tasks/{task_id}/{artifact_type}/{filename}
```

## 7. 执行器和 Agent

### 7.1 注册

管理员创建环境后生成一次性 Token 和 Docker 启动命令，在目标 Linux 主机执行。Token 仅以 SHA256 保存；再次生成会使旧 Agent 失效。

Agent 每 15 秒上报系统信息、最大并发、活动命令租约和空闲槽位。Backend 超过 45 秒未收到心跳时将环境标记为 `offline`。

### 7.2 框架部署

1. 管理员选择已上传框架并点击部署。
2. API 在一个事务中创建 `agent_deployments` 和 `deploy_framework` 命令。
3. Agent 有空闲槽时领取命令，通过受控 HTTP 接口下载框架。
4. Agent 校验架构、清单和 SHA256，在 runtime 中执行验证命令。
5. 验证成功后原子切换 `framework/current`，回传结果。

框架部署期间不允许创建该环境的新任务；环境已有活动任务时也不能部署。

## 8. 任务运行流程

1. 用户选择测试项目和 `ready + online` 的执行器。
2. 页面加载并允许编辑本次完整 INI 内容。
3. API 校验 INI，冻结项目文件版本，创建 `agent_tasks`、`agent_task_files` 和 `run_task` 命令；三者一次提交。
4. Agent 心跳按空闲槽主动领取命令。
5. Agent 从平台下载项目快照 ZIP，并覆盖临时项目的 `config/配置文件.ini`。
6. Agent 启动 `kw-task-{task_id}` runtime 容器，挂载框架和临时项目。
7. runtime 调用框架入口，Agent 实时回传日志。
8. Agent 上传报告和结果，平台更新最终状态。

同一项目可以使用不同地址的 INI 同时创建多个任务；并发限制按环境独立计算。

## 9. PostgreSQL 命令队列与租约

`agent_commands` 是唯一可靠调度队列，状态为：

```text
queued → leased → running → success / failed / canceled
             └── 租约过期 → queued
```

关键字段：

| 字段 | 用途 |
|---|---|
| `priority` | 数值越小优先级越高；取消 0、部署 50、运行 100 |
| `lease_id` | 区分每次投递，拒绝旧连接的过期结果 |
| `lease_expires_at` | Agent 必须通过心跳续租 |
| `delivery_count` | 限制连续失败重投次数 |

领取使用 PostgreSQL `FOR UPDATE SKIP LOCKED`，即使以后启动多个 Backend 实例，也不会把同一命令同时租出。取消命令不占测试并发槽，因此环境满载时仍可立即领取取消请求。

Agent 以 `command_id` 缓存最近完成结果，并在上传产物前持久化 runtime 退出码。平台重投同一命令时直接回传缓存，不重复执行。任务容器固定命名为 `kw-task-{task_id}` 并带 `kw.command_id` 标签；Agent 进程重启后若容器仍存在，会重新跟踪而不是启动第二份。

## 10. 后台维护与故障恢复

FastAPI 生命周期启动一个每 30 秒运行的轻量维护协程，数据库操作在线程中完成，不阻塞 API：

- 标记心跳超时的 Agent 离线。
- 回收过期命令租约并重新排队。
- 达到最大投递次数后结束命令和关联业务记录。
- 回收超过任务超时值加五分钟宽限期的任务。
- 为旧 Redis 日志补充七天 TTL。

维护轮次使用 PostgreSQL advisory transaction lock；将来横向扩容 Backend 时，每轮只有一个实例执行维护。

故障行为：

| 故障 | 恢复方式 |
|---|---|
| Backend 重启 | 命令仍在 PostgreSQL，Agent 自动重连 |
| Redis 清空 | 历史实时日志丢失，任务和命令不丢失 |
| Agent 短暂断线 | 心跳携带活动租约并续租 |
| Agent 进程重启 | 租约过期后重投；完成缓存或容器重接管避免重复 |
| 执行器长期离线 | 命令保持 queued，不占平台工作进程 |

## 11. 权限与安全

| 角色 | 权限 |
|---|---|
| `admin` | 用户、对象、成员、环境、部署和全部任务 |
| `tester` | 被授权项目的文件维护、创建任务、取消本人任务 |
| `viewer` | 被授权项目、任务、结果和报告只读 |

安全边界：

- 用户使用 JWT；密码只保存哈希。
- Agent 使用环境独立 Token，远端不保存数据库和 MinIO凭据。
- Agent 只识别 `deploy_framework`、`run_task`、`cancel_task`，不提供任意 Shell API。
- 上传路径和归档解压均拒绝绝对路径及 `..` 越界。
- runtime 按任务隔离；生产环境应通过防火墙和 HTTPS 保护 8000、9000、9001。

## 12. 定时任务扩展

后续需要定时执行时使用 APScheduler，不恢复 Celery。新增：

```text
models/task_schedule.py
schemas/task_schedule.py
crud/task_schedule.py
api/v1/endpoints/task_schedules.py
jobs/scheduler.py
```

调度器只在触发时调用与手工创建相同的任务创建函数；`(schedule_id, scheduled_at)` 唯一约束防止重复触发。单 Backend 时可嵌入进程，多实例时使用 PostgreSQL advisory lock 选主，必要时再以同一 Backend 镜像启动独立 scheduler 进程，不改变 Agent 协议。

## 13. 第一版运行拓扑

| 容器 | 数量 | 可横向扩展 |
|---|---:|---|
| frontend | 1 | 可 |
| backend | 1 | 可；维护任务已有数据库锁 |
| postgres | 1 | 由数据库方案决定 |
| redis | 1 | 可替换为高可用 Redis |
| minio | 1 | 可替换为分布式 MinIO/S3 |
| agent | 每个执行器 1 个 | 直接新增环境 |
| runtime | 每个运行任务 1 个 | 受环境并发数控制 |

部署命令和完整操作步骤见 [deployment.md](deployment.md)，接口见 [api.md](api.md)，表结构见 [database.md](database.md)。
