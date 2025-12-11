from datetime import datetime
from typing import Any

from pydantic import model_validator

from agent_analytics.core.data.element_data import ElementData


class BaseTraceData(ElementData):
    """Base class for a trace"""
    start_time: datetime | None = None
    end_time: datetime | None = None
    service_name: str | None = None
    num_of_spans: int | None = -1
    failures: dict[str, int] | None={}
    agent_ids: list[str] | None=[]

    # Mark BaseTrace as non-storable

    @classmethod
    def is_storable(cls) -> bool:
        """Returns whether this artifact type can be stored in persistence layer"""
        # Look for _storable in class.__dict__ to get class-specific value
        return False


    @model_validator(mode='before')
    @classmethod
    def ensure_null_parent(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data['root_id'] = None
        return data


    @classmethod
    async def get_by_id(cls,data_manager: 'DataManager',element_id:str) -> "BaseTraceData":
        return await data_manager.get_trace(element_id)
