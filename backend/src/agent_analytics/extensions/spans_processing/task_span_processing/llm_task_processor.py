from typing import Any

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.task_span_processing.base_task_processor import (
    BaseTaskGraphVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.span_utils import (
    LLMSpanProcessor,
)
from agent_analytics_common.interfaces.task import TaskTag


class LLMTaskProcessor(BaseTaskGraphVisitor):
    """Standalone processor for LLM spans not claimed by framework processors."""

    def __init__(self):
        super().__init__()
        self.name = 'llm processor'
        self.llm_processor = LLMSpanProcessor(self.span_utils)

    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        """Process all LLM spans with priority over framework processors.

        This processor runs first and claims all LLM spans before framework
        processors get a chance to process them.
        """
        return self.span_utils.is_llm_span(span)

    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        """Always create tasks for LLM spans that reach this processor."""
        return self.span_utils.is_llm_span(span)

    def _extract_framework_task_from_span(
        self,
        task: HierarchicalTask,
        span: BaseSpanComposite,
        context: dict[str, Any]
    ) -> None:
        """Process LLM-specific information using LLM span processor."""
        if self.span_utils.is_llm_span(span):
            self.llm_processor.process_llm_task(task, span)

    def _should_attach_to_graph(self) -> bool:
        """Don't attach to any graph."""
        return False

    def _update_framework_propagated_info(
        self,
        parent_task: HierarchicalTask,
        span: BaseSpanComposite,
        context: dict[str, Any],
        task: HierarchicalTask = None
    ):
        """No framework-specific propagation."""
        pass

    def is_applicable_task(
        self,
        task: HierarchicalTask,
        context: dict[str, Any] | None = None
    ) -> bool:
        """Check if this is an LLM task."""
        return TaskTag.LLM_CALL in task.tags

    def _detect_dependencies_between_siblings(
        self,
        parent_task: HierarchicalTask,
        context: dict[str, Any] | None = None
    ) -> None:
        """Simple time-based sequential dependency detection for LLM tasks."""
        if not parent_task.children:
            return

        # Sort by start time
        parent_task.children.sort(key=lambda t: t.start_time)

        # Sequential dependency: each task depends on the previous one
        for i in range(1, len(parent_task.children)):
            prev_task = parent_task.children[i - 1]
            curr_task = parent_task.children[i]

            if self._has_valid_time_relationship(prev_task, curr_task):
                self._add_dependency(curr_task, prev_task)
