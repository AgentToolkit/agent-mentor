import importlib
import time
from datetime import datetime
from inspect import isabstract
from typing import Annotated, Any, TypedDict

from langgraph.graph import START, StateGraph
from pydantic import BaseModel

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.runtime.executor.executor_results_data_manager import (
    ExecutionResultsDataManager,
)
from agent_analytics.runtime.registry.analytics_metadata import AnalyticsMetadata
from agent_analytics.runtime.registry.analytics_registry import AnalyticsRegistry


def merge_results(left: dict[str, ExecutionResult], right: dict[str, ExecutionResult]) -> dict[str, ExecutionResult]:
    """
    Reducer function to merge concurrent updates to the results dictionary.
    This allows multiple analytics to complete in parallel and update results simultaneously.
    """
    return {**left, **right}


class AnalyticsGraphState(TypedDict):
    analytics_id: str
    input_data: dict[str, Any]
    results: Annotated[dict[str, ExecutionResult], merge_results]

class AnalyticsRuntimeEngine:
    def __init__(self, analytics_registry: AnalyticsRegistry,
                  execution_results_manager: ExecutionResultsDataManager,
                  data_manager: DataManager):
        self.registry = analytics_registry
        self.execution_results_data_manager = execution_results_manager
        self.data_manager = data_manager

    def _find_concrete_analytics_class(self,module) -> type[BaseAnalyticsPlugin]:
        # Get all module attributes that are classes
        classes = [obj for obj in module.__dict__.values()
                if isinstance(obj, type)]

        # Find concrete implementations (not the base class itself)
        concrete_classes = [cls for cls in classes
                        if issubclass(cls, BaseAnalyticsPlugin)
                        and cls != BaseAnalyticsPlugin
                        and not isabstract(cls)]

        if not concrete_classes:
            raise ValueError("No concrete implementation of BaseAnalyticsPlugin found in module")

        if len(concrete_classes) > 1:
            raise ValueError("Multiple implementations of BaseAnalyticsPlugin found in module")

        return concrete_classes[0]

    def _check_dependencies(self, state: AnalyticsGraphState, dependencies: list[str]) -> ExecutionError | None:
        """Check if any dependencies have failed"""
        failed_deps = []
        for dep_id in dependencies:
            if dep_id in state["results"]:
                result = state["results"][dep_id]
                if result.status == ExecutionStatus.FAILURE:
                    failed_deps.append(dep_id)

        if failed_deps:
            return ExecutionError(
                error_type="DependencyFailure",
                message=f"Dependencies failed: {', '.join(failed_deps)}",
                details={"failed_dependencies": failed_deps}
            )
        return None

    def _create_failure_result(
        self,
        analytics_id: str,
        error: ExecutionError,
        metadata: AnalyticsMetadata | None,
        start_time: float,
        input_data: dict[str, Any],
        output_result: dict[str, Any] = None
    ) -> ExecutionResult:
        """Helper method to create failure execution results"""
        result = ExecutionResult(
            analytics_id=analytics_id,
            status=ExecutionStatus.FAILURE,
            error=error,
            config_used=metadata.template.config if metadata else None,
            input_data_used=input_data,
            output_result=output_result or {},
            end_time=datetime.utcnow()
        )
        execution_time = time.time() - start_time
        result.complete_execution(execution_time)
        return result

    async def _find_cached_result(
        self,
        analytics_id: str,
        input_data: dict[str, Any]
    ) -> ExecutionResult | None:
        """
        Find a cached successful execution result with matching input data.
        
        Args:
            analytics_id: ID of the analytics to check
            input_data: Input data dictionary to match
            
        Returns:
            Most recent successful ExecutionResult with matching input, or None
        """
        try:
            # Use the general input-based lookup
            cached_result = await self.execution_results_data_manager.find_result_by_input(
                analytics_id=analytics_id,
                input_data=input_data
            )

            return cached_result

        except Exception as e:
            print(f"Warning: Error checking cache for {analytics_id}: {str(e)}")
            return None

    def create_analytics_function(self, analytics_id: str, data_manager: DataManager, all_predecessors: set[str]):
        """
        Create an analytics function that checks all predecessors (both dependencies and triggers).
        
        Args:
            analytics_id: ID of the analytics
            data_manager: Data manager instance
            all_predecessors: Set of all analytics that must execute before this one
                            (includes both dependsOn and analytics that trigger this one)
        """
        async def analytics_function(state: AnalyticsGraphState) -> dict[str, Any]:
            start_time = time.time()
            input_data = {}
            try:
                # Get analytics metadata
                metadata = await self.registry.get_analytics(analytics_id)
                if not metadata:
                    raise ValueError(f"Analytics {analytics_id} not found")

                # Check if ANY predecessors failed (dependencies OR triggers)
                # This ensures that if A triggers B and A fails, B will also fail
                dep_error = self._check_dependencies(state, list(all_predecessors))
                if dep_error:
                    result = self._create_failure_result(
                        analytics_id, dep_error, metadata, start_time, state.get("input_data", {})
                    )
                    await self.execution_results_data_manager.store_result(result)
                    # Return only this result - reducer will merge with state
                    return {"results": {analytics_id: result}}

                # Prepare input data
                input_data = state["input_data"].copy()

                # Add results from ALL predecessors if they exist (dependencies OR triggers)
                # This ensures that if A triggers B and A succeeds, A's output becomes B's input
                for pred_id in all_predecessors:
                    if pred_id in state["results"]:
                        pred_result = state["results"][pred_id]
                        input_data.update(pred_result.output_result)

                # TODO : enable if needed **CACHING CHECK**: Look for cached result with matching input data
                # Right now disabled because: on forward triggereing there would be no cached results, so we just waste time checking
                # Most of the time it is just performance loss
                # cached_result = await self._find_cached_result(analytics_id, input_data)
                # if cached_result:
                #     print(f"Using cached result for analytics {analytics_id}")
                #     # Return only this result - reducer will merge with state
                #     return {"results": {analytics_id: cached_result}}

                # No cache hit - execute normally
                # Load analytics class
                module = importlib.import_module(metadata.template.runtime.config["module_path"])
                analytics_class = self._find_concrete_analytics_class(module)

                # Execute analytics
                analytics_instance = analytics_class()
                result = await analytics_instance.execute(
                    analytics_id=analytics_id,
                    data_manager=data_manager,
                    input_data=input_data,
                    config=metadata.template.config
                )

                # Record execution time
                execution_time = time.time() - start_time
                result.complete_execution(execution_time)

                # Store the execution result
                await self.execution_results_data_manager.store_result(result)

                # Return only this result - reducer will merge with state
                return {"results": {analytics_id: result}}

            except Exception as e:
                error = ExecutionError.from_exception(e)
                result = ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=error,
                    config_used=metadata.template.config if metadata else None,
                    input_data_used=input_data,
                    end_time=datetime.utcnow()
                )
                # Store failed result
                execution_time = time.time() - start_time
                result.complete_execution(execution_time)
                await self.execution_results_data_manager.store_result(result)

                # Return only this result - reducer will merge with state
                return {"results": {analytics_id: result}}

        # Set the name of the function dynamically
        analytics_function.__name__ = f"execute_{analytics_id}"
        return analytics_function

    def _topological_sort(
        self,
        analytics_ids: set[str],
        metadata_map: dict[str, AnalyticsMetadata]
    ) -> list[str]:
        """
        Perform topological sort to determine execution order.
        Uses Kahn's algorithm for topological sorting.
        """
        # Build adjacency list and in-degree count
        graph: dict[str, set[str]] = {aid: set() for aid in analytics_ids}
        in_degree: dict[str, int] = dict.fromkeys(analytics_ids, 0)

        for aid in analytics_ids:
            metadata = metadata_map[aid]

            # Add edges from dependencies to current (backward dependencies)
            # dependency -> current
            for dep_id in metadata.template.controller.dependsOn:
                if dep_id in analytics_ids:
                    graph[dep_id].add(aid)
                    in_degree[aid] += 1

            # Add edges from current to triggered (forward triggers)
            # current -> triggered
            for trigger_id in metadata.template.controller.triggers:
                if trigger_id in analytics_ids:
                    graph[aid].add(trigger_id)
                    in_degree[trigger_id] += 1

        # Kahn's algorithm for topological sort
        queue = [aid for aid in analytics_ids if in_degree[aid] == 0]
        result = []

        while queue:
            # Process node with no incoming edges
            current = queue.pop(0)
            result.append(current)

            # Remove edges from current to its neighbors
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check if all nodes were processed (no cycles)
        if len(result) != len(analytics_ids):
            raise ValueError("Cycle detected in dependency graph during topological sort")

        return result

    async def create_execution_graph(self, analytics_id: str, data_manager: DataManager):
        """
        Build complete execution graph including both backward (dependsOn) 
        and forward (triggers) dependencies.
        """
        visited: set[str] = set()
        analytics_to_execute: set[str] = set()
        analytics_metadata: dict[str, AnalyticsMetadata] = {}

        async def traverse_full_graph(current_id: str, path: list[str]):
            """
            Traverse both backward (dependsOn) and forward (triggers) dependencies.
            Builds the complete set of analytics that need to be executed.
            """
            # Check for circular dependencies
            if current_id in path:
                cycle = ' -> '.join(path + [current_id])
                raise ValueError(f"Circular dependency detected: {cycle}")

            # Skip if already visited
            if current_id in visited:
                return

            visited.add(current_id)
            analytics_to_execute.add(current_id)

            # Get metadata
            metadata = await self.registry.get_analytics(current_id)
            if not metadata:
                raise ValueError(f"Analytics {current_id} not found")

            analytics_metadata[current_id] = metadata

            # Traverse backward dependencies (these must execute BEFORE current)
            for dep_id in metadata.template.controller.dependsOn:
                await traverse_full_graph(dep_id, path + [current_id])

            # Traverse forward dependencies (these must execute AFTER current)
            for trigger_id in metadata.template.controller.triggers:
                await traverse_full_graph(trigger_id, path + [current_id])

        # Build the complete graph starting from requested analytics
        await traverse_full_graph(analytics_id, [])

        # Build the COMPLETE dependency graph including both dependsOn and triggers
        # This maps each analytics to its immediate predecessors (what must execute before it)
        predecessors: dict[str, set[str]] = {aid: set() for aid in analytics_to_execute}

        for aid in analytics_to_execute:
            metadata = analytics_metadata[aid]

            # Add edges from dependencies to current (backward dependencies)
            # dep_id must execute BEFORE aid
            for dep_id in metadata.template.controller.dependsOn:
                if dep_id in analytics_to_execute:
                    predecessors[aid].add(dep_id)

            # Add edges from current to triggered (forward triggers)
            # aid must execute BEFORE trigger_id
            for trigger_id in metadata.template.controller.triggers:
                if trigger_id in analytics_to_execute:
                    predecessors[trigger_id].add(aid)

        # Determine execution order via topological sort
        analytics_order = self._topological_sort(analytics_to_execute, analytics_metadata)

        # Build LangGraph workflow
        workflow = StateGraph(AnalyticsGraphState)

        # Add nodes for each analytics in the execution graph
        for current_id in analytics_order:
            # Pass all predecessors to the function so it can check failures and use outputs
            node_function = self.create_analytics_function(current_id, data_manager, predecessors[current_id])
            workflow.add_node(node_function.__name__, node_function)

        # Add edges based on the COMPLETE dependency graph (not just dependsOn)
        for current_id in analytics_order:
            node_name = f"execute_{current_id}"

            # Get all predecessors from the complete graph
            preds = predecessors[current_id]

            if preds:
                # Has predecessors - connect from all of them
                workflow.add_edge(
                    [f"execute_{pred_id}" for pred_id in preds],
                    node_name
                )
            else:
                # No predecessors - connect to START
                workflow.add_edge(START, node_name)

        return workflow.compile()

    async def execute_analytics(self, analytics_id: str, input_model: BaseModel) -> ExecutionResult:
        """Execute analytics with validated input model"""
        graph = await self.create_execution_graph(analytics_id, self.data_manager)
        output = await graph.ainvoke(
            input={
                "analytics_id": analytics_id,
                "input_data": input_model.model_dump(),
                "results": {}
            }
        )

        return output["results"][analytics_id]
