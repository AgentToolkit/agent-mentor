from typing import Any

from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from ibm_agent_analytics_common.interfaces.task import TaskTag
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.task_span_processing.base_task_processor import (
    BaseTaskGraphVisitor,
)
from agent_analytics.extensions.spans_processing.task_span_processing.graph_operations import (
    GraphOperationsMixin,
)
from agent_analytics.extensions.spans_processing.common.langfuse import LangfuseObservationType
class LangfuseVisitor(BaseTaskGraphVisitor, GraphOperationsMixin):
    def __init__(self):
        super(LangfuseVisitor, self).__init__()
        self.name = 'Langfuse processor'
        self.observation_to_tag = {
            LangfuseObservationType.GENERATION: TaskTag.LLM_CALL,
            LangfuseObservationType.TOOL: TaskTag.TOOL_CALL,
            LangfuseObservationType.RETRIEVER: TaskTag.DB_CALL, 
        }

    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        # langfuse observation
        return (span.raw_attributes.get(INSTRUMENATATION_SDK_NAME) == LANGFUSE_SDK_NAME
                or span.raw_attributes.get(IS_LANGFUSE_OBSERVATION) == True)
        

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

    # always 
    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        # TODO: need to implement wich observations we should convert to task
        return True 

    def _create_basic_task(self, span: BaseSpanComposite) -> HierarchicalTask:
        trace_id = span.context.trace_id
        name = span.name
        span_id = span.context.span_id
        start_time = span.start_time
        end_time = span.end_time

        task = HierarchicalTask(
            element_id="task_" + str(span_id),
            root_id=trace_id,
            name=name.removesuffix('.task'),
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
            # langfuse type mapping 
            observation_type = span.raw_attributes.get('langfuse.observation.type', 'SPAN')
            observation_tag = self.observation_to_tag.get(observation_type, TaskTag.TOOL_CALL)
            task.add_tag([observation_tag])
            task.attributes[FRAMEWORK] = self.name

            # propagate the events from the span to the task
            task.events = span.events #TODO: Discuss implications with Hadar/Dany

            # if self.span_utils.is_llm_span(span):
            #     self.openai_processor.process_llm_task(task, span)

            #TODO: add special processing for langfuse LLM observation 
            if observation_type == LangfuseObservationType.GENERATION:
                self._update_LLM_task(task, span)
                # self.openai_processor.process_llm_task(task, span)

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
    
    def _update_LLM_task(self, task: HierarchicalTask, span: BaseSpanComposite) -> None:
        usage_details = span.raw_attributes.get('langfuse.usage_details', {})
        if 'input' in usage_details: 
            task.attributes[LLM_INPUT_TOKENS] = usage_details['input']
        if 'output' in usage_details:
            task.attributes[LLM_OUTPUT_TOKENS] = usage_details['output']
        if 'total' in usage_details:
            task.attributes[LLM_TOTAL_TOKENS] = usage_details['total']
        
    def _extract_framework_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        pass 

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
