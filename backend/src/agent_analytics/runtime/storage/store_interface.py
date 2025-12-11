from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TypeVar, Generic, Optional, List, Dict, Any, Type, Sequence
from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from agent_analytics.core.data.element_data import ElementData
from .store_config import StoreConfig

M = TypeVar('M', bound=BaseModel)

class SortOrder(Enum):
    ASCENDING = 1
    DESCENDING = -1

class StoreException(Exception):
    """Base exception class for Store operations"""
    pass

class DuplicateKeyException(StoreException):
    """Raised when attempting to insert a duplicate key"""
    pass

class QueryOperator(Enum):
    EQUAL = "eq"
    GREATER_EQUAL = "gte"
    LESS_EQUAL = "lte"
    ARRAY_CONTAINS = "array_contains"
    EQUALS_MANY = "eqm"

@dataclass
class QueryFilter:
    operator: QueryOperator
    value: Any
    
"""
Abstract base store interface that can be implemented by different storage backends
"""
class BaseStore(ABC, Generic[M]):
    def __init__(self, use_field_aliases: bool = False):
        self.use_field_aliases = use_field_aliases

    def _translate_field_name(self, field: str, type_info: Type[M]) -> str:
        if not self.use_field_aliases:
            return field

        parts = field.split('.')
        current_class = type_info
        for part in parts[:-1]:
            field_info = current_class.model_fields.get(part)
            if field_info is None or field_info.annotation is None:
                return field
            current_class = field_info.annotation
            if not hasattr(current_class, 'model_fields'):
                return field

        last_part = parts[-1]
        field_info = current_class.model_fields.get(last_part)
        if field_info and field_info.serialization_alias:
            parts[-1] = field_info.serialization_alias
            return '.'.join(parts)
        return field

    
    @abstractmethod
    def _translate_query_filter(self, field:str,value: QueryFilter) -> Any:
        """
        Translate generic query to concrete storage backend query
        """
        pass

    @abstractmethod
    async def initialize(self, **kwargs) -> None:
        """Initialize the store with any necessary setup"""
        pass

    @abstractmethod
    async def store(
        self, 
        data: M, 
        type_info: Optional[Type[M]] = None
    ) -> str:
        """Store a single document with optional type information"""
        pass

    @abstractmethod
    async def retrieve(
        self,
        id_field: str,
        id_value: Any,
        type_info: Optional[Type[M]] = None
    ) -> Optional[M]:
        """Retrieve a single document"""
        pass

    @abstractmethod
    async def search(
        self,
        query: Dict[str, QueryFilter],
        type_info: Optional[Type[M]] = None,
        sort_by: Optional[Dict[str, SortOrder]] = None,
        skip: int = 0,
        limit: Optional[int] = None,
    ) -> List[M]:
        """Search for documents with optional type filtering"""
        pass

    @abstractmethod
    async def update(
        self,
        id_field: str,
        id_value: Any,
        data: Dict[str, Any],
        type_info: Optional[Type[M]] = None,
        upsert: bool = False
    ) -> bool:
        """Update a document"""
        pass

    @abstractmethod
    async def delete(
        self,
        id_field: str,
        id_value: Any,
        type_info: Optional[Type[M]] = None
    ) -> bool:
        """Delete a document"""
        pass

    @abstractmethod
    async def bulk_store(
        self,
        items: Sequence[M],
        type_info: Optional[Type[M]] = None,
        ignore_duplicates: bool = False
    ) -> List[str]:
        """Store multiple documents"""
        pass

    @abstractmethod
    async def bulk_update(
        self,
        updates: List[tuple[Dict[str, Any], Dict[str, Any]]],
        type_info: Optional[Type[M]] = None,
        ordered: bool = True
    ) -> int:
        """Update multiple documents"""
        pass

class StoreFactory(ABC):
    """Abstract factory for creating store instances"""
    @abstractmethod
    async def create_store(
        self,
        model_class: Type[M],
        config: StoreConfig,
    ) -> BaseStore[M]:
        """Create and return a configured store instance"""
        pass