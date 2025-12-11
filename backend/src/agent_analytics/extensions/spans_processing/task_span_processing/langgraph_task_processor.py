import json
from typing import Any

from ibm_agent_analytics_common.interfaces.graph import Graph

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.extensions.spans_processing.common.utils import *
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.task_span_processing.base_task_processor import (
    BaseTaskGraphVisitor,
)
from ibm_agent_analytics_common.interfaces.task import TaskTag


class LangGraphTaskGraphVisitor(BaseTaskGraphVisitor):
    def __init__(self):
        super(LangGraphTaskGraphVisitor, self).__init__()
        self.name = 'langgraph processor'

    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        return span.raw_attributes.get(TRACELOOP_WORKFLOW, '').startswith(LANGGRAPH)

    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        return self._is_node_span(span)

    def _is_workflow_span(self, span: BaseSpanComposite) -> bool:
        return span.name in LANGGRAPH_WORKFLOW_SPAN_NAMES

    def _is_node_span(self, span: BaseSpanComposite) -> bool:
        potential_task_name = span.name.split(TASK_SUFF)[0]
        return potential_task_name != LANGGRAPH_START and potential_task_name == span.raw_attributes.get(TRACELOOP_LANGGRAPH_NODE, '')

    def _extract_framework_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        if self._is_node_span(span):
            self._update_node_task(task, span)

    def _update_workflow_task(self, task: HierarchicalTask, span: BaseSpanComposite) -> None:
        task.add_tag([TaskTag.COMPLEX, LANGGRAPH_WORKFLOW])
        graph_info = span.raw_attributes.get(LANGGRAPH_STRUCTURE, '{}')
        graph_info = json.loads(graph_info)
        task.children_node_graph = Graph().from_dict(graph_info)

    def _should_attach_to_graph(self) -> bool:
        return False

    def _update_framework_propagated_info(self, parent_task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any], task: HierarchicalTask=None):
        if self._is_workflow_span(span):
            self._update_workflow_task(parent_task, span)

    def _handle_after_children_framework(self, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        if self._is_workflow_span(span):
            parent_task = context[LAST_PARENTS][-1]
            if parent_task.name == ROOT_NAME:
                self._detect_dependencies(parent_task, context)

    def _update_node_task(self, task: HierarchicalTask, span: BaseSpanComposite) -> None:
        task.add_tag([LANGGRAPH_NODE])

    def is_applicable_task(self, task: HierarchicalTask,
                           context: dict[str, Any] | None = None) -> bool:
        """Check if this task should be processed by the LangGraph visitor."""
        return task.children_node_graph is not None

    def _detect_dependencies_between_siblings(self, parent_task: HierarchicalTask,
                                              context: dict[str, Any] | None = None) -> None:
        """
        Detect dependencies between sibling tasks based on LangGraph structure.
        """
        # Check if this is a LangGraph task
        if not self.is_applicable_task(parent_task, context):
            return

        # Process each child task
        for child in parent_task.children:
            node = parent_task.children_node_graph.get_node(child.name)
            self._process_edge_dependencies(parent_task, child, node, context)

    def _find_dependency_in_siblings(self, parent_task: HierarchicalTask,
                                     child: HierarchicalTask,
                                     source_node_name: str,
                                     context: dict[str, Any] | None = None) -> HierarchicalTask | None:
        """Find a suitable dependency in the siblings list for LangGraph."""
        for sibling in parent_task.children:
            if sibling == child:
                break

            if (self._has_valid_time_relationship(sibling, child) and
                    sibling.name == source_node_name and
                    all(d.name != child.name for d in sibling.dependees)):
                return sibling

        return None
