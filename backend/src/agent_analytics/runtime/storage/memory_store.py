import os
from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from .store_config import StoreConfig
from .store_interface import (
    BaseStore,
    DuplicateKeyException,
    M,
    QueryFilter,
    QueryOperator,
    SortOrder,
    StoreFactory,
)


class MemoryStore(BaseStore[M]):
    """In-memory implementation of BaseStore using a dictionary as storage with tenant isolation"""

    def __init__(
        self,
        id_field: str,
        model_class: type[M],
        tenant_id: str,
        use_field_aliases: bool = False,
        soft_delete: bool = False,
        case_sensitive: bool = True,
        ttl_hours: int | None = None,
        max_size: int | None = None
    ):
        super().__init__(use_field_aliases=use_field_aliases)
        self._storage: dict[str, dict[str, Any]] = {}
        self._soft_delete = soft_delete
        self.id_field = id_field
        self._case_sensitive = case_sensitive
        self.model_class = model_class
        self.tenant_id = tenant_id

        # Eviction configuration
        ttl_hours = ttl_hours if ttl_hours is not None else int(os.environ.get('MEMORY_STORE_TTL_HOURS', '24'))
        self._ttl_seconds = ttl_hours * 3600 if ttl_hours > 0 else 0
        self._max_size = max_size if max_size is not None else int(os.environ.get('MEMORY_STORE_MAX_SIZE', '10000'))

    async def initialize(self, **kwargs) -> None:
        """No initialization needed for in-memory store"""
        pass

    def _check_tenant_isolation(self, doc: dict[str, Any]) -> bool:
        """Check if document belongs to the current tenant"""
        return doc.get('tenant_id') == self.tenant_id

    def _evict(self) -> None:
        """Evict expired and excess documents globally across all tenants"""
        # First pass: Remove expired objects (if TTL > 0)
        if self._ttl_seconds > 0:
            now = datetime.utcnow()
            expired_ids = []
            for doc_id, doc in self._storage.items():
                created_at = doc.get('created_at')
                if created_at and (now - created_at).total_seconds() > self._ttl_seconds:
                    expired_ids.append(doc_id)

            for doc_id in expired_ids:
                del self._storage[doc_id]

        # Second pass: Remove oldest objects if at or over max size (and max_size > 0)
        # Need to make room for incoming object, so evict when at limit
        if self._max_size > 0 and len(self._storage) >= self._max_size:
            # Sort by created_at timestamp (oldest first)
            sorted_docs = sorted(
                self._storage.items(),
                key=lambda x: x[1].get('created_at', datetime.min)
            )

            # Calculate how many to evict (need to free up at least 1 slot for new item)
            num_to_evict = len(self._storage) - self._max_size + 1

            # Delete oldest documents
            for i in range(num_to_evict):
                doc_id = sorted_docs[i][0]
                del self._storage[doc_id]

    async def store(self, data: M, type_info: type[M] | None = None) -> str:
        """Store a single document"""
        # Run eviction check before storing
        self._evict()

        type_info = type_info or self.model_class

        # Convert to dict and get ID using configured id_field
        data_dict = data.model_dump(by_alias=self.use_field_aliases)
        if self.id_field not in data_dict:
            raise ValueError(f"Document missing required ID field: {self.id_field}")

        id_value = str(data_dict[self.id_field])

        # Check for duplicates within the same tenant
        existing_doc = self._storage.get(id_value)
        if existing_doc and self._check_tenant_isolation(existing_doc):
            raise DuplicateKeyException(f"Document with ID {id_value} already exists for tenant {self.tenant_id}")

        # Store copy of data with metadata including tenant_id
        self._storage[id_value] = {
            **deepcopy(data_dict),
            'tenant_id': self.tenant_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'type': type_info.__name__
        }

        if self._soft_delete:
            self._storage[id_value]['deleted_at'] = None

        return id_value

    async def retrieve(
        self,
        id_field: str,
        id_value: Any,
        type_info: type[M] | None = None
    ) -> M | None:
        """Retrieve a single document with tenant isolation"""
        # Use stored model_class as default if type_info is not provided
        type_info = type_info or self.model_class

        str_id = str(id_value)
        doc = self._storage.get(str_id)

        if not doc:
            return None

        # Check tenant isolation
        if not self._check_tenant_isolation(doc):
            return None

        if self._soft_delete and doc.get('deleted_at') is not None:
            return None

        if doc.get('type') != type_info.__name__:
            return None

        filtered_doc = {k: v for k, v in doc.items()
                      if k not in ['created_at', 'updated_at', 'deleted_at', 'type', 'tenant_id']}

        return type_info.model_validate(filtered_doc)

    def _matches_filter(self, doc: dict[str, Any], field: str, filter_: QueryFilter) -> bool:
        """Check if document matches the given filter"""
        # Handle nested fields using dot notation
        value = doc
        for part in field.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return False
            if value is None:
                return False

        filter_value = filter_.value

        # Equal operator works with any types
        if filter_.operator == QueryOperator.EQUAL:
            # Case-insensitive comparison for strings
            if isinstance(value, str) and isinstance(filter_value, str) and not self._case_sensitive:
                return value.lower() == filter_value.lower()
            return value == filter_value

        # ARRAY_CONTAINS checks if the array field contains the filter value
        if filter_.operator == QueryOperator.ARRAY_CONTAINS:
            if isinstance(value, list):
                # For case-insensitive string comparison
                if isinstance(filter_value, str) and not self._case_sensitive:
                    filter_value_lower = filter_value.lower()
                    for item in value:
                        if isinstance(item, str) and item.lower() == filter_value_lower:
                            return True
                    return False
                else:
                    # Direct comparison for case-sensitive or non-string types
                    return filter_value in value
            return False

        # EQUALS_MANY checks if field value is in the provided array
        if filter_.operator == QueryOperator.EQUALS_MANY:
            if isinstance(filter_value, list):
                # For case-insensitive string comparison
                if isinstance(value, str) and not self._case_sensitive:
                    value_lower = value.lower()
                    for item in filter_value:
                        if isinstance(item, str) and item.lower() == value_lower:
                            return True
                    return False
                else:
                    # Direct comparison for case-sensitive or non-string types
                    return value in filter_value
            return False

        # For comparison operators, handle type-specific comparisons
        if filter_.operator in [QueryOperator.GREATER_EQUAL, QueryOperator.LESS_EQUAL]:
            # Both are numeric types (int, float)
            if isinstance(value, (int, float)) and isinstance(filter_value, (int, float)):
                if filter_.operator == QueryOperator.GREATER_EQUAL:
                    return value >= filter_value
                else:  # LESS_EQUAL
                    return value <= filter_value

            # Both are strings
            elif isinstance(value, str) and isinstance(filter_value, str):
                # Apply case-insensitivity if configured
                if not self._case_sensitive:
                    value = value.lower()
                    filter_value = filter_value.lower()

                if filter_.operator == QueryOperator.GREATER_EQUAL:
                    return value >= filter_value
                else:  # LESS_EQUAL
                    return value <= filter_value

            # Both are datetime objects
            elif isinstance(value, datetime) and isinstance(filter_value, datetime):
                # If one is naive and the other is aware, copy the timezone
                if value.tzinfo is None and filter_value.tzinfo is not None:
                    value = value.replace(tzinfo=UTC)

                if filter_.operator == QueryOperator.GREATER_EQUAL:
                    return value >= filter_value
                else:  # LESS_EQUAL
                    return value <= filter_value

            # Types don't match or aren't comparable
            return False

        return False

    def _translate_query_filter(self, field: str, value: QueryFilter) -> Any:
        """Translation not needed for in-memory implementation"""
        return value

    async def search(
        self,
        query: dict[str, QueryFilter],
        type_info: type[M] | None = None,
        sort_by: dict[str, SortOrder] | None = None,
        skip: int = 0,
        limit: int | None = None,
    ) -> list[M]:
        """Search for documents with tenant isolation and optional type filtering"""
        # Use stored model_class as default if type_info is not provided
        type_info = type_info or self.model_class

        # Filter documents
        results = []
        for doc in self._storage.values():
            # Check tenant isolation first
            if not self._check_tenant_isolation(doc):
                continue

            if self._soft_delete and doc.get('deleted_at') is not None:
                continue

            if doc.get('type') != type_info.__name__:
                continue

            matches = True
            for field, filter_ in query.items():
                translated_field = self._translate_field_name(field, type_info) if type_info else field
                if not self._matches_filter(doc, translated_field, filter_):
                    matches = False
                    break

            if matches:
                filtered_doc = {k: v for k, v in doc.items()
                              if k not in ['created_at', 'updated_at', 'deleted_at', 'type', 'tenant_id']}
                results.append(filtered_doc)

        # Sort results if requested
        if sort_by:
            for field, order in reversed(sort_by.items()):
                translated_field = self._translate_field_name(field, type_info) if type_info else field
                results.sort(
                    key=lambda x: self._get_nested_value(x, translated_field),
                    reverse=(order == SortOrder.DESCENDING)
                )

        # Apply pagination
        results = results[skip:]
        if limit is not None:
            results = results[:limit]

        # Convert to model instances
        return [type_info.model_validate(doc) for doc in results]

    def _get_nested_value(self, doc: dict[str, Any], field: str) -> Any:
        """Get value from nested dictionary using dot notation"""
        value = doc
        for part in field.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    async def update(
        self,
        id_field: str,
        id_value: Any,
        data: dict[str, Any],
        type_info: type[M] | None = None,
        upsert: bool = False
    ) -> bool:
        """Update a document with tenant isolation"""
        # Use stored model_class as default if type_info is not provided
        type_info = type_info or self.model_class

        str_id = str(id_value)
        existing_doc = self._storage.get(str_id)

        # Check if document exists and belongs to current tenant
        if not existing_doc or not self._check_tenant_isolation(existing_doc):
            if not upsert:
                return False
            # Create new document for this tenant
            self._storage[str_id] = {
                self.id_field: str_id,
                'tenant_id': self.tenant_id,
                'created_at': datetime.utcnow(),
                'type': type_info.__name__
            }
            if self._soft_delete:
                self._storage[str_id]['deleted_at'] = None

        doc = self._storage[str_id]

        # Type check
        if doc.get('type') != type_info.__name__:
            if not upsert:
                return False
            doc['type'] = type_info.__name__

        if self._soft_delete and doc.get('deleted_at') is not None:
            if not upsert:
                return False
            doc['deleted_at'] = None

        # Update fields
        update_data = deepcopy(data)
        update_data['updated_at'] = datetime.utcnow()
        doc.update(update_data)

        # Ensure tenant_id doesn't get overwritten
        doc['tenant_id'] = self.tenant_id

        # Validate updated document
        try:
            filtered_doc = {k: v for k, v in doc.items()
                          if k not in ['created_at', 'updated_at', 'deleted_at', 'type', 'tenant_id']}
            type_info.model_validate(filtered_doc)
        except Exception:
            # Rollback changes on validation failure
            if upsert and str_id not in self._storage:
                del self._storage[str_id]
            return False

        return True

    async def delete(
        self,
        id_field: str,
        id_value: Any,
        type_info: type[M] | None = None
    ) -> bool:
        """Delete a document with tenant isolation"""
        # Use stored model_class as default if type_info is not provided
        type_info = type_info or self.model_class

        str_id = str(id_value)
        doc = self._storage.get(str_id)

        if not doc:
            return False

        # Check tenant isolation
        if not self._check_tenant_isolation(doc):
            return False

        if doc.get('type') != type_info.__name__:
            return False

        if self._soft_delete:
            doc['deleted_at'] = datetime.utcnow()
        else:
            del self._storage[str_id]
        return True

    async def bulk_store(
        self,
        items: Sequence[M],
        type_info: type[M] | None = None,
        ignore_duplicates: bool = False
    ) -> list[str]:
        """Store multiple documents with tenant isolation"""
        # Use stored model_class as default if type_info is not provided
        type_info = type_info or self.model_class

        ids = []
        for item in items:
            try:
                id_ = await self.store(item, type_info)
                ids.append(id_)
            except DuplicateKeyException:
                if not ignore_duplicates:
                    raise
        return ids

    async def bulk_update(
        self,
        updates: list[tuple[dict[str, Any], dict[str, Any]]],
        type_info: type[M] | None = None,
        ordered: bool = True
    ) -> int:
        """Update multiple documents with tenant isolation"""
        # Use stored model_class as default if type_info is not provided
        type_info = type_info or self.model_class

        success_count = 0
        for query, update_data in updates:
            # Get ID from query using configured id_field
            id_value = query.get(self.id_field)
            if not id_value:
                if ordered:
                    break
                continue

            try:
                if await self.update(self.id_field, id_value, update_data, type_info):
                    success_count += 1
                elif ordered:
                    break
            except Exception:
                if ordered:
                    break
        return success_count



class MemoryStoreConfig(StoreConfig):
    """Memory-specific configuration"""
    id_field: str  # Required field to specify which field is the ID
    tenant_id: str  # Required tenant ID for data isolation
    case_sensitive: bool = True  # Whether string comparisons should be case-sensitive
    ttl_hours: int | None = None  # Optional TTL in hours
    max_size: int | None = None   # Optional max cache size
    initial_data: dict[str, dict[str, Any]] | None = None  # Optional initial data to populate the store

class MemoryStoreFactory(StoreFactory):
    """Factory for creating memory store instances"""


    async def create_store(
        self,
        model_class: type[M],
        config: StoreConfig,
    ) -> MemoryStore[M]:
        """Create and return a configured memory store instance"""
        if not isinstance(config, MemoryStoreConfig):
            raise ValueError("Memory store requires MemoryStoreConfig")

        # Create store with configuration and model class
        store = MemoryStore(
            id_field=config.id_field,
            model_class=model_class,
            tenant_id=config.tenant_id,
            use_field_aliases=config.use_field_aliases,
            soft_delete=config.soft_delete,
            case_sensitive=config.case_sensitive,
            ttl_hours=config.ttl_hours,
            max_size=config.max_size
        )

        return store
