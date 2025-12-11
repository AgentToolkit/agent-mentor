from typing import Any

from opentelemetry import trace

from agent_analytics_common.interfaces.resources import Resource
from agent_analytics_common.interfaces.events import AIEvent
from agent_analytics_common.interfaces.elements import Element
from agent_analytics_common.interfaces.annotations import DataAnnotation
from agent_analytics_common.interfaces.issues import Issue
from agent_analytics_common.interfaces.metric import Metric

import datetime
import inspect
from enum import Enum
import json


class AIEventTracer:
    """Captures AI-related events."""

    @staticmethod
    def _get_caller_metadata():
        # Get caller function
        caller_frame = inspect.stack()[2]
        caller_filename = caller_frame.filename
        caller_function = caller_frame.function
        return caller_filename, caller_function

    @staticmethod
    def _prepare_attribute_for_otel(value: Any) -> Any:
        """Prepares values for OpenTelemetry attributes."""
        if value is None:
            return None
        elif isinstance(value, (str, bool, int, float)):
            return value
        elif isinstance(value, Enum):
            return str(value)
        elif isinstance(value, datetime.datetime):
            return value.isoformat()
        elif isinstance(value, list):
            if all(isinstance(item, (str, bool, int, float)) for item in value):
                return ", ".join(str(item) for item in value)
            else:
                try:
                    return json.dumps([AIEventTracer._prepare_attribute_for_otel(item) for item in value])
                except (TypeError, ValueError):
                    return str(value)
        elif isinstance(value, dict):
            try:
                return json.dumps({k: AIEventTracer._prepare_attribute_for_otel(v) for k, v in value.items()})
            except (TypeError, ValueError):
                return str(value)
        else:
            try:
                # Try to convert to dict if it's a Pydantic model
                if hasattr(value, "dict"):
                    return json.dumps(value.dict())
                # Otherwise, use default JSON serialization
                return json.dumps(value)
            except (TypeError, ValueError):
                return str(value)

    @staticmethod
    def _get_element_base_attributes(element: Element) -> dict:
        """Extract all base Element attributes."""
        attributes = {
            "id": element.element_id,
            "name": element.name,
            "description": element.description,
        }

        # Handle tags
        if element.tags:
            attributes["tags"] = AIEventTracer._prepare_attribute_for_otel(element.tags)

        # Handle attributes dictionary
        if element.attributes:
            for key, value in element.attributes.items():
                attributes[f"attr_{key}"] = AIEventTracer._prepare_attribute_for_otel(value)

        return attributes

    @staticmethod
    def capture_resource(resource: Resource):
        """Captures Resource objects in spans."""
        current_span = trace.get_current_span()

        # Prepare attributes up front
        attributes = AIEventTracer._get_element_base_attributes(resource)
        attributes.update({
            "category": str(resource.category) if resource.category else None,
            "format": resource.format
        })

        try:
            attributes["payload"] = json.dumps(resource.payload) if resource.payload is not None else None
        except (TypeError, ValueError):
            attributes["payload"] = str(resource.payload) if resource.payload is not None else None

        if hasattr(resource, "dict"):
            resource_dict = resource.dict()
            for key, value in resource_dict.items():
                if key not in attributes and key not in ["attributes", "tags", "payload"]:
                    attributes[key] = AIEventTracer._prepare_attribute_for_otel(value)

        attributes = {k: v for k, v in attributes.items() if v is not None}
        event_name = f"{resource.name or resource.element_id}.resource"

        if current_span.get_span_context().is_valid and current_span.is_recording():
            current_span.add_event(name=event_name, attributes=attributes)
        else:
            caller_filename, caller_function = AIEventTracer._get_caller_metadata()
            tracer = trace.get_tracer(caller_filename)
            with tracer.start_as_current_span(f"{caller_function}.resource") as record_span:
                record_span.add_event(name=event_name, attributes=attributes)

    @staticmethod
    def capture_data_annotation(annotation: DataAnnotation):
        """Captures DataAnnotation objects in spans."""
        current_span = trace.get_current_span()

        # Prepare attributes up front
        attributes = AIEventTracer._get_element_base_attributes(annotation)

        if annotation.path_to_string is not None:
            attributes["path_to_string"] = annotation.path_to_string

        if annotation.segment_start is not None:
            attributes["segment_start"] = annotation.segment_start

        if annotation.segment_end is not None:
            attributes["segment_end"] = annotation.segment_end

        if annotation.annotation_type is not None:
            attributes["annotation_type"] = str(annotation.annotation_type)

        if annotation.annotation_title is not None:
            attributes["annotation_title"] = annotation.annotation_title

        if annotation.annotation_content is not None:
            attributes["annotation_content"] = annotation.annotation_content

        if hasattr(annotation, "model_dump"):
            annotation_dict = annotation.model_dump()
        elif hasattr(annotation, "dict"):
            annotation_dict = annotation.dict()
        else:
            annotation_dict = {}

        for key, value in annotation_dict.items():
            if (key not in attributes and
                key not in ["attributes", "tags", "id", "path_to_string", "segment_start",
                            "segment_end", "annotation_type", "annotation_title", "annotation_content",
                            "type", "owner_id", "name", "description"]):
                attributes[key] = AIEventTracer._prepare_attribute_for_otel(value)

        attributes = {k: v for k, v in attributes.items() if v is not None}
        event_name = f"{annotation.name or annotation.element_id}.data_annotation"

        if current_span.get_span_context().is_valid and current_span.is_recording():
            current_span.add_event(name=event_name, attributes=attributes)
        else:
            caller_filename, caller_function = AIEventTracer._get_caller_metadata()
            tracer = trace.get_tracer(caller_filename)
            with tracer.start_as_current_span(f"{caller_function}.data_annotation") as record_span:
                record_span.add_event(name=event_name, attributes=attributes)

    @staticmethod
    def capture_ai_event(ai_event: AIEvent):
        """Captures AIEvent objects in spans."""
        current_span = trace.get_current_span()

        # Prepare attributes up front
        attributes = AIEventTracer._get_element_base_attributes(ai_event)
        attributes.update({
            "status": str(ai_event.status) if ai_event.status else None,
        })

        if hasattr(ai_event, "timestamp"):
            attributes["event_timestamp"] = AIEventTracer._prepare_attribute_for_otel(ai_event.timestamp)

        if hasattr(ai_event, "dict"):
            ai_event_dict = ai_event.dict()
            for key, value in ai_event_dict.items():
                if key not in attributes and key not in ["attributes", "tags", "status"]:
                    attributes[f"event_{key}"] = AIEventTracer._prepare_attribute_for_otel(value)

        attributes = {k: v for k, v in attributes.items() if v is not None}
        event_name = f"{ai_event.name or ai_event.element_id}.ai_event"

        if current_span.get_span_context().is_valid and current_span.is_recording():
            current_span.add_event(name=event_name, attributes=attributes)
        else:
            caller_filename, caller_function = AIEventTracer._get_caller_metadata()
            tracer = trace.get_tracer(caller_filename)
            with tracer.start_as_current_span(f"{caller_function}.ai_event") as record_span:
                record_span.add_event(name=event_name, attributes=attributes)

    @staticmethod
    def capture_issue(issue: Issue):
        """Captures Issue objects in spans."""
        current_span = trace.get_current_span()

        # Prepare attributes up front
        attributes = AIEventTracer._get_element_base_attributes(issue)
        attributes.update({
            "level": str(issue.level) if issue.level else None,
            "timestamp": issue.timestamp,
        })

        if issue.related_to_ids:
            attributes["related_to_ids"] = AIEventTracer._prepare_attribute_for_otel(issue.related_to_ids)

        if issue.effect:
            attributes["effect"] = AIEventTracer._prepare_attribute_for_otel(issue.effect)

        if hasattr(issue, "dict"):
            issue_dict = issue.dict()
            for key, value in issue_dict.items():
                if (
                    key not in attributes
                    and key not in ["attributes", "tags", "level", "timestamp", "related_to_ids", "effect"]
                ):
                    attributes[f"issue_{key}"] = AIEventTracer._prepare_attribute_for_otel(value)

        attributes = {k: v for k, v in attributes.items() if v is not None}
        event_name = f"{issue.name or issue.element_id}.issue"

        if current_span.get_span_context().is_valid and current_span.is_recording():
            current_span.add_event(name=event_name, attributes=attributes)
        else:
            caller_filename, caller_function = AIEventTracer._get_caller_metadata()
            tracer = trace.get_tracer(caller_filename)
            with tracer.start_as_current_span(f"{caller_function}.issue") as record_span:
                record_span.add_event(name=event_name, attributes=attributes)

    @staticmethod
    def capture_metric(metric: Metric):
        """Captures Metric objects in spans."""
        current_span = trace.get_current_span()

        # Prepare attributes up front
        attributes = AIEventTracer._get_element_base_attributes(metric)
        attributes.update({"value": AIEventTracer._prepare_attribute_for_otel(metric.value)})

        if metric.timestamp is not None:
            attributes["timestamp"] = AIEventTracer._prepare_attribute_for_otel(metric.timestamp)

        if metric.related_to_ids:
            attributes["related_to_ids"] = AIEventTracer._prepare_attribute_for_otel(metric.related_to_ids)

        if hasattr(metric, "dict"):
            metric_dict = metric.dict()
            for key, value in metric_dict.items():
                if key not in attributes and key not in ["attributes", "tags", "value", "timestamp", "related_to_ids"]:
                    attributes[key] = AIEventTracer._prepare_attribute_for_otel(value)

        attributes = {k: v for k, v in attributes.items() if v is not None}
        event_name = f"{metric.name or metric.element_id}.metric"

        if current_span.get_span_context().is_valid and current_span.is_recording():
            current_span.add_event(name=event_name, attributes=attributes)
        else:
            caller_filename, caller_function = AIEventTracer._get_caller_metadata()
            tracer = trace.get_tracer(caller_filename)
            with tracer.start_as_current_span(f"{caller_function}.metric") as record_span:
                record_span.add_event(name=event_name, attributes=attributes)
