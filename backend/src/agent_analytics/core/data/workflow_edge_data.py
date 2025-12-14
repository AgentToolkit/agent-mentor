
from agent_analytics_common.interfaces.iunits import Relation
from pydantic import Field

from agent_analytics.core.data.element_data import ElementData


class WorkflowEdgeData(ElementData, Relation):
    source_category: str = Field(description="The category of the source node")
    parent_id: str = Field(description="The ID of the parent workflow")
    destination_category: str = Field(description="The category of the destination node")
    trace_count: int = Field(description="Counter for the number of tasks", default=0)
