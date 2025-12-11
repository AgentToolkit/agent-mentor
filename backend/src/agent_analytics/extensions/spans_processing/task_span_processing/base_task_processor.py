from abc import ABC, abstractmethod
from typing import Any

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask, HierarchicalTaskNamingUtils
from agent_analytics.extensions.spans_processing.common.utils import *
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.span_processor import SpanProcessor, VisitPhase
from agent_analytics.extensions.spans_processing.task_span_processing.span_utils import (
    SpanProcessingUtils,
)
from ibm_agent_analytics_common.interfaces.task import TaskTag


class BaseTaskGraphVisitor(SpanProcessor, ABC):
    """
    Base abstract class for task graph building visitors.

    Implements the core logic for building task graphs with framework-specific
    customization points.
    """

    def __init__(self):
        """Initialize the task graph visitor."""
        self.name = 'base processor'
        self.span_utils = SpanProcessingUtils()

    def should_process(self, span: BaseSpanComposite, context: dict[str, Any]) -> bool:
        """
        Determine if this visitor should process this span.

        Args:
            span: The span to check
            context: Shared context dictionary

        Returns:
            True if this visitor should process the span
        """
        return self._is_framework_span(span) or self._is_parent_framework_span(span, context)

    @abstractmethod
    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        """
        Check if the span is from the framework this visitor handles.ss

        Args:
            span: The span to check

        Returns:
            True if the span is from this visitor's framework
        """
        pass

    def _is_parent_framework_span(self, span, context: dict[str, Any]):
        """
        if a span does not contain a framework identifier, rule according to it's closest parent
        Args:
            span:
            context:

        Returns:

        """
        if not any(framework_identifier in span.raw_attributes for framework_identifier in FRAMEWORK_SPAN_IDENTIFIERS):
            last_parent = self.get_last_parent(context)
            if last_parent is None:
                return False
            return last_parent.attributes.get(FRAMEWORK, '') == self.name
        return False

    def get_last_parent(self, context: dict[str, Any]):
        last_parents = context.get(LAST_PARENTS, [])
        if len(last_parents):
            return last_parents[-1]

    @staticmethod
    def initialize_context(context: dict[str, Any]):
        defaults = {
            LAST_PARENTS: [],
            SPAN_ID_TO_TASK: {},
            ROOT_TASKS: [],
            AFTER_TRAVERSAL: False,
            TASKS: {}
        }

        for key, default_value in defaults.items():
            if key not in context:
                context[key] = default_value

    def process(self, span: BaseSpanComposite, phase: VisitPhase, context: dict[str, Any]) -> None:
        """
        Process a span to create or update tasks.

        Args:
            span: The span being processed
            phase: Current traversal phase
            context: Shared context dictionary
        """
        self.initialize_context(context)
        # create root task
        if ROOT_NAME not in context[SPAN_ID_TO_TASK].keys():
            root_task = self._ensure_root_task(context, span)
            context[LAST_PARENTS].append(root_task)

        # finish if span was already processed by another visitor
        if span.raw_attributes.get(PROCESSED, False):
            return
        if phase == VisitPhase.BEFORE_CHILDREN:
            # Handle before children phase - create task
            self._handle_before_children(span, context)
        else:
            # Handle after children phase - update task with collected data
            self._handle_after_children(span, context)

    def _handle_before_children(self, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        """
        Handle the span in the before-children phase.

        Args:
            span: The span being processed
            context: Shared context dictionary
        """
        task = self._create_task(span, None, context)
        if task is not None:
            if self.span_utils.is_llm_task_doubled(task, context):
                return
            # Set parent-child relationship
            current_parent = context[LAST_PARENTS][-1]
            current_parent.children.append(task)
            task.parent = current_parent
            current_parent.add_tag([TaskTag.COMPLEX])

            context[LAST_PARENTS].append(task)
            context[SPAN_ID_TO_TASK][span.context.span_id] = task

    def _handle_after_children(self, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        """
        Handle the span in the after-children phase.

        Args:
            span: The span being processed
            context: Shared context dictionary
        """
        self._handle_after_children_framework(span, context)
        created_task = context[SPAN_ID_TO_TASK].get(span.context.span_id, None)
        if created_task is not None:
            context[LAST_PARENTS].pop()

            self._detect_dependencies(created_task, context)

            span.raw_attributes[PROCESSED] = True
            del created_task.attributes[FRAMEWORK]

    def _handle_after_children_framework(self, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        pass

    def _create_task(self, span: BaseSpanComposite, parent_task: HierarchicalTask | None,
                     context: dict[str, Any]) -> HierarchicalTask | None:
        """
        Create a task from a span.

        Args:
            span: The span to create a task from
            parent_task: The parent task if any
            context: Shared context dictionary

        Returns:
            The created task, or None if no task should be created
        """
        if span.name in HTTP_SPANS:
            return None
        task = self._create_basic_task(span) if self._should_create_task(span) else None
        self._extract_task_from_span(task, span, context)
        return task

    def _create_basic_task(self, span: BaseSpanComposite) -> HierarchicalTask:
        trace_id = span.context.trace_id
        name = span.name
        span_id = span.context.span_id
        start_time = span.start_time
        end_time = span.end_time

        task = HierarchicalTask(
            element_id="task_" + str(span_id),
            root_id=trace_id,
            name=name,
            log_reference={
                'trace_id': trace_id,
                'span_id': span_id
            },
            start_time=start_time,
            end_time=end_time
        )
        return task

    def _extract_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        """
        Extract task information from a span.

        Args:
            task: The task to update
            span: The original span
            context: Shared context dictionary
        """
        if task is not None:
            task.input, task.output, task.attributes = self.span_utils.extract_input_output(span.raw_attributes)
            task.add_tag([TaskTag.TOOL_CALL])
            task.attributes[FRAMEWORK] = self.name

            # propagate the events from the span to the task
            task.events = span.events #TODO: Discuss implications with Hadar/Dany


            # Extract framework-specific information
            self._extract_framework_task_from_span(task, span, context)

            # finalize task name
            task.name = task.name.split(TASK_SUFF)[0]

        self._update_propagated_info(task, span, context)

    def extract_events_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        task = context[LAST_PARENTS][-1] if task is None else task
        for event in span.events:
            if event.attributes.get(ID, '').startswith(ISSUE_PRE):
                if ISSUE_SPAN_IDS not in task.attributes:
                    task.attributes[ISSUE_SPAN_IDS] = []
                task.attributes[ISSUE_SPAN_IDS].append(span.context.span_id)

            if event.attributes.get(ID, '').startswith(ANNOT_PRE):
                if ANNOT_SPAN_IDS not in task.attributes:
                    task.attributes[ANNOT_SPAN_IDS] = []
                task.attributes[ANNOT_SPAN_IDS].append(span.context.span_id)


    @abstractmethod
    def _extract_framework_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        pass

    @abstractmethod
    def _should_attach_to_graph(self) -> bool:
        pass

    def _update_propagated_info(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]):
        self.extract_events_from_span(task, span, context)

        current_parent = context[LAST_PARENTS][-1]
        if task is not None and TaskTag.LLM_CALL in task.tags \
                and TaskTag.LLM_CALL not in current_parent.tags:
            current_parent.add_tag([TaskTag.COMPLEX])
        # else:
        #     parent_task.attributes.update(attr)
        #     parent_task.metadata.update(metadata)
        #     current_parent.events.extend(task.events)

        self._update_framework_propagated_info(current_parent, span, context, task)

    @abstractmethod
    def _update_framework_propagated_info(self, parent_task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any], task: HierarchicalTask = None):
        pass

    def after_traversal(self, context: dict[str, Any]) -> None:
        """
        Called after all spans have been traversed for final processing.

        This method performs cleanup, ensures proper hierarchy, detects dependencies,
        and assigns prefixes to tasks.

        Args:
            context: Shared context dictionary
        """
        if not context.get(AFTER_TRAVERSAL, False):
            self._fix_root_times(context)

            # Assign hierarchical prefixes
            if len(context.get(ROOT_TASKS, [])):
                HierarchicalTaskNamingUtils.assign_hierarchical_prefixes(context[ROOT_TASKS])

            # save final attributes
            if SPAN_ID_TO_TASK in context.keys():
                context[TASKS] = {**context.get(TASKS, {}), **{task.id: task.flatten() for task in context[SPAN_ID_TO_TASK].values()}}
            else:
                context[TASKS] = {}
            context[AFTER_TRAVERSAL] = True

    def _ensure_root_task(self, context: dict[str, Any], span: BaseSpanComposite = None) -> HierarchicalTask:
        """
        Ensure there is a proper root task.

        If there are no root tasks or multiple root tasks, create a single root task
        to contain them all.

        Args:
            context: Shared context dictionary
        """
        # Create a new root task
        trace_id = span.context.trace_id if span is not None else get_unique_id()

        root_task = HierarchicalTask(
            element_id="root_task_" + trace_id,
            root_id=trace_id,
            name="_ROOT",
            log_reference={
                'trace_id': trace_id
            },
            start_time=0,
            end_time=0
        )

        root_task.add_tag([TaskTag.COMPLEX])

        context[ROOT_TASKS] = [root_task]
        context[SPAN_ID_TO_TASK][ROOT_NAME] = root_task
        return root_task

    def _fix_root_times(self, context: dict[str, Any]):
        """
        Update min/max times across all tasks
        """
        if SPAN_ID_TO_TASK not in context.keys():
            return
        min_start_time = None
        max_end_time = None

        for task in context[SPAN_ID_TO_TASK].values():
            if task.name == ROOT_NAME:
                continue
            if min_start_time is None or task.start_time < min_start_time:
                min_start_time = task.start_time
            if max_end_time is None or task.end_time > max_end_time:
                max_end_time = task.end_time
        root_task = context[SPAN_ID_TO_TASK].get(ROOT_NAME, None)
        if root_task is not None:
            root_task.start_time = min_start_time
            root_task.end_time = max_end_time

    @abstractmethod
    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        """determines whether this span should be converted into a task or not """
        pass

    def _detect_dependencies(self, task: HierarchicalTask, context: dict[str, Any] | None = None) -> None:
        """
        Detect dependencies between the children of the given task.
        This method is called by the traversal system for each task.

        Args:
            task: The task whose children's dependencies need to be detected
            context: Optional additional context
        """
        if not task.children:
            return

        # Sort children by start time for consistent processing
        task.children.sort(key=lambda t: t.start_time)

        # Process dependencies between this task's children
        self._detect_dependencies_between_siblings(task, context)

    def _detect_dependencies_between_siblings(self, parent_task: HierarchicalTask,
                                              context: dict[str, Any] | None = None) -> None:
        """
        Abstract method to be implemented by framework-specific visitors.
        Detects dependencies between sibling tasks.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def _has_valid_time_relationship(self, potential_dependency: HierarchicalTask,
                                     dependent_task: HierarchicalTask) -> bool:
        """
        Check if two tasks have a valid timing relationship for dependency.
        """
        return (potential_dependency.end_time and
                potential_dependency.end_time < dependent_task.start_time)

    def _add_dependency(self, dependent_task: HierarchicalTask,
                        dependency_task: HierarchicalTask) -> None:
        """
        Establish dependency relationship between two tasks.
        """
        dependent_task.dependent.append(dependency_task)
        dependency_task.dependees.append(dependent_task)

    def _process_edge_dependencies(self, parent_task: HierarchicalTask,
                                   child: HierarchicalTask,
                                   node: Any,
                                   context: dict[str, Any] | None = None) -> bool:
        """
        Process dependencies for a child based on its incoming edges.

        Args:
            parent_task: The parent task
            child: The child task whose dependencies are being detected
            node: The node corresponding to the child in the graph
            context: Optional additional context

        Returns:
            bool: Whether dependencies were found
        """
        if not node:
            return False

        dependencies_found = False

        # Check each incoming edge for potential dependencies
        for edge in node.incoming_edges:
            dependencies: list[HierarchicalTask] = []

            # Process each source node
            for source_node in edge.sources:
                # Check for special handling in subclasses
                special_result = self._handle_special_source_node(source_node, child, context)
                if special_result:
                    dependencies_found = True
                    break

                # Find dependency among siblings
                dependency = self._find_dependency_in_siblings(
                    parent_task, child, source_node.node_name, context
                )

                if dependency:
                    dependencies.append(dependency)

            # If we found all dependencies for this edge, establish the relationships
            if not dependencies_found and len(dependencies) == len(edge.sources):
                for dependent in dependencies:
                    self._add_dependency(child, dependent)
                dependencies_found = True
                break

        return dependencies_found

    def _handle_special_source_node(self, source_node: Any,
                                    child: HierarchicalTask,
                                    context: dict[str, Any] | None = None) -> bool:
        """
        Handle special source nodes. Override in subclasses if needed.

        Returns:
            bool: Whether the source node was handled specially
        """
        return False

    def _find_dependency_in_siblings(self, parent_task: HierarchicalTask,
                                     child: HierarchicalTask,
                                     source_node_name: str,
                                     context: dict[str, Any] | None = None) -> HierarchicalTask | None:
        """
        Default method to find a suitable dependency in the siblings list.
        Override in subclasses if implementation in subclass is different.
        """
        child_node_name = child.attributes.get(TASK_ID, '')

        for sibling in parent_task.children:
            if sibling == child:
                break

            if TASK_ID not in sibling.attributes:
                continue

            if (self._has_valid_time_relationship(sibling, child) and
                    sibling.attributes.get(TASK_ID, '') == source_node_name and
                    all(d.attributes.get(TASK_ID, '') != child_node_name for d in sibling.dependees)):
                return sibling

        return None

    @abstractmethod
    def is_applicable_task(self, task: HierarchicalTask,
                           context: dict[str, Any] | None = None) -> bool:
        """
        Determine if this visitor is applicable to the given task.
        Override in subclasses to implement framework-specific checks.
        """
        raise NotImplementedError("Subclasses must implement this method")
