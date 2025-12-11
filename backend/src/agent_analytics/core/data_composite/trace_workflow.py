import json
import uuid
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from agent_analytics.core.data.trace_workflow_data import TraceWorkflowData
from agent_analytics.core.data_composite.action import ActionComposite
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.metric import MetricComposite
from agent_analytics.core.data_composite.workflow import BaseWorkflow, WorkflowComposite
from agent_analytics.core.data_composite.workflow_edge import (
    BaseWorkflowEdge,
    WorkflowEdgeComposite,
)
from agent_analytics.core.data_composite.workflow_node import (
    BaseWorkflowNode,
    WorkflowNodeComposite,
)
from agent_analytics.core.data_composite.workflow_node_gateway import BaseWorkflowNodeGateway


class TraceWorkflowComposite(ElementComposite[TraceWorkflowData]):
    """Composite representation of a Task with related Metrics"""
    # Specify the corresponding data class
    data_class: ClassVar[type[TraceWorkflowData]] = TraceWorkflowData

    def __init__(self, data_manager: "DataManager", base_workflow_data: TraceWorkflowData,*, _token: object = None):
        super().__init__(data_manager, base_workflow_data, _token=_token)


    # Basic properties that reflect the underlying data object

    @property
    def action_ids(self) -> list[str]:
        """Get the list of action IDs in this workflow"""
        return self._data_object.actions

    @property
    def workflows_ids(self) -> list[str]:
        """Get the list of workflow objects"""
        return self._data_object.workflows

    @property
    async def workflows(self)->list[WorkflowComposite]:
        """
        Get all workflows in this trace workflow
        
        Returns a list of logical Workflow objects corresponding to the workflow_ids in this object
        """
        workflows_list = []
        for workflow in self._data_object.workflows:
            workflows_list.append(await self._data_manager.get_by_id(workflow,WorkflowComposite))
        return workflows_list

    @property
    def workflows_nodes_ids(self) -> list[str]:
        """Get the list of workflow nodes objects"""
        return self._data_object.workflow_nodes

    @property
    async def workflow_nodes(self) -> list[WorkflowNodeComposite]:
        """
        Get all workflow nodes in this trace workflow
        
        Returns a list of logical WorkflowNode objects corresponding to the workflow_node_ids in this object
        """
        workflows_nodes_list = []
        for workflow_node in self._data_object.workflow_nodes:
            workflows_nodes_list.append(await self._data_manager.get_by_id(workflow_node,WorkflowNodeComposite))
        return workflows_nodes_list

    @property
    async def workflow_edges(self) -> list[WorkflowEdgeComposite]:
        """
        Get all workflow nodes in this trace workflow
        
        Returns a list of logical WorkflowNode objects corresponding to the workflow_node_ids in this object
        """
        workflows_edge_list = []
        for workflow_edge in self._data_object.workflow_edges:
            workflows_edge_list.append(await self._data_manager.get_by_id(workflow_edge,WorkflowEdgeComposite))
        return workflows_edge_list

    @property
    def workflow_edges_ids(self) -> list[str]:
        """Get the list of workflow edge objects"""
        return self._data_object.workflow_edges

    @property
    async def metrics(self) -> list[MetricComposite]:
        """
        Get all metrics related to this workflow node.
        Returns:
            List of metrics related to this workflow node
        """
        # Use the data manager to retrieve elements related to this task
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self, MetricComposite)
        return related_elements

    @classmethod
    async def get_metrics_workflow(cls, data_manager, workflow_id):
        workflow = await data_manager.get_by_id(workflow_id, TraceWorkflowComposite)
        metrics = await workflow.metrics
        return metrics

    # Relationship properties that use the data manager

    async def get_actions(self) -> list[ActionComposite]:
        """
        Get all actions in this workflow
        
        Returns a list of logical Action objects corresponding to the actions IDs in this workflow.
        """
        actions_list = []
        for action in self._data_object.actions:
            actions_list.append(await self._data_manager.get_by_id(action,ActionComposite))
        return actions_list

    @classmethod
    async def create(cls,
                    data_manager: "DataManager",
                    element_id: str,
                    name: str,
                    description: str,
                    actions: list[ActionComposite | str] | None = None,
                    workflows: list[BaseWorkflow] | None = None,
                    workflow_nodes: list[BaseWorkflowNode] | None = None,
                    workflow_edges: list[BaseWorkflowEdge] | None = None,
                    root: ElementComposite | str | None = None,
                    **kwargs) -> 'TraceWorkflowComposite':
        """
        Factory method to create a new trace workflow
        
        Args:
            data_manager: The data manager to use for storage operations
            element_id: The unique identifier for the trace workflow
            name: The name of the trace workflow
            description: A description of the trace workflow
            actions: List of actions to include in the workflow
            workflows: List of workflow objects to include
            workflow_nodes: List of workflow node objects to include
            workflow_edges: List of workflow edge objects to include
            root: The root element for this trace workflow
            **kwargs: Additional attributes for the trace workflow
            
        Returns:
            A new TraceWorkflowComposite instance
        """
        root_id = None
        if root is not None:
            if isinstance(root, ElementComposite):
                root_id = root.element_id
            elif isinstance(root, str):
                root_id = root
            else:
                raise TypeError("root must be either an Element object or a string ID")

        # Process actions IDs
        actions_ids = []
        if actions:
            for action in actions:
                if isinstance(action, ActionComposite):
                    actions_ids.append(action.element_id)
                elif isinstance(action, str):
                    actions_ids.append(action)
                else:
                    raise TypeError("actions must be either ActionComposite objects or string IDs")

        # Bulk store workflow builder objects and collect their IDs
        workflow_ids = []
        if workflows:
            stored_workflows = await BaseWorkflow.bulk_store(data_manager, workflows)
            workflow_ids = [wf.element_id for wf in stored_workflows]

        # Bulk store workflow node builder objects and collect their IDs
        workflow_node_ids = []
        if workflow_nodes:
            stored_workflow_nodes = await BaseWorkflowNode.bulk_store(data_manager, workflow_nodes)
            workflow_node_ids = [wn.element_id for wn in stored_workflow_nodes]

        # Bulk store workflow edge builder objects and collect their IDs
        workflow_edge_ids = []
        if workflow_edges:
            stored_workflow_edges = await BaseWorkflowEdge.bulk_store(data_manager, workflow_edges)
            workflow_edge_ids = [we.element_id for we in stored_workflow_edges]

        # Create trace workflow data
        trace_workflow_data = TraceWorkflowData(
            element_id=element_id,
            root_id=root_id,
            name=name,
            description=description,
            actions=actions_ids,
            workflows=workflow_ids,
            workflow_nodes=workflow_node_ids,
            workflow_edges=workflow_edge_ids,
            **kwargs
        )


        # Create trace workflow instance
        trace_workflow = cls(data_manager, trace_workflow_data, _token=_CREATION_TOKEN)

        # Store the trace workflow
        await data_manager.store(trace_workflow)

        # Return the trace workflow
        return trace_workflow




class BaseTraceWorkflow(BaseModel):
    """
    Builder class for TraceWorkflowComposite logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable TraceWorkflowComposite logical object.
    """
    model_config = {"arbitrary_types_allowed": True}

    # --- Basic fields ---
    element_id: str = Field(default_factory=lambda: f"trace-workflow-{uuid.uuid4()}")
    name: str = ""
    description: str = ""

    # --- Workflow-specific fields ---
    actions: list[ActionComposite | str] = Field(default_factory=list)
    workflows: list[BaseWorkflow] = Field(default_factory=list)
    workflow_nodes: list[BaseWorkflowNode | BaseWorkflowNodeGateway] = Field(default_factory=list)
    workflow_edges: list[BaseWorkflowEdge] = Field(default_factory=list)

    # --- Relationship fields ---
    root: ElementComposite | str | None = None

    # --- Helper fields ---
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    def generate_id_prefix(self) -> str:
        """Generate an ID prefix for this trace workflow"""
        return "trace-workflow"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseTraceWorkflow':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseTraceWorkflow':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> TraceWorkflowComposite:
        if not self.name:
            raise ValueError("Trace workflow name must be set before building")
        if not self.description:
            raise ValueError("Trace workflow description must be set before building")

        # Bulk store all sub-objects first and collect their IDs

        # Bulk store workflow builder objects
        stored_workflow_ids = []
        if self.workflows:
            stored_workflows = await BaseWorkflow.bulk_store(data_manager, self.workflows)
            stored_workflow_ids = [wf.element_id for wf in stored_workflows]

        # Bulk store workflow node builder objects
        stored_workflow_node_ids = []
        if self.workflow_nodes:
            stored_workflow_nodes = await BaseWorkflowNode.bulk_store(data_manager, self.workflow_nodes)
            stored_workflow_node_ids = [wn.element_id for wn in stored_workflow_nodes]

        # Bulk store workflow edge builder objects
        stored_workflow_edge_ids = []
        if self.workflow_edges:
            stored_workflow_edges = await BaseWorkflowEdge.bulk_store(data_manager, self.workflow_edges)
            stored_workflow_edge_ids = [we.element_id for we in stored_workflow_edges]

        # Process root information
        root_id = None
        if self.root is not None:
            if isinstance(self.root, ElementComposite):
                root_id = self.root.element_id
            elif isinstance(self.root, str):
                root_id = self.root
            else:
                raise TypeError("root must be either an Element object or a string ID")

        # Process actions IDs
        actions_ids = []
        for action in self.actions:
            if isinstance(action, ActionComposite):
                actions_ids.append(action.element_id)
            elif isinstance(action, str):
                actions_ids.append(action)
            else:
                raise TypeError("actions must be either ActionComposite objects or string IDs")

        # Create trace workflow data directly
        trace_workflow_data = TraceWorkflowData(
            element_id=self.element_id,
            root_id=root_id,
            name=self.name,
            description=self.description,
            actions=actions_ids,
            workflows=stored_workflow_ids,
            workflow_nodes=stored_workflow_node_ids,
            workflow_edges=stored_workflow_edge_ids,
            tags=self.tags or [],
            attributes=self.attributes or {},
        )

        # Create trace workflow composite directly
        trace_workflow = TraceWorkflowComposite(data_manager, trace_workflow_data, _token=_CREATION_TOKEN)

        # Store the trace workflow
        await data_manager.store(trace_workflow)

        # Return the trace workflow
        return trace_workflow

    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_trace_workflows: list['BaseTraceWorkflow']) -> list[TraceWorkflowComposite]:
        """
        Efficiently store multiple BaseTraceWorkflow objects at once.
        
        This method performs hierarchical bulk storage: first bulk stores all sub-objects
        across all trace workflows, then bulk stores the trace workflows themselves.
        
        Args:
            data_manager: The data manager to use for storage
            base_trace_workflows: List of BaseTraceWorkflow objects to store
            
        Returns:
            List of created TraceWorkflowComposite objects
        """
        # Validate all builders before proceeding
        for base_trace_workflow in base_trace_workflows:
            if not base_trace_workflow.name:
                raise ValueError(f"Trace workflow name must be set before building (id: {base_trace_workflow.element_id})")
            if not base_trace_workflow.description:
                raise ValueError(f"Trace workflow description must be set before building (id: {base_trace_workflow.element_id})")

        # Build mappings from trace workflow element_id to its sub-objects
        trace_workflow_to_workflows = {}
        trace_workflow_to_workflow_nodes = {}
        trace_workflow_to_workflow_edges = {}

        for base_trace_workflow in base_trace_workflows:
            trace_workflow_to_workflows[base_trace_workflow.element_id] = [
                wf.element_id for wf in base_trace_workflow.workflows
            ]
            trace_workflow_to_workflow_nodes[base_trace_workflow.element_id] = [
                wn.element_id for wn in base_trace_workflow.workflow_nodes
            ]
            trace_workflow_to_workflow_edges[base_trace_workflow.element_id] = [
                we.element_id for we in base_trace_workflow.workflow_edges
            ]

        # Collect all unique sub-objects for bulk storage (avoid duplicates)
        all_workflows = []
        all_workflow_nodes = []
        all_workflow_edges = []

        seen_workflow_ids = set()
        seen_workflow_node_ids = set()
        seen_workflow_edge_ids = set()

        for base_trace_workflow in base_trace_workflows:
            for workflow in base_trace_workflow.workflows:
                if workflow.element_id not in seen_workflow_ids:
                    all_workflows.append(workflow)
                    seen_workflow_ids.add(workflow.element_id)

            for workflow_node in base_trace_workflow.workflow_nodes:
                if workflow_node.element_id not in seen_workflow_node_ids:
                    all_workflow_nodes.append(workflow_node)
                    seen_workflow_node_ids.add(workflow_node.element_id)

            for workflow_edge in base_trace_workflow.workflow_edges:
                if workflow_edge.element_id not in seen_workflow_edge_ids:
                    all_workflow_edges.append(workflow_edge)
                    seen_workflow_edge_ids.add(workflow_edge.element_id)

        # Bulk store all unique sub-objects
        if all_workflows:
            await BaseWorkflow.bulk_store(data_manager, all_workflows)
        if all_workflow_nodes:
            await BaseWorkflowNode.bulk_store(data_manager, all_workflow_nodes)
        if all_workflow_edges:
            await BaseWorkflowEdge.bulk_store(data_manager, all_workflow_edges)

        # Create all trace workflow composite objects
        composite_objects = []
        for base_trace_workflow in base_trace_workflows:
            # Process root information
            root_id = None
            if base_trace_workflow.root is not None:
                if isinstance(base_trace_workflow.root, ElementComposite):
                    root_id = base_trace_workflow.root.element_id
                elif isinstance(base_trace_workflow.root, str):
                    root_id = base_trace_workflow.root
                else:
                    raise TypeError("root must be either an Element object or a string ID")

            # Process actions IDs
            actions_ids = []
            for action in base_trace_workflow.actions:
                if isinstance(action, ActionComposite):
                    actions_ids.append(action.element_id)
                elif isinstance(action, str):
                    actions_ids.append(action)
                else:
                    raise TypeError("actions must be either ActionComposite objects or string IDs")

            # Get sub-object IDs using the pre-built mappings
            workflow_ids = trace_workflow_to_workflows[base_trace_workflow.element_id]
            workflow_node_ids = trace_workflow_to_workflow_nodes[base_trace_workflow.element_id]
            workflow_edge_ids = trace_workflow_to_workflow_edges[base_trace_workflow.element_id]

            # Create trace workflow data
            trace_workflow_data = TraceWorkflowData(
                element_id=base_trace_workflow.element_id,
                root_id=root_id,
                name=base_trace_workflow.name,
                description=base_trace_workflow.description,
                actions=actions_ids,
                workflows=workflow_ids,
                workflow_nodes=workflow_node_ids,
                workflow_edges=workflow_edge_ids,
                tags=base_trace_workflow.tags or [],
                attributes=base_trace_workflow.attributes or {},
            )

            # Create trace workflow instance without storing it
            composite = TraceWorkflowComposite(data_manager, trace_workflow_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects
