from typing import Any

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.task_span_processing.base_task_processor import (
    BaseTaskGraphVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.graph_operations import (
    GraphOperationsMixin,
)
from agent_analytics_common.interfaces.task import TaskTag


class VectorDBVisitor(BaseTaskGraphVisitor, GraphOperationsMixin):
    def __init__(self):
        super(VectorDBVisitor, self).__init__()
        self.name = 'vectorDB processor'

    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        return True

    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        return self._is_db_insert(span) or self._is_db_search(span)

    def _is_db_insert(self, span):
        return span.name == MILVUS_INSERT_SPAN
    def _is_db_search(self, span):
        return span.name in MILVUS_SEARCH_SPAN


    def _extract_framework_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        if self._is_db_insert(span):
            self._update_db_task(task, span, context)

        elif self._is_db_search(span):
            self._update_db_task(task, span, context)

    def _update_db_task(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        task.add_tag([TaskTag.DB_CALL])
        task.attributes = self.span_utils.add_fields_acc_to_startswith([DB_STARTSWITH_ATTR], span.raw_attributes, {})
        self._attach_llm_to_graph(task, span, context)

    def _should_attach_to_graph(self) -> bool:
        return True

    def _update_framework_propagated_info(self, parent_task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any], task: HierarchicalTask=None):
        pass

    def is_applicable_task(self, task: HierarchicalTask,
                           context: dict[str, Any] | None = None) -> bool:
        """Check if this task should be processed by the new framework visitor."""
        return False

    def _detect_dependencies_between_siblings(self, parent_task: HierarchicalTask,
                                              context: dict[str, Any] | None = None) -> None:
        """
        Detect dependencies between sibling tasks based on the framework's structure.
        """
        pass
