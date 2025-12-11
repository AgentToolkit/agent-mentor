import asyncio
import json
import threading
from typing import Any

from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data_composite.action import BaseAction
from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.extensions.spans_processing.common.utils import *
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.object_extraction.action_processor import (
    ActionVisitor,
)
from agent_analytics.extensions.spans_processing.span_traversal_orchestrator import (
    SpanProcessingOrchestrator,
)
from agent_analytics.extensions.spans_processing.task_span_processing.langchain_task_processor import (
    LangChainTaskGraphVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.langgraph_task_processor import (
    LangGraphTaskGraphVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.crewai_task_processor import (
    CrewAITaskGraphVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.vector_db_processor import (
    VectorDBVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.llm_task_processor import (
    LLMTaskProcessor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.langfuse_task_processor import (
    LangfuseVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.manual_task_processor import (
    ManualTaskVisitor,
)

def normalize_input(input_data: Any) -> dict:
    """Normalize input data to a canonical dictionary format with consistent typing.

    Args:
        input_data: The input data which could be a string (JSON), array, or object

    Returns:
        dict: Normalized dictionary representation with consistent string types

    Raises:
        ValueError: If input cannot be normalized or is in unexpected format
    """

    def stringify_value(v: Any) -> str:
        """Convert any primitive value to string."""
        if v is None:
            return ""
        if isinstance(v, (bool, int, float)):
            return str(v)
        if isinstance(v, str):
            return v
        raise ValueError(f"Unexpected value type: {type(v)}, value: {v}")

    # Handle string (assumed to be JSON)
    if isinstance(input_data, str):
        try:
            parsed = json.loads(input_data)
            return normalize_input(parsed)
        except json.JSONDecodeError:
            return {'output': stringify_value(input_data)}

    # Handle dictionary
    if isinstance(input_data, dict):
        return {
            k: normalize_input(v) if isinstance(v, (dict, list))
            else stringify_value(v)
            for k, v in input_data.items()
        }

    # Handle arrays
    if isinstance(input_data, list):
        if not input_data:
            return {}
        return {
            str(i): normalize_input(item) if isinstance(item, (dict, list))
            else stringify_value(item)
            for i, item in enumerate(input_data)
        }

    # might be numeric?
    return {'result': stringify_value(input_data)}


class TaskAnalyticsInput(BaseModel):
    trace_id: str | None = Field(description="Id of the trace to run this analytic on", default=None)
    trace_ids: list[str] | None = Field(description="List of trace ids to run this analytic on", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group to run this analytic on", default=None)
    spans: list[dict[str, Any]] | None = Field(description="List of spans to run this analytic on", default=None)


class TaskAnalyticsOutput(BaseModel):
    trace_id: str | None = Field(description="Id of the trace this analytic was run on", default=None)
    trace_ids: list[str] | None = Field(description="List of trace ids this analytic was run on", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group this analytic was run on", default=None)
    task_list: list[dict[str, Any]] = Field(..., description="List of analyzed tasks")
    actions_list: list[Any] = Field(..., description="List of analyzed action objects")


class TaskAnalytics(BaseAnalyticsPlugin):
    DEFAULT_MAX_CONCURRENT_TRACES = 20

    @classmethod
    def get_input_model(cls) -> type[TaskAnalyticsInput]:
        return TaskAnalyticsInput

    @classmethod
    def get_output_model(cls) -> type[TaskAnalyticsOutput]:
        return TaskAnalyticsOutput

    # def get_task_flow_obj(self, span_list: List) -> Optional[HierarchicalTaskGraph]:
    #     return TaskDiscoveryRouter().get_task_flow_obj(span_list)

    async def _execute(self, analytics_id: str, data_manager: DataManager, input_data: TaskAnalyticsInput, config: dict[str, Any]) -> ExecutionResult:
        input_trace_id = input_data.trace_id
        input_trace_ids = input_data.trace_ids
        trace_group_id = input_data.trace_group_id
        spans = input_data.spans

        # Get max_concurrent from config or use default
        max_concurrent = self.DEFAULT_MAX_CONCURRENT_TRACES
        shared_action_context = {
            'code_id_to_action': {},  # Maps code_id -> BaseAction object
            'action_lock': threading.Lock()  # Thread-safe access to shared dict
        }

        if config:
            max_concurrent = config.get('max_concurrent_traces', self.DEFAULT_MAX_CONCURRENT_TRACES)

        if not input_trace_id and not input_trace_ids and not spans and not trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No relevant input provided for the analytics (neither of trace_id, trace_ids, group_trace_id or span list is given)"
                )
            )
        all_tasks_list = []
        all_actions_list = []
        # Case 1: Process a trace group
        if trace_group_id or input_trace_ids:
            if trace_group_id:
            # Fetch the TraceGroup object
                trace_group = await TraceGroupComposite.get_by_id(data_manager=data_manager,id=trace_group_id)
                if not trace_group:
                    return ExecutionResult(
                        analytics_id=analytics_id,
                        status=ExecutionStatus.FAILURE,
                        error=ExecutionError(
                            error_type="DataError",
                            message=f"No trace group found with id {trace_group_id}"
                        )
                    )

                trace_ids = trace_group.traces_ids

            if input_trace_ids:
                trace_ids = input_trace_ids

            # Create semaphore to limit concurrent processing
            semaphore = asyncio.Semaphore(max_concurrent)
            #Process each trace in parallel with concurrency control
            async def process_single_trace(trace_id: str) -> tuple[list[HierarchicalTask],list[BaseAction]]:
                """Process a single trace and return its tasks"""
                async with semaphore:  # Acquire semaphore before processing
                    try:
                        spans = await BaseSpanComposite.get_spans_for_trace(data_manager=data_manager, trace_id=trace_id)
                        if not spans:
                            return [],[]   # Return empty list for traces with no spans

                        # Process this trace's spans
                        tasks_list, action_list = await self._process_spans(spans, shared_action_context)
                        return tasks_list, action_list
                    except Exception as e:
                        # Log the error but don't fail the entire operation
                        print(f"Warning: Failed to process trace_id {trace_id}: {str(e)}")
                        return [],[]

            # Process all traces in parallel with concurrency limit
            print(f"Processing {len(trace_ids)} traces in parallel (max {max_concurrent} concurrent)...")
            all_results = await asyncio.gather(*[process_single_trace(trace_id) for trace_id in trace_ids])
            trace_results, action_results = zip(*all_results, strict=False) if all_results else ([], [])

            # Flatten all task lists and count successful traces
            successful_traces = 0
            for trace_tasks in trace_results:
                if trace_tasks:  # Only count non-empty results as successful
                    successful_traces += 1
                all_tasks_list.extend(trace_tasks)

            # Flatten all task lists and count successful traces
            successful_actions = 0
            for action in action_results:
                if action:  # Only count non-empty results as successful
                    successful_actions += 1
                all_actions_list.extend(action)

            print(f"Parallel processing completed. Processed {successful_traces}/{len(trace_ids)} traces successfully. Total tasks: {len(all_tasks_list)}. Total actions: {len(all_actions_list)}")


        # Case 2: Process a single trace or provided spans
        else:
            # Fetch all spans for this trace if not provided
            if not spans:
                spans_list = await BaseSpanComposite.get_spans_for_trace(data_manager=data_manager,trace_id=input_trace_id)
            else:
                input_trace_id = spans[0].context.trace_id
                #convert the given spans Dicts to objects
                spans_list = [BaseSpanComposite.from_dict(data_manager, span_dict) for span_dict in spans]

            if not spans_list:
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="DataError",
                        message=f"No spans found for trace {input_trace_id}"
                    )
                )

            # Process this trace's spans
            all_tasks_list, all_actions_list = await self._process_spans(spans_list)


        # Bulk store all tasks after successful processing of all traces
        task_list_dicts = []
        action_list_dict=[]
        if all_tasks_list:
            all_tasks=await HierarchicalTask.bulk_store(data_manager=data_manager,
                                              tasks=all_tasks_list)
            task_list_dicts= [task.model_dump() for task in all_tasks]

        if all_actions_list:
            all_actions = await BaseAction.bulk_store(data_manager=data_manager, base_actions=all_actions_list)
            action_list_dict = [action.model_dump() for action in all_actions]

        output = TaskAnalyticsOutput(
            trace_id=input_trace_id if not trace_group_id and not input_trace_ids else None,
            trace_ids=input_trace_ids if input_trace_ids else None,
            trace_group_id=trace_group_id if trace_group_id else None,
            task_list=task_list_dicts,
            actions_list = action_list_dict
        )

        return ExecutionResult(
            analytics_id=analytics_id,
            status=ExecutionStatus.SUCCESS,
            output=output
        )



    async def _process_spans(self, spans: list[BaseSpanComposite],shared_action_context: dict | None = None) -> tuple[list[HierarchicalTask], list[BaseAction]]:
        """Helper method to process spans and generate tasks without storing them"""
        orchestrator = SpanProcessingOrchestrator()

        # Register LLM processor first 
        orchestrator.register_processor(ManualTaskVisitor())
        orchestrator.register_processor(LLMTaskProcessor())
        # Register framework processors 
        orchestrator.register_processor(LangChainTaskGraphVisitor())
        orchestrator.register_processor(LangGraphTaskGraphVisitor())
        orchestrator.register_processor(CrewAITaskGraphVisitor())
        orchestrator.register_processor(VectorDBVisitor())
        orchestrator.register_processor(LangfuseVisitor())
        action_visitor = ActionVisitor(shared_action_context)
        orchestrator.register_processor(action_visitor)


        # Process spans
        context = orchestrator.process_spans(spans)
        tasks_list = list(context.get(TASKS, {}).values())
        actions_list = context.get(ACTIONS, [])

        for task in tasks_list:
            task.input = normalize_input(task.input)
            task.output = normalize_input(task.output)

        return tasks_list, actions_list
