#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/test-platform}"
cd "$PROJECT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已生成 $PROJECT_DIR/.env，请修改密码后重新执行。"
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif docker-compose --version >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "未安装 Docker Compose" >&2
  exit 1
fi

COMPOSE_ARGS=()
if [[ "$(uname -r)" == 3.10.* && -f docker-compose.centos7.yml ]]; then
  COMPOSE_ARGS=(-f docker-compose.yml -f docker-compose.centos7.yml)
  DEFAULT_PIP_INDEX_URL="https://mirrors.aliyun.com/pypi/simple"
  DEFAULT_NPM_REGISTRY="https://registry.npmmirror.com"
else
  DEFAULT_PIP_INDEX_URL="https://pypi.org/simple"
  DEFAULT_NPM_REGISTRY="https://registry.npmjs.org"
fi

PIP_INDEX_URL="${PIP_INDEX_URL:-$DEFAULT_PIP_INDEX_URL}"
NPM_REGISTRY="${NPM_REGISTRY:-$DEFAULT_NPM_REGISTRY}"
docker build --build-arg PIP_INDEX_URL="$PIP_INDEX_URL" -f backend/Dockerfile -t testplatform-backend:v1 .
docker build --build-arg NPM_REGISTRY="$NPM_REGISTRY" -f frontend/Dockerfile -t testplatform-frontend:v1 .
"${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" up -d --no-build --remove-orphans
"${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" ps

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    echo "API 已就绪：http://127.0.0.1:8000"
    exit 0
  fi
  sleep 2
done

"${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" logs --tail=100 backend
echo "API 启动超时" >&2
exit 1
