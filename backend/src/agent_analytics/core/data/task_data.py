from typing import List, Any
from ibm_agent_analytics_common.interfaces.task import Task
from pydantic import Field

from agent_analytics.core.data.element_data import ElementData


class TaskData(ElementData, Task):
    """Persistent data representation of a Task"""
    # TODO: dependent_ids convert to dependencies_ids
    id: str = Field(description='The unique identifier of the task in the persistency layer')
    dependent_ids: list[str] = Field(description='List of IDs of tasks that this task depends on', default_factory=list)
    graph_id: str | None = Field(description='The identifier of the state graph associated with the task', default=None)
    parent_name: str | None = Field(description='The name of the parent task', default=None)
    action_id: str | None = Field( default=None, description="Action ID" )
    events: List[Any] = Field(
        default_factory=list, 
        description="A list containing information about exceptions/events during task execution"
    )



