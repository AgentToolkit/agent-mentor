
from pydantic import Field

from agent_analytics.core.data.element_data import ElementData


class WorkflowNodeData(ElementData):
    node_type: str = Field(description="The type of the workflow node")
    parent_id: str = Field(description="The ID of the parent workflow")
    action_id: str = Field(description="The ID of the associated action")
    task_counter: int = Field(description="Counter for the number of tasks", default=0)
    trace_counter: int = Field(description="Counter for the number of tasks", default=0)
