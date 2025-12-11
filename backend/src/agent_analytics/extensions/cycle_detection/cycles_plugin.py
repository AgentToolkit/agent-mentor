import traceback
from typing import Any

from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.issue import BaseIssue
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.extensions.cycle_detection.detect_by_structure import CycleDetector


class CyclesDetectorInput(BaseModel):
    trace_id: str | None = Field(default=None, description="Single trace ID to analyze")
    trace_group_id: str | None = Field(description="Id of the trace group to run this analytic on", default=None)
    # task_list: Optional[List[Dict[str, Any]]] = Field(default=None, description="List of analyzed tasks")


class CyclesDetectorOutput(BaseModel):
    trace_id: str | None = Field(default=None, description="Single trace ID when processing single trace")
    trace_group_id: str | None = Field(description="Id of the trace group this analytic was run on", default=None)
    issues: list[dict[str, Any]] = Field(..., description="List of extracted issues")
    new_issues_id: list[str] | None = None


class CyclesDetectorPlugin(BaseAnalyticsPlugin):

    @classmethod
    def get_input_model(cls) -> type[CyclesDetectorInput]:
        return CyclesDetectorInput

    @classmethod
    def get_output_model(cls) -> type[CyclesDetectorOutput]:
        return CyclesDetectorOutput

    async def _execute(
            self,
            analytics_id: str,
            data_manager: DataManager,
            input_data: CyclesDetectorInput,
            config: dict[str, Any]
    ) -> ExecutionResult:
        # Validate input
        trace_id = input_data.trace_id
        trace_group_id = input_data.trace_group_id
        # task_list = input_data.task_list

        if not trace_id and not trace_group_id:# and not task_list:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No relevant input provided for the analytics (neither trace_id, group_trace_id, nor task list is given)"
                )
            )

        try:
            all_issues = []

            # if task_list:
            #     # Process provided task list directly
            #     tasks_map = {task.id: task for task in task_list}
            #     detector = CycleDetector(tasks_map)
            #     cycles, repeated_names, repeated_ids = detector.detect_maximal_cycles_with_repeated_names(min_occurrences=int(config['min_occurrences']))
            #     new_issues = detector.add_issue_per_cycle(cycles, repeated_names, repeated_ids)
            #     all_issues.extend(new_issues)

            if trace_group_id:
                # Process each trace in the group separately
                trace_group = await TraceGroupComposite.get_by_id(data_manager=data_manager, id=trace_group_id)
                if not trace_group:
                    return ExecutionResult(
                        analytics_id=analytics_id,
                        status=ExecutionStatus.FAILURE,
                        error=ExecutionError(
                            error_type="DataError",
                            message=f"No trace group found with id {trace_group_id}"
                        )
                    )

                for single_trace_id in trace_group.traces_ids:
                    # Get tasks for this specific trace
                    tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=single_trace_id)
                    # trace_task_list = [obj.model_dump() for obj in tasks]

                    if tasks:
                        # Process this trace's tasks
                        tasks_map = {task.id: task for task in tasks}
                        detector = CycleDetector(tasks_map)
                        cycles, repeated_names, repeated_ids = detector.detect_maximal_cycles_with_repeated_names(
                            min_occurrences=int(config['min_occurrences']))
                        new_issues = detector.add_issue_per_cycle(cycles, repeated_names,single_trace_id,analytics_id)
                        all_issues.extend(new_issues)

            elif trace_id:
                # Process single trace
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=trace_id)

                if tasks:
                    tasks_map = {task.id: task for task in tasks}
                    detector = CycleDetector(tasks_map)
                    cycles, repeated_names, repeated_ids = detector.detect_maximal_cycles_with_repeated_names(
                        min_occurrences=int(config['min_occurrences']))
                    new_issues = detector.add_issue_per_cycle(cycles, repeated_names,trace_id,analytics_id)
                    all_issues.extend(new_issues)


            # Store all collected issues
            stored_issues = []
            if all_issues:
                stored_issues = await BaseIssue.bulk_store(data_manager=data_manager, base_issues=all_issues)

            issue_list_dicts = [issue.model_dump() for issue in stored_issues]
            new_issue_ids = [issue.element_id for issue in all_issues]
            output = CyclesDetectorOutput(
                trace_id=trace_id,
                trace_group_id=trace_group_id,
                issues=issue_list_dicts,
                new_issues_id=new_issue_ids
            )

            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.SUCCESS,
                output=output
            )

        except Exception as e:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="ProcessingError",
                    message=f"Failed to process cycle detection analytics: {str(e)}",
                    stacktrace=traceback.format_exc()
                )
            )

