from abc import ABC, abstractmethod
from datetime import datetime
from typing import (
    Any,
    Generic,
    TextIO,
    TypeVar,
    Union,
)

from agent_analytics.core.data.element_data import ElementData
from agent_analytics.core.data_composite.element import ElementComposite

# Generic Type for artifacts
T = TypeVar("T", bound=Union['ElementComposite', 'ElementData'])

class DataManager(ABC, Generic[T]):
    """
    Abstract DataManager interface for storing and retrieving artifacts with support for parent-child relationships.
    """

    @abstractmethod
    async def store(self, artifact: T) -> None:
        """
        Stores the artifact in the database.
        """
        pass

    @abstractmethod
    async def get_by_id(
        self,
        element_id: str,
        artifact_type: type[T],
        tag: str | None = None
    ) -> T | None:
        """
        Retrieves an artifact by its ID and type.
        
        Args:
            element_id: The ID of the element to retrieve
            artifact_type: The type of the artifact
            tag: Optional tag to narrow down the store search
        """
        pass

    @abstractmethod
    async def get_children(
        self,
        root_id: str,
        child_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Retrieves all children of a specific type for a given parent.
        
        Args:
            root_id: The parent ID
            child_type: The type of children to retrieve
            tag: Optional tag to narrow down the store search
        """
        pass

    @abstractmethod
    async def get_children_for_list(
        self,
        root_ids: list[str],
        child_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Retrieves all children of a specific type for a list of parents.
        
        Args:
            root_ids: List of parent IDs
            child_type: The type of children to retrieve
            tag: Optional tag to narrow down the store search
        """
        pass

    @abstractmethod
    async def delete(
        self,
        element_id: str,
        artifact_type: type[T],
        tag: str | None = None
    ) -> None:
        """
        Deletes an artifact by its ID and type.
        
        Args:
            element_id: The ID of the element to delete
            artifact_type: The type of the artifact
            tag: Optional tag to narrow down the store search
        """
        pass

    @abstractmethod
    async def get_all(
        self,
        artifact_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Retrieves all artifacts of a specific type.
        
        Args:
            artifact_type: The type of artifacts to retrieve
            tag: Optional tag to narrow down the store search
        """
        pass

    @abstractmethod
    async def bulk_store(self, artifacts: list[T], ignore_duplicates: bool = False) -> list[str]:
        """Store artifacts with their type information"""
        pass

    @abstractmethod
    async def search(
        self,
        item_type: type[T],
        query: dict[str, Any],
        tag: str | None = None
    ) -> list[T]:
        """
        Search for items of the specified type based on a query.
        
        Args:
            item_type: The type of items to search for
            query: The query to use for searching
            tag: Optional tag to narrow down the store search
            
        Returns:
            A list of items that match the query
        """
        pass

    @abstractmethod
    async def store_trace_logs(self, source: str | TextIO) -> tuple[list[T], str | None]:
        """
        Parse trace logs and store all traces and spans in the database.
        """
        pass

    @abstractmethod
    async def get_traces(
        self,
        service_name: str,
        from_date: datetime,
        to_date: datetime | None,
        tag: str | None = None
    ) -> list[T]:
        """
        Get all traces for the service name, within the given date range.
        
        Args:
            service_name: Name of the service
            from_date: Start of the time range
            to_date: Optional end of time range
            tag: Optional tag to narrow down which traces to retrieve
        """
        pass

    @abstractmethod
    async def get_trace(
        self,
        trace_id: str,
        tag: str | None = None
    ) -> T:
        """
        Return trace object for the given trace_id.
        
        Args:
            trace_id: ID of the trace
            tag: Optional tag to narrow down which spans to retrieve
        """
        pass

    @abstractmethod
    async def get_spans(
        self,
        trace_id: str,
        tag: str | None = None
    ) -> list[T]:
        """
        Get all spans belonging to a specific trace.
        
        Args:
            trace_id: ID of the trace to get spans for
            tag: Optional tag to narrow down which spans to retrieve
        """
        pass

    @abstractmethod
    async def get_trace_groups(
        self,
        service_name: str,
        tag: str | None = None
    ) -> list[T]:
        """
        For the given service name, return all trace groups.
        
        Args:
            service_name: Name of the service
            tag: Optional tag to narrow down which trace groups to retrieve
        """
        pass

    @abstractmethod
    async def get_traces_for_trace_group(
        self,
        trace_group_id: str,
        tag: str | None = None
    ) -> list[T]:
        """
        For the trace group, return all the traces.
        
        Args:
            trace_group_id: ID of the trace group
            tag: Optional tag to narrow down which traces to retrieve
        """
        pass

    @abstractmethod
    async def get_related_elements(
        self,
        element_id: str,
        artifact_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Get all related-to objects of the given RelatableElement type and id.
        
        Args:
            element_id: ID of the relatable element
            artifact_type: Type of the relatable element
            tag: Optional tag to narrow down which related elements to retrieve
        """
        pass

    @abstractmethod
    async def get_related_elements_for_artifact(self, artifact: T) -> list[T]:
        """
        Get all related-to objects of the given RelatableElement artifact.
        """
        pass

    @abstractmethod
    async def get_elements_related_to_artifact(self, artifact: T) -> list[T]:
        """
        Given an artifact fetch all elements which this artifact is on the list of "related_to".
        """
        pass

    @abstractmethod
    async def get_elements_related_to_artifact_and_type(self, artifact: T, relatable_type: type[T]) -> list[T]:
        """
        Given an artifact fetch all elements which this artifact is on the list of "related_to" 
        and of specified relatable_type.
        """
        pass

    @abstractmethod
    async def get_elements_related_to(
        self,
        element_id: str,
        artifact_type: type[T],
        tag: str | None = None
    ) -> list[T]:
        """
        Given an artifact id and type fetch all elements which this artifact is on the list of "related_to".
        
        Args:
            element_id: ID of the artifact
            artifact_type: Type of the artifact
            tag: Optional tag to narrow down which stores to search for related elements
        """
        pass
