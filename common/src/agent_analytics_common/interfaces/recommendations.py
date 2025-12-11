from pydantic import BaseModel, Field
from typing import Optional, List,Dict,Any
from enum import Enum
from datetime import datetime,timezone
from agent_analytics_common.interfaces.relatable_element import RelatableElement
import json

class RecommendationLevel(str, Enum):
    """
    Levels of impact.
    """
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MODERATE = "MODERATE"
    MINOR = "MINOR"

class Recommendation(RelatableElement):
    timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), 
        description="The time the recommendation was generated (ISO formatted string)"
    )    
    effect: List[str] = Field(
        default_factory=list, 
        description="The effect of the recommendation on the corresponding element"
    )
    level: RecommendationLevel = Field(
        default=RecommendationLevel.MODERATE, 
        description="Impact level of the recommendation"
    )
    

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Recommendation':
        """Create a recommendation from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'Recommendation':
        """Create a recommendation from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)