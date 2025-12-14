
import json
from typing import Any, ClassVar

from agent_analytics_common.interfaces.runnable import Runnable
from pydantic import Field

from agent_analytics.core.data.element_data import ElementData
from agent_analytics.core.data.runnable_data import RunnableData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.workflow import WorkflowComposite


class RunnableComposite(ElementComposite[RunnableData]):
    """Composite representation of a Runnable"""
    # Specify the corresponding data class
    data_class: ClassVar[type[ElementData]] = RunnableData

    @property
    def input_schema(self) -> str | None:
        return self._data_object.input_schema

    @property
    def output_schema(self) -> str | None:
        return self._data_object.output_schema
    @property
    def code_id(self) -> str | None:
        return self._data_object.code_id
    @property
    def is_generated(self)-> bool:
        return self._data_object.is_generated

    @property
    def consumed_resources(self)->list[str] | None:
        return self._data_object.consumed_resources

    @property
    async def workflow(self) -> WorkflowComposite:
        """
        Get a workflow related to this runnable
        
        Returns:
            List of metrics related to this task
        """
        # Use the data manager to retrieve elements related to this task
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self,WorkflowComposite)
        #TODO is the correct assumption there is just one workflow per runnable?
        return related_elements[0] if related_elements else None

    def __init__(self, data_manager: "DataManager", runnable_data: RunnableData,*, _token: object = None):
        super().__init__(data_manager, runnable_data ,_token=_token)


    @classmethod
    async def create(cls,
                    data_manager: "DataManager",
                    element_id: str,
                    root: ElementComposite | str | None,
                    name: str,
                    description: str,
                    input_schema: str | None = None,
                    output_schema: str | None = None,
                    code_id:str | None = None,
                    is_generated: bool = False,
                    tags: list[str] | None = None,
                    consumed_resources: list[str] | None=None) -> 'RunnableComposite':
        """
        Factory method to create a new Issue
        
        Args:
            data_manager: The data manager to use for storage operations
            element_id: The unique identifier for the issue
            name: The name of the issue
            description: A description of the issue
            level: The severity level of the issue
            effect: The effects of the issue
            related_to: List of elements that this issue relates to
            **kwargs: Additional attributes for the issue
            
        Returns:
            A new Issue instance
        """
        # Prepare related_to_ids and related_to_types lists from related_to elements

        root_id = None
        if root is not None:
            if isinstance(root, ElementComposite):
                root_id = root.element_id
            elif isinstance(root, str):
                root_id = root
            else:
                raise TypeError("root must be either an Element object or a string ID")

        # Create issue data
        runnable_data = RunnableData(
            element_id=element_id,
            root_id=root_id,
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            code_id=code_id,
            is_generated=is_generated,
            tags=tags or [],
            consumed_resources=consumed_resources or []
        )

        # Create runnable instance
        runnable = cls(data_manager, runnable_data,_token=_CREATION_TOKEN)

        # Store the issue
        await data_manager.store(runnable)

        # Return the issue
        return runnable





class BaseRunnable(Runnable):
    """
    Builder class for Runnable logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable Runnable logical object.
    """
    model_config = {"arbitrary_types_allowed": True}

    # --- Basic runnable fields ---
    input_schema: str | None = None
    output_schema: str | None = None
    code_id: str | None = None
    is_generated: bool = False
    consumed_resources: list[str] = Field(default_factory=list)

    # --- Relationship fields ---
    root: ElementComposite | str | None = None




    # --- Helper fields for building ---

    def generate_id_prefix(self) -> str:
        """Override to use the parent interface class name."""
        # Call the generate_id_prefix on the Runnable class directly
        prefix = Runnable.generate_class_name()  # This will return "Runnable"
        return prefix

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseRunnable':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseRunnable':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> RunnableComposite:
        """
        Build the Runnable logical object.
        
        Args:
            data_manager: The data manager to use for creating the Runnable
            
        Returns:
            The created Runnable logical object
        """
        # Validate required fields
        if not self.name:
            raise ValueError("Runnable name must be set before building")
        if not self.description:
            raise ValueError("Runnable description must be set before building")

        # Create the runnable
        return await RunnableComposite.create(
            data_manager=data_manager,
            element_id=self.element_id,
            root=self.root,
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            code_id=self.code_id,
            is_generated=self.is_generated,
            consumed_resources=self.consumed_resources,
            tags=self.tags,
            **self.attributes
        )

    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_runnables: list['BaseRunnable']) -> list[RunnableComposite]:
        """
        Efficiently store multiple BaseRunnable objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            base_runnables: List of BaseRunnable objects to store
            
        Returns:
            List of created RunnableComposite objects
        """
        # Validate all builders before proceeding
        for base_runnable in base_runnables:
            if not base_runnable.name:
                raise ValueError(f"Runnable name must be set before building (id: {base_runnable.element_id})")
            if not base_runnable.description:
                raise ValueError(f"Runnable description must be set before building (id: {base_runnable.element_id})")

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_runnable in base_runnables:
            # Process root information
            root_id = None
            if base_runnable.root is not None:
                if isinstance(base_runnable.root, ElementComposite):
                    root_id = base_runnable.root.element_id
                elif isinstance(base_runnable.root, str):
                    root_id = base_runnable.root
                else:
                    raise TypeError("root must be either an Element object or a string ID")

            # Create runnable data
            runnable_data = RunnableData(
                element_id=base_runnable.element_id,
                root_id=root_id,
                name=base_runnable.name,
                description=base_runnable.description,
                input_schema=base_runnable.input_schema,
                output_schema=base_runnable.output_schema,
                code_id=base_runnable.code_id,
                is_generated=base_runnable.is_generated,
                consumed_resources=base_runnable.consumed_resources or [],
                tags=base_runnable.tags or [],
                attributes=base_runnable.attributes or {}
            )

            # Create runnable instance without storing it
            composite = RunnableComposite(data_manager, runnable_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects

    def __hash__(self):
        """
        Return hash value based on code_id.
        Objects with the same code_id will have the same hash.
        """
        return hash(self.code_id)

    def __eq__(self, other):
        """
        Check equality based on code_id.
        Two objects are equal if they have the same code_id.
        """
        if not isinstance(other, self.__class__):
            return False
        return self.code_id == other.code_id
