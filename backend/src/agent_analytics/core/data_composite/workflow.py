import json
from typing import Any, ClassVar

from agent_analytics_common.interfaces.relatable_element import RelatableElement
from pydantic import Field

from agent_analytics.core.data.workflow_data import WorkflowData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.metric import MetricComposite
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils


class WorkflowComposite(RelatableElementComposite[WorkflowData]):
    """Composite representation of a Task with related Metrics"""
    # Specify the corresponding data class
    data_class: ClassVar[type[WorkflowData]] = WorkflowData

    def __init__(self, data_manager: "DataManager", workflow_data: WorkflowData,*, _token: object = None):
        super().__init__(data_manager, workflow_data, _token=_token)


    @property
    def owner_id(self) -> str:
        return self._data_object.owner_id

    @property
    def type(self) -> str:
        return self._data_object.type

    @property
    def control_flow_ids(self) -> list[str]:
        return self._data_object.control_flow_ids

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
        workflow = await data_manager.get_by_id(workflow_id, WorkflowComposite)
        metrics = await workflow.metrics
        return metrics

    @classmethod
    async def create(cls,
                    data_manager: "DataManager",
                    element_id: str,
                    root: ElementComposite | str | None,
                    name: str,
                    description: str,
                    owner_id: str,
                    object_type: str,
                    control_flow_ids: list[str],
                    plugin_metadata_id: str | None=None,
                    related_to: list[ElementComposite] | tuple[list[str], list[str]] = None,
                    **kwargs) -> 'WorkflowComposite':
        """
        Factory method to create a new Issue
        
        Args:
            data_manager: The data manager to use for storage operations
            element_id: The unique identifier for the issue
            name: The name of the issue
            description: A description of the issue
            level: The severity level of the issue
            effect: The effects of the issue
            related_to: List of elements(Actions?) that this workflow relates to
            **kwargs: Additional attributes for the issue
            
        Returns:
            A new Workflow instance
        """
        # Prepare related_to_ids and related_to_types lists from related_to elements
        related_to_ids = []
        related_to_types = []

        if related_to:
            # Check if related_to is a tuple of (ids, types)
            if isinstance(related_to, tuple) and len(related_to) == 2:
                related_to_ids = related_to[0]
                related_to_types = related_to[1]
            # Otherwise process as a list of composite elements
            elif isinstance(related_to, list):
                for element in related_to:
                    # Get the element_id from the element
                    related_to_ids.append(element.element_id)

                    # Get the type name from the element's data object
                    data_type = type(element._data_object)
                    type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(data_type)
                    related_to_types.append(type_name)
            else:
                raise TypeError("related_to must be either a list of ElementComposite objects or a tuple of (ids, types) lists")

        root_id = None
        if root is not None:
            if isinstance(root, ElementComposite):
                root_id = root.element_id
            elif isinstance(root, str):
                root_id = root
            else:
                raise TypeError("root must be either an Element object or a string ID")

        # Create issue data
        workflow_data = WorkflowData(
            element_id=element_id,
            root_id=root_id,
            plugin_metadata_id=plugin_metadata_id,
            name=name,
            description=description,
            owner_id=owner_id,
            type=object_type,
            control_flow_ids=control_flow_ids,
            related_to_ids=related_to_ids or [],
            related_to_types=related_to_types or [],
            **kwargs
        )

        # Create issue instance
        workflow = cls(data_manager, workflow_data,_token=_CREATION_TOKEN)

        # Store the issue
        await data_manager.store(workflow)

        # Return the issue
        return workflow





class BaseWorkflow(RelatableElement):
    """
    Builder class for Issue logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable Issue logical object.
    """
    model_config = {"arbitrary_types_allowed": True}

    # ---Additional platform fields
    plugin_metadata_id: str | None = Field(
        description='The identifier of the analytics which created this object', default=None
    )

        # --- Fields from TraceGroup ---
    owner_id: str = Field(description="The ID of the owner action")
    type: str = Field(default="WorkflowData", description="Workflow element")
    control_flow_ids: list[str] = Field(description="List of control flow IDs associated with the workflow", default_factory=list)

    # --- Relationship fields ---
    related_to: list[ElementComposite] | tuple[list[str], list[str]] = Field(default_factory=list)
    root: ElementComposite | str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseWorkflow':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseWorkflow':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> WorkflowComposite:
        """
        Build the Issue logical object.
        
        Args:
            data_manager: The data manager to use for creating the Issue
            
        Returns:
            The created Issue logical object
        """
        # Validate required fields
        if not self.name:
            raise ValueError("Issue name must be set before building")
        if not self.description:
            raise ValueError("Issue description must be set before building")

        # Create the issue
        return await WorkflowComposite.create(
            data_manager=data_manager,
            element_id=self.element_id,
            root=self.root,
            plugin_metadata_id=self.plugin_metadata_id,
            name=self.name,
            description=self.description,
            owner_id=self.owner_id,
            object_type=self.type,
            control_flow_ids=self.control_flow_ids,
            related_to=self.related_to,
            tags=self.tags,
            **self.attributes
        )


    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_workflows: list['BaseWorkflow']) -> list[WorkflowComposite]:
        """
        Efficiently store multiple BaseIssue objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            builders: List of BaseIssue objects to store
            
        Returns:
            List of created IssueComposite objects
        """
        # Validate all builders before proceeding
        for base_workflow in base_workflows:
            if not base_workflow.name:
                raise ValueError(f"Issue name must be set before building (id: {base_workflow.element_id})")
            if not base_workflow.description:
                raise ValueError(f"Issue description must be set before building (id: {base_workflow.element_id})")


        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_workflow in base_workflows:
            # Create issue data
            related_to_ids = []
            related_to_types = []

            if base_workflow.related_to:
                # Check if related_to is a tuple of (ids, types)
                if isinstance(base_workflow.related_to, tuple) and len(base_workflow.related_to) == 2:
                    related_to_ids = base_workflow.related_to[0]
                    related_to_types = base_workflow.related_to[1]
                # Otherwise process as a list of composite elements
                elif isinstance(base_workflow.related_to, list):
                    for elem in base_workflow.related_to:
                        related_to_ids.append(elem.element_id)
                        type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(type(elem._data_object))
                        related_to_types.append(type_name)
                else:
                    raise TypeError("related_to must be either a list of ElementComposite objects or a tuple of (ids, types) lists")

            workflow_data = WorkflowData(
                element_id=base_workflow.element_id,
                root_id=base_workflow.root.element_id if isinstance(base_workflow.root, ElementComposite) else base_workflow.root,
                plugin_metadata_id=base_workflow.plugin_metadata_id,
                name=base_workflow.name,
                description=base_workflow.description,
                type=base_workflow.type,
                owner_id=base_workflow.owner_id,
                control_flow_ids=base_workflow.control_flow_ids,
                related_to_ids=related_to_ids,
                related_to_types=related_to_types,
                tags=base_workflow.tags or [],
                attributes=base_workflow.attributes or {},

            )

            # Create issue instance without storing it
            composite = WorkflowComposite(data_manager, workflow_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects
