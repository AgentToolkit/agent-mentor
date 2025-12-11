from typing import Any

from pydantic import BaseModel, Field

from src.core.data.base_data_manager import DataManager
from src.core.data_composite.base_trace import BaseTraceComposite
from src.core.data_composite.task import TaskComposite
from src.core.data_composite.trace_group import TraceGroupComposite
from src.core.data_composite.trace_workflow import BaseTraceWorkflow
from src.core.data_composite.workflow import BaseWorkflow
from src.core.data_composite.workflow_edge import BaseWorkflowEdge
from src.core.data_composite.workflow_node import BaseWorkflowNode
from src.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)


class TraceWorkflowInput(BaseModel):
    trace_id: str | None = Field(None, description="Single trace ID")
    trace_group_id: str | None = Field(None, description="ID of trace group")


class TraceWorkflowOutput(BaseModel):
    trace_id: str | None = Field( description="Id of the trace this analytic was run on",default=None)
    trace_group_id: str | None = Field(description="Id of the trace group this analytic was run on",default=None)
    trace_workflow: list[dict[str, Any]] = Field(..., description="List of analyzed tasks")


async def extract_workflow(trace_ids, all_tasks:list[TaskComposite])-> BaseTraceWorkflow:
    tasks_by_id = {task.id: task for task in all_tasks}

    action_dict = {}
    workflow_dict = {}
    workflow_nodes = {}
    workflow_edges = {}

        # First pass: Create actions
    for task in all_tasks:
        action = await task.executor
        action_name = action.name
        #counter for the number of tasks per action
        if action_name not in action_dict:
            action_dict[action_name]=action


        # Second pass: Create workflows and workflow nodes
    for task in all_tasks:
        if task.parent_id:
            parent_task = tasks_by_id.get(task.parent_id)
            #fetch the action names for parent task and current task
            parent_executor = await parent_task.executor
            parent_name = parent_executor.name
            action = await task.executor
            action_name = action.name
            action_id = action.element_id

            # Create Workflow
            if parent_name not in workflow_dict:
                workflow_dict[parent_name] = BaseWorkflow(
                        # element_id=f"Workflow:{parent_name}",
                        description=f"Workflow:{parent_name}",
                        root=trace_ids[0],
                        type="Workflow",
                        name=parent_name,
                        owner_id=f"Action:{parent_name}",
                        control_flow_ids=[],
                        related_to=[parent_executor]                        #connect the workflow to the action
                    )
            # Create WorkflowNode
            node_id = f"WorkflowNode:{parent_name}#{action_name}"
            if node_id not in workflow_nodes:
                workflow_nodes[node_id] = BaseWorkflowNode(
                        # element_id=node_id,
                        root_id=trace_ids[0],
                        name=node_id,
                        description = node_id,
                        type="WorkflowNode",
                        parent_id=workflow_dict[parent_name].element_id,
                        # owner_id=f"Action:{parent_name}",
                        action_id=action_id
                    )
                workflow_nodes[node_id].task_counter = 1
            else:
                workflow_nodes[node_id].task_counter += 1

    # Third pass: Create workflow edges based on dependencies
    for task in all_tasks:
        if task.parent_id and task.dependent_ids:
            parent_task = tasks_by_id.get(task.parent_id)
            workflow_key = (await parent_task.executor).name

            destination_action = (await task.executor).name
            destination_node_id = f"WorkflowNode:{workflow_key}#{destination_action}"
            destination_id = workflow_nodes[destination_node_id].element_id

            source_ids = []
            for dep_id in task.dependent_ids:
                dep_task = tasks_by_id.get(dep_id)
                source_action=(await dep_task.executor).name
                source_node_id = f"WorkflowNode:{workflow_key}#{source_action}"
                source_id = workflow_nodes[source_node_id].element_id
                source_ids.append(source_id)

            relation_category = "SEQUENTIAL" if len(source_ids) == 1 else "JOIN"
            edge_id = f"WorkflowEdge:{workflow_key} from {', '.join(source_ids)} to {destination_id}"

            if edge_id not in workflow_edges:
                workflow_edges[edge_id] = BaseWorkflowEdge(
                        # element_id=edge_id,
                        name=edge_id,
                        description = edge_id,
                        root_id=trace_ids[0],
                        type="WorkflowEdge",
                        source_category=relation_category,
                        parent_id=workflow_dict[workflow_key].element_id,
                        source_ids=source_ids,
                        destination_ids=[destination_id],
                        destination_category="SEQUENTIAL",
                        weight=1
                    )
            else:
                workflow_edges[edge_id].weight += 1


    # Fourth pass: Connect nodes with no dependencies to their previous node by timestamp
    # First, organize tasks by workflow and sort by timestamp
    tasks_by_workflow = {}
    for task in all_tasks:
        if task.parent_id:
            parent_task = tasks_by_id.get(task.parent_id)
            workflow_key = (await parent_task.executor).name

            if workflow_key not in tasks_by_workflow:
                tasks_by_workflow[workflow_key] = []

            tasks_by_workflow[workflow_key].append(task)

    # Sort tasks in each workflow by creation timestamp
    for workflow_key, workflow_tasks in tasks_by_workflow.items():
        workflow_tasks.sort(key=lambda x: x.start_time)

        # Check each task (except the first one) for missing dependencies
        for idx, task in enumerate(workflow_tasks):
            if idx == 0:  # Skip the first task (it's the earliest by definition)
                continue

            # Check if this task has no dependencies
            if not task.dependent_ids:
                destination_action = (await task.executor).name
                destination_node_id = f"WorkflowNode:{workflow_key}#{destination_action}"
                destination_id = workflow_nodes[destination_node_id].element_id

                # Find a suitable previous task (by timestamp)
                suitable_prev_idx = None
                for prev_idx in range(idx - 1, -1, -1):
                    prev_task = workflow_tasks[prev_idx]

                    # Check if start times are different
                    if prev_task.start_time == task.start_time:
                        continue  # Skip tasks with the same start time

                    # Check end time constraint - if prev_task has end_time, it must be before or equal to task's start time
                    if hasattr(prev_task, 'end_time') and prev_task.end_time is not None:
                        if prev_task.end_time >= task.start_time:
                            #print('hey')
                            continue  # Skip tasks where end_time is after current task's start_time

                    # Found a suitable previous task
                    suitable_prev_idx = prev_idx
                    break

                # If we found a suitable previous task, create an edge
                if suitable_prev_idx is not None:
                    prev_task = workflow_tasks[suitable_prev_idx]
                    source_action = (await prev_task.executor).name
                    source_node_id = f"WorkflowNode:{workflow_key}#{source_action}"
                    source_id = workflow_nodes[source_node_id].element_id

                    # Create an edge from the previous task to this task
                    edge_id = f"WorkflowEdge:{workflow_key} from {source_node_id} to {destination_node_id} (timestamp-based)"

                    if edge_id not in workflow_edges:
                        workflow_edges[edge_id] = BaseWorkflowEdge(
                            root_id=trace_ids[0],
                            # element_id=edge_id,
                            name=edge_id,
                            description = edge_id,
                            type="WorkflowEdge",
                            source_category="SEQUENTIAL",
                            parent_id=workflow_dict[workflow_key].element_id,
                            source_ids=[source_id],
                            destination_ids=[destination_id],
                            destination_category="SEQUENTIAL",
                            weight=1
                        )

                    else:
                        workflow_edges[edge_id].weight += 1
                # If no suitable previous task was found, this node will remain without a parent

        # ---------------------------
        # Step 4: Assemble TraceWorkflow object
        # ---------------------------
        #Return both the actions which needs to be saved separately and the trace workflow
    trace_workflow = BaseTraceWorkflow(
            element_id=f'trace_workflow_{trace_ids[0]}',
            name=f'trace_workflow_{trace_ids[0]}',
            description=f'trace_workflow_{trace_ids[0]}',
            root=trace_ids[0],  # TODO : handle multiple trace_ids with root_id (maybe create new object for grouped traces)
            actions=[action.element_id for action in action_dict.values()],
            workflows=list(workflow_dict.values()),
            workflow_nodes=list(workflow_nodes.values()),
            workflow_edges=list(workflow_edges.values())
    )

    return trace_workflow


class TraceWorkflowPlugin(BaseAnalyticsPlugin):

    @classmethod
    def get_input_model(cls) -> type[TraceWorkflowInput]:
        return TraceWorkflowInput

    @classmethod
    def get_output_model(cls) -> type[TraceWorkflowOutput]:
        return TraceWorkflowOutput

    async def _execute(
        self,
        analytics_id: str,
        data_manager: DataManager,
        input_data: TraceWorkflowInput,
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
                    message="Either trace_id or trace_group_id must be provided"
                )
            )

        if trace_id and trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="Only one of trace_id or trace_group_id can be provided"
                )
            )

        trace_ids = None
        if trace_group_id:
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
            if trace_ids is None or len(trace_ids) == 0:
                return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No traces for the provided trace group id exists"
                )
            )

        trace_ids = trace_ids or [trace_id]

        try:
            # ---------------------------
            # Step 1: Fetch tasks
            # ---------------------------
            all_tasks = []
            for trace in trace_ids:
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager,trace_id=trace)
                all_tasks.extend(tasks)

            if not all_tasks:
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="DataError",
                        message="No tasks found for provided trace_id(s)"
                    )
                )

            # ---------------------------
            # Step 2: Process tasks into trace workflow structure
            # ---------------------------
            trace_workflow = await extract_workflow(trace_ids, all_tasks)
            trace_workflow_composite = await trace_workflow.store(data_manager=data_manager)

            # ---------------------------
            # Step 4: Return output
            # ---------------------------

            workflow_list_dicts = [task.model_dump() for task in [trace_workflow_composite]] #TODO:what is task in trace_workflow?

            output = TraceWorkflowOutput(
                    trace_id=trace_id if not trace_group_id else None,
                    trace_group_id=trace_group_id if trace_group_id else None,
                    trace_workflow=workflow_list_dicts
            )


            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.SUCCESS,
                output=output
            )

        except Exception as e:
            import traceback
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="ProcessingError",
                    message=f"Failed to process trace workflow: {str(e)}",
                    stacktrace=traceback.format_exc()
                )
            )
