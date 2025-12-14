import json
from typing import Any, ClassVar

from agent_analytics_common.interfaces.elements import Element
from pydantic import Field

from agent_analytics.core.data.workflow_edge_data import WorkflowEdgeData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.metric import MetricComposite


class WorkflowEdgeComposite(ElementComposite[WorkflowEdgeData]):
    """Composite representation of a WorkflowEdge with related elements"""
    # Specify the corresponding data class
    data_class: ClassVar[type[WorkflowEdgeData]] = WorkflowEdgeData

    def __init__(self, data_manager: "DataManager", workflow_edge_data: WorkflowEdgeData, *, _token: object = None):
        super().__init__(data_manager, workflow_edge_data, _token=_token)


    @property
    def type(self) -> str:
        return self._data_object.relation_type

    @property
    def source_category(self) -> str:
        return self._data_object.source_category

    @property
    def parent_id(self) -> str:
        return self._data_object.parent_id

    @property
    def source_ids(self) -> list[str]:
        return self._data_object.source_ids

    @property
    def destination_ids(self) -> list[str]:
        return self._data_object.destination_ids

    @property
    def destination_category(self) -> str:
        return self._data_object.destination_category

    @property
    def weight(self) -> int:
        return self._data_object.weight
    
    @property
    def trace_count(self) -> int:
        return self._data_object.trace_count
    
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
    async def create(cls,
                    data_manager: "DataManager",
                    element_id: str,
                    root: ElementComposite | str | None,
                    name: str,
                    description: str,
                    edge_type: str,
                    source_category: str,
                    parent_id: str,
                    source_ids: list[str],
                    destination_ids: list[str],
                    destination_category: str,
                    weight: int = 0,
                    trace_count: int = 0,
                    plugin_metadata_id: str | None = None,
                    **kwargs) -> 'WorkflowEdgeComposite':
        """
        Factory method to create a new WorkflowEdge
        
        Args:
            data_manager: The data manager to use for storage operations
            element_id: The unique identifier for the workflow edge
            root: The root element this edge belongs to
            name: The name of the workflow edge
            description: A description of the workflow edge
            edge_type: The type of the workflow edge
            source_category: The category of the source node
            parent_id: The ID of the parent workflow
            source_ids: List of source node IDs
            destination_ids: List of destination node IDs
            destination_category: The category of the destination node
            weight: The weight of the edge (default: 0)
            plugin_metadata_id: Optional plugin metadata identifier
            **kwargs: Additional attributes for the workflow edge
            
        Returns:
            A new WorkflowEdgeComposite instance
        """
        root_id = None
        if root is not None:
            if isinstance(root, ElementComposite):
                root_id = root.element_id
            elif isinstance(root, str):
                root_id = root
            else:
                raise TypeError("root must be either an Element object or a string ID")

        # Create workflow edge data
        workflow_edge_data = WorkflowEdgeData(
            element_id=element_id,
            root_id=root_id,
            plugin_metadata_id=plugin_metadata_id,
            name=name,
            description=description,
            relation_type=edge_type,
            source_category=source_category,
            parent_id=parent_id,
            source_ids=source_ids,
            destination_ids=destination_ids,
            destination_category=destination_category,
            weight=weight,
            trace_count=trace_count
            **kwargs
        )

        # Create workflow edge instance
        workflow_edge = cls(data_manager, workflow_edge_data, _token=_CREATION_TOKEN)

        # Store the workflow edge
        await data_manager.store(workflow_edge)

        # Return the workflow edge
        return workflow_edge


class BaseWorkflowEdge(Element):
    """
    Builder class for WorkflowEdge logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable WorkflowEdge logical object.
    """
    model_config = {"arbitrary_types_allowed": True}

    # ---Additional platform fields
    plugin_metadata_id: str | None = Field(
        description='The identifier of the analytics which created this object', default=None
    )

    # --- Fields specific to WorkflowEdge ---
    type: str = Field(description="The type of the workflow edge")
    source_category: str = Field(description="The category of the source node")
    parent_id: str = Field(description="The ID of the parent workflow")
    source_ids: list[str] = Field(description="List of source node IDs", default_factory=list)
    destination_ids: list[str] = Field(description="List of destination node IDs", default_factory=list)
    destination_category: str = Field(description="The category of the destination node")
    weight: int = Field(description="The weight of the edge (as an integer)", default=0)
    trace_count: int = Field(description="The weight of the edge (as an integer)", default=0)
    # --- Relationship fields ---
    root_id: str = Field(description="The ID of the root trace of the workflow")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseWorkflowEdge':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseWorkflowEdge':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> WorkflowEdgeComposite:
        """
        Build the WorkflowEdge logical object.
        
        Args:
            data_manager: The data manager to use for creating the WorkflowEdge
            
        Returns:
            The created WorkflowEdge logical object
        """
        # Validate required fields
        if not self.name:
            raise ValueError("WorkflowEdge name must be set before building")
        if not self.description:
            raise ValueError("WorkflowEdge description must be set before building")
        if not self.type:
            raise ValueError("WorkflowEdge type must be set before building")
        if not self.source_category:
            raise ValueError("WorkflowEdge source_category must be set before building")
        if not self.parent_id:
            raise ValueError("WorkflowEdge parent_id must be set before building")
        if not self.source_ids:
            raise ValueError("WorkflowEdge source_ids must be set before building")
        if not self.destination_ids:
            raise ValueError("WorkflowEdge destination_ids must be set before building")
        if not self.destination_category:
            raise ValueError("WorkflowEdge destination_category must be set before building")

        # Create the workflow edge
        return await WorkflowEdgeComposite.create(
            data_manager=data_manager,
            element_id=self.element_id,
            root=self.root_id,
            plugin_metadata_id=self.plugin_metadata_id,
            name=self.name,
            description=self.description,
            edge_type=self.type,
            source_category=self.source_category,
            parent_id=self.parent_id,
            source_ids=self.source_ids,
            destination_ids=self.destination_ids,
            destination_category=self.destination_category,
            weight=self.weight,
            trace_count=self.trace_count,
            tags=self.tags,
            **self.attributes
        )

    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_workflow_edges: list['BaseWorkflowEdge']) -> list[WorkflowEdgeComposite]:
        """
        Efficiently store multiple BaseWorkflowEdge objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            base_workflow_edges: List of BaseWorkflowEdge objects to store
            
        Returns:
            List of created WorkflowEdgeComposite objects
        """
        # Validate all builders before proceeding
        for base_workflow_edge in base_workflow_edges:
            if not base_workflow_edge.name:
                raise ValueError(f"WorkflowEdge name must be set before building (id: {base_workflow_edge.element_id})")
            if not base_workflow_edge.description:
                raise ValueError(f"WorkflowEdge description must be set before building (id: {base_workflow_edge.element_id})")
            if not base_workflow_edge.type:
                raise ValueError(f"WorkflowEdge type must be set before building (id: {base_workflow_edge.element_id})")
            if not base_workflow_edge.source_category:
                raise ValueError(f"WorkflowEdge source_category must be set before building (id: {base_workflow_edge.element_id})")
            if not base_workflow_edge.parent_id:
                raise ValueError(f"WorkflowEdge parent_id must be set before building (id: {base_workflow_edge.element_id})")
            if not base_workflow_edge.source_ids:
                raise ValueError(f"WorkflowEdge source_ids must be set before building (id: {base_workflow_edge.element_id})")
            if not base_workflow_edge.destination_ids:
                raise ValueError(f"WorkflowEdge destination_ids must be set before building (id: {base_workflow_edge.element_id})")
            if not base_workflow_edge.destination_category:
                raise ValueError(f"WorkflowEdge destination_category must be set before building (id: {base_workflow_edge.element_id})")

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_workflow_edge in base_workflow_edges:
            # Create workflow edge data
            workflow_edge_data = WorkflowEdgeData(
                element_id=base_workflow_edge.element_id,
                root_id=base_workflow_edge.root_id,
                plugin_metadata_id=base_workflow_edge.plugin_metadata_id,
                name=base_workflow_edge.name,
                description=base_workflow_edge.description,
                relation_type=base_workflow_edge.type,
                source_category=base_workflow_edge.source_category,
                parent_id=base_workflow_edge.parent_id,
                source_ids=base_workflow_edge.source_ids,
                destination_ids=base_workflow_edge.destination_ids,
                destination_category=base_workflow_edge.destination_category,
                weight=base_workflow_edge.weight,
                trace_count = base_workflow_edge.trace_count,
                tags=base_workflow_edge.tags or [],
                attributes=base_workflow_edge.attributes or {},
            )

            # Create workflow edge instance without storing it
            composite = WorkflowEdgeComposite(data_manager, workflow_edge_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects
