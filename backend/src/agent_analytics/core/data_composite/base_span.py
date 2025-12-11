from abc import ABC
from typing import Optional, Dict, Any, List, ClassVar, Type, Union
from datetime import datetime
import json

from pydantic import BaseModel, Field

from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.element import ElementComposite, _CREATION_TOKEN
from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.span_data import (
    BaseSpanData, SpanKind, SpanStatus, SpanContext, 
    SpanEvent, Resource, ResourceAttributes
)

class BaseSpanComposite(ElementComposite[BaseSpanData]):
    """
    Logical representation of a span in a trace
    
    This class provides a logical view of span data and methods for
    working with spans in a distributed tracing system.
    """
    
    # Specify the corresponding data class
    data_class: ClassVar[Type[BaseSpanData]] = BaseSpanData
    
    def __init__(self, data_manager: DataManager, span_data: BaseSpanData,*, _token: object = None):
        super().__init__(data_manager, span_data, _token=_token)
    
    # Basic properties that reflect the underlying data object
    
    @property
    def context(self) -> SpanContext:
        return self._data_object.context
    
    #TODO do we need this or can we return parent span instead?
    @property
    def parent_id(self) -> Optional[str]:
        return self._data_object.parent_id
    
    @property
    def kind(self) -> SpanKind:
        return self._data_object.kind
    
    @property
    def start_time(self) -> datetime:
        return self._data_object.start_time
    
    @property
    def end_time(self) -> datetime:
        return self._data_object.end_time
    
    @property
    def status(self) -> SpanStatus:
        return self._data_object.status
    
    @property
    def resource(self) -> Resource:
        return self._data_object.resource
    
    @property
    def raw_attributes(self) -> Dict[str, Any]:
        return self._data_object.raw_attributes
    
    @property
    def events(self) -> List[SpanEvent]:
        return self._data_object.events
    
    @property
    def links(self) -> List[Any]:
        return self._data_object.links
    
    # Derived properties and convenience methods
    
    @property
    def service_name(self) -> str:
        """Get the service name from the resource attributes"""
        return self._data_object.resource.attributes.service_name
    
    @property
    def duration_ms(self) -> float:
        """Calculate the duration of the span in milliseconds"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() * 1000
        return 0
    
    @property
    def is_error(self) -> bool:
        """Determine if the span represents an error"""
        return self.status.status_code.upper() not in ["OK", "SUCCESS"]
    
    # Relationship properties that use the data manager
      
    
    @property
    async def trace(self) -> Any:
        """Get the trace this span belongs to"""        
        return await self._data_manager.get_by_id(self.root_id, BaseTraceComposite)
    
    # Factory method for creating spans

    @classmethod
    async def get_spans_for_trace(cls,data_manager:'DataManager',trace_id:str) -> List['BaseSpanComposite']:
        return await data_manager.get_spans(trace_id)
    
    @classmethod
    async def create(cls,
                   data_manager: DataManager,
                   name: str,
                   trace_id: str,
                   span_id: str,                   
                   kind: SpanKind,
                   start_time: datetime,
                   end_time: datetime,
                   service_name: str,
                   status_code: str = "OK",
                   parent_id: Optional[str] = None,
                   attributes: Dict[str, Any] = None,
                   events: List[SpanEvent] = None,
                   links: List[Any] = None,
                   **resource_attributes) -> 'BaseSpanComposite':
        """
        Factory method to create a new span
        
        Args:
            data_manager: The data manager to use for storage
            name: The name of the span
            trace_id: The ID of the trace this span belongs to
            span_id: The unique identifier for this span
            kind: The kind of span (CLIENT, SERVER, etc.)
            start_time: When the span started
            end_time: When the span ended
            service_name: The name of the service this span belongs to
            status_code: The status code (OK, ERROR, etc.)
            parent_id: The ID of the parent span, if any
            attributes: Additional attributes for the span
            events: List of events associated with the span
            links: List of links to other spans
            **resource_attributes: Additional resource attributes
            
        Returns:
            A new BaseSpan instance
        """
        # Create context
        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            trace_state=""
        )
        
        # Create status
        status = SpanStatus(status_code=status_code)
        
        # Create resource
        resource_attrs = {"service_name": service_name, **resource_attributes}
        resource = Resource(
            attributes=ResourceAttributes(**resource_attrs),
            schema_url=""
        )
        
        # Create span data
        span_data = BaseSpanData(
            element_id=span_id,
            root_id=trace_id,
            name=name,
            context=context,
            parent_id=parent_id,
            kind=kind,
            start_time=start_time,
            end_time=end_time,
            status=status,
            resource=resource,
            raw_attributes=attributes or {},
            events=events or [],
            links=links or []
        )
        
        # Store span data
        span  = cls(data_manager, span_data,_token=_CREATION_TOKEN)
        
        await data_manager.store(span)
        
        # Return span
        return span
    



class BaseSpan(BaseModel):
    """
    Builder class for Span logical objects.
    
    This class provides a mutable interface that can be used to gather data
    before creating an immutable Span logical object.
    """
    model_config = {"arbitrary_types_allowed": True}
    
    # --- Basic span fields ---
    name: str
    trace_id: str
    span_id: Optional[str] = None
    kind: SpanKind
    start_time: datetime
    end_time: datetime
    service_name: str
    status_code: str = "OK"
    parent_id: Optional[str] = None
    
    # --- Additional span data ---
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[SpanEvent] = Field(default_factory=list)
    links: List[Any] = Field(default_factory=list)
    resource_attributes: Dict[str, Any] = Field(default_factory=dict)
    
    
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseSpan':
        """Create a builder from a dictionary"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'BaseSpan':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    async def store(self, data_manager: DataManager) -> BaseSpanComposite:
        """
        Build the Span logical object.
        
        Args:
            data_manager: The data manager to use for creating the Span
            
        Returns:
            The created Span logical object
        """
        # Generate span_id if not provided
        
            
        # Validate required fields
        if not self.name:
            raise ValueError("Span name must be set before building")
        if not self.trace_id:
            raise ValueError("Trace ID must be set before building")
        if not self.service_name:
            raise ValueError("Service name must be set before building")
        
        # Create the span
        return await BaseSpanComposite.create(
            data_manager=data_manager,
            name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            kind=self.kind,
            start_time=self.start_time,
            end_time=self.end_time,
            service_name=self.service_name,
            status_code=self.status_code,
            parent_id=self.parent_id,
            attributes=self.attributes,
            events=self.events,
            links=self.links,
            **self.resource_attributes
        )
    
    @classmethod
    async def bulk_store(cls, data_manager: DataManager, base_spans: List['BaseSpan']) -> List[BaseSpanComposite]:
        """
        Efficiently store multiple BaseSpan objects at once.
        
        Args:
            data_manager: The data manager to use for storage
            base_spans: List of BaseSpan objects to store
            
        Returns:
            List of created BaseSpanComposite objects
        """
        # Validate all builders before proceeding
        for base_span in base_spans:
            if not base_span.name:
                raise ValueError(f"Span name must be set before building (id: {base_span.element_id})")
            if not base_span.trace_id:
                raise ValueError(f"Trace ID must be set before building (id: {base_span.element_id})")
            if not base_span.service_name:
                raise ValueError(f"Service name must be set before building (id: {base_span.element_id})")
            
            
        
        # Create all composite objects but don't store them individually
        composite_objects = []
        for base_span in base_spans:
            # Create context
            context = SpanContext(
                trace_id=base_span.trace_id,
                span_id=base_span.span_id,
                trace_state=""
            )
            
            # Create status
            status = SpanStatus(status_code=base_span.status_code)
            
            # Create resource
            resource_attrs = {"service_name": base_span.service_name, **base_span.resource_attributes}
            resource = Resource(
                attributes=ResourceAttributes(**resource_attrs),
                schema_url=""
            )
            
            # Create span data
            span_data = BaseSpanData(
                element_id=base_span.span_id,
                root_id=base_span.trace_id,
                name=base_span.name,
                context=context,
                parent_id=base_span.parent_id,
                kind=base_span.kind,
                start_time=base_span.start_time,
                end_time=base_span.end_time,
                status=status,
                resource=resource,
                raw_attributes=base_span.attributes or {},
                events=base_span.events or [],
                links=base_span.links or []
            )
            
            # Create span instance without storing it
            composite = BaseSpanComposite(data_manager, span_data, _token=_CREATION_TOKEN)
            composite_objects.append(composite)
        
        # Use the bulk_store method of the data manager
        await data_manager.bulk_store(composite_objects)
        
        # Return the created composite objects
        return composite_objects