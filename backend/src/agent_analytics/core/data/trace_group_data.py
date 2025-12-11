from typing import List
from pydantic import Field
from agent_analytics.core.data.element_data import ElementData

class TraceGroupData(ElementData):
    traces_ids: List[str] = Field(..., description="List of trace IDs associated with the scope")
    service_name: str = Field(..., description="The service name this trace group belongs to")

    # Legacy fields - kept for backward compatibility
    # Note: These are no longer populated by default. Use Metric objects instead,
    # which are stored separately with owner=trace_group and related_to=trace_group.
    avg_duration: float | None = Field(None, description="Average duration across all traces in seconds")
    success_rate: float | None = Field(None, description="Success rate across all traces (0.0 to 1.0)")
    total_traces: int = Field(0, description="Total number of traces in the group")
    failure_count: int = Field(0, description="Number of failed traces")