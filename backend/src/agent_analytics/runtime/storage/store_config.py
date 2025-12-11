from enum import Enum
from typing import Any

from pydantic import BaseModel


class StorageTag(str, Enum):
    """Tags for routing data objects to appropriate storage backends"""
    TASK = "task"

class StoreConfig(BaseModel):
    """Base configuration class for store implementations"""
    soft_delete: bool = False
    use_field_aliases: bool = False
    additional_config: dict[str, Any] | None = None

