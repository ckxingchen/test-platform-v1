# 测试平台模块化重构实施方案

> 适用项目：FastAPI + Vue 3 + 独立执行器 Agent 测试平台
> 重构性质：仅调整代码组织、依赖边界和公共封装，不改变现有功能
> 核心目标：一个业务菜单对应一个前后端模块，公共能力统一下沉，模块内只保留业务特有逻辑

## 1. 背景与现状

当前后端采用标准的横向分层结构：

```text
api/endpoints → services → crud → models
                   ↓
              schemas/utils/core
```

该结构在项目早期清晰、直接，但平台功能逐渐完整后，一个业务功能通常分散在多个目录。例如“任务管理”同时涉及：

- `api/v1/endpoints/tasks.py`
- `api/v1/endpoints/task_results.py`
- `api/v1/endpoints/streams.py`
- `services/task_lifecycle.py`
- `crud/task.py`
- `schemas/task.py`
- `models/task.py`

前端也采用平铺结构，所有页面位于 `views/`，所有路由集中在单个 `router.js`，所有 HTTP 请求共享单个 `api.js`。新增菜单时，前后端文件之间缺少直观的目录对应关系。

本次重构将平台调整为“模块化单体（Modular Monolith）”：

```text
modules → shared → platform
```

- `modules`：按菜单和业务领域垂直聚合。
- `shared`：带有少量平台业务语义的跨模块复用能力。
- `platform`：完全不理解项目、框架、任务等业务概念的技术基础设施。

## 2. 重构目标

### 2.1 必须实现

1. 每个业务菜单拥有独立的后端模块和前端模块。
2. 前后端模块名称保持一致，可以从页面目录直接定位后端代码。
3. 数据库、HTTP、认证、Redis、MinIO、日志等高复用代码进入公共层。
4. 业务模块只保留接口定义、业务编排、特定查询和特定校验。
5. 明确并自动检查模块之间的依赖方向。
6. 每次只迁移一个模块，迁移完成即可独立测试、部署和回滚。

### 2.2 明确不做

本次重构不包含以下改动：

- 不替换 FastAPI、SQLAlchemy、Vue、Element Plus。
- 不拆分微服务。
- 不修改数据库表名、字段、索引、外键和已有数据。
- 不拆分当前共表的 `Resource` 项目/框架模型。
- 不修改 API URL、请求方法、状态码和响应字段。
- 不修改前端访问路径和菜单行为。
- 不修改 Redis Key、MinIO Bucket/Object Key。
- 不修改 Agent 通信协议和任务状态流转。
- 不在目录重构中顺带新增业务功能。

## 3. 架构原则

### 3.1 依赖方向

```text
backend/app/modules  ──────→ backend/app/shared ──────→ backend/app/platform
         │                            │                           │
         └──────────────允许直接依赖 platform─────────────────────┘
```

必须遵守：

- `platform` 不得导入 `shared` 或 `modules`。
- `shared` 不得导入 `modules`。
- 模块不得直接导入其他模块的内部 `repository.py`。
- 跨模块调用通过对方的 `facade.py` 或公开 service 完成。
- 后端 `router.py` 不直接编写复杂 SQL、MinIO 或 Redis 操作。
- `repository.py` 不依赖 FastAPI，不抛出 `HTTPException`。
- 前端 `shared` 不依赖任何具体业务模块。

### 3.2 公共封装原则

1. 公共层提供“机制”，业务模块决定“规则”。
2. 同类代码至少在三个模块出现后再提取，避免提前抽象。
3. 优先使用组合和显式调用，避免复杂继承、元编程和自动生成路由。
4. 通用仓库只处理基础 CRUD，复杂关联查询仍归业务仓库。
5. 不创建含义模糊的超大 `common.py` 或 `utils.py`。

### 3.3 命名约定

- Python 和前端模块目录统一采用 `snake_case`，保证一一对应。
- 后端接口文件统一叫 `router.py`。
- 数据访问统一叫 `repository.py`，不再混用 `crud.py`。
- 请求响应模型统一叫 `schemas.py`。
- SQLAlchemy 模型统一叫 `models.py`。
- 业务编排统一叫 `service.py`。
- 对其他模块开放的调用入口统一叫 `facade.py`。

## 4. 目标目录结构

### 4.1 项目根目录

```text
test-platform/
├── backend/                     # FastAPI 平台服务
├── frontend/                    # Vue 3 管理界面
├── agent/                       # 独立部署的执行器 Agent，保持独立
├── scripts/                     # 构建、部署、快照和验证脚本
├── tests/
│   ├── contract/               # 外部契约快照
│   ├── platform/               # 公共层单元测试
│   ├── modules/                # 业务模块测试
│   └── e2e/                    # 端到端冒烟测试
├── docs/
└── docker-compose.yml
```

### 4.2 后端目录

```text
backend/app/
├── __init__.py
├── main.py                         # FastAPI 实例、异常处理、生命周期装配
├── router.py                       # 只聚合各模块 router
│
├── platform/                       # 纯技术基础设施
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py                 # DeclarativeBase、utcnow
│   │   ├── session.py              # engine、SessionLocal、get_db
│   │   ├── mixins.py               # ID/Timestamp/Enabled mixin
│   │   ├── repository.py           # BaseRepository
│   │   ├── transaction.py          # commit/rollback/IntegrityError 转换
│   │   ├── serialization.py        # model_to_dict
│   │   └── migrations.py           # 迁移注册与执行
│   ├── web/
│   │   ├── __init__.py
│   │   ├── dependencies.py         # current_user、admin 等通用依赖
│   │   ├── errors.py               # ServiceError/NotFound/Conflict 等
│   │   ├── exception_handlers.py   # 统一异常到 HTTP 响应
│   │   ├── pagination.py
│   │   ├── responses.py            # download_response
│   │   └── helpers.py              # get_or_404 等无业务绑定 helper
│   ├── security/
│   │   ├── password.py
│   │   ├── token.py
│   │   └── crypto.py
│   ├── storage/
│   │   ├── base.py                 # ObjectStorage Protocol
│   │   └── minio.py                # MinIO 实现
│   ├── messaging/
│   │   ├── redis.py
│   │   └── stream_log.py           # Redis Stream 通用日志读写
│   └── observability/
│       └── logging.py
│
├── shared/                         # 跨业务公共能力
│   ├── __init__.py
│   ├── files/
│   │   ├── archive.py
│   │   ├── hashing.py
│   │   ├── paths.py
│   │   └── stored_file_service.py
│   ├── permissions/
│   │   └── project_access.py       # 项目成员权限语义
│   ├── resources/
│   │   ├── models.py               # Resource/ResourceFile/ResourceMember
│   │   ├── schemas.py
│   │   ├── repository.py
│   │   └── file_service.py         # ResourceFile + MinIO 复合操作
│   └── schemas/
│       └── base.py                 # ORMModel
│
└── modules/                        # 菜单/业务模块
    ├── __init__.py
    ├── auth/
    ├── dashboard/
    ├── users/
    ├── objects/
    │   ├── agent_packages/
    │   ├── frameworks/
    │   └── projects/
    ├── executors/
    ├── tasks/
    └── agent_gateway/              # Agent 专用内部接口，无前端模块
```

### 4.3 前端目录

```text
frontend/src/
├── main.js
│
├── app/
│   ├── App.vue
│   ├── router.js                   # 聚合各模块 routes
│   ├── navigation.js               # 菜单定义
│   └── layout/
│       └── MainLayout.vue
│
├── platform/
│   ├── http/
│   │   ├── client.js               # Axios 实例
│   │   ├── interceptors.js
│   │   └── download.js
│   ├── auth/
│   │   ├── session.js
│   │   └── route_guard.js
│   └── storage/
│       └── local_storage.js
│
├── shared/
│   ├── components/
│   │   ├── StatusBadge.vue
│   │   ├── CodeEditor.vue
│   │   ├── PathTree.vue
│   │   ├── CaseCheckTree.vue
│   │   └── StatBar.vue
│   ├── composables/
│   │   ├── useDownload.js
│   │   ├── usePolling.js
│   │   └── useTableQuery.js
│   ├── constants/
│   │   └── terminology.js
│   ├── theme/
│   └── utils/
│
└── modules/
    ├── auth/
    ├── dashboard/
    ├── users/
    ├── objects/
    │   ├── agent_packages/
    │   ├── frameworks/
    │   └── projects/
    ├── executors/
    └── tasks/
```

## 5. 标准业务模块模板

### 5.1 后端模板

```text
modules/<module_name>/
├── __init__.py
├── router.py              # 接口、参数、权限依赖、HTTP 状态码
├── schemas.py             # Pydantic 请求/响应模型
├── models.py              # 模块独占的 SQLAlchemy 模型
├── repository.py          # 特定查询和持久化
├── service.py             # 业务校验、状态流转、业务编排
├── facade.py              # 可选；供其他模块调用的稳定入口
├── constants.py           # 可选；本模块状态和枚举
└── dependencies.py        # 可选；本模块专属权限/对象加载
```

一个简单接口的调用链应保持为：

```text
router
  ├── 使用 platform.web.dependencies 完成通用认证
  ├── 使用本模块 dependencies 完成对象级权限
  └── 调用 service
          ├── 调用 repository
          ├── 调用 shared 公共业务能力
          └── 调用 platform 技术基础设施
```

### 5.2 前端模板

```text
modules/<module_name>/
├── api.js                 # 本模块后端接口定义
├── routes.js              # 本模块路由
├── constants.js           # 模块状态/选项
├── pages/
│   ├── ListPage.vue
│   ├── DetailPage.vue
│   └── CreatePage.vue
├── components/            # 只服务本模块的组件
├── composables/           # 只服务本模块的状态和行为
└── store.js               # 需要跨页面共享状态时才创建
```

禁止模块页面直接使用全局 Axios 实例拼接 URL。应先在模块 `api.js` 中定义：

```javascript
export const taskApi = {
  list: params => http.get('/tasks', { params }),
  detail: id => http.get(`/tasks/${id}`),
  create: data => http.post('/tasks', data),
  cancel: id => http.post(`/tasks/${id}/cancel`)
}
```

## 6. 平台公共层设计

### 6.1 数据库基础能力

`BaseRepository` 仅提供低风险的基础操作：

```python
class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def get(self, db: Session, item_id: int) -> ModelT | None: ...
    def list(self, db: Session, *, offset: int = 0, limit: int = 100): ...
    def add(self, db: Session, item: ModelT) -> ModelT: ...
    def delete(self, db: Session, item: ModelT) -> None: ...
    def exists(self, db: Session, **filters) -> bool: ...
```

以下内容不进入 `BaseRepository`：

- 多表 Join 和名称冗余组装。
- 项目成员权限过滤。
- 任务状态和执行器状态过滤。
- 框架平台/架构匹配。
- 带 MinIO、Redis 副作用的复合操作。

这些逻辑继续由模块 repository/service 显式实现。

### 6.2 事务管理

统一提供：

- 正常提交。
- 异常回滚。
- `IntegrityError` 转平台 `ConflictError`。
- 可选的事务上下文管理器。

业务模块不重复编写 `try/commit/except/rollback`，也不在 repository 中提交事务。事务边界由 service 决定。

### 6.3 通用异常

公共异常建议定义为：

```text
PlatformError
├── ValidationError       → 422
├── AuthenticationError   → 401
├── PermissionDeniedError → 403
├── NotFoundError         → 404
└── ConflictError         → 409
```

模块 service 抛公共异常，FastAPI 全局异常处理器转换 HTTP 响应。迁移完成后，router 不再重复捕获 `ServiceError` 再转换 `HTTPException`。

### 6.4 对象存储

`platform.storage` 提供纯技术接口：

- `put_bytes`
- `get_bytes`
- `remove`
- `ensure_bucket`

`shared.resources.file_service` 提供带业务语义的复合操作：

- 上传 MinIO 并写入 `ResourceFile`。
- 替换资源文件并删除旧对象。
- 删除资源全部文件。
- 保留项目文件的 Version ID。

各模块只负责指定：

- Bucket。
- Object Key 规则。
- 文件类型和大小约束。
- 归档内容的模块专属校验。

### 6.5 Redis Stream 日志

`platform.messaging.stream_log.StreamLogService` 统一提供：

- 单条/批量追加日志。
- 按游标增量读取。
- 设置最大长度和 TTL。
- 同步与异步读取。

任务和部署模块只负责生成 Stream Key：

```text
task:{task_id}:logs
deployment:{deployment_id}:logs
```

Key 格式在重构中保持不变。

### 6.6 HTTP 公共能力

从现有代码迁移并继续复用：

- `get_or_404`
- `download_response`
- current user/admin 认证依赖
- 统一错误响应
- 分页请求和响应

`get_accessible_project` 带有项目业务语义，应进入 `shared.permissions.project_access`，不放在纯技术 `platform.web`。

## 7. 业务模块边界

| 模块 | 后端职责 | 前端页面 | 主要拥有的数据 |
|---|---|---|---|
| `auth` | 登录、当前用户、修改密码 | 登录 | 无独立表，使用 User |
| `dashboard` | 仪表盘聚合查询 | 仪表盘 | 无独立表 |
| `users` | 用户 CRUD、角色、启停 | 用户管理 | User |
| `objects/agent_packages` | Agent 包上传、下载、删除 | AGENT 管理 | AgentPackage |
| `objects/frameworks` | 框架包检查、上传、查询、删除 | 框架管理 | Resource(type=framework) |
| `objects/projects` | 项目、成员、文件、归档 | 项目列表/详情 | Resource(type=project)、ResourceMember/File |
| `executors` | 执行器 CRUD、SSH、Agent 部署、框架部署 | 执行器列表/详情 | Environment、Deployment、AgentCommand |
| `tasks` | 创建、重跑、取消、结果、附件、日志 | 任务列表/创建/详情 | Task、TaskFile/Result/Artifact |
| `agent_gateway` | Agent 心跳、领取任务、下载、状态/日志/结果上报 | 无 | 操作多个模块，不拥有页面 |

### 7.1 跨模块调用规则

- `tasks` 通过 projects/frameworks/executors 的 facade 读取就绪信息。
- `executors` 通过 agent_packages/frameworks facade 定位部署包。
- `agent_gateway` 通过 tasks/executors facade 更新状态。
- 模块不得跨边界直接调用其他模块 repository。
- ORM 注册允许统一从 `backend/app/models.py` 或模块注册器导入，但不对业务层暴露旧聚合路径。

## 8. 当前文件到目标目录的迁移映射

### 8.1 后端公共层

| 当前文件 | 目标文件 | 说明 |
|---|---|---|
| `core/config.py` | `platform/config/settings.py` | 配置不变 |
| `core/security.py` | `platform/security/password.py` + `token.py` | 拆密码和 Token |
| `core/crypto.py` | `platform/security/crypto.py` | SSH 密码加密 |
| `core/storage.py` | `platform/storage/minio.py` | MinIO 适配器 |
| `core/redis.py` | `platform/messaging/redis.py` | Redis 客户端 |
| `db/base.py` | `platform/db/base.py` | Base/utcnow |
| `db/session.py` | `platform/db/session.py` | 会话 |
| `db/migrations.py` | `platform/db/migrations.py` | 第一阶段仅移动，不改迁移逻辑 |
| `api/deps.py` | `platform/web/dependencies.py` + `shared/permissions/project_access.py` | 分离通用认证与项目权限 |
| `api/helpers.py` | `platform/web/helpers.py` + `shared/permissions/project_access.py` | 按是否含业务语义拆分 |
| `crud/common.py:model_to_dict` | `platform/db/serialization.py` | 通用 ORM 序列化 |
| `crud/common.py:remove_resource_files` | `shared/resources/file_service.py` | MinIO + ResourceFile 复合操作 |
| `schemas/base.py` | `shared/schemas/base.py` | Pydantic ORM 基类 |
| `utils/hashing.py` | `shared/files/hashing.py` | 文件摘要 |
| `utils/archive.py` | `shared/files/archive.py` | 安全归档读取 |
| `utils/paths.py` | `shared/files/paths.py` | 相对路径校验 |

迁移期间旧路径保留兼容导出，例如：

```python
# app/core/redis.py（临时兼容层）
from app.platform.messaging.redis import get_async_redis, get_redis

__all__ = ["get_redis", "get_async_redis"]
```

所有调用方迁移后再删除兼容层。

### 8.2 后端业务模块

| 当前文件 | 目标模块 |
|---|---|
| `endpoints/auth.py`、`schemas/auth.py` | `modules/auth` |
| `endpoints/users.py`、`crud/user.py`、`models/user.py`、`schemas/user.py` | `modules/users` |
| Dashboard 使用的聚合查询 | `modules/dashboard` |
| `endpoints/agent_packages.py`、`services/agent_package_service.py`、`crud/agent_package.py`、`models/agent_package.py`、`schemas/agent_package.py` | `modules/objects/agent_packages` |
| `endpoints/frameworks.py`、`services/framework_service.py`、框架专属查询 | `modules/objects/frameworks` |
| `endpoints/projects.py`、`project_files.py`、`project_members.py` | `modules/objects/projects` |
| `models/resource.py`、Resource 通用查询 | `shared/resources` |
| `endpoints/environments.py`、`deployments.py`、`services/agent_deploy_service.py`、`deployment_service.py`、`ssh_service.py` | `modules/executors` |
| `models/environment.py`、`models/command.py`、`schemas/environment.py`、`crud/environment.py` | `modules/executors` |
| `endpoints/tasks.py`、`task_results.py`、`streams.py` | `modules/tasks` |
| `services/task_lifecycle.py`、`crud/task.py`、`models/task.py`、`schemas/task.py` | `modules/tasks` |
| `endpoints/agents.py` | `modules/agent_gateway` |
| `jobs/maintenance.py` | 调度循环留 platform，任务/执行器修复逻辑分别进入对应模块 facade |

### 8.3 前端

| 当前文件 | 目标目录 |
|---|---|
| `api.js` | `platform/http/client.js` + `download.js` |
| `auth.js` | `platform/auth/session.js` |
| `router.js` | `app/router.js`，业务路由拆入各模块 `routes.js` |
| `views/Layout.vue` | `app/layout/MainLayout.vue` |
| `views/Login.vue` | `modules/auth/pages/LoginPage.vue` |
| `views/Dashboard.vue` | `modules/dashboard/pages/DashboardPage.vue` |
| `views/Users.vue` | `modules/users/pages/UserListPage.vue` |
| `views/AgentPackages.vue` | `modules/objects/agent_packages/pages/AgentPackageListPage.vue` |
| `views/Frameworks.vue` | `modules/objects/frameworks/pages/FrameworkListPage.vue` |
| `views/Projects.vue`、`ProjectDetail.vue` | `modules/objects/projects/pages` |
| `views/Environments.vue`、`ExecutorDetail.vue` | `modules/executors/pages` |
| `views/Tasks.vue`、`TaskCreate.vue`、`TaskDetail.vue` | `modules/tasks/pages` |
| `components/LogConsole.vue` | `modules/tasks/components`，若部署日志也复用则保留 shared |
| 其他通用组件 | `shared/components` |
| `theme/` | `shared/theme` |
| `constants.js` | `shared/constants/terminology.js` + 各模块 constants |

## 9. 路由聚合方式

### 9.1 后端

每个模块只导出一个 router：

```python
# modules/tasks/__init__.py
from app.modules.tasks.router import router

__all__ = ["router"]
```

总路由只负责聚合：

```python
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(frameworks.router)
api_router.include_router(agent_packages.router)
api_router.include_router(executors.router)
api_router.include_router(tasks.router)
api_router.include_router(agent_gateway.router)
```

现有 URL 前缀保持原样，不因为目录变化修改 URL。

### 9.2 前端

每个模块导出 routes 数组：

```javascript
export const taskRoutes = [
  { path: 'tasks', component: () => import('./pages/TaskListPage.vue') },
  { path: 'tasks/create', component: () => import('./pages/TaskCreatePage.vue') },
  { path: 'tasks/:id', component: () => import('./pages/TaskDetailPage.vue') }
]
```

`app/router.js` 只聚合各模块 routes，旧路径和 redirect 全部保留。

## 10. 功能不变的保护基线

在移动任何业务代码前，先生成以下快照。

### 10.1 HTTP/OpenAPI 快照

记录：

- 路径。
- Method。
- request body schema。
- response model。
- status code。
- 权限要求。

重构前后对 `app.openapi()` 进行结构化 diff。允许文档顺序变化，不允许契约字段变化。

### 10.2 数据库快照

记录 PostgreSQL：

- 表名和字段。
- 类型和可空性。
- 主键、外键、唯一约束、索引。
- 当前迁移函数清单。

重构阶段数据库快照必须零差异，不生成业务迁移。

### 10.3 外部资源契约

记录并锁定：

- MinIO Bucket 名称和 Object Key 规则。
- Redis Stream Key 和 TTL。
- WebSocket URL、鉴权方式和消息结构。
- Agent API 路径、请求和响应结构。
- Docker Compose 服务名、端口、Volume、环境变量。
- 前端路由和 redirect。

### 10.4 行为基线

至少覆盖：

1. 管理员登录、当前用户、修改密码。
2. 用户新增、修改、停用和权限拒绝。
3. 项目新增、成员权限、文件上传/下载/删除。
4. 框架上传、检查、下载、重新部署。
5. Agent 包上传和重新部署 Agent。
6. 执行器新增、SSH 测试、启停和详情。
7. 任务创建、重跑、取消、超时。
8. 实时日志、历史日志、结果和附件下载。
9. Agent 心跳、领取任务、状态上报。

## 11. 分阶段实施计划

### 阶段 0：冻结基线

工作项：

- 补充 OpenAPI 快照测试。
- 补充路由清单测试。
- 补充数据库结构快照。
- 整理现有真实冒烟流程。
- 给当前后端、前端镜像添加可回滚标签。
- 禁止该阶段新增功能代码。

验收：

- 当前测试全部通过。
- 前端生产构建通过。
- 远端真实任务通过。
- 快照文件纳入版本控制。

### 阶段 1：创建公共层骨架

工作项：

- 新增 `platform/`、`shared/`、`modules/`。
- 迁移 config/db/redis/storage/security。
- 迁移 `model_to_dict`、HTTP helpers。
- 旧 import 路径保留 re-export 兼容层。
- 不迁移任何菜单模块。

验收：

- OpenAPI 和数据库快照零差异。
- 旧测试 import 不需要一次性修改。
- 服务启动、Redis、MinIO、登录正常。

### 阶段 2：认证、用户、仪表盘

迁移顺序：

```text
auth → users → dashboard
```

每迁移一个模块：

- 后端 router/schema/model/repository/service 归位。
- 前端 page/api/routes 归位。
- 原文件变成临时兼容导出或删除。
- 运行模块测试、契约测试、前端构建。
- 部署远端冒烟后再开始下一个模块。

### 阶段 3：对象管理

迁移顺序：

```text
shared/resources
    ↓
agent_packages → frameworks → projects
```

重点：

- `Resource/ResourceFile/ResourceMember` 继续使用原表。
- 框架和项目的业务 service 分离。
- 通用 MinIO + ResourceFile 写入统一放 shared。
- 项目成员权限统一放 shared permissions。

验收重点：文件版本、SHA、Object Key、归档路径完全不变。

### 阶段 4：执行器管理

迁移：

- Environment/Deployment/AgentCommand 模型。
- 执行器 CRUD 和 overview。
- SSH 会话。
- Agent 部署。
- 框架部署。
- 部署日志。

该模块风险较高，应增加部署状态机测试，覆盖 pending/deploying/deployed/failed。

### 阶段 5：任务管理

迁移：

- Task/TaskFile/TaskResult/TaskArtifact。
- 创建、重跑、取消、超时。
- 项目快照。
- 任务实时日志 WebSocket。
- 结果和附件。
- 前端任务列表、创建和详情页面。

必须使用真实高日志量任务验证性能，确保重构没有恢复逐行推送或改变日志游标行为。

### 阶段 6：Agent Gateway

最后迁移 `agents.py`，按内部职责拆成：

```text
modules/agent_gateway/
├── router.py
├── schemas.py
├── authentication.py
├── heartbeat_service.py
├── action_service.py
├── task_dispatch_service.py
├── upload_service.py
└── facade.py
```

Agent Gateway 可以调用 tasks/executors facade，但不得直接包含大量跨模块数据库状态机。

验收必须使用真实 Agent：

- 心跳在线。
- 领取任务。
- 下载项目。
- 上传批量日志。
- 上传结果和附件。
- 任务成功/失败/取消状态上报。

### 阶段 7：收尾

- 删除旧目录中的兼容导出文件。
- 删除未使用 import。
- 增加依赖方向静态检查。
- 更新 README、部署文档、模块开发模板。
- 输出最终目录树和模块所有权表。
- 完成全量回归和远端验证。

## 12. 测试策略

### 12.1 Platform 单元测试

- BaseRepository 基础操作。
- 事务提交、回滚、冲突转换。
- 对象存储接口。
- Redis Stream 批量写入和游标读取。
- JWT、密码、加解密。
- 归档路径安全检查。
- 公共异常到 HTTP 映射。

### 12.2 模块测试

每个模块至少包含：

- service 业务校验测试。
- repository 特定查询测试。
- router 权限和状态码测试。
- schema 请求/响应边界测试。

### 12.3 契约测试

- OpenAPI snapshot。
- 前端 route snapshot。
- Agent API 请求/响应 fixture。
- WebSocket 消息 fixture。
- 数据库 schema snapshot。

### 12.4 端到端冒烟

建议在 `tests/e2e` 固化一条主流程：

```text
登录
→ 创建/选择项目
→ 确认执行器在线
→ 确认框架已部署
→ 创建任务
→ 接收实时日志
→ 等待任务结束
→ 校验用例结果
→ 下载报告附件
```

## 13. 部署与回滚

### 13.1 每阶段部署流程

1. 本地模块测试。
2. 全量契约测试。
3. 前端生产构建。
4. 为当前远端镜像创建备份 Tag。
5. 构建新后端/前端镜像。
6. 重启对应容器。
7. 检查 `/health`、容器状态和日志。
8. 执行模块冒烟。
9. 涉及 tasks/agent_gateway 时运行真实任务。

Agent 源码目录保持独立。只有 `agent/` 实际代码变化时才重新打包并部署 Agent，单纯后端目录移动不应重建 Agent。

### 13.2 回滚条件

出现以下任一情况立即回滚当前阶段：

- OpenAPI 快照出现非预期差异。
- 数据库结构发生变化。
- Agent 无法心跳或领取任务。
- 任务状态无法进入终态。
- 实时日志断流或重复。
- 文件下载内容/SHA 不一致。
- 旧前端 URL 失效。

### 13.3 回滚单位

- 每个业务模块一个独立提交和部署批次。
- 公共层每种能力一个独立提交，例如 DB、Storage、Redis 分开。
- 禁止把公共层迁移、任务模块迁移和前端页面改版放在同一提交。

## 14. 风险与控制

| 风险 | 级别 | 控制方式 |
|---|---|---|
| 大量移动导致循环 import | 高 | facade、依赖方向检查、兼容导出 |
| ORM 模型未完整注册 | 高 | 集中模型注册测试、Base.metadata 表快照 |
| API schema/错误文案变化 | 高 | OpenAPI + 行为契约测试 |
| Resource 共表被错误拆分 | 高 | 第一阶段禁止数据库设计调整 |
| Agent Gateway 跨模块状态更新遗漏 | 高 | 最后迁移、真实 Agent 全流程测试 |
| MinIO Object Key 或 Version ID 变化 | 高 | 固化对象存储 fixture 和 SHA 验证 |
| 公共层过度抽象 | 中 | Rule of Three、基础仓库保持最小能力 |
| 兼容导出长期残留 | 中 | 阶段 7 建立删除清单和 import 扫描 |
| 前端移动导致懒加载路径失效 | 中 | route snapshot + `npm run build` |

## 15. 完成定义

满足以下条件才算重构完成：

- 所有菜单均有前后端同名模块目录。
- 模块内部文件职责清晰，无超大“万能模块”。
- 公共 DB、HTTP、Storage、Redis、认证逻辑只有一份实现。
- 业务模块不重复实现提交回滚、下载响应、日志 Stream、MinIO 基础操作。
- `platform` 和 `shared` 不反向依赖业务模块。
- 后端旧横向业务目录和兼容导出全部清理。
- OpenAPI、数据库、Redis、MinIO、Agent、前端路由契约均未改变。
- 所有测试和前端构建通过。
- 远端平台、Agent 在线且真实任务运行成功。
- README、部署文档和新增模块模板已更新。

## 16. 建议的第一批实施内容

第一批只做“保护基线 + 公共层骨架”，不移动业务菜单：

1. 新增 OpenAPI、数据库、前端路由快照。
2. 创建 `platform/`、`shared/`、`modules/` 空目录及依赖说明。
3. 迁移 `config/db/redis/storage`，旧路径 re-export。
4. 迁移公共异常、事务和 HTTP helper。
5. 全量验证后部署远端。

第一批稳定后，再从 `auth/users` 开始逐模块迁移。这样能够先验证新的公共基础是否可靠，同时保持回滚范围最小。
