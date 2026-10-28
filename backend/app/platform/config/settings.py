"""平台配置模块，统一从环境变量和 .env 文件读取运行参数。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """平台运行配置及其默认值。"""

    app_name: str = "Test Platform"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://testplatform:testplatform123@postgres:5432/testplatform"
    redis_url: str = "redis://redis:6379/0"
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_secure: bool = False
    jwt_secret: str = "change-me-in-production"
    access_token_expire_minutes: int = 120
    superadmin_username: str = "admin"
    superadmin_password: str = "admin123"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    project_bucket: str = "test-projects"
    framework_bucket: str = "test-frameworks"
    artifact_bucket: str = "test-task-artifacts"
    agent_bucket: str = "test-agents"
    agent_public_url: str = ""
    agent_deploy_wait_seconds: int = 90
    agent_image: str = "kw-agent:latest"
    runtime_image: str = "kw-executor-runtime:latest"
    agent_offline_after_seconds: int = 45
    command_lease_seconds: int = 90
    command_max_deliveries: int = 5
    maintenance_interval_seconds: int = 30
    log_retention_seconds: int = 604800

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的 CORS 来源转换成已清理的列表。"""

        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    """创建并缓存全局配置实例，避免重复解析环境变量。"""

    return Settings()


settings = get_settings()
