
from datetime import datetime
from typing import Any

from agent_analytics.core.plugin.base_plugin import ExecutionResult, ExecutionStatus
from agent_analytics.runtime.storage.store_config import StoreConfig
from agent_analytics.runtime.storage.store_interface import (
    BaseStore,
    QueryFilter,
    QueryOperator,
    StoreFactory,
)


class ExecutionResultsDataManager:
    def __init__(self, store: BaseStore[ExecutionResult]):
        self._store = store

    @classmethod
    async def create(
        cls,
        store_factory: StoreFactory,
        config: StoreConfig
    ) -> 'ExecutionResultsDataManager':
        """
        Create a new ExecutionResultsDataManager instance.
        
        Args:
            store_factory: Factory for creating the underlying store
            config: Store-specific configuration
        """
        store = await store_factory.create_store(
            model_class=ExecutionResult,
            config=config
        )
        return cls(store)

    async def store_result(self, result: ExecutionResult) -> str:
        """Store an execution result"""
        return await self._store.store(result, type_info=ExecutionResult)

    async def get_result_by_id(self, result_id: str) -> ExecutionResult | None:
        """Get a result by ID"""
        return await self._store.retrieve(
            id_field="result_id",
            id_value=result_id,
            type_info=ExecutionResult
        )

    async def get_results_by_analytics_id(
        self,
        analytics_id: str,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> list[ExecutionResult]:
        """Get results for an analytics ID within a time range"""
        query = {
            "analytics_id": QueryFilter(operator=QueryOperator.EQUAL, value=analytics_id)
        }
        if start:
            query["start_time"] = QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=start)
        if end:
            if "start_time" in query:
                query["end_time"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=end)
            else:
                query["start_time"] = QueryFilter(operator=QueryOperator.LESS_EQUAL, value=end)
        return await self._store.search(query=query, type_info=ExecutionResult)

    async def get_results_by_status(
        self,
        status: ExecutionStatus,
        analytics_id: str | None = None
    ) -> list[ExecutionResult]:
        """Get results by status"""
        query = {
            "status": QueryFilter(operator=QueryOperator.EQUAL, value=status.value)
        }
        if analytics_id:
            query["analytics_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=analytics_id)
        return await self._store.search(query=query, type_info=ExecutionResult)


    async def get_results_in_timeframe(
        self,
        start: datetime,
        end: datetime,
        analytics_id: str | None = None
    ) -> list[ExecutionResult]:
        """Get results within a time range"""
        query = {
            "start_time": QueryFilter(operator=QueryOperator.GREATER_EQUAL, value=start),
            "end_time": QueryFilter(operator=QueryOperator.LESS_EQUAL, value=end)
        }
        if analytics_id:
            query["analytics_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=analytics_id)
        return await self._store.search(query=query, type_info=ExecutionResult)

    async def get_results_by_trace_or_group_id(
        self,
        analytics_id: str,
        trace_or_group_ids: list[str]
    ) -> dict[str, list[ExecutionResult]]:
        """
        Get results for an analytics ID with a specific trace_id.
        The trace_id is expected to be in the input_data_used dictionary.
        
        Args:
            analytics_id: ID of the analytics
            trace_id: Trace ID to search for in input_data_used
            
        Returns:
            List of execution results matching both criteria
        """
        # Create a query for analytics_id (direct field)
        query = {
            "analytics_id": QueryFilter(operator=QueryOperator.EQUAL, value=analytics_id)
        }

        # Fetch all results for the analytics_id
        results = await self._store.search(query=query, type_info=ExecutionResult)

        # Filter results that have the matching trace_id in input_data_used
        filtered_results = {}
        for result in results:
            input_data = result.input_data_used
            if input_data and isinstance(input_data, dict):
                if input_data.get("trace_id") in trace_or_group_ids:
                    if input_data.get("trace_id") != None and input_data.get("trace_id") not in filtered_results:
                        filtered_results[input_data.get("trace_id")] = []
                    filtered_results[input_data.get("trace_id")].append(result)
                elif input_data.get("trace_group_id") != None and input_data.get("trace_group_id") in trace_or_group_ids:
                    if input_data.get("trace_group_id") not in filtered_results:
                        filtered_results[input_data.get("trace_group_id")] = []
                    filtered_results[input_data.get("trace_group_id")].append(result)

        return filtered_results

    async def find_result_by_input(
        self,
        analytics_id: str,
        input_data: dict[str, Any],
        limit: int = 100
    ) -> ExecutionResult | None:
        """
        Find the most recent successful execution result for an analytics 
        with matching input data.
        
        Args:
            analytics_id: ID of the analytics
            input_data: Input data dictionary to match against
            limit: Maximum number of recent results to check (default 100)
            
        Returns:
            Most recent successful ExecutionResult with matching input, or None
        """
        # Query for successful results for this analytics
        query = {
            "analytics_id": QueryFilter(operator=QueryOperator.EQUAL, value=analytics_id),
            "status": QueryFilter(operator=QueryOperator.EQUAL, value=ExecutionStatus.SUCCESS.value)
        }

        # Fetch recent successful results
        results = await self._store.search(query=query, type_info=ExecutionResult)

        if not results:
            return None

        # Sort by end_time (most recent first) and limit
        results.sort(key=lambda x: x.end_time if x.end_time else datetime.min, reverse=True)
        results = results[:limit]

        # Find the first result with matching input data
        for result in results:
            if result.input_data_used == input_data:
                return result

        return None

    async def update_result(
            self,
            result_id: str,
            result: ExecutionResult
        ) -> bool:
            """Update a result"""
            return await self._store.update(
                id_field="result_id",
                id_value=result_id,
                data=result.model_dump(),
                type_info=ExecutionResult
            )

    async def delete_result(self, result_id: str) -> bool:
        """Delete a result"""
        return await self._store.delete(
            id_field="result_id",
            id_value=result_id,
            type_info=ExecutionResult
        )

    async def get_failed_results(
        self,
        analytics_id: str | None = None
    ) -> list[ExecutionResult]:
        """Get failed results"""
        query = {
            "status": QueryFilter(operator=QueryOperator.EQUAL, value=ExecutionStatus.FAILURE.value)
        }
        if analytics_id:
            query["analytics_id"] = QueryFilter(operator=QueryOperator.EQUAL, value=analytics_id)
        return await self._store.search(query=query, type_info=ExecutionResult)


