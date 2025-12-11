# AgentOps SDK - Complete Documentation

**Version:** 1.1.0
**Last Updated:** October 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Reference](#api-reference)
4. [Architecture & Design](#architecture--design)
5. [Data Models](#data-models)
6. [Advanced Usage](#advanced-usage)
7. [Examples](#examples)

---

## Overview

The AgentOps SDK provides a modern, developer-friendly Python interface for the AgentOps analytics platform. It abstracts away the complexity of the internal APIs while maintaining full functionality.

### Features

- **Simple initialization**: Single `AgentOpsClient.create()` call
- **Resource-based API**: Intuitive `client.traces`, `client.spans`, `client.metrics`, `client.issues`, etc.
- **Type inference**: Automatically infers metric types from values
- **Bulk operations**: Efficient `create_many()` for batch operations
- **Clean data models**: Lightweight wrappers that auto-proxy to internal composites
- **Async/await support**: Native async Python for optimal performance
- **Type hints**: Full type annotations for IDE support
- **Low maintenance**: Uses `__getattr__` to automatically expose all composite properties

### Installation

The SDK is included with the AgentOps platform. No additional installation required.

```python
from agent_analytics.sdk import AgentOpsClient
```

---

## Quick Start

```python
from datetime import datetime, timedelta
from agent_analytics.sdk import AgentOpsClient

# Initialize the client
client = await AgentOpsClient.create()

# Query traces
traces = await client.traces.fetch(
    service_name="my-service",
    from_date=datetime.now() - timedelta(days=7)
)

# Get spans for a trace
spans = await client.spans.fetch(trace_id=traces[0].id)

# Create a metric owned by a trace
metric = await client.metrics.create(
    owner=traces[0],
    name="quality_score",
    value=0.95,
    units="score",
    description="Overall quality score"
)

# Create a metric related to a span
metric = await client.metrics.create(
    owner=traces[0],
    name="High Latency",
    description="Response time exceeded threshold",
    level=IssueLevel.WARNING,
    related_to=[spans[0]]
)

# Retrieve metrics owned by trace
metrics = await client.metrics.fetch_by_owner(traces[0])

# Retrieve metrics related to span
metrics = await client.metrics.fetch_by_related(spans[0])

# And vice versa - Retrieve metrics related to span - through the span object
metrics = await spans[0].related_elements(element_type=Metric)
```

---

## API Reference

### Client Initialization

#### `AgentOpsClient.create(tenant_id=None)`

Create and initialize a new AgentOps client.

**Parameters:**
- `tenant_id` (str, optional): Tenant identifier. Defaults to the default tenant.

**Returns:**
- `AgentOpsClient`: An initialized client instance

**Example:**
```python
# Use default tenant
client = await AgentOpsClient.create()

# Use specific tenant
client = await AgentOpsClient.create(tenant_id="my-tenant")
```

---

### Traces API

#### `client.traces.fetch(service_name, from_date, to_date=None, names=None, agent_ids=None, min_duration=None, max_duration=None)`

List all traces for a service within a time window with optional filtering.

**Parameters:**
- `service_name` (str): Name of the service to filter by
- `from_date` (datetime): Start of the time window
- `to_date` (datetime, optional): End of the time window (defaults to now)
- `names` (list[str], optional): Filter by trace names
- `agent_ids` (list[str], optional): Filter by agent IDs
- `min_duration` (float, optional): Minimum duration in seconds
- `max_duration` (float, optional): Maximum duration in seconds

**Returns:**
- `list[Trace]`: List of Trace objects

**Examples:**
```python
# Basic query
traces = await client.traces.fetch(
    service_name="my-service",
    from_date=datetime.now() - timedelta(days=7)
)

# Filter by trace names
traces = await client.traces.fetch(
    service_name="my-service",
    from_date=datetime.now() - timedelta(days=7),
    names=["login_flow", "checkout_flow"]
)

# Filter by agent IDs
traces = await client.traces.fetch(
    service_name="my-service",
    from_date=datetime.now() - timedelta(days=7),
    agent_ids=["agent-1", "agent-2"]
)

# Filter by duration range
traces = await client.traces.fetch(
    service_name="my-service",
    from_date=datetime.now() - timedelta(days=7),
    min_duration=1.0,  # At least 1 second
    max_duration=10.0  # At most 10 seconds
)
```

#### `client.traces.get(trace_id)`

Get a specific trace by ID.

**Parameters:**
- `trace_id` (str): The unique identifier of the trace

**Returns:**
- `Trace | None`: Trace object if found, None otherwise

---

### Trace Groups API

#### `client.trace_groups.fetch(service_name, names=None, min_duration=None, max_duration=None, min_success_rate=None, max_success_rate=None)`

List all trace groups for a service with optional filtering. Trace groups aggregate multiple traces with the same service and operation name.

**Parameters:**
- `service_name` (str): Name of the service to filter by
- `names` (list[str], optional): Filter by trace group names (operation names)
- `min_duration` (float, optional): Minimum average duration in seconds
- `max_duration` (float, optional): Maximum average duration in seconds
- `min_success_rate` (float, optional): Minimum success rate (0.0-1.0)
- `max_success_rate` (float, optional): Maximum success rate (0.0-1.0)

**Returns:**
- `list[TraceGroup]`: List of TraceGroup objects

**Examples:**
```python
# Basic query
trace_groups = await client.trace_groups.fetch(service_name="my-service")

# Filter by operation names
trace_groups = await client.trace_groups.fetch(
    service_name="my-service",
    names=["process_payment", "send_notification"]
)

# Filter by success rate
trace_groups = await client.trace_groups.fetch(
    service_name="my-service",
    min_success_rate=0.95  # Only high-performing groups
)

# Filter by duration
trace_groups = await client.trace_groups.fetch(
    service_name="my-service",
    max_duration=5.0  # Only fast operations
)
```

#### `client.trace_groups.get(trace_group_id)`

Get a specific trace group by ID.

**Parameters:**
- `trace_group_id` (str): The unique identifier of the trace group

**Returns:**
- `TraceGroup | None`: TraceGroup object if found, None otherwise

#### `client.trace_groups.create(service_name, operation_name, trace_ids=None)`

Create a new trace group.

**Parameters:**
- `service_name` (str): Name of the service
- `operation_name` (str): Name of the operation
- `trace_ids` (list[str], optional): List of trace IDs to include in the group

**Returns:**
- `TraceGroup`: The created TraceGroup object

**Example:**
```python
trace_group = await client.trace_groups.create(
    service_name="my-service",
    operation_name="process_payment",
    trace_ids=[trace1.id, trace2.id]
)
```

#### `client.trace_groups.create_many(trace_groups)`

Bulk create multiple trace groups.

**Parameters:**
- `trace_groups` (list[dict]): List of trace group definitions

**Returns:**
- `list[TraceGroup]`: List of created TraceGroup objects

**Example:**
```python
trace_groups = await client.trace_groups.create_many([
    {
        "service_name": "my-service",
        "operation_name": "process_payment",
        "trace_ids": [trace1.id, trace2.id]
    },
    {
        "service_name": "my-service",
        "operation_name": "send_notification",
        "trace_ids": [trace3.id]
    }
])
```

#### `client.trace_groups.fetch_by_owner(owner, names=None)`

Get all trace groups owned by a specific element.

**Parameters:**
- `owner` (Any): The owner element (wrapper, composite, or ID string)
- `names` (list[str], optional): Filter by trace group names

**Returns:**
- `list[TraceGroup]`: List of TraceGroup objects

---

### Spans API

#### `client.spans.fetch(trace_id, names=None)`

List all spans for a specific trace with optional filtering.

**Parameters:**
- `trace_id` (str): The ID of the trace to get spans for
- `names` (list[str], optional): Filter by span names

**Returns:**
- `list[Span]`: List of Span objects

**Examples:**
```python
# Get all spans for a trace
spans = await client.spans.fetch(trace_id=trace.id)

# Filter by span names
spans = await client.spans.fetch(
    trace_id=trace.id,
    names=["database_query", "api_call"]
)
```

#### `client.spans.get(span_id)`

Get a specific span by ID.

**Parameters:**
- `span_id` (str): The unique identifier of the span

**Returns:**
- `Span | None`: Span object if found, None otherwise

---

### Metrics API

#### `client.metrics.create(owner, name, value, ...)`

Create a new metric owned by an element (trace, trace group, or any other element).

**Parameters:**
- `owner` (Any): Owner element this metric belongs to (Trace, TraceGroup, or any Element)
- `name` (str): Display name for the metric
- `value` (Any): The metric value
- `metric_type` (MetricType, optional): Type of metric (auto-inferred if not provided)
- `related_to` (list[Any], optional): List of elements this relates to (e.g., Span, Task)
- `units` (str, optional): Units of measurement
- `description` (str, optional): Description of what this metric measures
- `tags` (list[str], optional): List of tags for categorization
- `plugin_id` (str, optional): Identifier of the plugin that created this metric

**Returns:**
- `Metric`: The created Metric object

**Examples:**
```python
# Numeric metric
metric = await client.metrics.create(
    owner=trace,
    name="quality_score",
    value=0.95,
    units="score"
)

# String metric
metric = await client.metrics.create(
    owner=trace,
    name="status",
    value="SUCCESS"
)

# Distribution metric
metric = await client.metrics.create(
    owner=trace,
    name="tool_usage",
    value={"tool_a": 0.5, "tool_b": 0.3, "tool_c": 0.2},
    metric_type=MetricType.DISTRIBUTION
)

# Metric related to a span
metric = await client.metrics.create(
    owner=trace,
    name="span_quality",
    value=0.85,
    related_to=[span],
    units="score"
)
```

#### `client.metrics.create_many(owner, metrics)`

Create multiple metrics at once for better performance.

**Parameters:**
- `owner` (Any): Owner element these metrics belong to
- `metrics` (list[dict]): List of metric definitions

**Returns:**
- `list[Metric]`: List of created Metric objects

**Example:**
```python
metrics = await client.metrics.create_many(
    owner=trace,
    metrics=[
        {"name": "metric1", "value": 0.95, "units": "score"},
        {"name": "metric2", "value": "SUCCESS"}
    ]
)
```

#### `client.metrics.fetch_by_owner(owner, names=None)`

Get all metrics owned by a specific element with optional filtering.

**Parameters:**
- `owner` (Any): The owner element (wrapper, composite, or ID string)
- `names` (list[str], optional): Filter by metric names

**Returns:**
- `list[Metric]`: List of Metric objects

**Examples:**
```python
# Get all metrics for a trace
metrics = await client.metrics.fetch_by_owner(trace)

# Get all metrics for a trace group
metrics = await client.metrics.fetch_by_owner(trace_group)

# Filter by metric names
metrics = await client.metrics.fetch_by_owner(
    trace,
    names=["quality_score", "performance_score"]
)
```

#### `client.metrics.fetch_by_related(element, names=None)`

Get all metrics related to a specific element with optional filtering.

**Parameters:**
- `element` (Any): The element to find relations for
- `names` (list[str], optional): Filter by metric names

**Returns:**
- `list[Metric]`: List of Metric objects

**Examples:**
```python
# Get all metrics related to a span
metrics = await client.metrics.fetch_by_related(span)

# Filter by metric names
metrics = await client.metrics.fetch_by_related(
    span,
    names=["latency", "throughput"]
)
```

#### Backward-Compatible Methods

For backward compatibility, the following methods are still available:

- `client.metrics.list_for_trace(trace)` - Alias for `fetch_by_owner(trace)`
- `client.metrics.list_for_span(span)` - Alias for `fetch_by_related(span)`

---

### Issues API

#### `client.issues.create(owner, name, description, ...)`

Create a new issue owned by an element.

**Parameters:**
- `owner` (Any): Owner element this issue belongs to (Trace, TraceGroup, or any Element)
- `name` (str): Display name for the issue
- `description` (str): Description of the issue
- `level` (IssueLevel, optional): Severity level (INFO, WARNING, ERROR, CRITICAL)
- `confidence` (float, optional): Confidence level (0.0 to 1.0)
- `effect` (list[str], optional): List of effects this issue causes
- `related_to` (list[Any], optional): Optional elements to relate this issue to
- `tags` (list[str], optional): List of tags for categorization
- `plugin_id` (str, optional): Identifier of the plugin that created this issue

**Returns:**
- `Issue`: The created Issue object

**Example:**
```python
from ibm_agent_analytics_common.interfaces.issues import IssueLevel

issue = await client.issues.create(
    owner=trace,
    name="High Latency",
    description="Response time exceeded threshold",
    level=IssueLevel.WARNING,
    confidence=0.95,
    effect=["slow_response"],
    related_to=[span1, span2]
)
```

#### `client.issues.create_many(owner, issues)`

Create multiple issues at once for better performance.

#### `client.issues.fetch_by_owner(owner, names=None)`

Get all issues owned by a specific element with optional filtering.

**Parameters:**
- `owner` (Any): The owner element
- `names` (list[str], optional): Filter by issue names

#### `client.issues.fetch_by_related(element, names=None)`

Get all issues related to a specific element with optional filtering.

**Parameters:**
- `element` (Any): The element to find relations for
- `names` (list[str], optional): Filter by issue names

---

### Trace Workflows API

#### `client.trace_workflows.create(owner, name, description, owner_id, ...)`

Create a new trace workflow owned by an element.

**Parameters:**
- `owner` (Any): Owner element this workflow belongs to
- `name` (str): Display name for the workflow
- `description` (str): Description of the workflow
- `owner_id` (str): ID of the owner runnable
- `workflow_type` (str, optional): Type of workflow
- `control_flow_ids` (list[str], optional): List of control flow IDs
- `related_to` (list[Any], optional): Optional elements to relate this workflow to
- `tags` (list[str], optional): List of tags
- `plugin_id` (str, optional): Plugin identifier

**Returns:**
- `TraceWorkflow`: The created TraceWorkflow object

**Note:** The resource was renamed from `client.workflows` to `client.trace_workflows` to better reflect that it handles trace-specific workflows.

---

### Recommendations API

#### `client.recommendations.create(owner, name, description, ...)`

Create a new recommendation owned by an element.

**Parameters:**
- `owner` (Any): Owner element this recommendation belongs to
- `name` (str): Display name for the recommendation
- `description` (str): Description of the recommendation
- `level` (RecommendationLevel, optional): Impact level (MINOR, MODERATE, MAJOR, CRITICAL)
- `effect` (list[str], optional): List of effects this recommendation provides
- `related_to` (list[Any], optional): Optional elements to relate this recommendation to
- `tags` (list[str], optional): List of tags
- `plugin_id` (str, optional): Plugin identifier

**Returns:**
- `Recommendation`: The created Recommendation object

---

### Annotations API

#### `client.annotations.create(owner, name, description, segment_start, ...)`

Create a new annotation owned by an element.

**Parameters:**
- `owner` (Any): Owner element this annotation belongs to
- `name` (str): Display name for the annotation
- `description` (str): Description of the annotation
- `segment_start` (int): Start position of the annotated segment
- `annotation_type` (DataAnnotation.Type, optional): Type of annotation
- `path_to_string` (str, optional): Path to the annotated string
- `segment_end` (int, optional): End position of the annotated segment
- `annotation_title` (str, optional): Title of the annotation
- `annotation_content` (str, optional): Content of the annotation
- `related_to` (list[Any], optional): Optional elements to relate this annotation to
- `tags` (list[str], optional): List of tags
- `plugin_id` (str, optional): Plugin identifier

**Returns:**
- `Annotation`: The created Annotation object

---

## Architecture & Design

### Layer Structure

```
┌─────────────────────────────────────┐
│     SDK Layer (src/sdk/)            │
│  - AgentOpsClient                   │
│  - Resource APIs (traces, spans,    │
│    metrics, issues, etc.)           │
│  - Simplified Models (Trace, Span,  │
│    Metric, Issue, etc.)             │
└─────────────────────────────────────┘
              │
              │ Uses internally
              ↓
┌─────────────────────────────────────┐
│   Internal APIs                      │
│  - BaseTraceComposite               │
│  - BaseSpanComposite                │
│  - BaseMetric, MetricComposite      │
│  - AnalyticsDataManager             │
└─────────────────────────────────────┘
              │
              │ Stores to
              ↓
┌─────────────────────────────────────┐
│   Storage Layer                      │
│  - Elasticsearch / OpenSearch       │
│  - MongoDB / Memory Store           │
└─────────────────────────────────────┘
```

### Key Design Patterns

#### 1. Resource Pattern

Each resource (traces, spans, metrics, issues, etc.) is implemented as a separate class that encapsulates all operations for that resource type. This provides:

- Clear organization
- Easy discoverability
- Consistent API patterns
- Extensibility

#### 2. Proxy Pattern (`__getattr__`)

SDK models use Python's attribute lookup mechanism to automatically forward all property access to internal composites. Benefits:

- **Low maintenance**: New composite properties automatically available
- **Selective renaming**: Only map what needs to change (e.g., `element_id` → `id`)
- **Additive**: Can layer SDK-specific properties on top
- **Transparent**: Users get full composite functionality

```python
@dataclass(repr=False)
class Element:
    _composite: ElementComposite

    _FIELD_MAPPING = {
        "id": "element_id",  # Rename element_id to id
    }

    def __getattr__(self, name: str) -> Any:
        """Auto-proxy to composite"""
        composite_name = self._FIELD_MAPPING.get(name, name)
        return getattr(self._composite, composite_name)
```

#### 3. Type Inference

Metric types are automatically inferred from values:
- `int` or `float` → `NUMERIC`
- `str` → `STRING`
- `dict` → `DISTRIBUTION`

Users can override with explicit `metric_type` parameter.

---

## Data Models

### Wrapper Hierarchy

```
Element (base wrapper)
├── RelatableElement
│   ├── Metric
│   ├── Issue
│   ├── Workflow
│   ├── Recommendation
│   └── Annotation
├── Trace
├── Span
├── Task
├── Runnable
├── TraceGroup
├── TraceWorkflow (renamed from Workflow)
├── WorkflowNode
├── WorkflowNodeGateway
└── WorkflowEdge
```

This mirrors the internal composite hierarchy exactly.

### Trace

Wraps `BaseTraceComposite` to represent a single execution trace.

**Primary Attributes:**
- `id` (str): Unique identifier (renamed from `element_id`)
- `service_name` (str): Name of the service that created this trace
- `start_time` (datetime): When the trace started
- `end_time` (datetime | None): When the trace completed
- `num_of_spans` (int | None): Number of spans in this trace
- `agent_ids` (list[str] | None): List of agent identifiers involved
- `failures` (dict[str, int] | None): Dictionary of failure counts by type

**SDK-Added Properties:**
- `duration` (float | None): Duration of the trace in seconds

**Note:** All other properties from `BaseTraceComposite` are automatically available.

### TraceGroup

Wraps `TraceGroupComposite` to represent a group of traces with the same service and operation name.

**Primary Attributes:**
- `id` (str): Unique identifier
- `service_name` (str): Service name
- `operation_name` (str): Operation name
- `traces_ids` (list[str]): List of trace IDs in this group

**Aggregate Metrics:**
TraceGroup provides aggregate statistics through separate Metric objects. When you create a TraceGroup, the following metrics are automatically generated:
- `avg_duration`: Average duration across all traces (in seconds)
- `success_rate`: Success rate across all traces (0.0-1.0)
- `total_traces`: Total number of traces in the group
- `failure_count`: Number of failed traces

**Accessing Metrics:**
```python
# Get all metrics for a trace group
metrics = await trace_group.metrics

# Get a specific metric value directly
avg_duration = await trace_group.get_metric_value("avg_duration")
success_rate = await trace_group.get_metric_value("success_rate")

# Get the full metric object with metadata
avg_duration_metric = await trace_group.get_metric("avg_duration")
print(f"{avg_duration_metric.name}: {avg_duration_metric.value} {avg_duration_metric.units}")
```

**Convenience Methods:**
- `metrics` (async property): Returns list of all Metric objects owned by this trace group
- `get_metric(name)` (async method): Returns a specific Metric object by name
- `get_metric_value(name, default=None)` (async method): Returns just the value of a metric

### Span

Wraps `BaseSpanComposite` to represent a single span within a trace.

**Primary Attributes:**
- `id` (str): Unique identifier
- `trace_id` (str): ID of the parent trace
- `name` (str): Name of the span
- `start_time` (datetime): When the span started
- `end_time` (datetime | None): When the span completed

**SDK-Added Properties:**
- `duration` (float | None): Duration of the span in seconds

### Metric

Wraps `MetricComposite` to represent a computed metric.

**Primary Attributes:**
- `id` (str): Unique identifier
- `name` (str): Display name of the metric
- `value` (Any): The metric value
- `units` (str | None): Units of measurement
- `description` (str | None): Description of what this metric measures
- `timestamp` (datetime | None): When this metric was computed
- `tags` (list[str] | None): List of tags for categorization

**SDK-Added Properties:**
- `metric_type` (MetricType): Type of the metric
- `trace_id` (str): ID of the trace this metric belongs to
- `span_id` (str | None): Optional ID of a specific span this relates to

### MetricType

Enumeration of supported metric types.

**Values:**
- `NUMERIC`: Numeric measurements (float)
- `STRING`: String-based measurements
- `DISTRIBUTION`: Distribution measurements (dict)
- `TIME_SERIES`: Time series measurements (list of tuples)
- `HISTOGRAM`: Histogram measurements (dict)
- `STATISTICS`: Statistical aggregations (dict)

### RelatableElement Types

All RelatableElement types (Metric, Issue, Workflow, Recommendation, Annotation) share common functionality:

- Can be owned by any element (Trace, TraceGroup, etc.)
- Can be related to any other element(s)
- Support `fetch_by_owner()` and `fetch_by_related()` queries
- Can be created individually or in bulk

---

## Advanced Usage

### Using Trace Groups

Trace groups aggregate multiple traces and can be used as owners for metrics and issues. They provide aggregated statistics through separate Metric objects that are automatically created when the trace group is instantiated.

```python
# Get trace groups for a service
trace_groups = await client.trace_groups.fetch(service_name="my-service")

if trace_groups:
    tg = trace_groups[0]

    # Access aggregated metrics (stored as separate Metric objects)
    avg_duration = await tg.get_metric_value("avg_duration")
    success_rate = await tg.get_metric_value("success_rate")
    total_traces = await tg.get_metric_value("total_traces")
    failure_count = await tg.get_metric_value("failure_count")

    print(f"Average duration: {avg_duration}s")
    print(f"Success rate: {success_rate * 100}%")
    print(f"Total traces: {total_traces}")
    print(f"Failures: {failure_count}")

    # View all metrics for the trace group
    all_metrics = await tg.metrics
    for metric in all_metrics:
        print(f"  {metric.name}: {metric.value} {metric.units or ''}")

    # Create a custom metric for the trace group
    metric = await client.metrics.create(
        owner=tg,
        name="group_quality_score",
        value=0.95,
        units="score",
        description="Quality score across all traces in this group"
    )

    # Create an issue for the trace group
    issue = await client.issues.create(
        owner=tg,
        name="Consistent Failures",
        description="Multiple traces failing",
        level=IssueLevel.ERROR
    )

# Create a new trace group (automatically creates aggregate metrics)
new_group = await client.trace_groups.create(
    service_name="my-service",
    operation_name="process_payment",
    trace_ids=[trace1.id, trace2.id]
)

# The trace group now has automatic metrics
avg_duration = await new_group.get_metric_value("avg_duration")
print(f"New group average duration: {avg_duration}s")

# Filter trace groups by success rate
high_performing = await client.trace_groups.fetch(
    service_name="my-service",
    min_success_rate=0.95
)
```

### Creating Related Elements

Elements can be related to other elements:

```python
# Create a metric related to multiple spans
metric = await client.metrics.create(
    owner=trace,
    name="multi_span_quality",
    value=0.88,
    related_to=[span1, span2, span3]
)

# Create an issue related to a task
issue = await client.issues.create(
    owner=trace,
    name="Task Timeout",
    description="Task exceeded time limit",
    related_to=[task]
)
```

### Querying Related Elements

You can query elements by their owner or by what they're related to, with optional name filtering:

```python
# Get all metrics for a trace (owner query)
trace_metrics = await client.metrics.fetch_by_owner(trace)

# Get all metrics related to a span (related query)
span_metrics = await client.metrics.fetch_by_related(span)

# Get all issues related to a task
task_issues = await client.issues.fetch_by_related(task)

# Filter by names
quality_metrics = await client.metrics.fetch_by_owner(
    trace,
    names=["quality_score", "performance_score"]
)

# Use the related_elements method on any element
from agent_analytics.sdk.models import Metric, Issue

# Get specific types of related elements
span_metrics = await span.related_elements(element_type=Metric)
span_issues = await span.related_elements(element_type=Issue)

# Get all related elements (any type)
all_related = await span.related_elements()
```

### Bulk Operations

For better performance, create multiple elements at once:

```python
# Bulk create metrics
metrics = await client.metrics.create_many(
    owner=trace,
    metrics=[
        {"name": f"metric_{i}", "value": float(i * 0.1)}
        for i in range(10)
    ]
)

# Bulk create issues
issues = await client.issues.create_many(
    owner=trace,
    issues=[
        {
            "name": f"issue_{i}",
            "description": f"Description {i}",
            "level": IssueLevel.WARNING
        }
        for i in range(5)
    ]
)
```

### Context Manager

Use async context manager for automatic cleanup:

```python
async with await AgentOpsClient.create() as client:
    traces = await client.traces.fetch(...)
    # Client automatically closed on exit
```

### Advanced Filtering

The SDK supports advanced filtering across multiple resource types:

```python
# Filter traces by duration and agent IDs
slow_traces = await client.traces.fetch(
    service_name="my-service",
    from_date=datetime.now() - timedelta(days=1),
    min_duration=5.0,  # Traces taking at least 5 seconds
    agent_ids=["agent-1", "agent-2"]
)

# Filter trace groups by success rate and duration
problematic_groups = await client.trace_groups.fetch(
    service_name="my-service",
    max_success_rate=0.9,  # Below 90% success
    min_duration=2.0  # Taking at least 2 seconds
)

# Filter spans and metrics by name
database_spans = await client.spans.fetch(
    trace_id=trace.id,
    names=["database_query", "db_transaction"]
)

performance_metrics = await client.metrics.fetch_by_owner(
    trace,
    names=["response_time", "throughput", "latency"]
)
```

---

## Examples

Complete examples are available in:
- **[sdk_examples.ipynb](../../sdk_examples.ipynb)**: Jupyter notebook with runnable examples
- **[tests/sdk/](../../tests/sdk/)**: Test files demonstrating various use cases

### Example 1: Fetching Traces and Spans

```python
from datetime import datetime, timedelta
from agent_analytics.sdk import AgentOpsClient

client = await AgentOpsClient.create()

# Query traces
traces = await client.traces.fetch(
    service_name="my-service",
    from_date=datetime.now() - timedelta(days=7)
)

# Get spans for each trace
for trace in traces:
    spans = await client.spans.fetch(trace_id=trace.id)
    print(f"Trace {trace.id}: {len(spans)} spans")
```

### Example 2: Creating and Retrieving Metrics

```python
# Create a metric
metric = await client.metrics.create(
    owner=trace,
    name="quality_score",
    value=0.95,
    units="score",
    description="Overall quality score"
)

# Retrieve metrics
trace_metrics = await client.metrics.fetch_by_owner(trace)
print(f"Found {len(trace_metrics)} metrics for trace")
```

### Example 3: Complete Workflow

```python
async def complete_workflow():
    # Initialize
    client = await AgentOpsClient.create()

    # Fetch traces
    traces = await client.traces.fetch(
        service_name="my-service",
        from_date=datetime.now() - timedelta(days=1)
    )

    if not traces:
        return

    trace = traces[0]
    spans = await client.spans.fetch(trace_id=trace.id)

    # Create metrics
    avg_duration = sum(s.duration or 0 for s in spans) / len(spans)

    await client.metrics.create_many(
        owner=trace,
        metrics=[
            {
                "name": "avg_span_duration",
                "value": avg_duration,
                "units": "seconds"
            },
            {
                "name": "span_count",
                "value": float(len(spans)),
                "units": "count"
            }
        ]
    )

    # Analyze results
    all_metrics = await client.metrics.fetch_by_owner(trace)
    print(f"Total metrics: {len(all_metrics)}")

await complete_workflow()
```

---

## Best Practices

1. **Use async context manager for cleanup:**
   ```python
   async with await AgentOpsClient.create() as client:
       traces = await client.traces.fetch(...)
   ```

2. **Leverage type inference:**
   ```python
   # Let the SDK infer the type
   metric = await client.metrics.create(
       owner=trace,
       name="score",
       value=0.95  # Automatically becomes NUMERIC
   )
   ```

3. **Use bulk operations for efficiency:**
   ```python
   # Create many metrics at once
   metrics = await client.metrics.create_many(
       owner=trace,
       metrics=[...]
   )
   ```

4. **Add descriptive metadata:**
   ```python
   metric = await client.metrics.create(
       owner=trace,
       name="quality_score",
       value=0.95,
       units="score",
       description="Overall quality score based on LLM evaluation",
       tags=["quality", "llm", "evaluation"]
   )
   ```

5. **Use trace groups for aggregated analytics:**
   ```python
   # Get trace groups instead of individual traces
   trace_groups = await client.trace_groups.fetch(service_name="my-service")

   # Create aggregated metrics
   for tg in trace_groups:
       await client.metrics.create(
           owner=tg,
           name="group_success_rate",
           value=calculate_success_rate(tg)
       )
   ```

---

## Support

For issues, questions, or contributions, please refer to the main AgentOps documentation or contact the development team.

---

**Document Version:** 1.2.0
**SDK Version:** 1.2.0
**Last Updated:** October 2025

## Recent Changes (v1.2.0)

### Breaking Changes

1. **TraceGroup Metrics Architecture**
   - Aggregate metrics (avg_duration, success_rate, total_traces, failure_count) are now stored as separate Metric objects instead of direct properties
   - **Migration:** Instead of `trace_group.avg_duration`, use `await trace_group.get_metric_value("avg_duration")`
   - Metrics are automatically created when a TraceGroup is instantiated
   - All metrics can be accessed via `await trace_group.metrics`

### New Features

1. **TraceGroup Metric Access Methods**
   - `trace_group.metrics` (async property) - Get all metrics for a trace group
   - `trace_group.get_metric(name)` - Get a specific Metric object by name
   - `trace_group.get_metric_value(name, default)` - Get just the metric value

2. **Consistent Metrics Pattern**
   - TraceGroups follow the same metrics pattern as Traces and other elements
   - Metrics have explicit `owner` and `related_to` properties
   - Use `client.metrics.fetch_by_owner(trace_group)` to query metrics

## Previous Changes (v1.1.0)

### Features Added in v1.1.0

1. **TraceGroup Creation**
   - `client.trace_groups.create()` - Create single trace group
   - `client.trace_groups.create_many()` - Bulk create trace groups

2. **Name-Based Filtering**
   - Added `names` parameter to filter by list of names on:
     - `client.trace_groups.fetch()`
     - `client.traces.fetch()`
     - `client.spans.fetch()`
     - `client.metrics.fetch_by_owner()` and `fetch_by_related()`
     - All relatable resources (issues, recommendations, annotations)

3. **Advanced Filtering**
   - TraceGroups and Traces: `min_duration`, `max_duration`
   - TraceGroups: `min_success_rate`, `max_success_rate`
   - Traces: `agent_ids` - Filter by agent IDs

4. **TraceGroup Ownership Queries**
   - `client.trace_groups.fetch_by_owner()` - Get trace groups owned by an element

5. **Fixed Workflow Resource**
   - Renamed `client.workflows` → `client.trace_workflows`
   - Changed `Workflow` → `TraceWorkflow` SDK model
   - Updated to use `TraceWorkflowComposite`
