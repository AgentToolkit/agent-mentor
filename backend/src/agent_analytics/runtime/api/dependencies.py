# api/dependencies.py
from typing import Any

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.runtime.api import app_state
from agent_analytics.runtime.executor.analytics_execution_engine import AnalyticsRuntimeEngine
from agent_analytics.runtime.executor.executor_results_data_manager import (
    ExecutionResultsDataManager,
)
from agent_analytics.runtime.registry.analytics_registry import AnalyticsRegistry


async def get_registry_by_tenant(tenant_id: str | None) -> AnalyticsRegistry:
    """Get registry for specific tenant by direct parameter."""
    components = app_state.get_tenant_components(tenant_id)
    if not components or not components.registry:
        raise RuntimeError(f"Registry not initialized for tenant: {tenant_id or 'default'}")
    return components.registry

async def get_executor_by_tenant(tenant_id: str | None) -> AnalyticsRuntimeEngine:
    """Get executor for specific tenant by direct parameter."""
    components = app_state.get_tenant_components(tenant_id)
    if not components or not components.executor:
        raise RuntimeError(f"Analytics executor not initialized for tenant: {tenant_id or 'default'}")
    return components.executor

async def get_data_manager_by_tenant(tenant_id: str | None) -> DataManager:
    """Get data manager for specific tenant by direct parameter."""
    components = app_state.get_tenant_components(tenant_id)
    if not components or not components.data_manager:
        raise RuntimeError(f"Data manager not initialized for tenant: {tenant_id or 'default'}")
    return components.data_manager

async def get_execution_results_manager_by_tenant(tenant_id: str | None) -> ExecutionResultsDataManager:
    """Get execution results manager for specific tenant by direct parameter."""
    components = app_state.get_tenant_components(tenant_id)
    if not components or not components.execution_results_manager:
        raise RuntimeError(f"Execution results manager not initialized for tenant: {tenant_id or 'default'}")
    return components.execution_results_manager

async def get_default_db_client() -> Any:
    """Get execution results manager for specific tenant by direct parameter."""
    components = app_state.get_tenant_components()
    if not components or not components.db_client:
        raise RuntimeError("DB client not initialized for default tenant")
    return components.db_client
