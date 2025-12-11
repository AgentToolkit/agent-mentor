import json
from typing import Any, ClassVar

from ibm_agent_analytics_common.interfaces.annotations import DataAnnotation
from pydantic import Field

from agent_analytics.core.data.annotation_data import AnnotationData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils


class AnnotationComposite(RelatableElementComposite[AnnotationData]):
    """Composite representation of a Task with related Metrics"""
    # Specify the corresponding data class
    data_class: ClassVar[type[AnnotationData]] = AnnotationData

    def __init__(self, data_manager: "DataManager", annotation_data: AnnotationData,*, _token: object = None):
        super().__init__(data_manager, annotation_data, _token=_token)


    @property
    def annotation_type(self) -> DataAnnotation.Type:
        return self._data_object.annotation_type

    @property
    def path_to_string(self) -> str | None:
        return self._data_object.path_to_string

    @property
    def segment_start(self) -> int:
        return self._data_object.segment_start

    @property
    def segment_end(self) -> int | None:
        return self._data_object.segment_end

    @property
    def annotation_title(self) -> str | None:
        return self._data_object.annotation_title

    @property
    def annotation_content(self) -> str | None:
        return self._data_object.annotation_content

    @classmethod
    async def create(cls,
                    data_manager: "DataManager",
                    element_id: str,
                    root: ElementComposite | str | None,
                    name: str,
                    description: str,
                    segment_start: int,
                    plugin_metadata_id: str | None=None,
                    annotation_type: DataAnnotation.Type = DataAnnotation.Type.RAW_TEXT,
                    path_to_string: str | None = None,
                    segment_end: int | None = None,
                    annotation_title: str | None = None,
                    annotation_content: str | None = None,
                    related_to: list[ElementComposite] | tuple[list[str], list[str]] = None,
                    **kwargs) -> 'AnnotationComposite':
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
        annotation_data = AnnotationData(
            element_id=element_id,
            root_id=root_id,
            plugin_metadata_id=plugin_metadata_id,
            name=name,
            description=description,
            annotation_type=annotation_type,
            path_to_string=path_to_string,
            segment_start=segment_start,
            segment_end=segment_end,
            annotation_title=annotation_title,
            annotation_content=annotation_content,
            related_to_ids=related_to_ids or [],
            related_to_types=related_to_types or [],
            **kwargs
        )

        # Create issue instance
        annotation = cls(data_manager, annotation_data,_token=_CREATION_TOKEN)

        # Store the issue
        await data_manager.store(annotation)

        # Return the issue
        return annotation





class BaseAnnotation(DataAnnotation):
    """
    Builder class for Annotation logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable Issue logical object.
    """
    model_config = {"arbitrary_types_allowed": True}
    # ---Additional platform fields
    plugin_metadata_id: str | None = Field(
        description='The identifier of the analytics which created this object', default=None
    )

    # --- Relationship fields ---
    related_to: list[ElementComposite] | tuple[list[str], list[str]] = Field(default_factory=list)
    root: ElementComposite | str | None = None

    # --- Helper fields for building ---
    def generate_id_prefix(self) -> str:
        """Override to use the parent interface class name."""
        # Call the generate_id_prefix on the Issue class directly
        prefix = DataAnnotation.generate_class_name()  # This will return "Issue"
        return prefix

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseAnnotation':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseAnnotation':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> AnnotationComposite:
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
        return await AnnotationComposite.create(
            data_manager=data_manager,
            element_id=self.element_id,
            root=self.root,
            name=self.name,
            plugin_metadata_id=self.plugin_metadata_id,
            description=self.description,
            annotation_type=self.annotation_type,
            path_to_string=self.path_to_string,
            segment_start=self.segment_start,
            segment_end=self.segment_end,
            annotation_title=self.annotation_title,
            annotation_content=self.annotation_content,
            related_to=self.related_to,
            tags=self.tags,
            **self.attributes
        )

    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_annotations: list['BaseAnnotation']) -> list[AnnotationComposite]:
        """
        Efficiently store multiple BaseAnnotation objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            base_annotations: List of BaseAnnotation objects to store
            
        Returns:
            List of created AnnotationComposite objects
        """
        # Validate all builders before proceeding
        for base_annotation in base_annotations:
            if not base_annotation.name:
                raise ValueError(f"Annotation name must be set before building (id: {base_annotation.element_id})")
            if not base_annotation.description:
                raise ValueError(f"Annotation description must be set before building (id: {base_annotation.element_id})")

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_annotation in base_annotations:
            related_to_ids = []
            related_to_types = []

            if base_annotation.related_to:
                # Check if related_to is a tuple of (ids, types)
                if isinstance(base_annotation.related_to, tuple) and len(base_annotation.related_to) == 2:
                    related_to_ids = base_annotation.related_to[0]
                    related_to_types = base_annotation.related_to[1]
                # Otherwise process as a list of composite elements
                elif isinstance(base_annotation.related_to, list):
                    for elem in base_annotation.related_to:
                        related_to_ids.append(elem.element_id)
                        type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(type(elem._data_object))
                        related_to_types.append(type_name)
                else:
                    raise TypeError("related_to must be either a list of ElementComposite objects or a tuple of (ids, types) lists")

            # Create annotation data
            annotation_data = AnnotationData(
                element_id=base_annotation.element_id,
                root_id=base_annotation.root.element_id if isinstance(base_annotation.root, ElementComposite) else base_annotation.root,
                plugin_metadata_id=base_annotation.plugin_metadata_id,
                name=base_annotation.name,
                description=base_annotation.description,
                annotation_type=base_annotation.annotation_type,
                path_to_string=base_annotation.path_to_string,
                segment_start=base_annotation.segment_start,
                segment_end=base_annotation.segment_end,
                annotation_title=base_annotation.annotation_title,
                annotation_content=base_annotation.annotation_content,
                related_to_ids=related_to_ids,
                related_to_types=related_to_types,
                tags=base_annotation.tags or [],
                attributes=base_annotation.attributes or {},
            )

            # Create annotation instance without storing it
            composite = AnnotationComposite(data_manager, annotation_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects
