from abc import ABC
from typing import TypeVar

from agent_analytics_common.interfaces.elements import Element
from pydantic import Field

# Type variable for ElementData subclasses
E = TypeVar('E', bound='ElementData')

class ElementData(ABC,Element):
    root_id: str | None = Field(
        description='The identifier of the composite data element', default=None
    )

    plugin_metadata_id: str | None = Field(
        description='The identifier of the analytics which created this object', default=None
    )



    def to_json(self, indent: int = 2, sort_keys: bool = True) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "ElementData":
        return cls.model_validate_json(json_str)

    def __str__(self) -> str:
        return self.to_json(indent=2)


    @classmethod
    def is_storable(cls) -> bool:
        """Returns whether this artifact type can be stored in persistence layer"""
        # Look for _storable in class.__dict__ to get class-specific value
        return True

    @classmethod
    async def get_by_id(cls,data_manager: 'DataManager',element_id:str) -> "ElementData":
        """Returns whether this artifact type can be stored in persistence layer"""
        pass


