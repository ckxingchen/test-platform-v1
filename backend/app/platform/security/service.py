"""认证安全模块，负责密码摘要、JWT 令牌和 Agent 令牌。"""

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from app.platform.config.settings import settings

PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """使用带随机盐的 PBKDF2-SHA256 生成密码摘要。"""

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode(),
        base64.urlsafe_b64encode(digest).decode(),
    )


def verify_password(password: str, encoded: str) -> bool:
    """以恒定时间方式校验明文密码和已保存摘要。"""

    try:
        algorithm, iterations, salt_value, expected_value = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_value)
        expected = base64.urlsafe_b64decode(expected_value)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    """为用户签发包含角色和过期时间的 JWT 访问令牌。"""

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """校验并解析 JWT 访问令牌。"""

    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def create_agent_token() -> str:
    """生成只展示给 Agent 的高熵认证令牌。"""

    return secrets.token_urlsafe(48)


def hash_agent_token(token: str) -> str:
    """生成 Agent 令牌的不可逆 SHA256 摘要。"""

    return hashlib.sha256(token.encode()).hexdigest()


def verify_agent_token(token: str, expected_hash: str | None) -> bool:
    """以恒定时间方式验证 Agent 令牌。"""

    return bool(expected_hash) and hmac.compare_digest(hash_agent_token(token), expected_hash)
