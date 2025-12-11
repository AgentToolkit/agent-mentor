from enum import Enum
from typing import Any, Dict

class VisitPhase(Enum):
    """Defines the phase of traversal for a span node."""
    BEFORE_CHILDREN = "before_children"  # First visit, before processing children
    AFTER_CHILDREN = "after_children"

class SpanProcessor:
    """Interface for span processors that are applied during traversal."""
    
    def process(self, span: Any, phase: VisitPhase, context: Dict[str, Any]) -> None:
        """
        Process a span during traversal.
        
        Args:
            span: The span being processed
            phase: Current traversal phase (before or after children)
            context: Shared context dictionary
        """
        raise NotImplementedError("Subclasses must implement process method")
                   
    def should_process(self, span: Any, context: Dict[str, Any]) -> bool:
        """
        Determine if this processor should handle the given span.
        
        Args:
            span: The span to check
            context: Shared context dictionary
            
        Returns:
            True if this processor should process the span, False otherwise
        """
        raise NotImplementedError("Subclasses must implement should_process method")
    
    def after_traversal(self, context: Dict[str, Any]) -> None:
        """
        Called after all spans have been traversed for final processing.
        
        Args:
            context: Shared context dictionary
        """
        raise NotImplementedError("Subclasses must implement after_traversal method")