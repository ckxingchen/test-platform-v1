"""统一创建 Redis 同步和异步客户端。"""

from app.platform.config.settings import settings
from redis import Redis
from redis.asyncio import Redis as AsyncRedis


def get_redis() -> Redis:
    """返回采用字符串解码的同步 Redis 客户端。"""

    return Redis.from_url(settings.redis_url, decode_responses=True)


def get_async_redis() -> AsyncRedis:
    """返回采用字符串解码的异步 Redis 客户端。"""

    return AsyncRedis.from_url(settings.redis_url, decode_responses=True)
