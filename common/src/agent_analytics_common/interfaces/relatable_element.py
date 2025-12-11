from abc import ABC
from typing import List, Optional

from pydantic import Field,field_validator
from agent_analytics_common.interfaces.elements import Element
from abc import ABCMeta


class RelatableElement(Element,metaclass=ABCMeta):
    related_to_ids: List[str] = Field(
        default_factory=list, description="Elements related to this object"
    )

    @field_validator('related_to_ids', mode='before')
    @classmethod
    def validate_related_to_ids(cls, v):
        if v is None:
            return []
        return v
    