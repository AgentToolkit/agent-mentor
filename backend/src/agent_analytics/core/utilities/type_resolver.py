import importlib
from typing import Type

from agent_analytics.core.data.element_data import ElementData
from agent_analytics.core.data_composite.element import ElementComposite
from typing import List, Type
from agent_analytics.core.data_composite.relatable_element import RelatableElementComposite
from agent_analytics.core.data.relatable_element_data import RelatableElementData


class TypeResolutionUtils:
    """Utility class for type name resolution and retrieval."""
    
    @staticmethod
    def get_fully_qualified_type_name(obj: ElementData) -> str:
        """
        Get the fully qualified type name of an object.
        
        Args:
            obj: The object to get the type name from
            
        Returns:
            A string representing the fully qualified type name (e.g., 'package.module.ClassName')
        """
        obj_type = type(obj)
        return TypeResolutionUtils.get_fully_qualified_type_name_for_type(obj_type)
    
    @staticmethod
    def get_fully_qualified_type_name_for_type(artifact_type: Type[ElementData]) -> str:
        """
        Get the fully qualified type name of an object.
        
        Args:
            obj: The object to get the type name from
            
        Returns:
            A string representing the fully qualified type name (e.g., 'package.module.ClassName')
        """
        module = artifact_type.__module__
        class_name = artifact_type.__name__
        return f"{module}.{class_name}"
    
    @staticmethod
    def resolve_type_from_fully_qualified_name(fully_qualified_name: str) -> Type[ElementData]:
        """
        Resolve a fully qualified type name to the actual type.
        
        Args:
            fully_qualified_name: The fully qualified name to resolve (e.g., 'package.module.ClassName')
            
        Returns:
            The actual type object
            
        Raises:
            ValueError: If the type could not be resolved
        """
        try:
            # Split into module path and class name
            module_path, class_name = fully_qualified_name.rsplit('.', 1)
            
            # Import the module
            module = importlib.import_module(module_path)
            
            # Get the class from the module
            return getattr(module, class_name)
        except (ImportError, AttributeError, ValueError) as e:
            raise ValueError(f"Could not resolve type: {fully_qualified_name}") from e
        
    @staticmethod    
    def get_relatable_element_subclasses() -> List[Type]:
        """Get all subclasses of RelatableElement using __subclasses__()"""
        
        def get_all_subclasses(cls):
            direct_subclasses = cls.__subclasses__()
            return direct_subclasses + [
                subclass 
                for direct in direct_subclasses 
                for subclass in get_all_subclasses(direct)
            ]
        
        return [
            cls for cls in get_all_subclasses(RelatableElementComposite) 
            if getattr(cls, 'is_storable', lambda: True)()
        ]
    
    @staticmethod    
    def get_relatable_element_data_subclasses() -> List[Type]:
        """Get all subclasses of RelatableElement using __subclasses__()"""
        
        def get_all_subclasses(cls):
            direct_subclasses = cls.__subclasses__()
            return direct_subclasses + [
                subclass 
                for direct in direct_subclasses 
                for subclass in get_all_subclasses(direct)
            ]
        
        return [
            cls for cls in get_all_subclasses(RelatableElementData) 
            if getattr(cls, 'is_storable', lambda: True)()
        ]
        
    @staticmethod    
    def get_element_subclasses() -> List[Type[ElementComposite]]:
        """Get all subclasses of RelatableElement using __subclasses__()"""
        
        def get_all_subclasses(cls):
            direct_subclasses = cls.__subclasses__()
            return direct_subclasses + [
                subclass 
                for direct in direct_subclasses 
                for subclass in get_all_subclasses(direct)
            ]
        
        return [
            cls for cls in get_all_subclasses(ElementComposite) 
            if getattr(cls, 'is_storable', lambda: True)()
        ]
        
