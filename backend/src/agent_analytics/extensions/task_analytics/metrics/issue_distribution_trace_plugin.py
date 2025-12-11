from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.task_data import TaskData
from agent_analytics.core.data.trace_data import BaseTraceData
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.data_composite.metric import BaseDistributionMetric, BaseMetric
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils


class IssueDistributionTraceInput(BaseModel):
    trace_id: str | None = Field(None, description="ID of trace")
    trace_group_id: str | None = Field(description="Id of the trace group", default=None)
# trace or task
# issues related to task


class IssueDistributionTraceOutput(BaseModel):
    trace_id: str | None= Field(description="ID of trace", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group", default=None)
    metric_element_ids: list[str] | None = None  # list of tasks with changed metrics objects


def _extract_level(issue):

    level = "WARNING"

    if "level" not in issue.keys():
        return level
    else:
        level_value = issue["level"]
        if level_value is not None:
            level = level_value.value

    return level


#####################################################################
def _compute_recursively_issue_dist(num_task, task_list, issue_list, task_computed, issue_distribution, parent_id):

    if task_computed[num_task]:
        return task_computed

    task_issue_distribution = {}
    for j in range(0, len(issue_list)):
        current_related_ids = issue_list[j].get('related_to_ids', [])

        if task_list[num_task]["element_id"] in current_related_ids:

            current_level = _extract_level(issue_list[j])
            current_issue_distribution = {current_level: 1}

            task_issue_distribution = dict(Counter(task_issue_distribution) + Counter(current_issue_distribution))

    task_tags = task_list[num_task].get("tags", [])
    if "complex" in task_tags:
        children_indices = [i for i, x in enumerate(parent_id) if x == task_list[num_task]["id"]]

        if len(children_indices) == 0:
            print("Warning! No children tasks were found for complex task " + task_list[num_task]["id"])

        if num_task in children_indices:
            print("Warning! parent id is equal to id for task " + task_list[num_task].id)
            children_indices.remove(num_task)

        # recursive computation for children
        for i in range(0, len(children_indices)):
            current_index = children_indices[i]
            child_issue_distribution = _compute_recursively_issue_dist(current_index, task_list, issue_list,
                    task_computed, issue_distribution, parent_id)

            task_issue_distribution = dict(Counter(task_issue_distribution) + Counter(child_issue_distribution))

    full_task_issue_distribution = {}
    full_task_issue_distribution["issue_distribution"] = task_issue_distribution
    full_task_issue_distribution["element_id"] = task_list[num_task]["element_id"]

    issue_distribution.append(full_task_issue_distribution)
    task_computed[num_task] = True

    return task_issue_distribution


def _compute_issue_distribution(task_list, issue_list):

    num_tasks = len(task_list)
    num_issues = len(issue_list)
    issue_distribution = []

    task_computed = [False] * num_tasks
    parent_id = []
    task_id = []

    for task in task_list:
        parent_id.append(task.get("parent_id", None))
        task_id.append(task["id"])

    if len(task_id) != len(set(task_id)):
        print("Warning! Some task ids are repeated. List of task ids:")
        print(task_id)

    for i in range(0, num_tasks):
        task_issue_distribution = _compute_recursively_issue_dist(i, task_list, issue_list, task_computed,
                        issue_distribution, parent_id)

    return issue_distribution


class IssueDistributionTracePlugin(BaseAnalyticsPlugin):

    @classmethod
    def get_input_model(cls) -> type[IssueDistributionTraceInput]:
        return IssueDistributionTraceInput

    @classmethod
    def get_output_model(cls) -> type[IssueDistributionTraceOutput]:
        return IssueDistributionTraceOutput

    async def _execute(
            self,
            analytics_id: str,
            data_manager: DataManager,
            input_data: IssueDistributionTraceInput,
            config: dict[str, Any]
    ) -> ExecutionResult:
        trace_id = input_data.trace_id
        trace_group_id = input_data.trace_group_id

        if not trace_id and not trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="Missing input: Trace id or trace group id are not provided"
                )
            )

        if trace_id:
            try:
                # Process single trace
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=trace_id)
                task_list = [obj.model_dump() for obj in tasks]

                issues = await BaseTraceComposite.get_all_issues_for_trace(data_manager=data_manager, trace_id=trace_id)
                issue_list = [obj.model_dump() for obj in issues]

                if not tasks:          # check if will work
                    return ExecutionResult(
                        analytics_id=analytics_id,
                        status=ExecutionStatus.FAILURE,
                        error=ExecutionError(
                            error_type="DataError",
                            message="No tasks found for provided trace_id"
                        )
                    )

                issue_distribution = _compute_issue_distribution(task_list, issue_list)

                computed_metrics = []
                computed_metric_ids = []

                for i in range(0, len(issue_distribution)):
                    if issue_distribution[i]["issue_distribution"]:
                        computed_metrics.append(BaseDistributionMetric(
                            element_id=f"Metric:Issue_Distribution:{issue_distribution[i]['element_id']}",
                            plugin_metadata_id=analytics_id,
                            root=trace_id,
                            name="Issue distribution in task",
                            description="Issue distribution in task " + issue_distribution[i]["element_id"] + " by severity",
                            related_to=([trace_id, issue_distribution[i]["element_id"]],
                                      [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                                      TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
                            value=issue_distribution[i]["issue_distribution"]
                        )
                        )
                        computed_metric_ids.append(f"Metric:Issue_Distribution:{issue_distribution[i]['element_id']}")

                if len(computed_metric_ids)>0:
                    await BaseMetric.bulk_store(data_manager=data_manager, base_metrics=computed_metrics)

                output = IssueDistributionTraceOutput(
                    trace_id=trace_id,
                    metric_element_ids=computed_metric_ids
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
                        message=f"Failed to process issue distribution metric: {str(e)}"
                    )
                )

        # process trace group
        else:
            try:
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

                trace_ids = trace_group.traces_ids
                print("trace ids")
                print(trace_ids)

                num_traces = len(trace_ids)

                overall_computed_metrics = []
                overall_computed_metric_ids = []

                for i in range(0, num_traces):
                    tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager,
                                                                         trace_id=trace_ids[i])
                    task_list = [obj.model_dump() for obj in tasks]

                    issues = await BaseTraceComposite.get_all_issues_for_trace(data_manager=data_manager,
                                                                               trace_id=trace_ids[i])
                    issue_list = [obj.model_dump() for obj in issues]

                    if len(task_list) == 0:  # check if will work
                        print("Warning! No tasks found for trace_id " + trace_ids[i])

                    issue_distribution = _compute_issue_distribution(task_list, issue_list)

                    computed_metrics = []
                    computed_metric_ids = []

                    for j in range(0, len(issue_distribution)):
                        if issue_distribution[j]["issue_distribution"]:
                            computed_metrics.append(BaseDistributionMetric(
                                element_id=f"Metric:Issue_Distribution:{issue_distribution[j]['element_id']}",
                                plugin_metadata_id=analytics_id,
                                root=trace_id,
                                name="Issue distribution in task",
                                description="Issue distribution in task " + issue_distribution[j]["element_id"] \
                                            + " by severity",
                                related_to=([trace_id, issue_distribution[j]["element_id"]],
                                            [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                                             TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
                                value=issue_distribution[j]["issue_distribution"]
                            )
                            )
                            computed_metric_ids.append(
                                f"Metric:Issue_Distribution:{issue_distribution[j]['element_id']}")

                        overall_computed_metrics.extend(computed_metrics)
                        overall_computed_metric_ids.extend(computed_metric_ids)

                if len(overall_computed_metric_ids) > 0:
                    await BaseMetric.bulk_store(data_manager=data_manager, base_metrics=overall_computed_metrics)

                output = IssueDistributionTraceOutput(
                    trace_group_id=trace_group_id,
                    metric_element_ids=overall_computed_metric_ids
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
                        message=f"Failed to process issue distribution metrics: {str(e)}"
                    )
                )