import json
from typing import Any
from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.task import HierarchicalTask
from agent_analytics.extensions.spans_processing.config.const import *
from agent_analytics.extensions.spans_processing.span_processor import VisitPhase
from agent_analytics.extensions.spans_processing.task_span_processing.base_task_processor import (
    BaseTaskGraphVisitor,

)
from agent_analytics.extensions.spans_processing.task_span_processing.graph_operations import (
    GraphOperationsMixin,
)
from ibm_agent_analytics_common.interfaces.task import (
    TaskTag, 
    TaskStatus, 
    TaskState, 
    TaskKind, 
    TaskInput, 
    TaskOutput, 
)


class ManualTaskVisitor(BaseTaskGraphVisitor, GraphOperationsMixin):
    def __init__(self):
        super(ManualTaskVisitor, self).__init__()
        self.name = 'ManualTask processor'

    def _is_framework_span(self, span: BaseSpanComposite) -> bool:
        return self._is_manual_task_span(span)

    def _should_create_task(self, span: BaseSpanComposite) -> bool:
        return self._is_manual_task_span(span)

    def _is_manual_task_span(self, span: BaseSpanComposite) -> bool:
        return OTEL_TASK_ID in span.raw_attributes.keys()

    def _create_basic_task(self, span: BaseSpanComposite) -> HierarchicalTask:
        """
        Extract task attributes from a span and create a HierarchicalTask object.
        
        Args:
            span: The span component containing task data
            
        Returns:
            A HierarchicalTask with all attributes extracted from the span
        """
        
        attrs = span.raw_attributes
        
        # Extract core identifiers
        trace_id = span.context.trace_id
        span_id = span.context.span_id
        task_element_id = attrs.get('gen_ai.task.id', f"task_{span_id}")
        
        # Extract basic task info
        name = attrs.get('gen_ai.task.name', span.name.replace('.task', ''))
        tags = json.loads(attrs.get('gen_ai.task.tags', '[]')) if 'gen_ai.task.tags' in attrs else []
        
        # Extract kind
        kind = None
        if 'gen_ai.task.kind' in attrs:
            try:
                kind = TaskKind(attrs['gen_ai.task.kind'])
            except ValueError:
                kind = None
        
        # Extract state
        state = None
        if 'gen_ai.task.state' in attrs:
            try:
                state = TaskState(attrs['gen_ai.task.state'])
            except ValueError:
                state = None
        
        # Extract status
        status = None
        if 'gen_ai.task.status' in attrs:
            try:
                status = TaskStatus(attrs['gen_ai.task.status'])
            except ValueError:
                status = TaskStatus.UNKNOWN
        
        # Extract ALL input attributes
        task_input = None
        input_attrs = {k: v for k, v in attrs.items() if k.startswith('gen_ai.task.input.')}
        if input_attrs:
            task_input = TaskInput(
                goal=attrs.get('gen_ai.task.input.goal'),
                instructions=json.loads(attrs['gen_ai.task.input.instructions']) if 'gen_ai.task.input.instructions' in attrs else None,
                examples=json.loads(attrs['gen_ai.task.input.examples']) if 'gen_ai.task.input.examples' in attrs else None,
                data=attrs.get('gen_ai.task.input.data'),
                metadata=json.loads(attrs['gen_ai.task.input.metadata']) if 'gen_ai.task.input.metadata' in attrs else None
            )
        
        # Extract ALL output attributes
        task_output = None
        output_attrs = {k: v for k, v in attrs.items() if k.startswith('gen_ai.task.output.')}
        if output_attrs:
            # Parse data_values
            data_values = None
            if 'gen_ai.task.output.data.values' in attrs:
                raw = attrs['gen_ai.task.output.data.values']
                data_values = json.loads(raw) if isinstance(raw, str) else raw
            
            # Parse data_ranking
            data_ranking = None
            if 'gen_ai.task.output.data.ranking' in attrs:
                raw = attrs['gen_ai.task.output.data.ranking']
                data_ranking = json.loads(raw) if isinstance(raw, str) else raw
            
            # Parse metadata (stored as list with JSON string)
            output_metadata = None
            if 'gen_ai.task.output.metadata' in attrs:
                raw = attrs['gen_ai.task.output.metadata']
                if isinstance(raw, list) and len(raw) > 0:
                    output_metadata = json.loads(raw[0])
                elif isinstance(raw, str):
                    output_metadata = json.loads(raw)
                else:
                    output_metadata = raw
            
            task_output = TaskOutput(
                data=attrs.get('gen_ai.task.output.data'),
                data_values=data_values,
                data_ranking=data_ranking,
                metadata=output_metadata
            )
        
        # Extract additional OpenTelemetry fields
        parent_task_id = attrs.get('gen_ai.task.parent.id', span.parent_id)
        code_id = attrs.get('gen_ai.task.code.id')
        code_vendor = attrs.get('gen_ai.task.code.vendor')
        
        # Extract requester info
        requester_id = attrs.get('gen_ai.task.requester.id')
        requester_type = attrs.get('gen_ai.task.requester.type')
        requester_role = attrs.get('gen_ai.task.requester.role')
        request_id = attrs.get('gen_ai.task.request.id')
        session_id = attrs.get('gen_ai.task.session.id')
        
        # Extract scheduling info
        dependencies_ids = None
        if 'gen_ai.task.dependencies.ids' in attrs:
            raw = attrs['gen_ai.task.dependencies.ids']
            dependencies_ids = json.loads(raw) if isinstance(raw, str) else raw

        action_id = attrs.get('gen_ai.task.action.id')
        priority = attrs.get('gen_ai.task.priority')
        
        # Extract additional attributes (exclude gen_ai.task.* to avoid duplication)
        additional_attrs = {
            k: v for k, v in attrs.items() 
            if not k.startswith('gen_ai.task.')
        }
        
        # Build metadata
        metadata = {
            'span_kind': str(span.kind),
            'service_name': span.service_name
        }
        
        # Extract events from span
        events = []
        issues = []
        for event in span.events:
            event_dict = {
                'name': event.name,
                'timestamp': event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                'attributes': dict(event.attributes) if hasattr(event, 'attributes') else {}
            }
            events.append(event_dict)
            
            # Extract issues from exception events
            if event.name == 'exception' and hasattr(event, 'attributes'):
                exception_msg = event.attributes.get('exception.message')
                if exception_msg and exception_msg not in issues:
                    issues.append(exception_msg)
        
        # Build metrics from span data
        metrics = {}
        if span.duration_ms > 0:
            metrics['duration_ms'] = span.duration_ms
        
        # Create the HierarchicalTask
        task = HierarchicalTask(
            id=task_element_id,
            element_id=task_element_id,
            root_id=trace_id,
            name=name,
            tags=tags,
            kind=kind,
            state=state,
            status=status,
            input=task_input,
            output=task_output,
            start_time=span.start_time,
            end_time=span.end_time,
            events=events,
            issues=issues,
            metrics=metrics,
            metadata=metadata,
            log_reference={
                'trace_id': trace_id,
                'span_id': span_id,
                'parent_span_id': span.parent_id
            },
            attributes=additional_attrs,
            # x§parent_id=parent_task_id,
            code_id=code_id,
            code_vendor=code_vendor,
            requester_id=requester_id,
            requester_type=requester_type,
            requester_role=requester_role,
            request_id=request_id,
            session_id=session_id,
            dependencies_ids=dependencies_ids,
            priority=priority,
            dependent_ids=[],
            plugin_metadata_id=None,
            action_id=action_id,
            graph_id=None,
            parent_name=None
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
            # task.input, task.output, task.attributes = self.span_utils.extract_input_output(span.raw_attributes)
            task.add_tag([TaskTag.MANUAL])
            task.attributes[FRAMEWORK] = self.name

            # propagate the events from the span to the task
            task.events = span.events #TODO: Discuss implications with Hadar/Dany


            # Extract framework-specific information
            self._extract_framework_task_from_span(task, span, context)

            # finalize task name
            task.name = task.name.split(TASK_SUFF)[0]

        self._update_propagated_info(task, span, context)

    def _should_attach_to_graph(self) -> bool:
        return True

    def _extract_framework_task_from_span(self, task: HierarchicalTask, span: BaseSpanComposite, context: dict[str, Any]) -> None:
        pass 

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