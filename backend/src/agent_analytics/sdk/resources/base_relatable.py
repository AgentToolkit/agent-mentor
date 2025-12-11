"""
Base resource class for RelatableElement operations in the AgentOps SDK

Provides generalized create/list methods that work for all RelatableElement types
(Metrics, Issues, Workflows, Recommendations, Annotations).
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from agent_analytics.core.data_composite.element import ElementComposite
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.runtime.storage.logical_data_manager import AnalyticsDataManager
from agent_analytics.runtime.storage.store_interface import QueryFilter, QueryOperator

# Type variables for composite and wrapper types
CompositeT = TypeVar("CompositeT", bound=RelatableElementComposite)
WrapperT = TypeVar("WrapperT")


class RelatableElementsResource(Generic[CompositeT, WrapperT], ABC):
    """
    Base resource class for working with RelatableElement types.

    This class provides generalized CRUD operations for all RelatableElement types:
    - Create single or multiple elements
    - List elements by root owner
    - List elements by related element
    - Get specific element by ID

    Subclasses must implement abstract methods to specify:
    - The composite class type
    - The SDK wrapper class type
    - How to convert composite to wrapper
    """

    def __init__(self, data_manager: AnalyticsDataManager):
        """
        Initialize the resource.

        Args:
            data_manager: The data manager instance
        """
        self._data_manager = data_manager

    @abstractmethod
    def _get_composite_class(self) -> type[CompositeT]:
        """
        Get the composite class for this resource.

        Returns:
            The RelatableElementComposite subclass (e.g., MetricComposite)
        """
        pass

    @abstractmethod
    def _get_builder_class(self) -> type:
        """
        Get the builder class for this resource.

        Returns:
            The builder class (e.g., BaseNumericMetric, BaseIssue)
        """
        pass

    @abstractmethod
    def _to_sdk_model(self, composite: CompositeT, **kwargs) -> WrapperT:
        """
        Convert internal composite to SDK wrapper model.

        Args:
            composite: Internal composite object
            **kwargs: Additional parameters needed for wrapper construction

        Returns:
            SDK wrapper model
        """
        pass

    @abstractmethod
    def _create_builder(self, **kwargs) -> Any:
        """
        Create a builder instance for this element type.

        Args:
            **kwargs: Parameters for building the element

        Returns:
            Builder instance
        """
        pass

    @abstractmethod
    def _validate_create_params(self, **kwargs):
        """
        Validate parameters for element creation.

        Args:
            **kwargs: Parameters to validate

        Raises:
            ValueError: If validation fails
        """
        pass

    def _prepare_root(self, root: ElementComposite | str | None) -> ElementComposite | str | None:
        """
        Prepare root parameter - can be Element wrapper or Element composite or string ID.

        Args:
            root: Root element (wrapper, composite, or ID string)

        Returns:
            ElementComposite or string ID suitable for builder
        """
        if root is None:
            return None

        # If it's an SDK wrapper, extract the composite
        if hasattr(root, "_composite"):
            return root._composite

        # Otherwise it's already a composite or string ID
        return root

    def _prepare_related_to(
        self, related_to: list[Any] | None
    ) -> list[ElementComposite] | tuple[list[str], list[str]] | None:
        """
        Prepare related_to parameter - can be list of Element wrappers/composites or tuple.

        Args:
            related_to: List of related elements (wrappers or composites) or tuple of (ids, types)

        Returns:
            List of ElementComposite objects or tuple of (ids, types) suitable for builder
        """
        if related_to is None or len(related_to) == 0:
            return None

        # If it's already a tuple of (ids, types), return as-is
        if isinstance(related_to, tuple) and len(related_to) == 2:
            return related_to

        # Convert list of wrappers/composites to list of composites
        composites = []
        for elem in related_to:
            if hasattr(elem, "_composite"):
                # It's an SDK wrapper - extract composite
                composites.append(elem._composite)
            elif isinstance(elem, ElementComposite):
                # It's already a composite
                composites.append(elem)
            elif isinstance(elem, str):
                # It's a string ID - we need to create tuple format
                # Collect all IDs and types
                ids = []
                types = []
                for e in related_to:
                    if isinstance(e, str):
                        ids.append(e)
                        # For string IDs, we can't determine type - caller must provide tuple format
                        raise TypeError(
                            "When providing string IDs in related_to, use tuple format: "
                            "([id1, id2], [type1, type2])"
                        )
                return (ids, types)
            else:
                raise TypeError(
                    f"related_to must contain Element objects or be a tuple of (ids, types), "
                    f"got {type(elem)}"
                )

        return composites

    async def create(
        self,
        owner: Any,  # Trace|TraceGroup|Element (wrapper or composite)
        name: str,
        description: str | None = None,
        related_to: list[Any] | tuple[list[str], list[str]] | None = None,
        tags: list[str] | None = None,
        plugin_id: str | None = None,
        **kwargs
    ) -> WrapperT:
        """
        Create a new relatable element.

        Args:
            owner: Owner element this belongs to (Trace, TraceGroup, or any Element).
                   Can be an SDK wrapper or composite object.
            name: Display name for the element
            description: Description of the element
            related_to: Optional list of elements this relates to (wrappers or composites)
                       or tuple of ([ids], [types])
            tags: List of tags for categorization
            plugin_id: Optional identifier of the plugin that created this element
            **kwargs: Additional type-specific parameters

        Returns:
            The created element as SDK wrapper

        Example:
            # Create with Trace owner and Span related_to
            element = await client.metrics.create(
                owner=trace,
                name="quality_score",
                description="Quality score",
                related_to=[span1, span2],
                value=0.95
            )

            # Create with TraceGroup owner
            issue = await client.issues.create(
                owner=trace_group,
                name="High latency",
                description="System is slow",
                related_to=[task1]
            )
        """
        # Validate type-specific parameters
        self._validate_create_params(name=name, description=description, **kwargs)

        # Prepare root and related_to (internal code still uses "root")
        prepared_root = self._prepare_root(owner)
        prepared_related_to = self._prepare_related_to(related_to)

        # Create builder
        builder = self._create_builder(
            name=name,
            description=description,
            tags=tags or [],
            plugin_metadata_id=plugin_id,
            **kwargs
        )

        # Set root and related_to (internal code still uses "root")
        builder.root = prepared_root
        if prepared_related_to is not None:
            builder.related_to = prepared_related_to

        # Store the element
        composite = await builder.store(self._data_manager)

        # Convert to SDK model with appropriate parameters
        return self._to_sdk_model(composite, root=owner, related_to=related_to, **kwargs)

    async def create_many(
        self,
        owner: Any,  # Trace|TraceGroup|Element
        elements: list[dict[str, Any]]
    ) -> list[WrapperT]:
        """
        Create multiple elements at once for better performance.

        Args:
            owner: Owner element these elements belong to (wrapper or composite)
            elements: List of element definitions, each containing:
                     - name: str (required)
                     - description: str (optional)
                     - related_to: list[Element] or tuple[list[str], list[str]] (optional)
                     - tags: list[str] (optional)
                     - plugin_id: str (optional)
                     - **kwargs: Type-specific parameters

        Returns:
            List of created elements as SDK wrappers

        Example:
            elements = await client.metrics.create_many(
                owner=trace,
                elements=[
                    {"name": "metric1", "value": 0.95},
                    {"name": "metric2", "value": "SUCCESS"}
                ]
            )
        """
        # Prepare root once (internal code still uses "root")
        prepared_root = self._prepare_root(owner)

        # Build all builders
        builders = []
        element_params = []  # Store params for later wrapper conversion

        for elem_def in elements:
            name = elem_def.get("name")
            description = elem_def.get("description")
            related_to = elem_def.get("related_to")
            tags = elem_def.get("tags", [])
            plugin_id = elem_def.get("plugin_id")

            # Extract type-specific kwargs
            type_specific = {k: v for k, v in elem_def.items()
                           if k not in ["name", "description", "related_to", "tags", "plugin_id"]}

            # Validate
            self._validate_create_params(name=name, description=description, **type_specific)

            # Prepare related_to
            prepared_related_to = self._prepare_related_to(related_to)

            # Create builder
            builder = self._create_builder(
                name=name,
                description=description,
                tags=tags,
                plugin_metadata_id=plugin_id,
                **type_specific
            )

            builder.root = prepared_root
            if prepared_related_to is not None:
                builder.related_to = prepared_related_to

            builders.append(builder)
            element_params.append({"related_to": related_to, **type_specific})

        # Bulk store
        builder_class = self._get_builder_class()
        composites = await builder_class.bulk_store(
            data_manager=self._data_manager,
            **{self._get_bulk_store_param_name(): builders}
        )

        # Convert to SDK models
        return [
            self._to_sdk_model(comp, root=owner, **params)
            for comp, params in zip(composites, element_params, strict=False)
        ]

    def _get_bulk_store_param_name(self) -> str:
        """
        Get the parameter name for bulk_store method.

        Returns:
            Parameter name (e.g., 'base_metrics', 'base_issues')
        """
        builder_class_name = self._get_builder_class().__name__
        # Convert BaseNumericMetric -> base_metrics
        # Remove 'Base' prefix and convert to snake_case plural
        name = builder_class_name.replace("Base", "").lower() + "s"
        return f"base_{name}"

    async def fetch_by_owner(self, owner: Any, names: list[str] | None = None) -> list[WrapperT]:
        """
        Get all elements owned by a specific owner element.

        Args:
            owner: The owner element (wrapper, composite, or ID string)
            names: Optional list of names to filter by

        Returns:
            List of element wrappers

        Example:
            # Get all metrics for a trace
            metrics = await client.metrics.fetch_by_owner(trace)

            # Get all issues for a trace group
            issues = await client.issues.fetch_by_owner(trace_group)

            # Filter by names
            metrics = await client.metrics.fetch_by_owner(trace, names=["metric1", "metric2"])
        """
        # Extract ID from owner (internal code still uses "root")
        if hasattr(owner, "id"):
            root_id = owner.id
        elif hasattr(owner, "element_id"):
            root_id = owner.element_id
        elif isinstance(owner, str):
            root_id = owner
        else:
            raise TypeError("owner must be an Element object or string ID")

        # Query elements by root_id (internal code still uses "root_id")
        composite_class = self._get_composite_class()
        query = {"root_id": QueryFilter(operator=QueryOperator.EQUAL, value=root_id)}

        # Add names filter if provided
        if names:
            query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

        composites = await self._data_manager.search(
            element_type=composite_class,
            query=query
        )

        # Convert to SDK models
        return [self._to_sdk_model(comp, root=owner) for comp in composites]

    async def fetch_by_related(self, element: Any, names: list[str] | None = None) -> list[WrapperT]:
        """
        Get all elements related to a specific element.

        Args:
            element: The element to find relations for (wrapper, composite, or ID string)
            names: Optional list of names to filter by

        Returns:
            List of element wrappers

        Example:
            # Get all metrics related to a span
            metrics = await client.metrics.fetch_by_related(span)

            # Get all issues related to a task
            issues = await client.issues.fetch_by_related(task)

            # Filter by names
            metrics = await client.metrics.fetch_by_related(span, names=["metric1", "metric2"])
        """
        # Extract ID from element
        if hasattr(element, "id"):
            element_id = element.id
        elif hasattr(element, "element_id"):
            element_id = element.element_id
        elif isinstance(element, str):
            element_id = element
        else:
            raise TypeError("element must be an Element object or string ID")

        # Query elements by searching for element_id in related_to_ids array
        composite_class = self._get_composite_class()
        query = {"related_to_ids": QueryFilter(operator=QueryOperator.ARRAY_CONTAINS, value=element_id)}

        # Add names filter if provided
        if names:
            query["name"] = QueryFilter(operator=QueryOperator.EQUALS_MANY, value=names)

        composites = await self._data_manager.search(
            element_type=composite_class,
            query=query
        )

        # Convert to SDK models
        return [self._to_sdk_model(comp, related_element=element) for comp in composites]

    async def get(self, element_id: str) -> WrapperT | None:
        """
        Get a specific element by ID.

        Args:
            element_id: The unique identifier of the element

        Returns:
            Element wrapper if found, None otherwise

        Example:
            metric = await client.metrics.get("metric-123")
        """
        composite_class = self._get_composite_class()
        composite = await composite_class.get_by_id(
            data_manager=self._data_manager,
            id=element_id
        )

        if composite is None:
            return None

        return self._to_sdk_model(composite)

    async def delete(self, element_id: str) -> bool:
        """
        Delete an element by its ID.

        Args:
            element_id: The unique identifier of the element to delete
        
        Returns:
            True if deleted successfully, False if element not found
        
        Example:
            success = await client.metrics.delete("metric-123")
        """
        composite_class = self._get_composite_class()
        data_class = self._data_manager._get_data_class_for_element(composite_class)

        return await self._data_manager._persistent_manager.delete(
            element_id=element_id,
            artifact_type=data_class
        )

    async def delete_by_root_id(self, root_id: str) -> int:
        """
        Delete all elements with the given root_id.
        
        Args:
            root_id: The root_id (trace_id) to delete elements for
        
        Returns:
            Number of elements deleted
        
        Example:
            count = await client.metrics.delete_by_root_id("trace-123")
        """
        # Get all elements with this root_id
        composite_class = self._get_composite_class()
        query = {"root_id": QueryFilter(operator=QueryOperator.EQUAL, value=root_id)}

        composites = await self._data_manager.search(
            element_type=composite_class,
            query=query
        )

        # Delete each element
        deleted_count = 0
        data_class = self._data_manager._get_data_class_for_element(composite_class)

        for composite in composites:
            try:
                await self._data_manager._persistent_manager.delete(
                    element_id=composite.element_id,
                    artifact_type=data_class
                )
                deleted_count += 1
            except Exception:
                # Log but continue deleting other elements
                pass

        return deleted_count