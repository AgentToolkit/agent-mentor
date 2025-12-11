from datetime import UTC, datetime
from typing import Any

from ibm_agent_analytics_common.interfaces.issues import IssueLevel
from pydantic import BaseModel, Field

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.span_data import SpanEvent
from agent_analytics.core.data_composite.base_span import BaseSpanComposite
from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.issue import BaseIssue
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite
from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)
from agent_analytics.extensions.spans_processing.config.const import ISSUE_SPAN_IDS


def extract_issue_event_data(event: SpanEvent) -> dict[str, Any] | None:
    """Extract issue-related data from span events.
    
    Args:
        event: A span event dictionary
        
    Returns:
        Optional[Dict[str, Any]]: Extracted issue data if the event represents an issue, None otherwise
    """
    # Check if the event name contains '.issue' (must be exact substring)
    attributes = event.attributes
    if not attributes:
        return None

    if attributes.get('issue_type') != 'Issue':
        return None

    # Parse the timestamp
    timestamp_str = attributes.get('timestamp', '')
    if not timestamp_str:
        timestamp = datetime.now(UTC).isoformat()
    else:
        timestamp = timestamp_str


    # Parse level
    level_str = attributes.get('level', 'WARNING')
    if level_str.startswith('IssueLevel.'):
        level_str = level_str.split('.')[1]

    try:
        level = IssueLevel(level_str.upper())
    except ValueError:
        level = IssueLevel.WARNING

    # TODO: change the mechanism to extract related to from SDK data
    #  Parse related_to_ids and effect
    related_to_ids = []
    if 'related_to_ids' in attributes:
        if isinstance(attributes['related_to_ids'], list):
            related_to_ids = attributes['related_to_ids']
        elif isinstance(attributes['related_to_ids'], str):
            related_to_ids = [id.strip() for id in attributes['related_to_ids'].split(',')]

    effects = []
    if 'effect' in attributes:
        if isinstance(attributes['effect'], list):
            effects = attributes['effect']
        elif isinstance(attributes['effect'], str):
            effects = [effects.strip() for effects in attributes['effect'].split(',')]

    # Ensure effects list matches related_to_ids list length
    if related_to_ids and effects and len(effects) == 1 and len(related_to_ids) > 1:
        effects = effects * len(related_to_ids)

    # Use explicit fields where available, fall back to inferred values
    return {
        'title': attributes.get('name', attributes.get('title', event.name)),
        'description': attributes.get('description', 'No description available'),
        'timestamp': timestamp,
        'level': level,
        'related_to_ids': related_to_ids, #TODO: need to add logic here to extract types as well
        'related_to_types': attributes.get('related_to_types', []),
        'effect': effects,
        'related_to': []
    }

def create_issue_from_span(span: BaseSpanComposite , all_tasks: list[TaskComposite]) -> list[BaseIssue]:
    """Create Issue objects from a span's events.
    
    Args:
        span: A BaseSpan object
        
    Returns:
        List[Issue]: List of created Issue objects
    """
    issues = []

    # Skip if span has no events
    if not span.events:
        return issues

    for event in span.events:
        issue_data = extract_issue_event_data(event)
        if not issue_data:
            continue

        issue_data['related_to'].append(span)
        #issue_data['related_to_ids'].append(span.context.span_id) #TODO why not element_id? if this span.context.span_id will be different than the element_id in BaseSpan , we will not be able to fetch it anyway..
        #issue_data['related_to_types'].append(TypeResolutionUtils.get_fully_qualified_type_name_for_type(BaseSpan))

        ###adding releated tasks by trace_id
        for task in all_tasks:
            if ISSUE_SPAN_IDS in task.attributes.keys() and span.context.span_id in task.attributes[ISSUE_SPAN_IDS]:
                issue_data['related_to'].append(task)
                #issue_data['related_to_ids'].append(task.artifact_id)
                #issue_data['related_to_types'].append(TypeResolutionUtils.get_fully_qualified_type_name_for_type(Task))


        # Create the Issue object
        issue = BaseIssue(
            root = span.context.trace_id,
            element_id = issue_data.get('id', f'issue_{span.element_id}_{issue_data["timestamp"]}_{issue_data["title"]}'),
            name=issue_data.get('title') if issue_data.get('title') else f'{issue_data["level"]} issue at {issue_data["timestamp"]}',
            description=issue_data['description'],
            timestamp=issue_data['timestamp'],
            level=issue_data['level'],
            #related_to_ids=issue_data['related_to_ids'],
            #related_to_types=issue_data['related_to_types'],
            related_to=issue_data['related_to'],
            effect=issue_data['effect']
        )
        issues.append(issue)

    return issues

class IssueAnalyticsInput(BaseModel):
    trace_id: str | None = Field(description="Id of the trace to run this analytic on", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group to run this analytic on", default=None)
    spans: list[dict[str, Any]] | None = Field(description="Spans to run this analytic on", default=None)

class IssueAnalyticsOutput(BaseModel):
    trace_id: str | None = Field(description="Id of the trace this analytic was run on", default=None)
    trace_group_id: str | None = Field(description="Id of the trace group this analytic was run on", default=None)
    issues: list[dict[str, Any]] = Field(..., description="List of extracted issues")

class IssueAnalytics(BaseAnalyticsPlugin):
    @classmethod
    def get_input_model(cls) -> type[IssueAnalyticsInput]:
        return IssueAnalyticsInput

    @classmethod
    def get_output_model(cls) -> type[IssueAnalyticsOutput]:
        return IssueAnalyticsOutput

    async def _execute(self, analytics_id: str, data_manager: DataManager, input_data: IssueAnalyticsInput, config: dict[str, Any]) -> ExecutionResult:
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

        all_issues = []

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
                issues = await self._process_spans(spans, tasks)
                all_issues.extend(issues)

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
            tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager,trace_id=input_trace_id)
            # Process this trace's spans
            all_issues = await self._process_spans(spans_list, tasks)

        # Bulk store all issues after successful processing of all traces
        stored_issues=[]
        if all_issues:
            stored_issues= await BaseIssue.bulk_store(data_manager=data_manager,base_issues=all_issues)

        issue_list_dicts=[issue.model_dump() for issue in stored_issues]

        output = IssueAnalyticsOutput(
            trace_id=input_trace_id if not trace_group_id else None,
            trace_group_id=trace_group_id if trace_group_id else None,
            issues=issue_list_dicts
        )

        return ExecutionResult(
            analytics_id=analytics_id,
            status=ExecutionStatus.SUCCESS,
            output=output
        )

    async def _process_spans(self, spans: list[BaseSpanComposite], tasks: list[TaskComposite]) -> list[BaseIssue]:
        """Helper method to process spans and generate issues without storing them"""
        all_issues = []

        for span in spans:
            issues = create_issue_from_span(span, tasks)
            all_issues.extend(issues)

        return all_issues
