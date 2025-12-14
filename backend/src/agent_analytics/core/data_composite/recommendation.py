import json
from typing import Any, ClassVar

from agent_analytics_common.interfaces.recommendations import (
    Recommendation,
    RecommendationLevel,
)
from pydantic import Field

from agent_analytics.core.data.recommendation_data import RecommendationData
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils


class RecommendationComposite(RelatableElementComposite[RecommendationData]):
    """Composite representation of a Recommendation with related elements"""
    # Specify the corresponding data class
    data_class: ClassVar[type[RecommendationData]] = RecommendationData

    def __init__(self, data_manager: "DataManager", recommendation_data: RecommendationData, *, _token: object = None):
        super().__init__(data_manager, recommendation_data, _token=_token)


    @property
    def effect(self) -> list[str]:
        return self._data_object.effect

    @property
    def level(self) -> RecommendationLevel:
        return self._data_object.level

    @property
    def timestamp(self) -> str | None:
        return self._data_object.timestamp

    @classmethod
    async def create(cls,
                    data_manager: "DataManager",
                    element_id: str,
                    root: ElementComposite | str | None,
                    name: str,
                    description: str,
                    level: RecommendationLevel = RecommendationLevel.MODERATE,
                    effect: list[str] = None,
                    plugin_metadata_id: str | None = None,
                    related_to: list[ElementComposite] | tuple[list[str], list[str]] = None,
                    **kwargs) -> 'RecommendationComposite':
        """
        Factory method to create a new Recommendation
        
        Args:
            data_manager: The data manager to use for storage operations
            element_id: The unique identifier for the recommendation
            root: The root element this recommendation belongs to
            name: The name of the recommendation
            description: A description of the recommendation
            level: The impact level of the recommendation           
            effect: The effects of the recommendation
            plugin_metadata_id: ID of the plugin that created this recommendation
            related_to: List of elements that this recommendation relates to
            **kwargs: Additional attributes for the recommendation
            
        Returns:
            A new RecommendationComposite instance
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

        # Create recommendation data
        recommendation_data = RecommendationData(
            element_id=element_id,
            root_id=root_id,
            plugin_metadata_id=plugin_metadata_id,
            name=name,
            description=description,
            level=level,
            effect=effect or [],
            related_to_ids=related_to_ids or [],
            related_to_types=related_to_types or [],
            **kwargs
        )

        # Create recommendation instance
        recommendation = cls(data_manager, recommendation_data, _token=_CREATION_TOKEN)

        # Store the recommendation
        await data_manager.store(recommendation)

        # Return the recommendation
        return recommendation


# base_recommendation.py
from typing import ClassVar

from agent_analytics_common.interfaces.recommendations import (
    RecommendationLevel,
)

from agent_analytics.core.data.recommendation_data import RecommendationData
from agent_analytics.core.data_composite.element import ElementComposite


class BaseRecommendation(Recommendation):
    """
    Builder class for Recommendation logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable Recommendation logical object.
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
        # Call the generate_id_prefix on the Recommendation class directly
        prefix = Recommendation.generate_class_name()  # This will return "Recommendation"
        return prefix

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'BaseRecommendation':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseRecommendation':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    async def store(self, data_manager: "DataManager") -> 'RecommendationComposite':
        """
        Build the Recommendation logical object.
        
        Args:
            data_manager: The data manager to use for creating the Recommendation
            
        Returns:
            The created RecommendationComposite logical object
        """
        # Import here to avoid circular imports
        from agent_analytics.core.data_composite.recommendation import RecommendationComposite

        # Validate required fields
        if not self.name:
            raise ValueError("Recommendation name must be set before building")
        if not self.description:
            raise ValueError("Recommendation description must be set before building")

        # Create the recommendation
        return await RecommendationComposite.create(
            data_manager=data_manager,
            element_id=self.element_id,
            root=self.root,
            plugin_metadata_id=self.plugin_metadata_id,
            name=self.name,
            description=self.description,
            level=self.level,
            effect=self.effect,
            related_to=self.related_to,
            tags=self.tags,
            **self.attributes
        )

    @classmethod
    async def bulk_store(cls, data_manager: "DataManager", base_recommendations: list['BaseRecommendation']) -> list['RecommendationComposite']:
        """
        Efficiently store multiple BaseRecommendation objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            base_recommendations: List of BaseRecommendation objects to store
            
        Returns:
            List of created RecommendationComposite objects
        """
        # Import here to avoid circular imports
        from agent_analytics.core.data_composite.recommendation import RecommendationComposite

        # Validate all builders before proceeding
        for base_recommendation in base_recommendations:
            if not base_recommendation.name:
                raise ValueError(f"Recommendation name must be set before building (id: {base_recommendation.element_id})")
            if not base_recommendation.description:
                raise ValueError(f"Recommendation description must be set before building (id: {base_recommendation.element_id})")

        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_recommendation in base_recommendations:
            # Create recommendation data
            related_to_ids = []
            related_to_types = []

            if base_recommendation.related_to:
                # Check if related_to is a tuple of (ids, types)
                if isinstance(base_recommendation.related_to, tuple) and len(base_recommendation.related_to) == 2:
                    related_to_ids = base_recommendation.related_to[0]
                    related_to_types = base_recommendation.related_to[1]
                # Otherwise process as a list of composite elements
                elif isinstance(base_recommendation.related_to, list):
                    for elem in base_recommendation.related_to:
                        related_to_ids.append(elem.element_id)
                        type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(type(elem._data_object))
                        related_to_types.append(type_name)
                else:
                    raise TypeError("related_to must be either a list of ElementComposite objects or a tuple of (ids, types) lists")

            recommendation_data = RecommendationData(
                element_id=base_recommendation.element_id,
                root_id=base_recommendation.root.element_id if isinstance(base_recommendation.root, ElementComposite) else base_recommendation.root,
                plugin_metadata_id=base_recommendation.plugin_metadata_id,
                name=base_recommendation.name,
                description=base_recommendation.description,
                level=base_recommendation.level,
                effect=base_recommendation.effect or [],
                related_to_ids=related_to_ids,
                related_to_types=related_to_types,
                tags=base_recommendation.tags or [],
                attributes=base_recommendation.attributes or {},
            )

            # Create recommendation instance without storing it
            composite = RecommendationComposite(data_manager, recommendation_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)

        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)

        # Return the created composite objects
        return composite_objects
