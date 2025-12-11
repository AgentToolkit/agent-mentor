
from pydantic import Field

from agent_analytics.core.data.element_data import ElementData


class TraceWorkflowData(ElementData):
    actions: list[str] = Field(description="List of Action ids", default_factory=list)
    workflows: list[str] = Field(description="List of Workflow ids", default_factory=list)
    workflow_nodes: list[str] = Field(description="List of WorkflowNode ids", default_factory=list)
    workflow_edges: list[str] = Field(description="List of WorkflowEdge ids", default_factory=list)
