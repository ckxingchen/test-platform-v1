"""SSH 凭据对称加密：基于 jwt_secret 派生 Fernet 密钥。"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.platform.config.settings import settings


def _fernet() -> Fernet:
    """从 jwt_secret 派生稳定的 Fernet 密钥（sha256 → urlsafe base64）。"""

    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """加密明文并返回可入库的字符串。"""

    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str | None) -> str | None:
    """解密密文字符串，空值或非法密文返回 None。"""

    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
