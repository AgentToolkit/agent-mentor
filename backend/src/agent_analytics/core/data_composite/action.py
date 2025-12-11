
import json
from typing import Any, ClassVar

from ibm_agent_analytics_common.interfaces.action import Action
from pydantic import Field

from agent_analytics.core.data.action_data import ActionData
from agent_analytics.core.data.element_data import ElementData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.workflow import WorkflowComposite


class ActionComposite(ElementComposite[ActionData]):
    """Composite representation of a Action"""
    # Specify the corresponding data class
    data_class: ClassVar[type[ElementData]] = ActionData

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
        Get a workflow related to this action
        
        Returns:
            List of metrics related to this task
        """
        # Use the data manager to retrieve elements related to this task
        related_elements = await self._data_manager.get_elements_related_to_artifact_and_type(self,WorkflowComposite)
        #TODO is the correct assumption there is just one workflow per action?
        return related_elements[0] if related_elements else None

    def __init__(self, data_manager: "DataManager", action_data: ActionData,*, _token: object = None):
        super().__init__(data_manager, action_data ,_token=_token)


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
                    consumed_resources: list[str] | None=None) -> 'ActionComposite':
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
        action_data = ActionData(
            element_id=element_id,
            root_id=root_id,
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            code_id=code_id,
            is_generated=is_generated,
            consumed_resources=consumed_resources or []
        )

        # Create action instance
        action = cls(data_manager, action_data,_token=_CREATION_TOKEN)

        # Store the issue
        await data_manager.store(action)

        # Return the issue
        return action





class BaseAction(Action):
    """
    Builder class for Action logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable Action logical object.
    """
    model_config = {"arbitrary_types_allowed": True}

    # --- Basic Action fields ---
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
        # Call the generate_id_prefix on the Action class directly
        prefix = Action.generate_class_name()  # This will return "Action"
        return prefix

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseAction':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseAction':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> ActionComposite:
        """
        Build the Action logical object.
        
        Args:
            data_manager: The data manager to use for creating the Action
            
        Returns:
            The created Action logical object
        """
        # Validate required fields
        if not self.name:
            raise ValueError("Action name must be set before building")
        if not self.description:
            raise ValueError("Action description must be set before building")

        # Create the Action
        return await ActionComposite.create(
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
    async def bulk_store(cls, data_manager: "DataManager", base_actions: list['BaseAction']) -> list[ActionComposite]:
        """
        Efficiently store multiple BaseAction objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            base_actions: List of BaseAction objects to store
            
        Returns:
            List of created ActionComposite objects
        """
        # Validate all builders before proceeding
        for base_action in base_actions:
            if not base_action.name:
                raise ValueError(f"Action name must be set before building (id: {base_action.element_id})")
            if not base_action.description:
                raise ValueError(f"Action description must be set before building (id: {base_action.element_id})")

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_action in base_actions:
            # Process root information
            root_id = None
            if base_action.root is not None:
                if isinstance(base_action.root, ElementComposite):
                    root_id = base_action.root.element_id
                elif isinstance(base_action.root, str):
                    root_id = base_action.root
                else:
                    raise TypeError("root must be either an Element object or a string ID")

            # Create action data
            action_data = ActionData(
                element_id=base_action.element_id,
                root_id=root_id,
                name=base_action.name,
                description=base_action.description,
                input_schema=base_action.input_schema,
                output_schema=base_action.output_schema,
                code_id=base_action.code_id,
                is_generated=base_action.is_generated,
                consumed_resources=base_action.consumed_resources or [],
                tags=base_action.tags or [],
                attributes=base_action.attributes or {}
            )

            # Create action instance without storing it
            composite = ActionComposite(data_manager, action_data, _token=_CREATION_TOKEN)
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
