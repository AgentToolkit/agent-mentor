import json
from typing import Any, ClassVar

from agent_analytics_common.interfaces.iunits import RelationType
from pydantic import Field

from agent_analytics.core.data.workflow_node_gateway import WorkflowNodeGatewayData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.workflow_node import BaseWorkflowNode


class WorkflowNodeGatewayComposite(ElementComposite[WorkflowNodeGatewayData]):
    """Composite representation of a WorkflowNode with related elements"""
    # Specify the corresponding data class
    data_class: ClassVar[type[WorkflowNodeGatewayData]] = WorkflowNodeGatewayData

    def __init__(self, data_manager: "DataManager", workflow_node__gateway_data: WorkflowNodeGatewayData, *, _token: object = None):
        super().__init__(data_manager, workflow_node__gateway_data, _token=_token)


    @property
    def type(self) -> str:
        return self._data_object.node_type

    @property
    def parent_id(self) -> str:
        return self._data_object.parent_id

    @property
    def action_id(self) -> str:
        return self._data_object.action_id

    @property
    def task_counter(self) -> int:
        return self._data_object.task_counter

    @property
    def gate_type(self) -> str:
        return self._data_object.gate_type

    @classmethod
    async def create(cls,
                    data_manager: "DataManager",
                    element_id: str,
                    root: ElementComposite | str | None,
                    name: str,
                    description: str,
                    node_type: str,
                    parent_id: str,
                    action_id: str,
                    task_counter: int ,
                    gate_type: RelationType,
                    plugin_metadata_id: str | None = None,
                    **kwargs) -> 'WorkflowNodeComposite':
        """
        Factory method to create a new WorkflowNode
        
        Args:
            data_manager: The data manager to use for storage operations
            element_id: The unique identifier for the workflow node
            root: The root element this node belongs to
            name: The name of the workflow node
            description: A description of the workflow node
            node_type: The type of the workflow node
            parent_id: The ID of the parent workflow
            action_id: The ID of the associated action
            plugin_metadata_id: Optional plugin metadata identifier
            **kwargs: Additional attributes for the workflow node
            
        Returns:
            A new WorkflowNodeComposite instance
        """
        root_id = None
        if root is not None:
            if isinstance(root, ElementComposite):
                root_id = root.element_id
            elif isinstance(root, str):
                root_id = root
            else:
                raise TypeError("root must be either an Element object or a string ID")

        # Create workflow node data
        workflow_node_gateway_data = WorkflowNodeGatewayData(
            element_id=element_id,
            root_id=root_id,
            plugin_metadata_id=plugin_metadata_id,
            name=name,
            description=description,
            node_type=node_type,
            parent_id=parent_id,
            task_counter=task_counter,
            action_id=action_id,
            gate_type=gate_type
            **kwargs
        )

        # Create workflow node instance
        workflow_gateway_node = cls(data_manager, workflow_node_gateway_data, _token=_CREATION_TOKEN)

        # Store the workflow node
        await data_manager.store(workflow_gateway_node)

        # Return the workflow node
        return workflow_gateway_node


class BaseWorkflowNodeGateway(BaseWorkflowNode):
    """
    Builder class for WorkflowNode logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable WorkflowNode logical object.
    """
    # --- Fields specific to WorkflowNodeGatewayData ---
    gate_type: RelationType = Field(description="The type of the workflow node gateway")



    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseWorkflowNodeGateway':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseWorkflowNodeGateway':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> WorkflowNodeGatewayComposite:
        """
        Build the WorkflowNode logical object.
        
        Args:
            data_manager: The data manager to use for creating the WorkflowNode
            
        Returns:
            The created WorkflowNode logical object
        """
        # Validate required fields
        if not self.name:
            raise ValueError("WorkflowNode name must be set before building")
        if not self.description:
            raise ValueError("WorkflowNode description must be set before building")
        if not self.type:
            raise ValueError("WorkflowNode type must be set before building")
        if not self.parent_id:
            raise ValueError("WorkflowNode parent_id must be set before building")
        if not self.action_id:
            raise ValueError("WorkflowNode action_id must be set before building")

        # Create the workflow node
        return await WorkflowNodeGatewayComposite.create(
            data_manager=data_manager,
            element_id=self.element_id,
            root=self.root_id,
            plugin_metadata_id=self.plugin_metadata_id,
            name=self.name,
            description=self.description,
            node_type=self.type,
            parent_id=self.parent_id,
            action_id=self.action_id,
            task_counter=self.task_counter,
            gate_type=self.gate_type,
            tags=self.tags,
            **self.attributes
        )

    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_workflow_nodes: list['BaseWorkflowNodeGateway']) -> list[WorkflowNodeGatewayComposite]:
        """
        Efficiently store multiple BaseWorkflowNode objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            base_workflow_nodes: List of BaseWorkflowNode objects to store
            
        Returns:
            List of created WorkflowNodeComposite objects
        """
        # Validate all builders before proceeding
        for base_workflow_node in base_workflow_nodes:
            if not base_workflow_node.name:
                raise ValueError(f"WorkflowNode name must be set before building (id: {base_workflow_node.element_id})")
            if not base_workflow_node.description:
                raise ValueError(f"WorkflowNode description must be set before building (id: {base_workflow_node.element_id})")
            if not base_workflow_node.type:
                raise ValueError(f"WorkflowNode type must be set before building (id: {base_workflow_node.element_id})")
            if not base_workflow_node.parent_id:
                raise ValueError(f"WorkflowNode parent_id must be set before building (id: {base_workflow_node.element_id})")
            if not base_workflow_node.action_id:
                raise ValueError(f"WorkflowNode action_id must be set before building (id: {base_workflow_node.element_id})")

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_workflow_node in base_workflow_nodes:
            # Create workflow node data
            workflow_node_data = WorkflowNodeGatewayData(
                element_id=base_workflow_node.element_id,
                root_id=base_workflow_node.root_id,
                plugin_metadata_id=base_workflow_node.plugin_metadata_id,
                name=base_workflow_node.name,
                description=base_workflow_node.description,
                node_type=base_workflow_node.type,
                parent_id=base_workflow_node.parent_id,
                action_id=base_workflow_node.action_id,
                task_counter=base_workflow_node.task_counter,
                gate_type=base_workflow_node.gate_type,
                tags=base_workflow_node.tags or [],
                attributes=base_workflow_node.attributes or {},
            )

            # Create workflow node instance without storing it
            composite = WorkflowNodeGatewayComposite(data_manager, workflow_node_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects
