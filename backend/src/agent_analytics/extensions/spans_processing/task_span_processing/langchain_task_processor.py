from typing import Any

from agent_analytics_common.interfaces.graph import Graph

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


class LangChainTaskGraphVisitor(BaseTaskGraphVisitor, GraphOperationsMixin):
    def __init__(self):
        super(LangChainTaskGraphVisitor, self).__init__()
        self.name = 'langchain processor'

    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        return span.raw_attributes.get(TRACELOOP_WORKFLOW, '').startswith(LANGCHAIN_AGENT) \
               or span.raw_attributes.get(TRACELOOP_WORKFLOW, '') == RUNNABLE_SEQUENCE

    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        return self._is_agent_span(span) or self.span_utils.is_tool_span(span)

    def _is_agent_span(self, span: BaseSpanComposite) -> bool:
        return span.name.startswith(LANGCHAIN_AGENT)

    def _extract_framework_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        if self.span_utils.is_tool_span(span):
            self._update_tool_task(task, span, context)

        elif self._is_agent_span(span):
            self._update_agent_task(task, span, context)



    def _should_attach_to_graph(self) -> bool:
        return True

    def _update_tool_task(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        task.add_tag([TaskTag.TOOL_CALL])
        task.attributes.update(span.raw_attributes)
        self._attach_tool_to_graph(task, context)

    def _update_agent_task(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        new_tags = [TaskTag.COMPLEX]
        new_tags += [LANGCHAIN_WORKFLOW_TAG if span.name.endswith(WORKFLOW_SUFF) else LANGCHAIN_AGENT_TAG]
        task.add_tag(new_tags)
        task.attributes.update(span.raw_attributes)
        task.children_node_graph = Graph()
        self._add_node_to_graph(task, context, task.children_node_graph)

    def _update_framework_propagated_info(self, parent_task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any], task: HierarchicalTask=None):
        pass

    # handle langchain-specific dependencies detection code
    def is_applicable_task(self, task: HierarchicalTask,
                           context: dict[str, Any] | None = None) -> bool:
        """Check if this task should be processed by the new framework visitor."""
        return hasattr(task, 'children_node_graph') and task.children_node_graph is not None

    def _detect_dependencies_between_siblings(self, parent_task: HierarchicalTask,
                                              context: dict[str, Any] | None = None) -> None:
        """
        Detect dependencies between sibling tasks based on the framework's structure.
        """
        if not self.is_applicable_task(parent_task, context):
            return

        # Process each child task
        for child in parent_task.children:
            node = parent_task.children_node_graph.get_node(child.attributes.get(TASK_ID, ''))
            self._process_edge_dependencies(parent_task, child, node, context)

