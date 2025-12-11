import datetime
from collections import Counter
from typing import Any

from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.task_data import TaskData
from agent_analytics.core.data.trace_data import BaseTraceData
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.metric import (
    BaseDistributionMetric,
    BaseMetric,
    BaseNumericMetric,
)
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils
from agent_analytics.runtime.storage.store_config import StorageTag


class TaskMetricInput(BaseModel):
    trace_id: str | None = Field(None, description="ID of trace")
    trace_group_id: str | None = Field(description="Id of the trace group", default=None)
    task_list: list[dict[str, Any]] | None = Field(default=None, description="List of analyzed tasks")

# trace or task
# issues related to task


class TaskMetricOutput(BaseModel):
    trace_id: str | None= Field(description="ID of trace", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group", default=None)
    metric_element_ids: list[str] | None = None  # list of tasks with changed objects


#############################################################################
# sum two lists starting from beginning
# needed for calculation of tree maximum width
def _sum_lists(l1, l2):
    max_len = max(len(l1), len(l2))
    if max_len == 0:
        return []
    l_sum = []
    for i in range(0, max_len):
        l_sum.append(0)
        if i <= len(l1) - 1:
            l_sum[i] += l1[i]
        if i <= len(l2) - 1:
            l_sum[i] += l2[i]
    return l_sum


############################################################################
def _compute_non_recursive(num_task, task_list, metric_list):

    if isinstance(task_list[num_task]["start_time"], str):
        start = datetime.strptime(task_list[num_task]["start_time"], "%Y-%m-%dT%H:%M:%S.%fZ")
        end = datetime.strptime(task_list[num_task]["end_time"], "%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        start = task_list[num_task]["start_time"]
        end = task_list[num_task]["end_time"]

    metric_list[num_task]["execution_time"] = (end - start).total_seconds()

    return


############################################################################
def _compute_recursive(num_task, task_list, task_computed, task_id, parent_id, metric_list):

    if task_computed[num_task]:
        return

    current_task_id = task_list[num_task]["element_id"]

    task_tags = task_list[num_task].get("tags", [])

    if "llm_call" in task_tags:

        if "tool_call" in task_tags or "complex" in task_tags:
            print("Warning! Incompatible tags for task " + current_task_id)

        metric_list[num_task]["llm_calls"] = 1
        metric_list[num_task]["tool_calls"] = 0
        metric_list[num_task]["subtasks"] = 0
        metric_list[num_task]["width"] = 1
        metric_list[num_task]["level_width"] = [1]

        if "num_input_tokens" in task_list[num_task]["attributes"].keys():
            metric_list[num_task]["num_input_tokens"] = task_list[num_task]["attributes"]["num_input_tokens"]
        else:
            metric_list[num_task]["num_input_tokens"] = 0
            print("warning! Attribute num_input_tokens is missing for task " + current_task_id)

        if "num_output_tokens" in task_list[num_task]["attributes"].keys():
            metric_list[num_task]["num_output_tokens"] = task_list[num_task]["attributes"]["num_output_tokens"]
        else:
            metric_list[num_task]["num_output_tokens"] = 0
            print("warning! Attribute num_output_tokens is missing for task " + current_task_id)

        if "num_total_tokens" in task_list[num_task]["attributes"].keys():
            metric_list[num_task]["num_total_tokens"] = task_list[num_task]["attributes"]["num_total_tokens"]
        else:
            metric_list[num_task]["num_total_tokens"] = 0
            print("warning! Attribute num_total_tokens is missing for task " + current_task_id)

        metric_list[num_task]["tool_distribution"] = {}

    elif "tool_call" in task_tags:
        tool_full_name = task_list[num_task]["name"]
        tool_name = tool_full_name.split(":", 1)[1]

        if "complex" in task_tags:
            print("Warning! Incompatible tags for task " + current_task_id)

        metric_list[num_task]["llm_calls"] = 0
        metric_list[num_task]["tool_calls"] = 1
        metric_list[num_task]["subtasks"] = 0
        metric_list[num_task]["width"] = 1
        metric_list[num_task]["level_width"] = [1]

        metric_list[num_task]["num_input_tokens"] = 0
        metric_list[num_task]["num_output_tokens"] = 0
        metric_list[num_task]["num_total_tokens"] = 0

        metric_list[num_task]["tool_distribution"] = {tool_name: 1}

    elif "complex" in task_tags:
        metric_list[num_task]["llm_calls"] = 0
        metric_list[num_task]["tool_calls"] = 0
        metric_list[num_task]["subtasks"] = 0
        metric_list[num_task]["width"] = 1
        metric_list[num_task]["level_width"] = [1]

        metric_list[num_task]["num_input_tokens"] = 0
        metric_list[num_task]["num_output_tokens"] = 0
        metric_list[num_task]["num_total_tokens"] = 0

        metric_list[num_task]["tool_distribution"] = {}

        children_indices = [i for i, x in enumerate(parent_id) if x == task_id[num_task]]

        if len(children_indices) == 0:
            print("Warning! No children tasks were found for complex task " + current_task_id)

        if num_task in children_indices:
            print("Warning! parent id is equal to id for task " + current_task_id)
            children_indices.remove(num_task)

        for i in range(0, len(children_indices)):
            current_index = children_indices[i]
            _compute_recursive(current_index, task_list, task_computed, task_id, parent_id, metric_list)
            metric_list[num_task]["llm_calls"] += metric_list[current_index]["llm_calls"]
            metric_list[num_task]["tool_calls"] += metric_list[current_index]["tool_calls"]
            metric_list[num_task]["subtasks"] = metric_list[num_task]["subtasks"] + \
                metric_list[current_index]["subtasks"] + 1

            added_list = list(metric_list[current_index]["level_width"])
            added_list.insert(0, 0)
            metric_list[num_task]["level_width"] = _sum_lists(metric_list[num_task]["level_width"], added_list)

            metric_list[num_task]["num_input_tokens"] += int(metric_list[current_index]["num_input_tokens"])
            metric_list[num_task]["num_output_tokens"] += int(metric_list[current_index]["num_output_tokens"])
            metric_list[num_task]["num_total_tokens"] += int(metric_list[current_index]["num_total_tokens"])

            metric_list[num_task]["tool_distribution"] = dict(Counter(metric_list[num_task]["tool_distribution"]) + \
                     Counter(metric_list[current_index]["tool_distribution"]))

        metric_list[num_task]["width"] = max(metric_list[num_task]["level_width"])

    else:

        print("Warning! Task type is not specified for task " + current_task_id)

        metric_list[num_task]["llm_calls"] = 0
        metric_list[num_task]["tool_calls"] = 0
        metric_list[num_task]["subtasks"] = 0
        metric_list[num_task]["width"] = 1
        metric_list[num_task]["level_width"] = [1]
        metric_list[num_task]["num_input_tokens"] = 0
        metric_list[num_task]["num_output_tokens"] = 0
        metric_list[num_task]["num_total_tokens"] = 0

        metric_list[num_task]["tool_distribution"] = {}

    task_computed[num_task] = True

    return


############################################################################################################
def compute_task_metrics_per_trace(analytics_id, trace_id, task_list):
    num_tasks = len(task_list)
    task_computed = [False] * num_tasks

    metric_list = []
    for i in range(0, num_tasks):
        metric_list.append({})

    parent_id = []
    task_id = []

    for task in task_list:
        parent_id.append(task.get("parent_id", None))
        task_id.append(task["id"])

    if len(task_id) != len(set(task_id)):
        print("Warning! Some task ids are repeated. List of task ids:")
        print(task_id)

    for num_task in range(0, num_tasks):
        _compute_non_recursive(num_task, task_list, metric_list)

    for num_task in range(0, num_tasks):
        _compute_recursive(num_task, task_list, task_computed, task_id, parent_id, metric_list)

    computed_metrics = []
    computed_metric_ids = []

    for i in range(0, num_tasks):
        current_task_id = task_list[i]["element_id"]

        ############################################################################################

        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:Execution_Time:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Execution time",
            description="Task execution time in task " + current_task_id + ", sec",
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["execution_time"],
            units='Sec',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Execution_Time:" + current_task_id)

        ###########################################################################################

        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:LLM_Calls:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="LLM calls",
            description="Number of LLM calls in task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["llm_calls"],
            units='Count',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:LLM_Calls:" + current_task_id)

        ############################################################################################

        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:Tool_Calls:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Tool calls",
            description="Number of tool calls in task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["tool_calls"],
            units='Count',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Tool_Calls:" + current_task_id)

        ############################################################################################

        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:Subtasks:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Subtasks",
            description="Number of subtasks in task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["subtasks"],
            units='Count',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Subtasks:" + current_task_id)

        ############################################################################################
        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:Width:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Maximal subtree",
            description="Maximal width of subtree under task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["width"],
            units='Width',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Width:" + current_task_id)

        ############################################################################################
        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:Input_Tokens:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Input tokens",
            description="Number of input tokens in task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["num_input_tokens"],
            units='Count',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Input_Token" + current_task_id)

        ############################################################################################
        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:Output_Tokens:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Output tokens",
            description="Number of output tokens in task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["num_output_tokens"],
            units='Count',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Output_Token" + current_task_id)
        #
        # ############################################################################################
        computed_metrics.append(BaseNumericMetric(
            element_id="Metric:Total_Tokens:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Total tokens",
            description="Number of total tokens in task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["num_total_tokens"],
            units='Count',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Total_Tokens:" + current_task_id)

        # ############################################################################################
        computed_metrics.append(BaseDistributionMetric(
            element_id="Metric:Tool_Distribution:" + current_task_id,
            plugin_metadata_id=analytics_id,
            root=trace_id,
            name="Tool distribution",
            description="Tool distribution in task " + current_task_id,
            related_to=([trace_id, current_task_id],
                        [TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData),
                         TypeResolutionUtils.get_fully_qualified_type_name_for_type(TaskData)]),
            value=metric_list[i]["tool_distribution"],
            units='Count',
            tags=[StorageTag.TASK])
        )
        computed_metric_ids.append("Metric:Tool_Distribution:" + current_task_id)

    return computed_metrics, computed_metric_ids

###############################################################################################
class TaskMetricPlugin(BaseAnalyticsPlugin):

    @classmethod
    def get_input_model(cls) -> type[TaskMetricInput]:
        return TaskMetricInput

    @classmethod
    def get_output_model(cls) -> type[TaskMetricOutput]:
        return TaskMetricOutput

    async def _execute(
            self,
            analytics_id: str,
            data_manager: DataManager,
            input_data: TaskMetricInput,
            config: dict[str, Any]
    ) -> ExecutionResult:
        trace_id = input_data.trace_id
        trace_group_id = input_data.trace_group_id
        task_list = input_data.task_list

        if not trace_id and not trace_group_id and not task_list:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No relevant input provided for the analytics: neither trace_id, or trace_group_id or task_list are given"
                )
            )

        if trace_id or task_list:
            try:
                if  not task_list and trace_id:
                    # Process single trace
                    tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=trace_id)
                    task_list = [obj.model_dump() for obj in tasks]


                if len(task_list) == 0:
                    return ExecutionResult(
                        analytics_id=analytics_id,
                        status=ExecutionStatus.FAILURE,
                        error=ExecutionError(
                            error_type="DataError",
                            message=f"No tasks found for provided trace_id {trace_id}"
                        )
                    )

                computed_metrics, computed_metric_ids = compute_task_metrics_per_trace(analytics_id, trace_id, task_list)

                if len(computed_metric_ids) > 0:
                    await BaseMetric.bulk_store(data_manager=data_manager, base_metrics=computed_metrics)

                output = TaskMetricOutput(
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
                        message=f"Failed to process task metrics: {str(e)}"
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
                    tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=trace_ids[i])
                    task_list = [obj.model_dump() for obj in tasks]

                    if len(task_list)==0:  # check if will work
                       print("Warning! No tasks found for trace_id " + trace_ids[i])

                    computed_metrics, computed_metric_ids = compute_task_metrics_per_trace(analytics_id, trace_ids[i],\
                                                                                            task_list)
                    overall_computed_metrics.extend(computed_metrics)
                    overall_computed_metric_ids.extend(computed_metric_ids)

                if len(overall_computed_metric_ids) > 0:
                    await BaseMetric.bulk_store(data_manager=data_manager, base_metrics=overall_computed_metrics)

                output = TaskMetricOutput(
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
                        message=f"Failed to process task metrics: {str(e)}"
                    )
                )


