
from abc import ABCMeta

from agent_analytics_common.interfaces.relatable_element import RelatableElement
from pydantic import Field

from agent_analytics.core.data.element_data import ElementData


class RelatableElementData(ElementData,RelatableElement,metaclass=ABCMeta):
    related_to_types: list[str] = Field(
        default_factory=list, description="Type names of the related to elements"
    )
