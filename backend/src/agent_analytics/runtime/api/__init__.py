import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.runtime.api.config import Settings
from agent_analytics.runtime.executor.analytics_execution_engine import AnalyticsRuntimeEngine
from agent_analytics.runtime.executor.executor_results_data_manager import (
    ExecutionResultsDataManager,
)
from agent_analytics.runtime.registry.analytics_registry import AnalyticsRegistry

logger = logging.getLogger(__name__)

@dataclass
class TenantComponents:
    """Container for all tenant-specific components."""
    tenant_id: str
    db_client: Any
    registry: AnalyticsRegistry
    executor: AnalyticsRuntimeEngine
    execution_results_manager: ExecutionResultsDataManager
    data_manager: DataManager
    initialized: bool = False

class AppState:
    """Global application state with tenant support."""

    def __init__(self):
        self.app: FastAPI | None = None
        self.config: dict[str, Any] = {}
        self._tenant_components: dict[str, TenantComponents] = {}
        self._initialization_locks: dict[str, asyncio.Lock] = {}
        self._default_tenant_id = Settings().DEFAULT_TENANT_ID

    def get_tenant_components(self, tenant_id: str | None = None) -> TenantComponents | None:
        """Get components for a specific tenant."""
        if tenant_id is None:
            tenant_id = self._default_tenant_id
        return self._tenant_components.get(tenant_id)

    def set_tenant_components(self, tenant_id: str | None, components: TenantComponents):
        """Store components for a specific tenant."""
        if tenant_id is None:
            tenant_id = self._default_tenant_id
        self._tenant_components[tenant_id] = components

    def get_initialization_lock(self, tenant_id: str | None = None) -> asyncio.Lock:
        """Get or create initialization lock for a tenant."""
        if tenant_id is None:
            tenant_id = self._default_tenant_id

        if tenant_id not in self._initialization_locks:
            self._initialization_locks[tenant_id] = asyncio.Lock()

        return self._initialization_locks[tenant_id]

    def is_tenant_initialized(self, tenant_id: str | None = None) -> bool:
        """Check if tenant components are initialized."""
        components = self.get_tenant_components(tenant_id)
        return components is not None and components.initialized

    async def cleanup_tenant(self, tenant_id: str | None = None):
        """Cleanup resources for a specific tenant."""
        if tenant_id is None:
            tenant_id = self._default_tenant_id

        components = self._tenant_components.get(tenant_id)
        if components and components.db_client:
            try:
                if hasattr(components.db_client, 'close'):
                    await components.db_client.close()
                elif hasattr(components.db_client, 'close'):
                    components.db_client.close()
            except Exception as e:
                logger.error(f"Error closing DB client for tenant {tenant_id}: {e}")

        # Remove from cache
        self._tenant_components.pop(tenant_id, None)
        self._initialization_locks.pop(tenant_id, None)

    async def cleanup_all_tenants(self):
        """Cleanup resources for all tenants."""
        tenant_ids = list(self._tenant_components.keys())
        for tenant_id in tenant_ids:
            await self.cleanup_tenant(tenant_id)

    def get_all_tenant_ids(self) -> list[str]:
        """Get list of all initialized tenant IDs."""
        return list(self._tenant_components.keys())

    @property
    def default_tenant_id(self) -> str:
        """Get the default tenant ID."""
        return self._default_tenant_id

# Global app state instance
app_state = AppState()
