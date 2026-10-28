# 平台与执行器部署文档

本文按可直接执行的顺序说明在线、离线、同机和远端部署。示例平台地址为 `192.168.14.100`，项目目录为 `/opt/test-platform`。

## 1. 最终部署组成

平台服务器运行 5 个容器：

```text
testplatform-frontend   80
testplatform-backend    8000
testplatform-pg         内网
testplatform-redis      内网
testplatform-minio      9000 / 9001
```

每台执行器主机运行：

```text
kw-agent                常驻
kw-task-{task_id}       有任务时临时创建
```

不再部署 Celery Worker、Beat 和 Flower。

## 2. 前置条件

### 2.1 平台服务器

- Linux x86_64；CentOS 7 可使用仓库提供的兼容 Compose 覆盖。
- Docker 20.10+。
- Docker Compose v2 或 `docker-compose` v1。
- 建议至少 4 核、8 GB 内存、50 GB 磁盘。

检查：

```bash
docker version
docker compose version || docker-compose --version
uname -m
```

### 2.2 网络

| 来源 | 目标端口 | 用途 |
|---|---:|---|
| 浏览器 | 80 | 平台页面 |
| 浏览器/Agent | 8000 | API 与 Agent WebSocket |
| 管理员 | 9001 | MinIO 控制台，可限制管理网 |
| 必要客户端 | 9000 | MinIO S3，可限制管理网 |

Agent 只需主动访问平台 8000，不需要平台 SSH 进入执行器，也不需要执行器访问 PostgreSQL、Redis 或 MinIO。

## 3. 在线部署平台

### 3.1 上传代码

```bash
mkdir -p /opt/test-platform
cd /opt/test-platform
# 将仓库全部文件复制到此目录
ls backend frontend agent docker-compose.yml scripts
```

### 3.2 创建配置

```bash
cd /opt/test-platform
cp .env.example .env
vi .env
```

至少修改：

```dotenv
POSTGRES_DB=testplatform
POSTGRES_USER=testplatform
POSTGRES_PASSWORD=数据库强密码
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=MinIO强密码
JWT_SECRET=至少32位随机字符串
SUPERADMIN_USERNAME=admin
SUPERADMIN_PASSWORD=管理员强密码
CORS_ORIGINS=http://192.168.14.100
AGENT_PUBLIC_URL=http://192.168.14.100:8000
AGENT_IMAGE=kw-agent:latest
RUNTIME_IMAGE=kw-executor-runtime:latest
```

`AGENT_PUBLIC_URL` 必须是执行器可访问的地址，不能填容器名或 `localhost`。

### 3.3 构建并启动

```bash
cd /opt/test-platform
chmod +x scripts/deploy-docker.sh
./scripts/deploy-docker.sh
```

脚本会：

1. 检测 Docker Compose 命令。
2. CentOS 7 内核自动叠加 `docker-compose.centos7.yml`。
3. 构建 Backend 和 Frontend 镜像。
4. 启动 5 个容器并删除旧版遗留的孤立 Celery 容器。
5. 等待 `/health` 成功。

手工启动方式：

```bash
docker compose up -d --build --remove-orphans
```

CentOS 7：

```bash
docker-compose -f docker-compose.yml -f docker-compose.centos7.yml \
  up -d --build --remove-orphans
```

### 3.4 验证

```bash
docker compose ps
curl -fsS http://127.0.0.1:8000/health
curl -I http://127.0.0.1/
```

访问：

- 平台：`http://192.168.14.100`
- API 文档：`http://192.168.14.100:8000/docs`
- MinIO 控制台：`http://192.168.14.100:9001`

首次登录使用 `.env` 的 `SUPERADMIN_USERNAME` 和 `SUPERADMIN_PASSWORD`，登录后建议立即修改密码。

## 4. 制作和部署 Agent 镜像

### 4.1 在有网络机器构建

```bash
cd /opt/test-platform
docker build -f agent/Dockerfile -t kw-agent:latest .
docker build -f agent/runtime.Dockerfile -t kw-executor-runtime:latest .
docker image inspect kw-agent:latest >/dev/null
docker image inspect kw-executor-runtime:latest >/dev/null
```

`runtime.Dockerfile` 是框架执行的基础容器。框架如果是 Linux 打包后的可执行程序，不需要在 runtime 安装项目 Python 环境；仍保留 runtime 隔离，可限制任务文件、进程和依赖冲突。

### 4.2 导出给离线执行器

```bash
docker save -o kw-executor-images.tar \
  kw-agent:latest kw-executor-runtime:latest
sha256sum kw-executor-images.tar > kw-executor-images.tar.sha256
```

把两个文件复制到执行器后：

```bash
sha256sum -c kw-executor-images.tar.sha256
docker load -i kw-executor-images.tar
docker image inspect kw-agent:latest >/dev/null
docker image inspect kw-executor-runtime:latest >/dev/null
```

## 5. 注册远端执行器

### 5.1 平台页面操作

1. 在“对象管理 / 测试框架”上传框架归档。
2. 在“环境管理 / 执行器环境管理”创建环境。
3. 填写名称、主机标识、工作目录、最大并发和框架。
4. 点击“生成 Agent 注册命令”。
5. 完整复制命令；每次重新生成都会使旧 Token 失效。

### 5.2 执行注册命令

登录目标 Linux 主机，确认镜像已存在，然后粘贴平台生成的整段命令。命令等价于：

```bash
mkdir -p /opt/kw-executor/framework /opt/kw-executor/jobs /opt/kw-executor/state
docker rm -f kw-agent >/dev/null 2>&1 || true
docker run -d --name kw-agent --restart unless-stopped \
  -e KW_PLATFORM_URL=http://192.168.14.100:8000 \
  -e KW_AGENT_TOKEN='平台一次性返回的Token' \
  -e KW_ENVIRONMENT_ID=1 \
  -e KW_EXECUTOR_ROOT=/executor \
  -e KW_HOST_ROOT=/opt/kw-executor \
  -e KW_RUNTIME_IMAGE=kw-executor-runtime:latest \
  -e KW_MAX_CONCURRENCY=2 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /etc/os-release:/host-os-release:ro \
  -v /opt/kw-executor:/executor \
  kw-agent:latest
```

验证：

```bash
docker ps --filter name=kw-agent
docker logs --tail=100 kw-agent
curl -fsS http://192.168.14.100:8000/health
```

页面通常在 15 秒内显示 `online`。

### 5.3 平台服务器同机部署 Agent

支持。把平台服务器自身地址作为环境 `host`，在平台服务器执行相同注册命令即可。Agent 仍是独立容器，任务仍在 runtime 容器运行；注意平台与测试任务共享 CPU、内存和磁盘，应保守设置并发数。

## 6. 上传并部署测试框架

### 6.1 打包框架

框架归档不再需要 `framework.json` 清单，名称、OS、架构和执行器入口路径均在页面填写。归档只需包含框架目录结构即可，例如打包后的 Linux 框架：

```text
framework.zip
└── TestFramework_kw/
    ├── driver/
    │   └── kw-cli
    ├── testsuits/
    └── ...
```

上传时在界面填写：

| 字段 | 说明 |
|---|---|
| 框架名称 | 字母 / 数字 / 点 / 横线 / 下划线，如 `x86-centos` |
| 操作系统 | `linux` 或 `windows` |
| CPU 架构 | `x86_64` 或 `arm64` |
| 执行器入口 | 相对归档根目录的路径，如 `driver/自动化测试框架` |

平台会自动探测归档是否整体包裹了一层目录（单顶层目录时自动剥离，作为 `archive_root`），并校验入口文件真实存在。

Windows 的 `.exe` 不能直接在 Linux runtime 运行，必须在 Linux 上重新打包生成 Linux 可执行程序（统一打包执行，不再支持 `runner_mode: python` 源码执行）。

### 6.2 页面部署

1. 上传或替换框架对象。
2. 确认执行器在线。
3. 在环境详情点击“部署框架”。
4. 查看部署日志直到环境为 `ready`。

Agent 会下载、校验、验证并原子切换框架。框架更新后，相关环境显示 `update_available`，再次部署即可。

## 7. 上传项目并运行

1. 创建测试项目。
2. 上传原项目下的 `testcase`、`business`、`config`、`casedata` 等文件，保持相对路径。
3. 给测试人员配置项目成员权限。
4. 新建任务，选择项目和 `ready` 环境。
5. 编辑本次 `配置文件.ini`，可为同一项目创建多组不同被测地址的并发任务。
6. 在任务详情查看实时日志、结果和报告。

## 8. 完全离线部署平台

### 8.1 在联网且同架构机器准备镜像

先按第 3 节构建应用镜像，并拉取基础服务：

```bash
docker pull postgres:16-alpine
docker pull redis:7-alpine
docker pull minio/minio:RELEASE.2025-04-22T22-12-26Z
docker build -f backend/Dockerfile -t testplatform-backend:v1 .
docker build -f frontend/Dockerfile -t testplatform-frontend:v1 .
docker save -o test-platform-images.tar \
  postgres:16-alpine \
  redis:7-alpine \
  minio/minio:RELEASE.2025-04-22T22-12-26Z \
  testplatform-backend:v1 \
  testplatform-frontend:v1
sha256sum test-platform-images.tar > test-platform-images.tar.sha256
```

同时复制完整项目目录、镜像包和摘要文件到离线服务器。

### 8.2 离线服务器加载并启动

```bash
cd /opt/test-platform
sha256sum -c test-platform-images.tar.sha256
docker load -i test-platform-images.tar
cp .env.example .env
vi .env
docker compose up -d --no-build --remove-orphans
```

CentOS 7 使用：

```bash
docker-compose -f docker-compose.yml -f docker-compose.centos7.yml \
  up -d --no-build --remove-orphans
```

离线环境不要运行会重新构建镜像的命令，除非已经准备本地软件包镜像源。

## 9. 更新平台

### 9.1 更新前备份

```bash
mkdir -p /opt/test-platform-backup
docker exec testplatform-pg pg_dump -U testplatform -Fc testplatform \
  > /opt/test-platform-backup/postgres-$(date +%Y%m%d-%H%M%S).dump
```

### 9.2 更新代码并重建

```bash
cd /opt/test-platform
# 覆盖为新代码，但保留 .env
./scripts/deploy-docker.sh
```

Backend 启动会执行幂等增量迁移。升级脚本使用 `--remove-orphans`，旧版的 `testplatform-orchestrator`、`testplatform-beat`、`testplatform-flower` 会被停止并删除，数据卷不会删除。

## 10. 运维命令

查看容器：

```bash
docker compose ps
```

查看平台日志：

```bash
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=100 frontend
docker compose logs --tail=100 postgres redis minio
```

查看执行器：

```bash
docker logs -f --tail=200 kw-agent
docker ps --filter 'name=kw-task-'
```

重启平台应用但不停止数据服务：

```bash
docker compose restart backend frontend
```

停止和恢复整个平台：

```bash
docker compose stop
docker compose start
```

不要执行 `docker compose down -v`，它会删除 PostgreSQL、Redis 和 MinIO 数据卷。

## 11. 故障排查

### Backend 无法启动

```bash
docker compose logs --tail=300 backend
docker compose ps postgres redis minio
```

检查 `.env` 密码、数据服务健康状态和 CentOS 7 是否使用兼容覆盖文件。

### Agent 一直离线

```bash
docker logs --tail=300 kw-agent
curl -v http://192.168.14.100:8000/health
```

常见原因：Token 已轮换、环境已停用、`AGENT_PUBLIC_URL` 不可达、代理未放行 WebSocket。

### 命令停在 queued

确认环境 `online`、框架部署状态正确和 Agent 有空闲槽。命令保存在 PostgreSQL，不需要检查 Redis 队列。

### 命令重复投递

Agent 会按 `command_id` 返回本地缓存结果，运行容器固定为 `kw-task-{task_id}`。检查 Agent 持久化目录 `/opt/kw-executor/state` 是否正确挂载，不要让多个 Agent 使用同一个环境 Token 同时运行。

### 框架验证失败

核对页面填写的 `os`、`arch`、`runner_path`；Linux 执行器不能运行 Windows `.exe`。
