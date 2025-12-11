import logging
from collections.abc import Mapping
from datetime import datetime
from typing import (
    TextIO,
    TypeVar,
    cast,
)

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.element_data import ElementData
from agent_analytics.core.data.relatable_element_data import RelatableElementData
from agent_analytics.core.data.span_data import BaseSpanData
from agent_analytics.core.data.trace_data import BaseTraceData
from agent_analytics.core.data.trace_group_data import TraceGroupData
from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils
from agent_analytics.runtime.utilities.file_loader import TraceLogParser, parse_trace_logs

from .store_config import StoreConfig
from .store_interface import BaseStore, QueryFilter, QueryOperator, StoreFactory

logger = logging.getLogger('data-object-manager')
logger.setLevel(logging.DEBUG)

E = TypeVar('E', bound=ElementData)

class PersistentDataManager(DataManager[ElementData]):
    """Implementation of DataManager that works with multiple store implementations"""

    def __init__(self):
        self._type_name_to_store: dict[str, BaseStore[ElementData]] = {}
        self._type_tag_to_store: dict[tuple[str, str], BaseStore[ElementData]] = {}
        self._default_store: BaseStore[ElementData] | None = None

    @classmethod
    async def create(
        cls,
        store_configs: (
            tuple[StoreFactory, StoreConfig]
            | Mapping[tuple[type[E], ...], tuple[StoreFactory, StoreConfig]]
            | Mapping[tuple[tuple[type[E], ...], str], tuple[StoreFactory, StoreConfig]]
        )
    ) -> 'PersistentDataManager':
        """
        Create a new PersistentDataManager instance.
        
        Args:
            store_configs: Can be one of:
                - Single (factory, config) tuple for all artifacts
                - Mapping of artifact type tuples to (factory, config) tuples
                - Mapping of ((artifact types,), tag) to (factory, config) tuples
            
        Examples:
            # Single store for all artifacts
            manager = await PersistentDataManager.create(
                store_configs=(mongo_factory, common_store_config)
            )
            
            # Multiple stores for different artifact types
            manager = await PersistentDataManager.create(
                store_configs={
                    (Flow, CustomFlow): (mongo_factory, flow_store_config),
                    (BaseSpan, ): (redis_factory, span_store_config)
                }
            )
            
            # Tag-specific stores
            manager = await PersistentDataManager.create(
                store_configs={
                    (MetricData,): (elasticsearch_factory, default_config),
                    ((MetricData,), "workflow"): (memory_factory, memory_config)
                }
            )
        """
        manager = cls()
        if isinstance(store_configs, tuple):
            # Single store for all artifacts
            factory, config = store_configs
            store = await factory.create_store(
                model_class=ElementData,
                config=config
            )
            manager._default_store = store
        else:
            # Multiple stores for different artifact types and/or tags
            if not store_configs:
                raise ValueError("store_configs mapping cannot be empty")

            for key, (factory, config) in store_configs.items():
                # Check if this is a tag-specific configuration
                if isinstance(key, tuple) and len(key) == 2 and isinstance(key[1], str):
                    # Format: ((Type1, Type2, ...), "tag")
                    artifact_types, tag = key

                    if not isinstance(artifact_types, tuple):
                        raise ValueError(
                            f"Invalid tag-specific config format. Expected ((Type,), 'tag'), got {key}"
                        )

                    for artifact_type in artifact_types:
                        store = await factory.create_store(
                            model_class=artifact_type,
                            config=config
                        )
                        store_key = (artifact_type.__name__, tag)
                        manager._type_tag_to_store[store_key] = store
                        logger.debug(
                            f"Registered tag-specific store: {artifact_type.__name__} with tag='{tag}'"
                        )
                else:
                    # Format: (Type1, Type2, ...)
                    artifact_types = key
                    for artifact_type in artifact_types:
                        store = await factory.create_store(
                            model_class=artifact_type,
                            config=config
                        )
                        manager._type_name_to_store[artifact_type.__name__] = store
                        logger.debug(f"Registered type-only store: {artifact_type.__name__}")

        return manager

    def _get_tags_from_artifact(self, artifact: ElementData) -> list[str]:
        """Extract tag strings from an artifact"""
        if not hasattr(artifact, 'tags') or artifact.tags is None:
            return []

        tags = []
        for tag in artifact.tags:
            if isinstance(tag, str):
                tags.append(tag)
            elif hasattr(tag, 'value'):  # Tag object
                tags.append(tag.value)
        return tags

    def _get_store_for_artifact(self, artifact: ElementData) -> BaseStore[ElementData]:
        """
        Get the appropriate store for an artifact based on its type and tags.
        Priority: tag-specific store > type-only store > default store
        """
        artifact_type = type(artifact)

        # Priority 1: Check for tag-specific store
        tags = self._get_tags_from_artifact(artifact)
        for tag in tags:
            for parent in artifact_type.__mro__:
                store_key = (parent.__name__, tag)
                store = self._type_tag_to_store.get(store_key)
                if store:
                    logger.debug(
                        f"Using tag-specific store for {artifact_type.__name__} with tag='{tag}'"
                    )
                    return store

        # Priority 2: Check type-only stores
        for parent in artifact_type.__mro__:
            store = self._type_name_to_store.get(parent.__name__)
            if store:
                return store

        # Priority 3: Default store
        if self._default_store:
            return self._default_store

        raise ValueError(f"No store found for artifact type {artifact_type.__name__}")

    def _get_stores_for_type_and_tag(
        self,
        artifact_type: type[E],
        tag: str | None = None
    ) -> list[BaseStore[E]]:
        """
        Get stores for a type, optionally filtered by tag.
        
        If tag is provided: returns [tag-specific store] + [type-only store as fallback]
        If tag is None: returns [type-only store] + [all tag-specific stores]
        """
        stores = []

        # If specific tag requested, prioritize tag-specific store
        if tag:
            for parent in artifact_type.__mro__:
                store_key = (parent.__name__, tag)
                store = self._type_tag_to_store.get(store_key)
                if store and store not in stores:
                    stores.append(store)
                    logger.debug(
                        f"Using tag-specific store for {artifact_type.__name__} with tag='{tag}'"
                    )
                    break

        # Add type-only store (as primary if no tag, as fallback if tag specified)
        for parent in artifact_type.__mro__:
            store = self._type_name_to_store.get(parent.__name__)
            if store and store not in stores:
                stores.append(store)
                break

        # If no type-specific store found, use default
        if not stores and self._default_store:
            stores.append(self._default_store)

        # If no tag specified, add ALL tag-specific stores for this type
        if not tag:
            for parent in artifact_type.__mro__:
                type_name = parent.__name__
                for (stored_type_name, stored_tag), store in self._type_tag_to_store.items():
                    if stored_type_name == type_name and store not in stores:
                        stores.append(store)
                        logger.debug(
                            f"Including tag-specific store for {artifact_type.__name__} "
                            f"with tag='{stored_tag}'"
                        )

        return stores

    async def store(self, artifact: ElementData) -> None:
        """Store an artifact with its type information"""
        if not type(artifact).is_storable():
            raise ValueError(
                f"Cannot store artifact of non-storable type {type(artifact).__name__}"
            )
        store = self._get_store_for_artifact(artifact)
        await store.store(artifact, type_info=artifact.__class__)

    async def bulk_store(
        self,
        artifacts: list[ElementData],
        ignore_duplicates: bool = False
    ) -> list[str]:
        """Store multiple artifacts - assumes all are same type and tags"""
        if not artifacts:
            return []

        # Assume all artifacts have the same type and tags - use first one
        store = self._get_store_for_artifact(artifacts[0])
        return await store.bulk_store(
            artifacts,
            type_info=artifacts[0].__class__,
            ignore_duplicates=ignore_duplicates
        )

    async def get_by_id(
        self,
        element_id: str,
        artifact_type: type[E],
        tag: str | None = None
    ) -> E | None:
        """
        Retrieve an artifact by its ID and type
        
        Args:
            element_id: The ID of the element to retrieve
            artifact_type: The type of the artifact
            tag: Optional tag to narrow down the store search
        """
        if not artifact_type.is_storable():
            artifact = await artifact_type.get_by_id(self, element_id)
            return artifact

        stores = self._get_stores_for_type_and_tag(artifact_type, tag)

        for store in stores:
            result = await store.retrieve(
                id_field="element_id",
                id_value=element_id,
                type_info=artifact_type
            )
            if result is not None:
                return cast(E | None, result)

        return None

    async def get_children(
        self,
        root_id: str,
        child_type: type[E],
        tag: str | None = None
    ) -> list[E]:
        """
        Retrieve all children of a specific type for a given parent
        
        Args:
            root_id: The parent ID
            child_type: The type of children to retrieve
            tag: Optional tag to narrow down the store search
        """
        stores = self._get_stores_for_type_and_tag(child_type, tag)

        all_results = []
        for store in stores:
            results = await store.search(
                query={"root_id": QueryFilter(
                    operator=QueryOperator.EQUAL,
                    value=root_id
                )},
                type_info=child_type
            )
            all_results.extend(results)

        return cast(list[E], all_results)

    async def get_children_for_list(
        self,
        root_ids: list[str],
        child_type: type[E],
        tag: str | None = None
    ) -> list[E]:
        """
        Retrieve all children of a specific type for a given list of parents
        
        Args:
            root_ids: List of parent IDs
            child_type: The type of children to retrieve
            tag: Optional tag to narrow down the store search
        """
        stores = self._get_stores_for_type_and_tag(child_type, tag)

        all_results = []
        for store in stores:
            results = await store.search(
                query={"root_id": QueryFilter(
                    operator=QueryOperator.EQUALS_MANY,
                    value=root_ids
                )},
                type_info=child_type
            )
            all_results.extend(results)

        return cast(list[E], all_results)

    async def delete(
        self,
        element_id: str,
        artifact_type: type[E],
        tag: str | None = None
    ) -> None:
        """
        Delete an artifact by its ID and type
        
        Args:
            element_id: The ID of the element to delete
            artifact_type: The type of the artifact
            tag: Optional tag to narrow down the store search
        """
        if tag:
            # If tag provided, use it to find the store
            stores = self._get_stores_for_type_and_tag(artifact_type, tag)
            for store in stores:
                try:
                    await store.delete(
                        id_field="element_id",
                        id_value=element_id,
                        type_info=artifact_type
                    )
                    return
                except:
                    continue
        else:
            # No tag - retrieve artifact first to determine correct store
            artifact = await self.get_by_id(element_id, artifact_type)

            if artifact is None:
                logger.warning(f"Artifact {element_id} not found for deletion")
                return

            store = self._get_store_for_artifact(artifact)
            await store.delete(
                id_field="element_id",
                id_value=element_id,
                type_info=artifact_type
            )

    async def get_all(
        self,
        artifact_type: type[E],
        tag: str | None = None
    ) -> list[E]:
        """
        Retrieve all artifacts of a specific type
        
        Args:
            artifact_type: The type of artifacts to retrieve
            tag: Optional tag to narrow down the store search
        """
        stores = self._get_stores_for_type_and_tag(artifact_type, tag)

        all_results = []
        for store in stores:
            results = await store.search(query={}, type_info=artifact_type)
            all_results.extend(results)

        return cast(list[E], all_results)

    async def search(
        self,
        artifact_type: type[E],
        query: dict[str, QueryFilter],
        tag: str | None = None
    ) -> list[E]:
        """
        Search for artifacts of the specified type based on a query
        
        Args:
            artifact_type: The type of artifacts to search for
            query: The search query
            tag: Optional tag to narrow down the store search
        """
        stores = self._get_stores_for_type_and_tag(artifact_type, tag)

        all_results = []
        for store in stores:
            results = await store.search(query=query, type_info=artifact_type)
            all_results.extend(results)

        return cast(list[E], all_results)

    async def store_trace_logs(
        self,
        source: str | TextIO
    ) -> tuple[list[BaseTraceData], str | None]:
        """Parse and store trace logs"""
        traces, spans, validate_warning = parse_trace_logs(source)
        _ = await self.bulk_store(spans, ignore_duplicates=True)
        return traces, validate_warning

    async def get_traces(
        self,
        service_name: str,
        from_date: datetime,
        to_date: datetime | None,
        tag: str | None = None
    ) -> list[BaseTraceData]:
        """
        Get all traces for the service name, within the given date range.
        
        Args:
            service_name: Name of the service to filter spans by
            from_date: Start of the time range
            to_date: Optional end of time range
            tag: Optional tag to narrow down which spans to search
        """
        query = {
            "resource.attributes.service_name": QueryFilter(
                operator=QueryOperator.EQUAL,
                value=service_name
            ),
            "start_time": QueryFilter(
                operator=QueryOperator.GREATER_EQUAL,
                value=from_date
            )
        }

        if to_date is not None:
            query["end_time"] = QueryFilter(
                operator=QueryOperator.LESS_EQUAL,
                value=to_date
            )

        spans = await self.search(BaseSpanData, query, tag=tag)
        traces = TraceLogParser.create_traces_from_spans(spans)
        return traces

    async def get_spans(
        self,
        trace_id: str,
        tag: str | None = None
    ) -> list[BaseSpanData]:
        """
        Get all spans belonging to a specific trace.
        
        Args:
            trace_id: ID of the trace to get spans for
            tag: Optional tag to narrow down which spans to retrieve
        """
        spans = await self.get_children(trace_id, BaseSpanData, tag=tag)
        return spans

    async def get_trace_groups(
        self,
        service_name: str,
        tag: str | None = None
    ) -> list[TraceGroupData]:
        """
        Return the trace groups for the given service name
        
        Args:
            service_name: Name of the service
            tag: Optional tag to narrow down which trace groups to retrieve
        """
        query = {
            "service_name": QueryFilter(
                operator=QueryOperator.EQUAL,
                value=service_name
            )
        }
        trace_groups = await self.search(TraceGroupData, query, tag=tag)
        return trace_groups

    async def get_traces_for_trace_group(
        self,
        trace_group_id: str,
        tag: str | None = None
    ) -> list[BaseTraceData]:
        """
        Return all traces for the given trace group id
        
        Args:
            trace_group_id: ID of the trace group
            tag: Optional tag to narrow down which traces/spans to retrieve
        """
        traces = []
        trace_group = await self.get_by_id(trace_group_id, TraceGroupData, tag=tag)

        if trace_group:
            traces_ids = trace_group.traces_ids
            spans = []
            for trace_id in traces_ids:
                try:
                    spans_for_trace = await self.get_spans(trace_id, tag=tag)
                    spans.extend(spans_for_trace)
                except:
                    logger.warning(
                        f"No spans found for trace_id: {trace_id} within group_id: {trace_group_id}. "
                        f"This implies that they were cleared from the DB already."
                    )
            traces.extend(TraceLogParser.create_traces_from_spans(spans))

        return traces

    async def get_trace(
        self,
        trace_id: str,
        tag: str | None = None
    ) -> BaseTraceData:
        """
        Return trace for the given trace id
        
        Args:
            trace_id: ID of the trace
            tag: Optional tag to narrow down which spans to retrieve
        """
        spans_for_trace = await self.get_spans(trace_id, tag=tag)
        traces = TraceLogParser.create_traces_from_spans(spans_for_trace)
        return traces[0]

    async def get_related_elements_for_artifact(
        self,
        artifact: RelatableElementData
    ) -> list[ElementData]:
        """
        Given a relatable element, fetch all elements it is related to as a list
        """
        element_id = artifact.element_id
        artifact_type = type(artifact)

        # Extract tags from the artifact
        tags = self._get_tags_from_artifact(artifact)

        # If no tags, call with tag=None (searches all stores)
        if not tags:
            return await self.get_related_elements(element_id, artifact_type, tag=None)

        # Try each tag and combine results
        all_related_artifacts = []
        seen_ids = set()

        for tag in tags:
            related_artifacts = await self.get_related_elements(element_id, artifact_type, tag=tag)
            # Deduplicate by element_id
            for related_artifact in related_artifacts:
                if related_artifact.element_id not in seen_ids:
                    seen_ids.add(related_artifact.element_id)
                    all_related_artifacts.append(related_artifact)

        return all_related_artifacts

    async def get_related_elements(
        self,
        element_id: str,
        artifact_type: type[RelatableElementData],
        tag: str | None = None
    ) -> list[ElementData]:
        """
        Given a relatable element information (id and type), 
        fetch all elements it is related to as a list
        
        Args:
            element_id: ID of the relatable element
            artifact_type: Type of the relatable element
            tag: Optional tag to narrow down which related elements to retrieve
        """
        related_artifacts = []
        artifact = await self.get_by_id(
            element_id=element_id,
            artifact_type=artifact_type,
            tag=tag
        )

        if artifact:
            for index, related_element_id in enumerate(artifact.related_to_ids):
                element_type_name = artifact.related_to_types[index]
                element_type = TypeResolutionUtils.resolve_type_from_fully_qualified_name(
                    element_type_name
                )

                # Pass tag=None to search ALL stores for that type
                element = await self.get_by_id(
                    related_element_id,
                    element_type,
                    tag=None
                )

                if element:
                    related_artifacts.append(element)

        return related_artifacts

    async def get_elements_related_to_by_type(
        self,
        element_id: str,
        artifact_type: type[ElementData],
        relatable_type: type[ElementData],
        tag: str | None = None
    ) -> list[RelatableElementData]:
        """
        Given a particular artifact, fetch all RelatableElements of the given type 
        which declared that they are related_to this artifact
        
        Args:
            element_id: ID of the artifact
            artifact_type: Type of the artifact
            relatable_type: Type of relatable elements to search for
            tag: Optional tag to narrow down which stores to search
        """
        if not issubclass(relatable_type, RelatableElementData):
            raise ValueError(
                f"The requested type: {relatable_type} is not a RelatableElement type"
            )

        all_related_elements = []
        artifact_type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(
            artifact_type
        )

        try:
            stores = self._get_stores_for_type_and_tag(relatable_type, tag)

            for store in stores:
                query = {
                    "related_to_ids": QueryFilter(
                        operator=QueryOperator.ARRAY_CONTAINS,
                        value=element_id
                    )
                }

                results = await store.search(query=query, type_info=relatable_type)

                filtered_results = []
                for result in results:
                    for i, related_id in enumerate(result.related_to_ids):
                        if (related_id == element_id and
                            i < len(result.related_to_types) and
                            result.related_to_types[i] == artifact_type_name):
                            filtered_results.append(result)
                            break

                all_related_elements.extend(filtered_results)

        except ValueError as e:
            print(f"No store found for type {relatable_type.__name__}: {str(e)}")
            raise ValueError()

        return all_related_elements

    async def get_elements_related_to(
        self,
        element_id: str,
        artifact_type: type[ElementData],
        tag: str | None = None
    ) -> list[RelatableElementData]:
        """
        Given an artifact information, fetch all elements related to it
        
        Args:
            element_id: ID of the artifact
            artifact_type: Type of the artifact
            tag: Optional tag to narrow down which stores to search for related elements
        """
        artifact_type_name = TypeResolutionUtils.get_fully_qualified_type_name_for_type(
            artifact_type
        )
        relatable_types = TypeResolutionUtils.get_relatable_element_data_subclasses()

        all_related_elements = []

        for relatable_type in relatable_types:
            if not issubclass(relatable_type, RelatableElementData):
                continue

            try:
                stores = self._get_stores_for_type_and_tag(relatable_type, tag)

                for store in stores:
                    query = {
                        "related_to_ids": QueryFilter(
                            operator=QueryOperator.ARRAY_CONTAINS,
                            value=element_id
                        )
                    }

                    results = await store.search(query=query, type_info=relatable_type)

                    filtered_results = []
                    for result in results:
                        for i, related_id in enumerate(result.related_to_ids):
                            if (related_id == element_id and
                                i < len(result.related_to_types) and
                                result.related_to_types[i] == artifact_type_name):
                                filtered_results.append(result)
                                break

                    all_related_elements.extend(filtered_results)

            except ValueError as e:
                print(f"No store found for type {relatable_type.__name__}: {str(e)}")
                continue

        return all_related_elements

    async def get_elements_related_to_artifact(
        self,
        artifact: ElementData
    ) -> list[RelatableElementData]:
        """
        Given an artifact, fetch all elements related to it
        """
        element_id = artifact.element_id
        artifact_type = type(artifact)

        # Search ALL stores (tag=None) because related elements might have different tags
        return await self.get_elements_related_to(element_id, artifact_type, tag=None)

    async def get_elements_related_to_artifact_and_type(
        self,
        artifact: ElementData,
        relatable_type: type[ElementData]
    ) -> list[RelatableElementData]:
        """
        Given an artifact, fetch all elements related to it of the given type
        """
        element_id = artifact.element_id
        artifact_type = type(artifact)

        # Search ALL stores (tag=None) because related elements might have different tags
        return await self.get_elements_related_to_by_type(
            element_id,
            artifact_type,
            relatable_type,
            tag=None
        )
