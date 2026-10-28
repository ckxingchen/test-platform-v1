# 业务模块开发指南

本指南约束重构后的 FastAPI + Vue 3 测试平台。目标是让每个菜单的前后端代码能够直接对应，同时避免数据库、HTTP、Redis、MinIO、鉴权等代码在业务目录中重复出现。

## 1. 依赖方向

```text
modules → shared → platform
```

- `platform` 只提供技术机制，禁止导入 `shared` 或 `modules`。
- `shared` 可以使用 `platform`，禁止导入业务模块。
- `modules` 可以使用 `shared` 和 `platform`。
- 一个业务模块调用另一个模块的行为时，优先从对方 `facade.py` 导入。
- ORM 关联查询需要引用其他模块模型时可以直接导入模型，但不得借此修改对方状态机。
- 旧的 `api/core/crud/db/models/schemas/services/utils` 横向目录已经移除，业务代码不得恢复这些路径。

依赖方向由 `tests/architecture/test_dependency_rules.py` 自动检查。

## 2. 后端模块模板

```text
backend/app/modules/<module>/
├── __init__.py
├── routes.py          # 聚合模块内多个 router
├── router.py          # FastAPI 路由、权限和 HTTP 状态码
├── schemas.py         # Pydantic 请求/响应结构
├── models.py          # 模块独占 ORM 模型
├── repository.py      # 查询和持久化，不提交事务
├── service.py         # 业务校验、状态流转和事务边界
├── facade.py          # 供其他业务模块调用的稳定入口
├── dependencies.py    # 可选，模块专属依赖
└── constants.py       # 可选，状态和枚举
```

调用链应保持：

```text
router → service → repository
   │         │
   └─ auth   ├─ shared
             ├─ platform
             └─ other_module.facade
```

### Router

- 只处理参数、FastAPI `Depends`、响应模型和 HTTP 错误转换。
- 不直接操作 MinIO、Redis 或编写复杂 SQL。
- 多个子路由由本模块 `routes.py` 聚合，总路由只包含模块入口。

### Service

- 负责业务规则、状态变化、复合写入和事务边界。
- 抛 `shared.errors.ServiceError`，不依赖 FastAPI。
- 不复制数据库提交回滚、文件哈希和对象存储基础代码。

### Repository

- 只负责数据库读取与写入，不依赖 FastAPI。
- 不调用 `commit()`，由 service 或明确的请求事务边界提交。
- 通用 CRUD 可以组合 `platform.db.repository.BaseRepository`，复杂查询保留显式函数。

### Facade

- 只导出其他模块真正需要的少量稳定方法。
- 不暴露 Router、HTTPException 或内部状态对象。
- 修改 Facade 接口时必须搜索并验证所有下游模块。

## 3. 前端模块模板

```text
frontend/src/modules/<module>/
├── api.js
├── routes.js
├── pages/
├── components/
└── composables/
```

- 页面只从本模块 `api.js` 获取后端能力。
- 模块独占组件留在模块目录；三个以上模块复用后才移动到 `shared/components`。
- 路由在模块 `routes.js` 定义，再由 `app/router.js` 聚合。
- 登录会话、Axios 实例属于 `platform`；主题、术语和展示组件属于 `shared`。
- 保持现有用户 URL 不变，旧 URL 统一放在 `app/routes_legacy.js`。

## 4. 新增模块步骤

1. 后端创建模块目录和 `routes.py`。
2. 在 `backend/app/router.py` 注册模块 `api_router`。
3. 前端创建同名模块、页面、`api.js` 和 `routes.js`。
4. 在 `frontend/src/app/router.js` 聚合路由。
5. 如需菜单入口，在 `frontend/src/app/navigation.js` 添加配置。
6. 增加模块单元测试、权限测试和关键行为测试。
7. 如果新增外部 URL 或数据库字段，有意识地更新契约基线并说明原因。
8. 运行后端测试和前端生产构建。

## 5. 提交前检查

```bash
python -m pytest -q
python -m compileall -q backend agent
cd frontend
npm run build
```

同时确认：

- OpenAPI 操作集合没有非预期变化。
- ORM 表和字段集合没有非预期变化。
- 前端现有路由没有丢失。
- `platform`、`shared` 依赖方向检查通过。
- 涉及任务和 Agent 时，真实执行器可以心跳、领取任务、上传批量日志和结果。
