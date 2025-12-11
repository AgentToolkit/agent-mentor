from typing import Any

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.task_span_processing.base_task_processor import (
    BaseTaskGraphVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.crewgraph import CrewGraph
from agent_analytics.extensions.spans_processing.task_span_processing.graph_operations import (
    GraphOperationsMixin,
)
from ibm_agent_analytics_common.interfaces.task import TaskTag


class CrewAITaskGraphVisitor(BaseTaskGraphVisitor, GraphOperationsMixin):
    def __init__(self):
        super(CrewAITaskGraphVisitor, self).__init__()
        self.name = 'crewai processor'
        self.cg = None

    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        return span.raw_attributes.get(LANGTRACE_SERVICE, '') == CREWAI \
               or span.raw_attributes.get(SERVICE_NAME, '') == CREWAI \
               or CREWAI_VERSION in span.raw_attributes

    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        return self._is_applying_tool_span(span) \
               or self._is_crew_task_execute_span(span) \
               or self._is_crew_task_execution_span(span) \
               or self._is_agent_execution_span(span)

    def _is_crew_creation_span(self, span: BaseSpanComposite) -> bool:
        return span.name == CREW_KICKOFF

    def is_crew_task_creation_span(self, span: BaseSpanComposite) -> bool:
        return span.name == TASK_CREATED

    def _is_crew_task_execution_span(self, span: BaseSpanComposite) -> bool:
        return span.name == TASK_EXECUTION

    def _is_crew_task_execute_span(self, span: BaseSpanComposite) -> bool:
        return span.name == TASK_EXECUTE

    def _is_applying_tool_span(self, span: BaseSpanComposite) -> bool:
        return self.span_utils.is_tool_span(span)

    def _is_tool_usage_error_span(self, span: BaseSpanComposite) -> bool:
        return span.name == CREW_TOOL_USAGE_ERROR

    def _is_agent_execution_span(self, span: BaseSpanComposite) -> bool:
        return span.name == CREW_AGENT_EXECUTE_TASK

    def is_crew_manager(self, span: BaseSpanComposite) -> bool:
        return span.raw_attributes.get(CREW_AGENT_ROLE, '') in CREW_MANAGER

    def _extract_framework_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        if self._is_crew_task_execution_span(span):
            self._update_crew_task_key_id(task, span)

        elif self._is_crew_task_execute_span(span):
            self._update_crew_task_execution_from_span(task, span)

        elif self._is_applying_tool_span(span):
            self._update_tool_usage_task_from_span(task, span, context)

        elif self._is_agent_execution_span(span):
            self._update_agent_execution_task_from_span(task, span, context)

        # NOTE: LLM processing moved to dedicated LLMTaskProcessor
        # elif self.span_utils.is_llm_span(span):
        #     # Data extraction already done by LLMTaskProcessor (two-phase)
        #     # Only attach to graph here
        #     self._attach_llm_to_graph(task, span, context)

    def _update_crew_creation_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite) -> None:
        task.add_tag([TaskTag.COMPLEX, CREW_TAG])
        task.children_node_graph = CrewGraph.from_crew_created_span(span.raw_attributes)
        self.cg = task.children_node_graph

    @staticmethod
    def _update_crew_task_key_id(task: HierarchicalTask, span: BaseSpanComposite) -> None:
        task.attributes[TASK_KEY] = span.raw_attributes.get(TASK_KEY, '')
        task.attributes[TASK_ID] = span.raw_attributes.get(TASK_ID, '')

    def _update_crew_task_execution_from_span(self, task: HierarchicalTask, span: BaseSpanComposite) -> None:
        task.input = span.raw_attributes.get(CREW_TASK_EXEC_INPUT, {})
        task.output = span.raw_attributes.get(CREW_TASK_EXEC_OUTPUT, {})
        task.attributes.update(self.span_utils.add_fields_acc_to_startswith([CREWAI_TASK_STARTSWITH_ATTR], span.raw_attributes, {}))
        task.add_tag([TaskTag.COMPLEX, CREWAI_TASK_TAG])

    def _update_tool_usage_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        task.add_tag([TaskTag.TOOL_CALL])
        task.attributes.update(span.raw_attributes)
        task.attributes[TASK_ID] = task.id
        task.attributes[TRACELOOP_NAME] = span.raw_attributes.get(TRACELOOP_NAME, '')
        self._attach_tool_to_graph(task, context)

    def _update_agent_execution_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        task.add_tag([CREWAI_AGENT_TAG])
        task.output = span.raw_attributes.get(CREW_AGENT_OUTPUT, {})
        task.attributes.update(self.span_utils.add_fields_acc_to_startswith([CREW_AGENT], span.raw_attributes, {}))
        self._attach_agent_to_graph(task, span, context)

    def _get_graph_from_context(self, context: dict[str, Any]):
        """
        Override to use CrewAI's specific graph reference.

        Args:
            context: Context with parent information

        Returns:
            CrewAI's graph object
        """
        return self.cg

    def _attach_agent_to_graph(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        """
        Attach new agent execution to existing task graph.

        Args:
            task: The hierarchical task to attach
            span: Span containing raw attributes
            context: Context with parent information
        """
        agent_id = span.raw_attributes.get(CREW_AGENT_ID, '')
        if agent_id in self.cg.crew_agent_id_key_map.keys():
            task.attributes[TASK_ID] = self.cg.crew_agent_id_key_map[agent_id]

    def _attach_tool_to_graph(self, task: HierarchicalTask, context: dict[str, Any]) -> None:
        """
        CrewAI-specific implementation for attaching tool nodes.
        Searches for the appropriate parent node in the hierarchy.

        Args:
            task: The hierarchical task to attach
            context: Context with parent information
        """
        # Ensure the node is added to the graph
        if self.cg.get_node(task.id) is None:
            self._add_node_to_graph(task, context, graph=self.cg)

        # Search for the proper parent and manage parent-child relationships
        for i in range(1, len(context[LAST_PARENTS])):
            parent_task = context[LAST_PARENTS][-i]
            if parent_task.name in CREWAI_PROPER_NODE_NAMES:
                parent_task.add_tag([TaskTag.COMPLEX])
                if TASK_ID not in parent_task.attributes:
                    parent_task.attributes[TASK_ID] = parent_task.id

                parent_id = parent_task.attributes[TASK_ID]

                # Connect to parent
                self._attach_node_to_graph(parent_id, task.id, context, self.cg)
                self._connect_to_last_sibling(parent_task, task, context, self.cg)

                # Now add to parent's children
                if task.id not in [child.id for child in parent_task.children]:
                    task.parent = parent_task
                    parent_task.children.append(task)

                break
            else:
                if task.id in [child.id for child in parent_task.children]:
                    parent_task.children.pop(parent_task.children.index(task))

    def _should_attach_to_graph(self):
        return True

    def _update_framework_propagated_info(self, parent_task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any], task: HierarchicalTask = None):
        if self._is_crew_creation_span(span):
            self._update_crew_creation_task_from_span(parent_task, span)
        elif self._is_tool_usage_error_span(span):
            # update tool error counter
            parent_task.attributes[CREW_TOOL_USAGE_ERROR] = 1 + parent_task.attributes.get(CREW_TOOL_USAGE_ERROR, 0)
        elif self.is_crew_task_creation_span(span):
            self._update_crew_task_key_id(parent_task, span)
        elif self._is_agent_execution_span(span) and self.is_crew_manager(span):
            agent = self.cg.add_agent(span.raw_attributes)
            task.attributes[TASK_ID] = agent.key
            self._attach_node_to_graph(parent_task.attributes[TASK_ID], agent.key, context, self.cg)

            # Connect to last sibling before adding to children
            self._connect_to_last_sibling(parent_task, task, context, self.cg)

    def _handle_after_children_framework(self, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        if self._is_crew_creation_span(span):
            parent_task = context[LAST_PARENTS][-1]
            if parent_task.name == ROOT_NAME:
                self._detect_dependencies(parent_task, context)

    def is_applicable_task(self, task: HierarchicalTask,
                           context: dict[str, Any] | None = None) -> bool:
        """Check if this task should be processed by the CrewAI visitor."""
        return any(TASK_ID in child.attributes for child in task.children)

    def _detect_dependencies_between_siblings(self, parent_task: HierarchicalTask,
                                              context: dict[str, Any] | None = None) -> None:
        """
        Detect dependencies between sibling tasks based on CrewAI structure.
        """
        if not self.is_applicable_task(parent_task, context):
            return

        # Process each child task
        for child in parent_task.children:
            if TASK_ID not in child.attributes:
                continue

            node = self.cg.get_node(child.attributes.get(TASK_ID, ''))
            self._process_edge_dependencies(parent_task, child, node, context)
