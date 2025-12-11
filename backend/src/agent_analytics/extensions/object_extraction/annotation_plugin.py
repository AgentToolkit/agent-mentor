from datetime import UTC, datetime
from typing import Any

from ibm_agent_analytics_common.interfaces.annotations import DataAnnotation
from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.span_data import SpanEvent
from agent_analytics.core.data_composite.annotation import BaseAnnotation
from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.extensions.spans_processing.config.const import ANNOT_SPAN_IDS


def extract_annotation_event_data(event: SpanEvent) -> dict[str, Any] | None:
    """Extract annotation-related data from span events.
    
    Args:
        event: A span event dictionary
        
    Returns:
        Optional[Dict[str, Any]]: Extracted annotation data if the event represents an annotation, None otherwise
    """
    attributes = event.attributes
    if not attributes:
        return None

    event_id = event.attributes.get('id', '')
    if 'DataAnnotation' not in event_id:
        return None

    # Try to parse the annotation type
    annotation_type_str = attributes.get('annotation_type', '')
    try:
        annotation_type = DataAnnotation.Type(annotation_type_str)
    except ValueError:
        # Default to RAW_TEXT if the type is invalid
        annotation_type = DataAnnotation.Type.RAW_TEXT

     # Process timestamp
    timestamp_str = event.timestamp
    timestamp = None
    if timestamp_str:
        try:
            if 'T' in timestamp_str:
                timestamp_str = timestamp_str.replace('Z', '+00:00')
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.fromtimestamp(float(timestamp_str), tz=UTC)
        except (ValueError, TypeError):
            timestamp = event.timestamp
    else:
        timestamp = datetime.now(UTC)

    # Check which format of annotation data we have
    has_segment_data = ('path_to_string' in attributes or
                       'segment_start' in attributes or
                       'segment_end' in attributes)

    has_content_data = ('annotation_title' in attributes or
                       'annotation_content' in attributes)

    result = {
        'annotation_type': annotation_type,
        'timestamp': timestamp
    }

    # Handle segment-based annotation data
    if has_segment_data:
        result['path_to_string'] = attributes.get('path_to_string')
        # Convert to integers if present, otherwise leave as None
        if 'segment_start' in attributes:
            try:
                result['segment_start'] = int(attributes['segment_start'])
            except (ValueError, TypeError):
                result['segment_start'] = int(timestamp.timestamp())
        else:
            result['segment_start'] = int(timestamp.timestamp())

        if 'segment_end' in attributes:
            try:
                result['segment_end'] = int(attributes['segment_end'])
            except (ValueError, TypeError):
                result['segment_end'] = None
        else:
            result['segment_end'] = None

        result['annotation_title'] = None
        result['annotation_content'] = None

    # Handle content-based annotation data
    elif has_content_data:
        result['path_to_string'] = None
        result['segment_start'] = int(timestamp.timestamp())
        result['segment_end'] = None
        result['annotation_title'] = attributes.get('annotation_title')
        result['annotation_content'] = attributes.get('annotation_content')

    # If neither format is present, skip this event
    else:
        return None

    result['id'] = attributes.get('id')

    return result

async def create_annotation_from_span(span: BaseSpanComposite, all_tasks: list[TaskComposite]) -> list[BaseAnnotation]:
    """Create Annotation objects from a span's events.
    
    Args:
        span: A BaseSpan object
        data_manager: The data manager to use for Task lookup
        
    Returns:
        List[Annotation]: List of created Annotation objects
    """

    annotations = []

    # Skip if span has no events
    if not span.events:
        return annotations

    # Calculate task_id for this span
    #related_to_ids = []
    #related_to_types = []
    related_to=[]
    for task in all_tasks:
        if ANNOT_SPAN_IDS in task.attributes.keys() and span.context.span_id in task.attributes[ANNOT_SPAN_IDS]:
            related_to.append(task)
            #related_to_ids.append(task.artifact_id)
            #related_to_types.append(TypeResolutionUtils.get_fully_qualified_type_name_for_type(Task))

    for event in span.events:
        annotation_data = extract_annotation_event_data(event)
        if not annotation_data:
            continue

        # Create the Annotation object
        annotation = BaseAnnotation(
            root=span.context.trace_id,
            element_id=f'annotation_{span.element_id}_{annotation_data["timestamp"]}_{annotation_data.get("id")}',
            name=annotation_data.get('id') or f'annotation_{span.element_id}_{annotation_data["timestamp"]}',
            description=annotation_data.get('id') or f'annotation_{span.element_id}_{annotation_data["timestamp"]}',
            annotation_type=annotation_data['annotation_type'],
            path_to_string=annotation_data['path_to_string'],
            segment_start=annotation_data['segment_start'],
            segment_end=annotation_data['segment_end'],
            annotation_title=annotation_data['annotation_title'],
            annotation_content=annotation_data['annotation_content'],
            related_to=related_to
            # related_to_ids=related_to_ids,
            # related_to_types=related_to_types
        )
        annotations.append(annotation)

    return annotations

class AnnotationAnalyticsInput(BaseModel):
    trace_id: str | None = Field(description="Id of the trace to run this analytic on", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group to run this analytic on", default=None)
    spans: list[dict[str, Any]] | None = Field(description="Spans to run this analytic on", default=None)

class AnnotationAnalyticsOutput(BaseModel):
    trace_id: str | None = Field(description="Id of the trace this analytic was run on", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group this analytic was run on", default=None)
    annotations: list[dict[str, Any]] = Field(..., description="List of extracted analytics")

class AnnotationAnalytics(BaseAnalyticsPlugin):
    @classmethod
    def get_input_model(cls) -> type[AnnotationAnalyticsInput]:
        return AnnotationAnalyticsInput

    @classmethod
    def get_output_model(cls) -> type[AnnotationAnalyticsOutput]:
        return AnnotationAnalyticsOutput

    async def _execute(self, analytics_id: str, data_manager: DataManager, input_data: AnnotationAnalyticsInput, config: dict[str, Any]) -> ExecutionResult:
        input_trace_id = input_data.trace_id
        trace_group_id = input_data.trace_group_id
        spans = input_data.spans

        if not input_trace_id and not spans and not trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="No relevant input provided for the analytics (neither trace_id, group_trace_id nor span list is given)"
                )
            )

        all_annotations = []

        # Case 1: Process a trace group
        if trace_group_id:
            # Fetch the TraceGroup object
            trace_group = await TraceGroupComposite.get_by_id(data_manager=data_manager,id=trace_group_id)
            if not trace_group:
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="DataError",
                        message=f"No trace group found with id {trace_group_id}"
                    )
                )

            trace_ids = trace_group.traces_ids
            # Process each trace in the group
            for trace_id in trace_ids:
                spans = await BaseSpanComposite.get_spans_for_trace(data_manager=data_manager,trace_id=trace_id)
                if not spans:
                    continue  # Skip traces with no spans

                # Process this trace's spans
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager,trace_id=trace_id)
                annotations = await self._process_spans(spans, tasks)

                all_annotations.extend(annotations)

        # Case 2: Process a single trace or provided spans
        else:
            # Fetch all spans for this trace if not provided
            if not spans:
                spans_list = await BaseSpanComposite.get_spans_for_trace(data_manager=data_manager,trace_id=input_trace_id)
            else:
                input_trace_id = spans[0].context.trace_id if spans else None
                spans_list = [BaseSpanComposite.from_dict(data_manager, span_dict) for span_dict in spans]

            if not spans_list:
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.FAILURE,
                    error=ExecutionError(
                        error_type="DataError",
                        message=f"No spans found for trace {input_trace_id}"
                    )
                )

            # Process this trace's spans
            tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager,trace_id=input_trace_id)
            all_annotations = await self._process_spans(spans_list, tasks)

        # Bulk store all issues after successful processing of all traces
        stored_annotations=[]
        if all_annotations:
            stored_annotations = await BaseAnnotation.bulk_store(data_manager=data_manager,base_annotations=all_annotations)

        # Create output based on what was processed
        annotation_list_dicts=[annotation.model_dump() for annotation in stored_annotations]


        output = AnnotationAnalyticsOutput(
            trace_id=input_trace_id if not trace_group_id else None,
            trace_group_id=trace_group_id if trace_group_id else None,
            annotations=annotation_list_dicts
        )

        return ExecutionResult(
            analytics_id=analytics_id,
            status=ExecutionStatus.SUCCESS,
            output=output
        )

    async def _process_spans(self, spans: list[BaseSpanComposite], tasks: list[TaskComposite]) -> list[BaseAnnotation]:
        """Helper method to process spans and generate annotations without storing them"""
        all_annotations = []

        for span in spans:
            annotations = await create_annotation_from_span(span, tasks)
            all_annotations.extend(annotations)

        return all_annotations
