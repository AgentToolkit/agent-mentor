from typing import Dict, Optional, List, Union

from agent_analytics_common.interfaces.resources import Resource, ResourceCategory
from agent_analytics_common.interfaces.elements import AttributeValue
from agent_analytics_common.interfaces.annotations import DataAnnotation
from agent_analytics_common.interfaces.issues import Issue, IssueLevel
from agent_analytics_common.interfaces.metric import Metric, MetricType
from .ai_event_tracer import AIEventTracer


class AIEventRecorder:
    """Creates and captures AI-related events in a single step."""

    @staticmethod
    def record_resource(
        name: Optional[str] = None,
        description: Optional[str] = "",
        category: Optional[Union[ResourceCategory, str]] = None,
        format: Optional[str] = None,
        payload: Optional[AttributeValue] = None,
        tags: Optional[List[str]] = None,
        attributes: Optional[Dict[str, AttributeValue]] = None
    ) -> Resource:
        """Creates and captures a Resource object from raw data."""

        # Create Resource object
        resource = Resource(
            name=name,
            description=description,
            category=category,
            format=format,
            payload=payload,
            tags=tags or [],
            attributes=attributes or {}
        )

        AIEventTracer.capture_resource(resource)

        return resource

    @staticmethod
    def record_data_annotation(
        name: Optional[str] = None,
        description: str = "",
        path_to_string: Optional[str] = None,
        segment_start: Optional[int] = None,
        segment_end: Optional[int] = None,
        annotation_type: Optional[Union[DataAnnotation.Type, str]] = None,
        annotation_title: Optional[str] = None,
        annotation_content: Optional[str] = None,
        tags: Optional[List[str]] = None,
        attributes: Optional[Dict[str, AttributeValue]] = None
    ) -> DataAnnotation:
        """Creates and captures a DataAnnotation object from raw data."""

        # Create DataAnnotation object
        annotation = DataAnnotation(
            name=name,
            description=description,
            path_to_string=path_to_string,
            segment_start=segment_start,
            segment_end=segment_end,
            annotation_type=annotation_type,
            annotation_title=annotation_title,
            annotation_content=annotation_content,
            tags=tags or [],
            attributes=attributes or {}
        )

        AIEventTracer.capture_data_annotation(annotation)

        return annotation

    @staticmethod
    def record_metric(
        type: str = "",
        name: Optional[str] = None,
        description: Optional[str] = None,
        value: float = 0.0,
        timestamp: Optional[str] = None,
        related_to_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        attributes: Optional[Dict[str, AttributeValue]] = None
    ) -> Metric:
        """Creates and captures a Metric object from raw data."""

        # Create Metric object
        # Support Numeric metrics for now
        metric = Metric(
            name=name,
            description=description,
            metric_type=MetricType.NUMERIC,
            value=value,
            timestamp=timestamp,
            related_to_ids=related_to_ids or [],
            tags=tags or [],
            attributes=attributes or {}
        )

        AIEventTracer.capture_metric(metric)

        return metric

    @staticmethod
    def record_issue(
        name: Optional[str] = None,
        description: str = "",
        level: Optional[Union[IssueLevel, str]] = None,
        timestamp: Optional[str] = None,
        related_to_ids: Optional[List[str]] = None,
        effect: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        attributes: Optional[Dict[str, AttributeValue]] = None
    ) -> Issue:
        """Creates and captures an Issue object from raw data."""

        # Create Issue object
        issue = Issue(
            name=name,
            description=description,
            level=level or IssueLevel.WARNING,
            timestamp=timestamp,
            related_to_ids=related_to_ids or [],
            effect=effect or [],
            tags=tags or [],
            attributes=attributes or {}
        )

        AIEventTracer.capture_issue(issue)

        return issue
