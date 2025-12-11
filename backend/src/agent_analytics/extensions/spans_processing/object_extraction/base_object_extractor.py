from abc import ABC, abstractmethod
from typing import Any

from agent_analytics.extensions.spans_processing.span_processor import SpanProcessor, VisitPhase


class BaseObjectExtractionVisitor(SpanProcessor, ABC):
    """
    Base abstract class for object extraction visitors.
    
    This class implements the SpanProcessor interface and provides the common
    structure for extracting framework-specific objects from spans.
    """

    def __init__(self):
        """Initialize the object extraction visitor."""
        # TODO: Map of object type to map of object ID to object
        # e.g. {'CrewGraph': {'crew_id_123': crew_graph_object}}
        self.extracted_objects: dict[str, dict[str, Any]] = {}

        # Set to track which span IDs have been used to extract objects
        self.extraction_span_ids: set[str] = set()

        # TODO: Set to track which object IDs have been updated
        self.updated_object_ids: set[str] = set()

        # Logger instance


    def process(self, span: Any, phase: VisitPhase, context: dict[str, Any]) -> None:
        """
        Process a span to extract or update objects.
        
        Args:
            span: The span being processed
            phase: Current traversal phase
            context: Shared context dictionary
        """
        # Get or create extracted_objects map in context
        if "extracted_objects" not in context:
            context["extracted_objects"] = {}

        if phase == VisitPhase.BEFORE_CHILDREN:
            # Handle before children phase - extract object
            self._handle_before_children(span, context)
        else:
            # Handle after children phase - update extracted objects
            self._handle_after_children(span, context)

    def should_process(self, span: Any, context: dict[str, Any]) -> bool:
        """
        Determine if this visitor should process this span - is it an "object" span?.
        
        Args:
            span: The span to check
            context: Shared context dictionary
            
        Returns:
            True if this visitor should process the span
        """
        return self._is_object_span(span)

    @abstractmethod
    def _is_object_span(self, span: Any) -> bool:
        #TODO: need to determine if need Visitor per type of span (type of object)? Or per framework? (if different frameworks would store object spans differently)
        #Perhaps need two types of inheritence - visitor per framework, and then particular implementation per object type
        """
        Check if the span represents an object this visitor can extract. 
        
        
        Args:
            span: The span to check
            
        Returns:
            True if the span represents an extractable object
        """
        pass

    def _handle_before_children(self, span: Any, context: dict[str, Any]) -> None:
        """
        Handle the span in the before-children phase.
        
        Args:
            span: The span being processed
            context: Shared context dictionary
        """
        # Skip if we've already extracted an object from this span
        if span.id in self.extraction_span_ids:
            return

        # Try to extract an object
        extraction_result = self._extract_object(span, context)

        # If no object was extracted, return
        if extraction_result is None:
            return

        # Unpack extraction result
        obj_type, obj_id, obj = extraction_result

        # Add to extraction span IDs
        self.extraction_span_ids.add(span.id)

        # Store the extracted object
        if obj_type not in self.extracted_objects:
            self.extracted_objects[obj_type] = {}

        self.extracted_objects[obj_type][obj_id] = obj

        # TODO: Store in context for other visitors? (if needed)
        context_objects = context["extracted_objects"]
        if obj_type not in context_objects:
            context_objects[obj_type] = {}

        context_objects[obj_type][obj_id] = obj



    def _handle_after_children(self, span: Any, context: dict[str, Any]) -> None:
        """
        Handle the span in the after-children phase.
        
        Args:
            span: The span being processed
            context: Shared context dictionary
        """
        # Try to update objects related to this span
        for obj_type, objects in self.extracted_objects.items():
            for obj_id, obj in objects.items():
                # Skip if we've already updated this object with this span
                update_key = f"{obj_id}:{span.id}"
                if update_key in self.updated_object_ids:
                    continue

                # Check if this span can update the object
                if self._can_update_object(obj_type, obj_id, obj, span):
                    # Update the object
                    self._update_object(obj_type, obj_id, obj, span, context)

                    # Add to updated object IDs
                    self.updated_object_ids.add(update_key)

                    # Update in context
                    context_objects = context["extracted_objects"]
                    if obj_type in context_objects and obj_id in context_objects[obj_type]:
                        context_objects[obj_type][obj_id] = obj

    @abstractmethod
    def _extract_object(self, span: Any, context: dict[str, Any]) -> tuple[str, str, Any] | None:
        """
        Extract an object from a span if applicable.
        
        Args:
            span: The span to extract from
            context: Shared context dictionary
            
        Returns:
            A tuple of (object_type, object_id, object) or None if no object was extracted
        """
        pass

    @abstractmethod
    def _can_update_object(self, obj_type: str, obj_id: str, obj: Any, span: Any) -> bool:
        """
        Check if a span can update an extracted object.
        
        Args:
            obj_type: The type of the object
            obj_id: The ID of the object
            obj: The object itself
            span: The span that might update the object
            
        Returns:
            True if the span can update the object
        """
        pass

    @abstractmethod
    def _update_object(self, obj_type: str, obj_id: str, obj: Any, span: Any, context: dict[str, Any]) -> None:
        """
        Update an extracted object with information from a span.
        
        Args:
            obj_type: The type of the object
            obj_id: The ID of the object
            obj: The object itself
            span: The span with update information
            context: Shared context dictionary
        """
        pass

    def after_traversal(self, context: dict[str, Any]) -> None:
        """
        Called after all spans have been traversed for final processing.
        
        Args:
            context: Shared context dictionary
        """
        self.logger.info(f"Finalized {sum(len(objs) for objs in self.extracted_objects.values())} "
                         f"objects from {len(self.extraction_span_ids)} spans")

        # Finalize extracted objects
        self._finalize_extracted_objects(context)

        # TODO: Update context with final objects- if needed
        context["extracted_objects"] = {**context.get("extracted_objects", {}), **self.extracted_objects}

        #TODO: persist the objects

    def _finalize_extracted_objects(self, context: dict[str, Any]) -> None:
        """
        Perform any final processing on extracted objects.
        
        This method can be overridden by subclasses to perform framework-specific
        finalization of extracted objects.
        
        Args:
            context: Shared context dictionary
        """
        pass

    def get_extracted_objects(self) -> dict[str, dict[str, Any]]:
        """
        Get all objects extracted by this visitor.
        
        Returns:
            Map of object type to map of object ID to object
        """
        return self.extracted_objects
