
from pydantic import Field

from agent_analytics.core.data.relatable_element_data import RelatableElementData


class WorkflowData(RelatableElementData):
    owner_id: str = Field(description="The ID of the owner action")
    type: str = Field(default="WorkflowData", description="Workfllow element")
    control_flow_ids: list[str] = Field(description="List of control flow IDs associated with the workflow", default_factory=list)
