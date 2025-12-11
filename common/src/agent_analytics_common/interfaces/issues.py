import json
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
from enum import Enum
from datetime import datetime, timezone
from agent_analytics_common.interfaces.relatable_element import RelatableElement

class IssueLevel(str, Enum):
    """
    Levels for report.
    """
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"

class Issue(RelatableElement):
    timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="The time the issue was detected (ISO formatted string)"
    )    
    effect: List[str] = Field(
        default_factory=list, description="The effect of the issue on the corresponding element"
    )
    level: IssueLevel = Field(
        default=IssueLevel.WARNING, description="Severity level of the issue"
    )
    confidence: Optional[float] = Field(
        default=None, description="Confidence for issue detection in (0,1) scale"
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Issue':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'Issue':
        """Create a builder from a JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
