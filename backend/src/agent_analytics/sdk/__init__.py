"""
AgentOps SDK - Developer-friendly interface for agent analytics

This SDK provides a modern, intuitive API for querying and storing
agent execution data, metrics, issues, recommendations, and more.

Example:
    from agent_analytics.sdk import AgentOpsClient

    # Initialize client
    client = await AgentOpsClient.create()

    # Query traces
    traces = await client.traces.fetch(
        service_name="my-service",
        from_date=datetime.now() - timedelta(days=7)
    )

    # Create metrics
    await client.metrics.create(
        owner=trace,
        name="quality_score",
        value=0.95
    )

    # Create issues
    await client.issues.create(
        owner=trace,
        name="High Latency",
        description="System response time exceeded threshold",
        related_to=[span]
    )
"""

from agent_analytics.sdk.client import AgentOpsClient
from agent_analytics.sdk.models import (
    Action,
    Annotation,
    Element,
    Issue,
    Metric,
    MetricType,
    Recommendation,
    RelatableElement,
    Span,
    Task,
    Trace,
    TraceGroup,
    TraceWorkflow,
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeGateway,
)

__all__ = [
    # Client
    "AgentOpsClient",
    # Base wrappers
    "Element",
    "RelatableElement",
    # Concrete wrappers (non-relatable)
    "Trace",
    "Span",
    "Task",
    "Action",
    "TraceGroup",
    "TraceWorkflow",
    "WorkflowNode",
    "WorkflowNodeGateway",
    "WorkflowEdge",
    # Concrete wrappers (relatable)
    "Metric",
    "Issue",
    "Workflow",
    "Recommendation",
    "Annotation",
    # Enums
    "MetricType",
]
