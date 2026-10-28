"""API 响应模型公共基类。"""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """支持直接从 SQLAlchemy 模型读取字段的响应模型基类。"""

    model_config = ConfigDict(from_attributes=True)
