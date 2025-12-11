from typing import Any

from agent_analytics.runtime.registry.analytics_metadata import AnalyticsMetadata
from agent_analytics.runtime.storage.store_config import StoreConfig
from agent_analytics.runtime.storage.store_interface import (
    BaseStore,
    QueryFilter,
    QueryOperator,
    StoreFactory,
)


class RegistryDataManager:
    def __init__(self, store: BaseStore[AnalyticsMetadata]):
        self._store = store

    @classmethod
    async def create(
        cls,
        store_factory: StoreFactory,
        config: StoreConfig
    ) -> 'RegistryDataManager':
        """
        Create a new RegistryDataManager instance.
        
        Args:
            store_factory: Factory for creating the underlying store
            config: Store-specific configuration
        """
        store = await store_factory.create_store(
            model_class=AnalyticsMetadata,
            config=config
        )
        return cls(store)

    async def register_analytic(self, metadata: AnalyticsMetadata) -> str:
        """Register a new analytic"""
        return await self._store.store(metadata, type_info=AnalyticsMetadata)

    async def find_analytic(self, analytics_id: str) -> AnalyticsMetadata | None:
        """Find an analytic by ID"""
        return await self._store.retrieve(
            id_field="id",
            id_value=analytics_id,
            type_info=AnalyticsMetadata
        )

    async def list_analytics(
        self,
        filter_params: dict[str, Any] | None = None
    ) -> list[AnalyticsMetadata]:
        """List analytics matching the filter"""
        if not filter_params:
            filter_params = {}

        query = {
            field: QueryFilter(operator=QueryOperator.EQUAL, value=value)
            for field, value in filter_params.items()
        }

        return await self._store.search(
            query=query,
            type_info=AnalyticsMetadata
        )


    async def update_analytic(
        self,
        analytics_id: str,
        metadata: AnalyticsMetadata
    ) -> bool:
        """Update an analytic's metadata"""
        return await self._store.update(
            id_field="id",
            id_value=analytics_id,
            data=metadata.model_dump(),
            type_info=AnalyticsMetadata
        )

    async def delete_analytic(self, analytics_id: str) -> bool:
        """Delete an analytic"""
        return await self._store.delete(
            id_field="id",
            id_value=analytics_id,
            type_info=AnalyticsMetadata
        )
