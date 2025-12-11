from collections import Counter
from typing import Any

import numpy as np
from ibm_agent_analytics_common.interfaces.metric import AggregatedStats
from pydantic import BaseModel, Field

from src.core.data.action_data import ActionData
from src.core.data.base_data_manager import DataManager
from src.core.data.trace_workflow_data import TraceWorkflowData

#from src.core.data.workflow_edge_data import WorkflowEdgeData
from src.core.data.workflow_node_data import WorkflowNodeData
from src.core.data_composite.base_trace import BaseTraceComposite
from src.core.data_composite.metric import (
    BaseBasicStatsMetric,
    BaseDistributionMetric,
    BaseMetric,
)
from src.core.data_composite.trace_group import TraceGroupComposite
from src.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from src.core.utilities.type_resolver import TypeResolutionUtils

##########################################################################################
# list_numeric_metrics = [("Number of visits", "Num_Visits"), \
#                         ("Task execution time, sec", "Execution_Time"), \
#                         ("Number of LLM calls in task", "LLM_Calls"), \
#                         ("Number of tool calls in task","Tool_Calls"), \
#                         ("Number of subtasks in task", "Subtasks"), \
#                         ("Maximal width of subtree under task", "Width"), \
#                         ("Number of input tokens in task", "Input_Tokens"), \
#                         ("Number of output tokens in task", "Output_Tokens"), \
#                         ("Number of total tokens in task", "Total_Tokens")]
#
# list_distribution_metrics = [("Tool distribution in task", "Tool_Distribution"),
#                              ("Issue distribution in task", "Issue_Distribution")]

class WorkflowMetricInput(BaseModel):
    trace_id: str | None = Field(None, description="A single trace ID to analyze.")
    trace_group_id: str | None = Field(None, description="An ID for a group of traces to analyze together.")
    trace_workflow: dict[str, Any] = Field(..., description="Workflow object")

class WorkflowMetricOutput(BaseModel):
    trace_id: str | None = Field(None, description="A single trace ID to analyze.")
    trace_group_id: str | None = Field(None, description="An ID for a group of traces to analyze together.")
    workflow_id: str
    metric_element_ids: list[str]


##########################################################################################
def extract_task_name_from_workflow(str):
    if str.endswith(".task"):
        str = str[:-5]
    # else chat task
    elif str != "0:_ROOT":
        str = str.rsplit(".", 1)[0] # before last period
        str = str.rsplit(":", 1)[-1] # after last :
    return str


##########################################################################################
def extract_task_name_from_task(str):
    if str == "0:_ROOT":
        return str
    else:
        str = str.rsplit(":", 1)[-1]
        if str.endswith(".chat"):
            str = str[:-5]
    return str


#############################################################################################
def get_node_obj(trace_workflow):
    node_obj = dict()

    extended_node_list = trace_workflow.get("workflow_nodes", [])
    for i in range(0, len(extended_node_list)):
        current_element = extended_node_list[i]
        if current_element.startswith("WorkflowNode"):
            start = current_element.find(":") + 1
            end = current_element.find("#", start)

            node_start = current_element[start:end]
            node_start = extract_task_name_from_workflow(node_start)

            start = end+1
            end = current_element.find("#", start)

            node_end = current_element[start:end]
            node_end = extract_task_name_from_workflow(node_end)

            node_obj[(node_start, node_end)] = {}
            node_obj[(node_start, node_end)]["node_name"] = current_element
            node_obj[(node_start, node_end)]["metrics"] = {}

    return node_obj


############################################################################################
# wokflow obj is updated
def compute_workflow_metrics(analytics_id, workflow_id, num_traces, workflow_node_obj, workflow_obj, num_node_visits,\
                             list_numeric_metrics, list_distribution_metrics):

    computed_metrics = []
    computed_metric_ids = []

    # workflow metrics
    for i in range(0, len(list_numeric_metrics)):
        metric_name = list_numeric_metrics[i][0]
        if metric_name in workflow_obj["metrics"].keys():
            workflow_obj["metrics"][metric_name]["count"] = len(workflow_obj["metrics"][metric_name]["values"])
            workflow_obj["metrics"][metric_name]["mean"] = np.mean(workflow_obj["metrics"][metric_name]["values"])
            workflow_obj["metrics"][metric_name]["std"] = np.std(workflow_obj["metrics"][metric_name]["values"])
            workflow_obj["metrics"][metric_name]["min"] = np.min(workflow_obj["metrics"][metric_name]["values"])
            workflow_obj["metrics"][metric_name]["max"] = np.max(workflow_obj["metrics"][metric_name]["values"])
            #workflow_obj["metrics"][metric_name]["sum"] = np.sum(workflow_obj["metrics"][metric_name]["values"])

            computed_metrics.append(BaseBasicStatsMetric(
                element_id="Metric:" + list_numeric_metrics[i][1] + ":" + workflow_id,
                plugin_metadata_id=analytics_id,
                root=workflow_id,
                name=metric_name,
                description=metric_name + " in workflow " + workflow_id,
                related_to=([workflow_id], [TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData)]),
                value=AggregatedStats(count=workflow_obj["metrics"][metric_name]["count"],
                                      mean=workflow_obj["metrics"][metric_name]["mean"],
                                      std=workflow_obj["metrics"][metric_name]["std"],
                                      min=workflow_obj["metrics"][metric_name]["min"],
                                      max=workflow_obj["metrics"][metric_name]["max"],
                                      #sum=workflow_obj["metrics"][metric_name]["sum"],
                                      attributes=None)))

            computed_metric_ids.append("Metric:" + list_numeric_metrics[i][1] + ":" + workflow_id)

    for i in range(0, len(list_distribution_metrics)):
        metric_name = list_distribution_metrics[i][0]
        if metric_name in workflow_obj["metrics"].keys():
            sum_distributions = workflow_obj["metrics"][metric_name]["values"][0]

            for j in range(1, len(workflow_obj["metrics"][metric_name]["values"])):
                sum_distributions = dict(Counter(sum_distributions) + \
                                         Counter(workflow_obj["metrics"][metric_name]["values"][j]))

            workflow_obj["metrics"][metric_name]["sum"] = sum_distributions

            computed_metrics.append(BaseDistributionMetric(
                element_id="Metric:" + list_distribution_metrics[i][1] + ":" + workflow_id,
                plugin_metadata_id=analytics_id,
                root=workflow_id,
                name=metric_name,
                description=metric_name + " in workflow " + workflow_id,
                related_to=([workflow_id], [TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData)]),
                value=workflow_obj["metrics"][metric_name]["sum"]))

            computed_metric_ids.append("Metric:" + list_distribution_metrics[i][1] + ":" + workflow_id)

    # Workflow nodes metrics
    for key in workflow_node_obj.keys():

        # process number of visits metrics
        workflow_node_obj[key]["metrics"]["Number of visits"] = {}
        workflow_node_obj[key]["metrics"]["Number of visits"]["values"] = np.zeros(num_traces)

        if key in num_node_visits.keys():
            trace_counter = 0
            for trace in num_node_visits[key].keys():
                workflow_node_obj[key]["metrics"]["Number of visits"]["values"][trace_counter] = num_node_visits[key][trace]
                trace_counter += 1

        for i in range(0, len(list_numeric_metrics)):
            metric_name = list_numeric_metrics[i][0]
            workflow_node_id = workflow_node_obj[key]["node_name"]
            splits = workflow_node_id.split('#')
            action_id=f'Action:{splits[-2]}#{splits[-1]}'

            if metric_name in workflow_node_obj[key]["metrics"].keys():
                workflow_node_obj[key]["metrics"][metric_name]["count"] = \
                    len(workflow_node_obj[key]["metrics"][metric_name]["values"])
                workflow_node_obj[key]["metrics"][metric_name]["mean"] = \
                    np.mean(workflow_node_obj[key]["metrics"][metric_name]["values"])
                workflow_node_obj[key]["metrics"][metric_name]["std"] = \
                    np.std(workflow_node_obj[key]["metrics"][metric_name]["values"])
                workflow_node_obj[key]["metrics"][metric_name]["min"] = \
                    np.min(workflow_node_obj[key]["metrics"][metric_name]["values"])
                workflow_node_obj[key]["metrics"][metric_name]["max"] = \
                    np.max(workflow_node_obj[key]["metrics"][metric_name]["values"])
                # workflow_node_obj[key]["metrics"][metric_name]["sum"] = \
                #     np.sum(workflow_node_obj[key]["metrics"][metric_name]["values"])

                computed_metrics.append(BaseBasicStatsMetric(
                    units = list_numeric_metrics[i][2],
                    element_id="Metric:" + list_numeric_metrics[i][1] + ":" + workflow_node_id,
                    plugin_metadata_id=analytics_id,
                    root=workflow_id,
                    name=metric_name,
                    description=metric_name+" in workflow node " + workflow_node_id,
                    related_to=([workflow_id, workflow_node_id, action_id],
                                [TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData),
                                 TypeResolutionUtils.get_fully_qualified_type_name_for_type(WorkflowNodeData),
                                 TypeResolutionUtils.get_fully_qualified_type_name_for_type(ActionData)],),
                    value=AggregatedStats(count=workflow_node_obj[key]["metrics"][metric_name]["count"],
                                          mean=workflow_node_obj[key]["metrics"][metric_name]["mean"],
                                          std=workflow_node_obj[key]["metrics"][metric_name]["std"],
                                          min=workflow_node_obj[key]["metrics"][metric_name]["min"],
                                          max=workflow_node_obj[key]["metrics"][metric_name]["max"],
                                          #sum=workflow_node_obj[key]["metrics"][metric_name]["sum"],
                                          attributes=None)))

                computed_metric_ids.append("Metric:" + list_numeric_metrics[i][1] + ":" + workflow_node_id)

        for i in range(0, len(list_distribution_metrics)):
            metric_name = list_distribution_metrics[i][0]
            workflow_node_id = workflow_node_obj[key]["node_name"]
            splits = workflow_node_id.split('#')
            action_id=f'Action:{splits[-2]}#{splits[-1]}'
            if metric_name in workflow_node_obj[key]["metrics"].keys():
                sum_distributions = workflow_node_obj[key]["metrics"][metric_name]["values"][0]

                for j in range(1, len(workflow_node_obj[key]["metrics"][metric_name]["values"])):
                    sum_distributions = dict(Counter(sum_distributions) + \
                        Counter(workflow_node_obj[key]["metrics"][metric_name]["values"][j]))

                workflow_node_obj[key]["metrics"][metric_name]["sum"] = sum_distributions

                computed_metrics.append(BaseDistributionMetric(
                    element_id="Metric:" + list_distribution_metrics[i][1] + ":" + workflow_node_id,
                    plugin_metadata_id=analytics_id,
                    root=workflow_id,
                    name=metric_name,
                    description=metric_name+" in workflow node " + workflow_node_id,
                    related_to=([workflow_id, workflow_node_id, action_id],
                                [TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData),
                                 TypeResolutionUtils.get_fully_qualified_type_name_for_type(WorkflowNodeData),
                                 TypeResolutionUtils.get_fully_qualified_type_name_for_type(ActionData)]),
                    value=workflow_node_obj[key]["metrics"][metric_name]["sum"]))

                computed_metric_ids.append("Metric:" + list_distribution_metrics[i][1] + ":" + workflow_node_id)

    return computed_metrics, computed_metric_ids

####################################################################################
def update_workflow_metrics(workflow_obj, all_metric_dict, trace_id, task_element_id,\
                            list_numeric_metrics, list_distribution_metrics):

    for i in range(0, len(list_numeric_metrics)):
        metric_name = list_numeric_metrics[i][0]
        if (trace_id, task_element_id, metric_name) in all_metric_dict.keys():
            current_value = all_metric_dict[(trace_id, task_element_id, metric_name)]["value"]
            if metric_name in workflow_obj["metrics"].keys():
                workflow_obj["metrics"][metric_name]["values"].append(current_value)
            else:
                workflow_obj["metrics"][metric_name] = {}
                workflow_obj["metrics"][metric_name]["values"] = [current_value]

    for i in range(0, len(list_distribution_metrics)):
        metric_name = list_distribution_metrics[i][0]
        if (trace_id, task_element_id, metric_name) in all_metric_dict.keys():
            current_value = all_metric_dict[(trace_id, task_element_id, metric_name)]["value"]
            if metric_name in workflow_obj["metrics"].keys():
                workflow_obj["metrics"][metric_name]["values"].append(current_value)
            else:
                workflow_obj["metrics"][metric_name] = {}
                workflow_obj["metrics"][metric_name]["values"] = [current_value]

    return


#########################################################################
def update_workflow_node_metrics(workflow_node_obj, all_metric_dict, trace_id, task_element_id, parent_name, task_name,\
                                 list_numeric_metrics, list_distribution_metrics):

    for i in range(0, len(list_numeric_metrics)):
        metric_name = list_numeric_metrics[i][0]
        if (trace_id, task_element_id, metric_name) in all_metric_dict.keys():
            current_value = all_metric_dict[(trace_id, task_element_id, metric_name)]["value"]
            if metric_name in workflow_node_obj[(parent_name, task_name)]["metrics"].keys():
                workflow_node_obj[(parent_name, task_name)]["metrics"][metric_name]["values"].append(current_value)
            else:
                workflow_node_obj[(parent_name, task_name)]["metrics"][metric_name] = {}
                workflow_node_obj[(parent_name, task_name)]["metrics"][metric_name]["values"] = [current_value]

    for i in range(0, len(list_distribution_metrics)):
        metric_name = list_distribution_metrics[i][0]
        if (trace_id, task_element_id, metric_name) in all_metric_dict.keys():
            current_value = all_metric_dict[(trace_id, task_element_id, metric_name)]["value"]
            if metric_name in workflow_node_obj[(parent_name, task_name)]["metrics"].keys():
                workflow_node_obj[(parent_name, task_name)]["metrics"][metric_name]["values"].append(current_value)
            else:
                workflow_node_obj[(parent_name, task_name)]["metrics"][metric_name] = {}
                workflow_node_obj[(parent_name, task_name)]["metrics"][metric_name]["values"] = [current_value]

    return

###############################################################################################
class WorkflowMetricPlugin(BaseAnalyticsPlugin):

    @classmethod
    def get_input_model(cls) -> type[WorkflowMetricInput]:
        return WorkflowMetricInput

    @classmethod
    def get_output_model(cls) -> type[WorkflowMetricOutput]:
        return WorkflowMetricOutput

    async def _execute(
            self,
            analytics_id: str,
            data_manager: DataManager,
            input_data: WorkflowMetricInput,
            config: dict[str, Any]
    ) -> ExecutionResult:
        trace_id = input_data.trace_id
        trace_group_id = input_data.trace_group_id
        trace_workflow = input_data.trace_workflow

        if not trace_id and not trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No relevant input provided for the analytics: neither trace_id, or trace_group_id, are given."
                )
            )

        list_numeric_metrics = config["list_numeric_metrics"]
        list_distribution_metrics = config["list_distribution_metrics"]

        if trace_id and trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="Both trace_id and trace_group_id are provided. Only one of these inputs should be provided."
                )
            )

        if trace_id:
            trace_ids = [trace_id]

        # process trace group
        elif trace_group_id:
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

            except Exception:
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="ProcessingError",
                        message=f"Failed to load trace group with id {trace_group_id}"
                    )
                )

        try:

            num_traces = len(trace_ids)

            workflow_obj = dict()
            workflow_obj["metrics"] = {}

            workflow_node_obj = get_node_obj(trace_workflow)
            workflow_id = trace_workflow["element_id"]

            #####################################################################
            # Get tasks list
            all_tasks = []
            all_task_dict = dict()
            all_metrics = []
            all_metric_dict = dict()

            for i in range(0, num_traces):
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager,
                                                                     trace_id=trace_ids[i])

                metrics = await BaseTraceComposite.get_all_metrics_for_trace(data_manager=data_manager,
                                                                             trace_id=trace_ids[i])

                task_list = [obj.model_dump() for obj in tasks]
                metric_list = [obj.model_dump() for obj in metrics]

                if len(task_list) == 0:  # check if will work
                    print("Warning! No tasks found for trace_id " + trace_ids[i])
                    continue

                if len(metric_list) == 0:  # check if will work
                    print("Warning! No metrics found for trace_id " + trace_ids[i])
                    continue

                all_tasks.extend(task_list)
                all_metrics.extend(metric_list)

                for j in range(0, len(task_list)):
                    all_task_dict[task_list[j]["id"]] = task_list[j]

                for j in range(0, len(metric_list)):
                    if len(metric_list[j]["related_to_ids"]) >= 2:
                        all_metric_dict[(metric_list[j]["related_to_ids"][0], metric_list[j]["related_to_ids"][1],\
                            metric_list[j]["name"])] = metric_list[j]

            num_tasks = len(all_tasks)

            # stores new num_node_visits metrics
            num_node_visits = dict()
            trace_list = []

            # read metric information from tasks and match to nodes
            for i in range(0, num_tasks):
                try:
                    current_name = all_tasks[i]["name"]
                    current_name = extract_task_name_from_task(current_name)
                    current_parent_id = all_tasks[i]["parent_id"]
                    current_element_id = all_tasks[i]["element_id"]
                    current_trace_id = all_tasks[i]["log_reference"]["trace_id"]

                    if current_trace_id not in trace_list:
                        trace_list.append(current_trace_id)

                    if current_parent_id is not None:
                        try:
                            current_parent_name = all_task_dict[current_parent_id]["name"]
                            current_parent_name = extract_task_name_from_task(current_parent_name)
                        except KeyError as e:
                            print(f"Error: Parent task not found in all_task_dict")
                            print(f"  current_parent_id: {current_parent_id}")
                            print(f"  available keys: {list(all_task_dict.keys())}")
                            print(f"  current_task: {all_tasks[i]}")
                            raise KeyError(f"Parent task with id '{current_parent_id}' not found in task dictionary") from e

                        if (current_parent_name, current_name) in workflow_node_obj.keys():
                            update_workflow_node_metrics(workflow_node_obj, all_metric_dict, current_trace_id,\
                                    current_element_id, current_parent_name, current_name, list_numeric_metrics,\
                                    list_distribution_metrics)

                            if (current_parent_name, current_name) not in num_node_visits.keys():
                                num_node_visits[(current_parent_name, current_name)] = {}
                            if current_trace_id in num_node_visits[(current_parent_name, current_name)].keys():
                                num_node_visits[(current_parent_name, current_name)][current_trace_id] += 1
                            else:
                                num_node_visits[(current_parent_name, current_name)][current_trace_id] = 1
                        else:
                            print("Warning! The node was not found in workflow information")
                            print((current_parent_name, current_name))

                    # ROOT task
                    else:
                        update_workflow_metrics(workflow_obj, all_metric_dict, current_trace_id, current_element_id,\
                                                list_numeric_metrics, list_distribution_metrics)

                except Exception as e:
                    print(f"Error processing task {i}/{num_tasks}")
                    print(f"  Task name: {all_tasks[i].get('name', 'UNKNOWN')}")
                    print(f"  Task element_id: {all_tasks[i].get('element_id', 'UNKNOWN')}")
                    print(f"  Task parent_id: {all_tasks[i].get('parent_id', 'UNKNOWN')}")
                    print(f"  Trace ID: {all_tasks[i].get('log_reference', {}).get('trace_id', 'UNKNOWN')}")
                    print(f"  Exception type: {type(e).__name__}")
                    print(f"  Exception message: {str(e)}")
                    import traceback
                    print(f"  Full traceback:\n{traceback.format_exc()}")
                    raise

            num_traces = len(trace_list)

            computed_metrics, computed_metric_ids = compute_workflow_metrics(analytics_id, workflow_id, num_traces,\
                workflow_node_obj, workflow_obj, num_node_visits, list_numeric_metrics, list_distribution_metrics)

            if len(computed_metric_ids) > 0:
                await BaseMetric.bulk_store(data_manager=data_manager, base_metrics=computed_metrics)

            output = WorkflowMetricOutput(
                trace_group_id=trace_group_id,
                trace_id=trace_id,
                workflow_id=workflow_id,
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


