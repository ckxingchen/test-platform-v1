"""内容摘要计算工具。"""

import hashlib


def sha256_bytes(data: bytes) -> str:
    """返回字节内容的小写 SHA256 十六进制摘要。"""

    return hashlib.sha256(data).hexdigest()
