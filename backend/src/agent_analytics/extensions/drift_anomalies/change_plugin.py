from typing import Any, Literal

import numpy as np
from changepy import pelt
from changepy.costs import normal_mean
from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.trace_data import BaseTraceData
from agent_analytics.core.data.trace_group_data import TraceGroupData
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.issue import BaseIssue
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils

ChangeDirection = Literal["up", "down", "both"]

class ChangePointInput(BaseModel):
    trace_group_id: str = Field(None, description="ID of trace group")
    metrics_list: list[tuple[str, str, ChangeDirection]] = Field(
        default_factory=lambda: [
            ("num_input_tokens", "number of input tokens", "up"),
            ("num_output_tokens", "number of output tokens", "up"),
            ("llm_calls", "number of LLM calls", "up"),
            ("tool_calls", "number of tool calls", "up"),
            ("execution_time", "execution time", "up")
        ]
    )


class ChangePointOutput(BaseModel):
    trace_group_id: str = Field(description="Id of the trace group this analytic was run on", default=None)
    detected_issues_id: list[str] | None = None


def _initialize_data(all_tasks, input_data, num_traces):
    detected_issues = []
    detected_issues_id = []

    num_metrics = len(input_data.metrics_list)
    metrics_values = np.zeros([num_metrics, num_traces])
    metrics_list = []
    metrics_name = []
    directions_list = []

    for i in range(0, num_metrics):
        metrics_list.append(input_data.metrics_list[i][0])
        metrics_name.append(input_data.metrics_list[i][1])
        directions_list.append(input_data.metrics_list[i][2])

    trace_ids = []
    start_timestamps = []
    end_timestamps = []
    task_counter = 0

    for task in all_tasks:
        if task.parent_id is None:
            task_counter += 1
            trace_ids.append(task.log_reference["trace_id"])
            start_timestamps.append(task.start_time)
            end_timestamps.append(task.end_time)

            for i in range(0, num_metrics):
                if metrics_list[i] in task.metrics.keys():
                    metrics_values[i, task_counter - 1] = task.metrics[metrics_list[i]]
                else:
                    metrics_values[i, task_counter - 1] = np.nan

    sorted_with_indices = sorted(enumerate(start_timestamps), key=lambda x: x[1])
    indices = [index for index, value in sorted_with_indices]

    end_timestamps = [end_timestamps[i] for i in indices]
    trace_ids = [trace_ids[i] for i in indices]

    for i in range(0, num_metrics):
        metrics_values[i, :] = [metrics_values[i, j] for j in indices]

    return num_metrics, directions_list, metrics_values, metrics_list, metrics_name, end_timestamps, trace_ids,\
        detected_issues, detected_issues_id


def _run_algorithm(config, current_input):

    stdev = np.std(current_input)
    num_obs = len(current_input)

    if stdev == 0:
        return [], 0

    change_points = pelt(normal_mean(current_input, stdev), num_obs)

    change_points = np.round(change_points).astype(int)    # - 1

    num_change_points = len(change_points)

    if num_change_points > 0:
        if change_points[0] == 0:
            change_points = change_points[1:]
            num_change_points = len(change_points)

    return change_points, num_change_points


def _compute_levels_before_after_change(current_input, interval_start, interval_end, current_change_point):

    continue_indicator = False
    counter = 0
    level_before = 0

    for k in range(interval_start, current_change_point):
        level_before += current_input[k]
        counter += 1

    if counter > 1:
        level_before /= counter
    else:
        continue_indicator = True

    counter = 0
    level_after = 0
    for k in range(current_change_point, interval_end):
        level_after += current_input[k]
        counter += 1

    if counter > 1:
        level_after /= counter
    else:
        continue_indicator = True

    return level_before, level_after, continue_indicator


def _compute_change_percent(anomaly_value, level_around):
    if level_around > 0 and anomaly_value >= 0:
        percent = abs(round(((anomaly_value - level_around) / level_around) * 100.0, 1))
        percent_computed = True
    else:
        percent_computed = False
        percent = 0
    return percent, percent_computed


def _change_words(anomaly_value, level_around):
    if anomaly_value > level_around:
        change_noun = "Increase "
        change_verb = " increased by "
    else:
        change_noun = "Decrease "
        change_verb = " decreased by "
    return change_noun, change_verb


def _detect_change_points(all_tasks, input_data, config, num_traces, trace_group_name, analytics_id):

    num_metrics, directions_list, metrics_values, metrics_list, metrics_name, end_timestamps, trace_ids,\
        detected_issues, detected_issues_id = _initialize_data(all_tasks, input_data, num_traces)

    num_issues = 0

    for i in range(0, num_metrics):

        current_direction = directions_list[i]

        current_input = metrics_values[i, :]

        if np.isnan(current_input).any():
            continue

        change_points, num_change_points = _run_algorithm(config, current_input)

        for j in range(0, num_change_points):
            current_change_point = change_points[j]

            # detect interval around anomaly
            interval_start = max(0, current_change_point-int(config["window_max"]))
            if j > 0:
                interval_start = max(interval_start, change_points[j-1]+1)

            interval_end = min(num_traces, current_change_point+int(config["window_max"]))
            if j < num_change_points-1:
                interval_end = min(interval_end, change_points[j+1])

            level_before, level_after, continue_ind = _compute_levels_before_after_change(current_input,\
                        interval_start, interval_end, current_change_point)

            if continue_ind:
                continue

            delta = abs(level_before-level_after)

            percent, percent_computed = _compute_change_percent(level_after, level_before)

            if not percent_computed or percent > float(config["change_ratio_bound"]) * 100:
                if delta > 0 and ((current_direction == "both") or\
                    (current_direction == "up" and level_after > level_before) or\
                    (current_direction == "down" and level_after < level_before)):

                    trace_id_change = trace_ids[current_change_point]
                    change_time = end_timestamps[current_change_point]
                    num_issues += 1

                    change_noun, change_verb = _change_words(level_after, level_before)

                    sentence_change = "The metric value" + change_verb + str(round(delta, 1))
                    if percent_computed:
                        sentence_change = sentence_change + " and by " +str(percent) + "%. "
                    else:
                        sentence_change += ". "

                    sentence_before = "Average metric level before change: "+str(round(level_before, 1)) + ". "
                    sentence_after = "Average metric level after change: "+str(round(level_after, 1)) + "."

                    current_time = str(change_time)
                    short_time = current_time.split('.')[0]

                    issue_description = ("Change in " + metrics_name[i] + " is detected at time " + short_time +
                                        " for trace group " + trace_group_name + ". " +
                                        sentence_change + sentence_before + sentence_after)

                    # print("Issue description:")
                    # print(issue_description)

                    detected_issues.append(BaseIssue(
                            element_id=f"Issue:Change:{metrics_list[i]}{trace_id_change}",
                            plugin_metadata_id=analytics_id,
                            root=input_data.trace_group_id,
                            name="Change detection: " + change_noun + "in " + metrics_name[i],
                            description=issue_description,
                            related_to=([input_data.trace_group_id, trace_id_change],
                                     [TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceGroupData),
                                     TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseTraceData)]),
                            effect=["Calculation is performed for trace group "+trace_group_name,
                                    "Change in " + metrics_name[i] + " is detected at trace "+trace_id_change]
                        )
                    )
                    detected_issues_id.append(f"Issue:{metrics_list[i]}{trace_id_change}")

    if num_issues == 0:
        detected_issues = None

    return detected_issues, detected_issues_id


class ChangePointPlugin(BaseAnalyticsPlugin):

    @classmethod
    def get_input_model(cls) -> type[ChangePointInput]:
        return ChangePointInput

    @classmethod
    def get_output_model(cls) -> type[ChangePointOutput]:
        return ChangePointOutput

    async def _execute(
            self,
            analytics_id: str,
            data_manager: DataManager,
            input_data: ChangePointInput,
            config: dict[str, Any]
    ) -> ExecutionResult:
        trace_group_id = input_data.trace_group_id

        if not trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="trace_group_id must be provided"
                )
            )

        trace_group = await TraceGroupComposite.get_by_id(data_manager=data_manager,id=trace_group_id)
        if not trace_group:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="The trace group for the provided trace_group_id doesn't exist"
                )
            )
        trace_ids = trace_group.traces_ids
        trace_group_name = trace_group.name

        if trace_ids is None or len(trace_ids) == 0:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No traces for the provided trace group id exists"
                )
            )

        try:
            all_tasks = []
            for trace in trace_ids:
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=trace)
                all_tasks.extend(tasks)

            if not all_tasks:          # check if will work
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="DataError",
                        message="No tasks found for provided trace_id(s)"
                    )
                )

            num_traces = 0

            for task in all_tasks:
                if task.parent_id is None:
                    num_traces += 1

            if num_traces < int(config["min_observations"]):
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="InputError",
                        message="Number of traces is too small for analytics. Minimal number of traces is " +
                                config["min_observations"]
                    )
                )

            detected_issues, detected_issues_id = _detect_change_points(all_tasks, input_data, config,
                                                                        num_traces, trace_group_name, analytics_id)

            # print("detected issues:")
            # print("***********************")
            # print(detected_issues)

            if detected_issues is not None:
                await BaseIssue.bulk_store(data_manager=data_manager, base_issues=detected_issues)

            output = ChangePointOutput(
                trace_group_id=trace_group_id,
                detected_issues_id=detected_issues_id
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
                    message=f"Failed to process change point: {str(e)}"
                )
            )
