from abc import ABC, abstractmethod
from typing import ClassVar, Generic, TypeVar, Type, Optional, List, Dict, Any
import inspect




from agent_analytics.core.data.element_data import ElementData, E

# A unique object instance to act as a private creation token
_CREATION_TOKEN = object()

# Type variable for Element subclasses
T = TypeVar('T', bound='ElementComposite')

class ElementComposite(ABC,Generic[E]):
    """
    Base class for all logical composite objects
    
    Each Element has an underlying data object that is persisted,
    and may have references to other Element objects
    """
    
    # Class variable that specifies the corresponding data class
    data_class: ClassVar[Type[ElementData]] = ElementData
    
    @classmethod
    def get_element_class_for_data(cls, data_object: ElementData) -> Type['ElementComposite']:
        """
        Default implementation that returns the class itself.
        Subclasses can override this to provide more sophisticated mapping.
        """
        return cls
             
    def __init__(self, data_manager: "DataManager", data_object: E,*, _token: object = None):
        """
        Initialize the Element.

        IMPORTANT: Direct instantiation is discouraged. Use factory methods
                     like '.create()' or obtain instances via AnalyticsDataManager.
        """
        # --- Token Check ---
        if _token is not _CREATION_TOKEN:
             # Get caller information for a more informative error message
            caller_module = "Unknown"
            caller_function = "Unknown"
            try:
                caller_frame = inspect.currentframe().f_back
                if caller_frame:
                    caller_module = caller_frame.f_globals.get('__name__', 'N/A')
                    caller_function = caller_frame.f_code.co_name
            except Exception:
                pass # Avoid errors during error reporting

            raise RuntimeError(
                f"Direct instantiation of {type(self).__name__} from module '{caller_module}' "
                f"(function: '{caller_function}') is not allowed. "
                f"Use the class's 'create()' method or AnalyticsDataManager methods instead."
            )
        # --- End Token Check ---
        self._data_manager = data_manager
        self._data_object = data_object
        
    @property
    def element_id(self) -> str:
        """Get the element ID from the underlying data object"""
        return self._data_object.element_id
    
    #TODO not sure we need this at this level
    @property
    def root_id(self) -> Optional[str]:
        return self._data_object.root_id

    @property
    def name(self) -> Optional[str]:
        return self._data_object.name

    @property
    def description(self) -> Optional[str]:
        return self._data_object.description

    @property
    def tags(self) -> Optional[List[str]]:
        return self._data_object.tags

    @property
    def plugin_metadata_id(self) -> Optional[str]:
        return self._data_object.plugin_metadata_id
    
    @property
    def attributes(self) -> dict[str, Any]:
        return self._data_object.attributes
    
    @property
    #For all objects fetch all related elements: (can also separate to different properties): Metrics,Issues,Recommendations
    async def related_elements(self)-> List['ElementComposite']:
        return await self._data_manager.get_elements_related_to_artifact(self)
    
    #TODO: not sure we need such method, perhaps better to have it as data manager method? 
    @classmethod
    async def get_by_id(cls: Type[T], data_manager: "DataManager", id: str) -> Optional[T]:
        """Get an element by its ID"""
        obj = await data_manager.get_by_id(id, cls)
        return obj

    def to_json(self, indent: int = 2, sort_keys: bool = True) -> str:
        return self._data_object.to_json(indent=indent, sort_keys=sort_keys)
    
    def __json__(self) -> Dict[str, Any]:
        """
        Make the object automatically JSON serializable.
        """
        return self.model_dump()

    def __str__(self) -> str:
        return self._data_object.to_json(indent=2)
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def for_default(self) -> Dict[str, Any]:
        """
        Method to be used with json.dumps(obj, default=lambda o: getattr(o, 'for_default', lambda: {})())
        """
        return self.model_dump()
    
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """
        Delegate model_dump to the underlying data object, with possible enhancements.
        """
        data = self._data_object.model_dump(**kwargs) 
        if 'type' in data:
            del data['type']        
        return data
    
    @classmethod
    def from_dict(cls: Type[T], data_manager: "DataManager", data_dict: Dict[str, Any]) -> T:
        """
        Create a composite object from a dictionary.
        This is the reverse operation of model_dump().
        
        Args:
            data_manager: The data manager instance
            data_dict: Dictionary containing the element data
            
        Returns:
            A new instance of the composite object
        """
        # Create the data object from the dictionary
        data_object = cls.data_class.model_validate(data_dict)
        
        # Get the appropriate element class (in case of inheritance)
        element_class = cls.get_element_class_for_data(data_object)
        
        # Create a new instance with the creation token
        return element_class(data_manager, data_object, _token=_CREATION_TOKEN)