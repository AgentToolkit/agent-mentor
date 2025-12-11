#####################################################
# AnalyticsDataManager Implementation
#####################################################

import inspect
import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import (
    Any,
    TextIO,
    TypeVar,
)

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.element_data import ElementData
from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.element import _CREATION_TOKEN, ElementComposite
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils

from .data_object_manager import PersistentDataManager
from .store_config import StoreConfig
from .store_interface import StoreFactory

logger = logging.getLogger('analytics-data-manager')
logger.setLevel(logging.DEBUG)

# Type variable for Element subclasses
T = TypeVar('T', bound=ElementComposite)

# Type variable for ElementData subclasses
E = TypeVar('E', bound=ElementData)


class AnalyticsDataManager(DataManager[ElementComposite]):
    """
    Implementation of DataManager that works with logical composite objects
    
    This class wraps a PersistentDataManager and provides an abstraction layer
    that works with logical objects instead of raw data objects
    """

    def __init__(self, persistent_manager: PersistentDataManager):
        """Initialize the AnalyticsDataManager with a persistent data manager"""
        self._persistent_manager = persistent_manager

        # Create mapping from data classes to element classes
        self._data_class_to_element_factory: dict[
            type[ElementData],
            Callable[[ElementData], type[ElementComposite]]
        ] = {}

        # Initialize the mapping
        self._initialize_type_mappings()

    @classmethod
    async def create(
        cls,
        store_configs: tuple[StoreFactory, StoreConfig] | Mapping[tuple[type[E], ...], tuple[StoreFactory, StoreConfig]] | Mapping[tuple[tuple[type[E], ...], str], tuple[StoreFactory, StoreConfig]]
    ) -> 'AnalyticsDataManager':
        """Create a new AnalyticsDataManager instance."""
        # Create a persistent data manager with the provided store configuration
        persistent_manager = await PersistentDataManager.create(store_configs)

        # Create and return an analytics data manager that wraps the persistent data manager
        return cls(persistent_manager)

    def _get_data_class_for_element(self, element_type: type[T]) -> type[ElementData]:
        """Get the data class for an element type"""
        if hasattr(element_type, 'data_class'):
            return element_type.data_class

        data_class_name = f"{element_type.__name__}Data"
        module = inspect.getmodule(element_type)
        if module and hasattr(module, data_class_name):
            return getattr(module, data_class_name)

        raise ValueError(f"Could not find data class for element type {element_type.__name__}")

    def _initialize_type_mappings(self):
        """Initialize the mapping from data classes to element classes"""
        element_classes = TypeResolutionUtils.get_element_subclasses()

        for element_class in element_classes:
            if hasattr(element_class, 'data_class'):
                data_class = element_class.data_class
                self._data_class_to_element_factory[data_class] = (
                    element_class.get_element_class_for_data
                )
                logger.debug(
                    f"Registered mapping: {data_class.__name__} -> {element_class.__name__}"
                )

        logger.info(
            f"Initialized type mappings with {len(self._data_class_to_element_factory)} entries"
        )

    def _get_element_class_for_data_class(
        self,
        data_object: ElementData
    ) -> type[ElementComposite] | None:
        """Get the element class for a data object"""
        data_class = type(data_object)

        if data_class in self._data_class_to_element_factory:
            factory_method = self._data_class_to_element_factory[data_class]
            return factory_method(data_object)

        for registered_data_class, factory_method in self._data_class_to_element_factory.items():
            if issubclass(data_class, registered_data_class):
                self._data_class_to_element_factory[data_class] = factory_method
                return factory_method(data_object)

        return None

    async def store(self, element: ElementComposite) -> None:
        """
        Store an element's data object
        Tags are extracted from the data object by persistent manager
        """
        await self._persistent_manager.store(element._data_object)

    async def get_by_id(
        self,
        element_id: str,
        element_type: type[T],
        tag: str | None = None
    ) -> T | None:
        """
        Get an element by its ID and type
        
        Args:
            element_id: The ID of the element
            element_type: The type of the element
            tag: Optional tag to narrow down the store search
        """
        data_class = self._get_data_class_for_element(element_type)

        if not data_class.is_storable():
            return await element_type.get_by_id(self, element_id)

        data_object = await self._persistent_manager.get_by_id(
            element_id,
            data_class,
            tag=tag
        )

        if data_object is None:
            return None

        return element_type(self, data_object, _token=_CREATION_TOKEN)

    async def get_children(
        self,
        root_id: str,
        child_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Get all children of a specific type for a given parent
        
        Args:
            root_id: The parent ID
            child_type: The type of children
            tag: Optional tag to narrow down the store search
        """
        data_class = self._get_data_class_for_element(child_type)

        data_objects = await self._persistent_manager.get_children(
            root_id,
            data_class,
            tag=tag
        )

        return [
            child_type(self, data_object, _token=_CREATION_TOKEN)
            for data_object in data_objects
        ]

    async def get_children_for_list(
        self,
        root_ids: list[str],
        child_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Retrieves all children of a specific type for a list of parents
        
        Args:
            root_ids: List of parent IDs
            child_type: The type of children
            tag: Optional tag to narrow down the store search
        """
        data_class = self._get_data_class_for_element(child_type)

        data_objects = await self._persistent_manager.get_children_for_list(
            root_ids,
            data_class,
            tag=tag
        )

        return [
            child_type(self, data_object, _token=_CREATION_TOKEN)
            for data_object in data_objects
        ]

    async def get_all(
        self,
        element_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Get all elements of a specific type
        
        Args:
            element_type: The type of elements
            tag: Optional tag to narrow down the store search
        """
        data_class = self._get_data_class_for_element(element_type)

        data_objects = await self._persistent_manager.get_all(data_class, tag=tag)

        return [
            element_type(self, data_object, _token=_CREATION_TOKEN)
            for data_object in data_objects
        ]

    async def search(
        self,
        element_type: type[T],
        query: dict[str, Any],
        tag: str | None = None
    ) -> list[T]:
        """
        Search for elements of the specified type based on a query
        
        Args:
            element_type: The type of elements
            query: The search query
            tag: Optional tag to narrow down the store search
        """
        data_class = self._get_data_class_for_element(element_type)

        data_objects = await self._persistent_manager.search(
            data_class,
            query,
            tag=tag
        )

        return [
            element_type(self, data_object, _token=_CREATION_TOKEN)
            for data_object in data_objects
        ]

    async def bulk_store(
        self,
        elements: list[ElementComposite],
        ignore_duplicates: bool = False
    ) -> list[str]:
        """
        Store multiple elements
        Tags are extracted from the data objects by persistent manager
        """
        if not elements:
            return []

        data_objects = [element._data_object for element in elements]

        return await self._persistent_manager.bulk_store(
            data_objects,
            ignore_duplicates=ignore_duplicates
        )

    async def get_related_elements(
        self,
        element_id: str,
        artifact_type: type[RelatableElementComposite],
        tag: str | None = None
    ) -> list[ElementComposite]:
        """
        Get all elements related to a relatable element (by ID)
        
        Args:
            element_id: ID of the relatable element
            artifact_type: Type of the relatable element
            tag: Optional tag to narrow down the store search
        """
        object = await self.get_by_id(element_id, artifact_type, tag=tag)
        if object:
            return await self.get_related_elements_for_artifact(object)
        return []

    async def get_related_elements_for_artifact(
        self,
        element: RelatableElementComposite
    ) -> list[ElementComposite]:
        """
        Get all elements that a relatable element is related to
        Tags are extracted from the element's data object by persistent manager
        """
        related_data_objects = await self._persistent_manager.get_related_elements_for_artifact(
            element._data_object
        )

        if not related_data_objects:
            return []

        related_elements = []

        for data_object in related_data_objects:
            element_class = self._get_element_class_for_data_class(data_object)

            if element_class:
                related_element = element_class(self, data_object, _token=_CREATION_TOKEN)
                related_elements.append(related_element)
            else:
                logger.warning(
                    f"No registered element class for data class "
                    f"{data_object.__class__.__name__}"
                )

        return related_elements

    async def get_elements_related_to(
        self,
        element_id: str,
        artifact_type: type[ElementComposite],
        tag: str | None = None
    ) -> list[ElementComposite]:
        """
        Get all elements that are related to a specific element (by ID)
        
        Args:
            element_id: ID of the element
            artifact_type: Type of the element
            tag: Optional tag to narrow down the store search
        """
        object = await self.get_by_id(element_id, artifact_type, tag=tag)
        if object:
            return await self.get_elements_related_to_artifact(object)
        return []

    async def get_elements_related_to_artifact_and_type(
        self,
        element: ElementComposite,
        relatable_type: type[ElementComposite]
    ) -> list[ElementComposite]:
        """
        Get all elements of a specific type that are related to an artifact
        Tags are extracted from the element's data object by persistent manager
        """
        data_object_type = relatable_type.data_class
        related_data_objects = await self._persistent_manager.get_elements_related_to_artifact_and_type(
            element._data_object,
            data_object_type
        )

        if not related_data_objects:
            return []

        related_elements = []

        for data_object in related_data_objects:
            element_class = self._get_element_class_for_data_class(data_object)

            if element_class:
                related_element = element_class(self, data_object, _token=_CREATION_TOKEN)
                related_elements.append(related_element)
            else:
                logger.warning(
                    f"No registered element class for data class "
                    f"{data_object.__class__.__name__}"
                )

        return related_elements

    async def get_elements_related_to_artifact(
        self,
        element: ElementComposite
    ) -> list[ElementComposite]:
        """
        Get all elements that are related to a given element
        Tags are extracted from the element's data object by persistent manager
        """
        related_data_objects = await self._persistent_manager.get_elements_related_to_artifact(
            element._data_object
        )

        if not related_data_objects:
            return []

        related_elements = []

        for data_object in related_data_objects:
            element_class = self._get_element_class_for_data_class(data_object)

            if element_class:
                related_element = element_class(self, data_object, _token=_CREATION_TOKEN)
                related_elements.append(related_element)
            else:
                logger.warning(
                    f"No registered element class for data class "
                    f"{data_object.__class__.__name__}"
                )

        return related_elements

    # ==================== Trace-specific methods ====================

    async def store_trace_logs(
        self,
        source: str | TextIO
    ) -> tuple[list[ElementComposite], str | None]:
        """Parse and store trace logs"""
        trace_data_objects, validate_warning = await self._persistent_manager.store_trace_logs(
            source
        )

        return (
            [
                BaseTraceComposite(self, trace_data, _token=_CREATION_TOKEN)
                for trace_data in trace_data_objects
            ],
            validate_warning
        )

    async def get_traces(
        self,
        service_name: str,
        from_date: datetime,
        to_date: datetime | None,
        tag: str | None = None
    ) -> list[ElementComposite]:
        """
        Get all traces for the service name within the given date range
        
        Args:
            service_name: Name of the service
            from_date: Start of the time range
            to_date: End of the time range
            tag: Optional tag to narrow down which traces to retrieve
        """
        trace_data_objects = await self._persistent_manager.get_traces(
            service_name,
            from_date,
            to_date,
            tag=tag
        )

        return [
            BaseTraceComposite(self, trace_data, _token=_CREATION_TOKEN)
            for trace_data in trace_data_objects
        ]

    async def get_spans(
        self,
        trace_id: str,
        tag: str | None = None
    ) -> list[ElementComposite]:
        """
        Get all spans belonging to a specific trace
        
        Args:
            trace_id: ID of the trace
            tag: Optional tag to narrow down which spans to retrieve
        """
        span_data_objects = await self._persistent_manager.get_spans(
            trace_id,
            tag=tag
        )

        return [
            BaseSpanComposite(self, span_data, _token=_CREATION_TOKEN)
            for span_data in span_data_objects
        ]

    async def get_trace_groups(
        self,
        service_name: str,
        tag: str | None = None
    ) -> list[ElementComposite]:
        """
        Get all trace groups for the given service name
        
        Args:
            service_name: Name of the service
            tag: Optional tag to narrow down which trace groups to retrieve
        """
        trace_group_data_objects = await self._persistent_manager.get_trace_groups(
            service_name,
            tag=tag
        )

        return [
            TraceGroupComposite(self, trace_group_data, _token=_CREATION_TOKEN)
            for trace_group_data in trace_group_data_objects
        ]

    async def get_traces_for_trace_group(
        self,
        trace_group_id: str,
        tag: str | None = None
    ) -> list[ElementComposite]:
        """
        Get all traces for the given trace group
        
        Args:
            trace_group_id: ID of the trace group
            tag: Optional tag to narrow down which traces to retrieve
        """
        trace_data_objects = await self._persistent_manager.get_traces_for_trace_group(
            trace_group_id,
            tag=tag
        )

        return [
            BaseTraceComposite(self, trace_data, _token=_CREATION_TOKEN)
            for trace_data in trace_data_objects
        ]

    async def get_trace(
        self,
        trace_id: str,
        tag: str | None = None
    ) -> ElementComposite:
        """
        Return trace object for the given id
        
        Args:
            trace_id: ID of the trace
            tag: Optional tag to narrow down which spans to retrieve
        """
        trace_data = await self._persistent_manager.get_trace(trace_id, tag=tag)
        return BaseTraceComposite(self, trace_data, _token=_CREATION_TOKEN)

    async def delete(
        self,
        element_id: str,
        element_type: type[T],
        tag: str | None = None
    ) -> None:
        """
        Delete an element (currently not implemented)
        
        Args:
            element_id: ID of the element
            element_type: Type of the element
            tag: Optional tag to narrow down the store search
        """
        pass
