"""对象存储实现必须满足的最小协议。"""

from typing import Protocol


class ObjectStorageProtocol(Protocol):
    def put_bytes(self, bucket: str, key: str, data: bytes) -> str | None: ...

    def get_bytes(self, bucket: str, key: str, version_id: str | None = None) -> bytes: ...

    def remove(self, bucket: str, key: str) -> None: ...
