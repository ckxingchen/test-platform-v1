"""MinIO 存储适配器，统一处理项目、框架和任务产物。"""

import io
from dataclasses import dataclass

from app.platform.config.settings import settings
from app.platform.storage.hashing import sha256_bytes
from minio import Minio
from minio.commonconfig import ENABLED
from minio.versioningconfig import SUSPENDED, VersioningConfig


@dataclass
class StoredObject:
    """对象上传后需要持久化的版本及校验信息。"""

    version_id: str | None
    sha256: str
    size: int


class ObjectStorage:
    """对 MinIO Python 客户端的轻量封装。"""

    def __init__(self) -> None:
        """根据平台配置创建 MinIO 客户端。"""

        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def ensure_buckets(self) -> None:
        """确保平台使用的存储桶存在并启用对象版本控制。"""

        buckets = (
            settings.project_bucket,
            settings.framework_bucket,
            settings.artifact_bucket,
            settings.agent_bucket,
        )
        for bucket in buckets:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
        self.client.set_bucket_versioning(settings.project_bucket, VersioningConfig(ENABLED))
        for bucket in (settings.framework_bucket, settings.artifact_bucket, settings.agent_bucket):
            self.client.set_bucket_versioning(bucket, VersioningConfig(SUSPENDED))

    def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        """上传字节内容并返回对象版本、摘要和大小。"""

        result = self.client.put_object(
            bucket, key, io.BytesIO(data), len(data), content_type=content_type
        )
        return StoredObject(
            getattr(result, "version_id", None),
            sha256_bytes(data),
            len(data),
        )

    def get_bytes(
        self, bucket: str, key: str, version_id: str | None = None
    ) -> bytes:
        """读取指定对象版本的完整字节内容。"""

        response = self.client.get_object(bucket, key, version_id=version_id)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def remove(self, bucket: str, key: str) -> None:
        """删除指定存储桶中的对象。"""

        self.client.remove_object(bucket, key)


storage = ObjectStorage()
