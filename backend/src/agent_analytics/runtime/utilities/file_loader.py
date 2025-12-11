import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TextIO

from ibm_agent_analytics_common.interfaces.issues import IssueLevel

from agent_analytics.core.data.span_data import BaseSpanData
from agent_analytics.core.data.trace_data import BaseTraceData


class TraceLogParser:

    @staticmethod
    def detect_issue_in_span(span: BaseSpanData) -> IssueLevel | None:
        """Detect if a span contains an issue and return its level"""
        if not span.events:
            return None

        for event in span.events:
            attributes = event.attributes
            if not attributes:
                continue
            if attributes.get('issue_type') != 'Issue':
                continue



            # Parse level from the issue event
            level_str = attributes.get('level', 'WARNING')
            if level_str.startswith('IssueLevel.'):
                level_str = level_str.split('.')[1]

            try:
                level = IssueLevel(level_str.upper())
                return level  # Return the first issue level found
            except ValueError:
                return IssueLevel.WARNING

        return None

    @staticmethod
    def create_traces_from_spans(spans: list[BaseSpanData]) -> list[BaseTraceData]:
        """Create trace objects based on unique trace_ids from spans"""
        # Group spans by trace_id
        traces_dict = defaultdict(list)
        trace_agent_ids = defaultdict(set)
        trace_issues = defaultdict(lambda: defaultdict(int))

        for span in spans:
            trace_id = span.context.trace_id
            traces_dict[trace_id].append(span)

            # Collect agent_ids for this trace
            if (hasattr(span, 'raw_attributes') and
                span.raw_attributes and
                isinstance(span.raw_attributes, dict) and
                'agent.id' in span.raw_attributes):
                trace_agent_ids[trace_id].add(span.raw_attributes['agent.id'])

            issue_level = TraceLogParser.detect_issue_in_span(span)
            if issue_level:
                trace_issues[trace_id][issue_level.value] += 1

        # Create Trace objects
        traces = []
        for trace_id, trace_spans in traces_dict.items():
            # Find a good name for the trace
            #root_spans = [s for s in trace_spans if not s.root_id or s.root_id == trace_id]
            #trace_name = root_spans[0].name if root_spans else f"Trace-{trace_id}"

            # Calculate trace timespan
            start_time = min(span.start_time for span in trace_spans)
            end_time = max(span.end_time for span in trace_spans)
            service_name = None
            for span in trace_spans:
                if span.resource and span.resource.attributes and span.resource.attributes.service_name:
                    service_name = span.resource.attributes.service_name
                    break

            trace = BaseTraceData(
                element_id=trace_id,
                name=trace_id,
                start_time=start_time,
                end_time=end_time,
                service_name=service_name,
                num_of_spans=len(trace_spans),
                failures=dict(trace_issues[trace_id]),
                agent_ids=list(trace_agent_ids[trace_id])
            )
            traces.append(trace)

        return traces

    @staticmethod
    def extract_json_objects(logfile_content : str):
        # json_objects = []
        # braces_count = 0
        # current_object = ""

        # for char in logfile_content:
        #     current_object += char
        #     if char == '{':
        #         braces_count += 1
        #     elif char == '}':
        #         braces_count -= 1

        #     if braces_count == 0 and current_object.strip():
        #         try:
        #             json_objects.append(json.loads(current_object))
        #         except json.JSONDecodeError as e:
        #             print(f"Failed to parse object: {e}")
        #         current_object = ""

        # return json_objects
        json_objects, start = [],0

        while start < len(logfile_content):
            try:
                json_obj, end = json.JSONDecoder().raw_decode(logfile_content[start:].lstrip())  # Strip leading spaces
                json_objects.append(json_obj)
                start += end+1
            except json.JSONDecodeError:
                break
        return json_objects

    @staticmethod
    def sanitize_service_name(service_name: str) -> str:
        """Convert file path to valid service name"""
        # Get the file name without extension
        # import os
        # base_name = os.path.basename(service_name)
        # name_without_ext = os.path.splitext(base_name)[0]

        # Replace any non-alphanumeric chars with underscore
        import re
        clean_name = re.sub(r'[^a-zA-Z0-9-]', '_', service_name)

        return clean_name

    @staticmethod
    def parse_content(content: str) -> tuple[list[BaseTraceData], list[BaseSpanData], str | None]:
        """Parse content string containing multiple JSON spans"""
        spans = []
        json_objects = TraceLogParser.extract_json_objects(content)

        if type(json_objects) == list and \
                len(json_objects) > 0 and \
                "spans" in json_objects[0]:
            json_objects = json_objects[0]["spans"]

        for json_str in json_objects:
            try:
                span = BaseSpanData(**json_str)
                spans.append(span)
            except Exception as e:
                print(f"Error parsing span: {e}")
                continue

        service_name = TraceLogParser.sanitize_service_name(spans[0].resource.attributes.service_name)
        #in case of old timestamps update them
        validate_warning = TraceLogParser.validate_spans(spans, service_name)

        # Create traces from spans
        traces = TraceLogParser.create_traces_from_spans(spans)
        
        return traces, spans, validate_warning

    @staticmethod
    def update_spans_to_current_date(spans: list[BaseSpanData]):
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
        for span in spans:
            # Keep the original time but change the date
            original_tz = span.start_time.tzinfo
            original_time = span.start_time.time()
            new_datetime = datetime.combine(yesterday, original_time).replace(tzinfo=original_tz)
            span.start_time = new_datetime
            original_time = span.end_time.time()
            new_datetime = datetime.combine(yesterday, original_time).replace(tzinfo=original_tz)
            span.end_time = new_datetime

    @staticmethod
    def validate_spans(spans: list[BaseSpanData], sanitized_service_name: str) -> str | None:
        earliest_time = int(datetime.now(UTC).timestamp() * 1e9)
        for span in spans:
            start_time = TraceLogParser.parse_timestamp(span.start_time)
            if earliest_time == None or earliest_time > start_time:
                earliest_time = start_time
            if span.resource.attributes.service_name:
                span.resource.attributes.service_name = sanitized_service_name
        minutes_back = -(60 * 24 * 30)
        oldest_allowed = datetime.now(UTC) + timedelta(minutes=minutes_back)
        oldest_allowed = int(oldest_allowed.timestamp() * 1e9)
        if earliest_time <= oldest_allowed:
            # Instead of returning an error, call a function to update the spans
            TraceLogParser.update_spans_to_current_date(spans)
            return "Warning: Spans older than 30 days were refactored to yesterday's date."
        return None

    @staticmethod
    def parse_timestamp(timestamp: str | datetime) -> int:
        """Convert ISO timestamp to nanoseconds since epoch"""
        if type(timestamp) != datetime:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            dt = timestamp
        return int(dt.timestamp() * 1e9)

def parse_trace_logs(source: str | TextIO) -> tuple[list[BaseTraceData], list[BaseSpanData],str | None]:
    """
    Parse trace logs and return lists of traces and spans.
    
    Args:
        source: Either a string containing the log content or a file handle (TextIO)
        
    Returns:
        Tuple[List[BaseTrace], List[BaseSpan]]: Lists of parsed traces and spans
    """
    parser = TraceLogParser()

    if isinstance(source, str):
        return parser.parse_content(source)
    else:
        return parser.parse_content(source.read())
