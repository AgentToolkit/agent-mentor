
from agent_analytics_common.interfaces.annotations import DataAnnotation
from agent_analytics_common.interfaces.elements import Element
from pydantic import BaseModel, Field


class TrajectoryElement(BaseModel):
    type: DataAnnotation.Type = Field(description='')
    message: str = Field(description='')
    title: str | None = Field(description='annotation title', default=None)
    start_index: int = Field(description='')

class TrajectoryStep(Element):
    task_id: str = Field(description='The element ID of the annotated element')
    task_name: str = Field(description='The element name of the annotated element')
    elements: list[TrajectoryElement] = Field(description='')
