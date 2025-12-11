from ibm_agent_analytics_common.interfaces.iunits import RelationType
from pydantic import Field

from agent_analytics.core.data.workflow_node_data import WorkflowNodeData


class WorkflowNodeGatewayData(WorkflowNodeData):
    gate_type: RelationType = Field(description="The type of gateway (XOR, OR, AND)")
