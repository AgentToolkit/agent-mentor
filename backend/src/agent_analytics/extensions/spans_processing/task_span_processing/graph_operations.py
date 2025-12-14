from typing import Any

from agent_analytics_common.interfaces.graph import Graph

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.extensions.spans_processing.config.const import *


class GraphOperationsMixin:
    """
    A mixin that provides graph operation capabilities to visitors.
    Visitors that need graph operations can include this mixin.
    """

    def _get_parent_node_id(self, context: dict[str, Any], return_parent=False) -> str | None:
        """
        Find the ID of the parent task from context.

        Args:
            context: Context dictionary containing parent information
            return_parent: If True, return both the parent ID and the parent task object

        Returns:
            If return_parent is False, returns the ID of the parent task, or None if not found
            If return_parent is True, returns a tuple of (parent_id, parent_task), or None if not found
        """
        if not context or LAST_PARENTS not in context or not context[LAST_PARENTS]:
            return None, None if return_parent else None

        parent_task = context[LAST_PARENTS][-1]

        if TASK_ID in parent_task.attributes:
            parent_id = parent_task.attributes[TASK_ID]
            return (parent_id, parent_task) if return_parent else parent_id

        return None, None if return_parent else None

    def _get_graph_from_context(self, context: dict[str, Any]):
        """
        Get the appropriate graph object based on context.
        Each graph-capable visitor should override this method.

        Args:
            context: Context with parent information

        Returns:
            Graph object to use for connections
        """
        parent_task = context[LAST_PARENTS][-1] if context and LAST_PARENTS in context else None
        if parent_task:
            return parent_task.children_node_graph
        return None

    def _attach_node_to_graph(self, source_id: str, destination_id: str, context: dict[str, Any], graph: Graph=None) -> None:
        """
        Connect two nodes in the appropriate graph based on context.

        Args:
            source_id: ID of the source node
            destination_id: ID of the destination node
            context: Context containing parent information
        """
        graph = graph if graph is not None else self._get_graph_from_context(context)
        if graph:
            graph.add_edge(source_names=source_id, destination_names=destination_id)

    def _add_node_to_graph(self, task: HierarchicalTask, context: dict[str, Any], graph: Graph=None) -> str:
        """
        Generic method to add a node to the graph.
        This is separate from attaching (creating an edge).

        Args:
            task: Task to add as node
            context: Context with graph information

        Returns:
            The ID of the added node
        """
        graph = graph if graph is not None else self._get_graph_from_context(context)
        if graph:
            graph.add_node(task.id)

        # Use task.id as the node ID
        task.attributes[TASK_ID] = task.id
        return task.id


    def _simple_attach_to_parent(self, task: HierarchicalTask, context: dict[str, Any]) -> None:
        """
        Simple implementation to attach a node to its immediate parent.

        Args:
            task: Task to attach
            context: Context with parent information
        """
        # Ensure task is added as a node first
        node_id = self._add_node_to_graph(task, context)

        # Connect to immediate parent
        parent_id, parent_task = self._get_parent_node_id(context, True)
        if parent_id:
            self._attach_node_to_graph(parent_id, node_id, context)

            self._connect_to_last_sibling(parent_task, task, context)

    def _attach_tool_to_graph(self, task: HierarchicalTask, context: dict[str, Any]) -> None:
        """
        Default implementation for attaching tool to graph.
        Uses simple parent attachment by default.

        Args:
            task: Task to attach
            context: Context with parent information
        """
        self._simple_attach_to_parent(task, context)

    def _attach_llm_to_graph(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        """
        Attach LLM execution to existing task graph.

        Args:
            task: The hierarchical task to attach
            span: Span containing raw attributes
            context: Context with parent information
        """
        # Set task ID first
        task.attributes[TASK_ID] = task.id

        # Use the simple attach method that handles adding the node and connections
        self._simple_attach_to_parent(task, context)

    def _connect_to_last_sibling(self, parent_task, task: HierarchicalTask, context: dict[str, Any], graph: Graph=None) -> None:
        """
        Connect the current task to the last sibling under the same parent.

        Args:
            parent_task: The parent task
            task: Current task to connect
            context: Context with graph information
        """
        if not parent_task.children:
            return

        last_child = parent_task.children[-1]
        if last_child == task:
            return

        # check timing compatibility
        if last_child.end_time > task.start_time:
            return

        # Create an edge from the last sibling to the current task
        if TASK_ID in last_child.attributes and TASK_ID in task.attributes:
            source_id = last_child.attributes[TASK_ID]
            dest_id = task.attributes[TASK_ID]
            self._attach_node_to_graph(source_id, dest_id, context, graph)
