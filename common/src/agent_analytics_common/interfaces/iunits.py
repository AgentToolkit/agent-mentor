from pydantic import Field
from typing import List, Any, Optional,Union
from enum import Enum
from .elements import Element  

class IUnit(Element):
    """
    Intelligent Unit (IUnit) is an element reflecting the non-deterministic nature of agentic systems.
    """
    code_id: Optional[str] = Field(
        None, description="The code identifier of the unit, if exists. E,g.: module.class.method name"
    )
    is_generated: bool = Field(
        None, description="Reflects if the unit is dynamically generated e.g. by GenAI"
    )
    consumed_resources: Optional[List[str]] = Field(
        None, description="List of resource IDs consumed by the unit"
    )

class RelationType(str, Enum):
        """
        Types of metric. 
        """
        OR = "OR"
        XOR = "XOR"
        AND = "AND"


class NodeType(str,Enum):
    START='start'
    END='end'
    OR = "OR"
    XOR = "XOR"
    AND = "AND"
       
class Relation(Element):
    source_ids: Optional[List[str]] = Field(
        None, description="Optional list of source intelligent units IDs."
    )
    destination_ids: Optional[List[str]] = Field(
        None, description="Optional list of destination intelligent units IDs."
    )
    weight: Optional[int] = Field(
        None, description="The weight associated with the relation."
    )
    relation_type: Optional[Union[RelationType, str]] = Field(
        None, description="Optional type of relation - can be predefined enum or custom string"
    )
