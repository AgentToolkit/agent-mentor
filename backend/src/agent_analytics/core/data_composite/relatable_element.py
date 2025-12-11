from abc import ABC, ABCMeta
from typing import Generic, List, TypeVar
from agent_analytics.core.data_composite.element import ElementComposite,_CREATION_TOKEN
from agent_analytics.core.data.relatable_element_data import RelatableElementData

R = TypeVar('R', bound=RelatableElementData)

class RelatableElementComposite(ElementComposite[R], Generic[R],metaclass=ABCMeta):
       
    def __init__(self, data_manager: "DataManager", reletable_element_data: R,*, _token: object = None):
        super().__init__(data_manager, reletable_element_data, _token=_token)
        
    @property
    #For all objects fetch all related elements: (can also separate to different properties): Metrics,Issues,Recommendations
    async def related_to(self)-> List['ElementComposite']:
        return await self._data_manager.get_related_elements_for_artifact(self)
    
    @property
    def related_to_ids(self) -> List[str]:
        return self._data_object.related_to_ids
    
    @property
    def related_to_types(self) -> List[str]:
        return self._data_object.related_to_types
