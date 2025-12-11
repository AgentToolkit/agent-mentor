import uuid
from pydantic import BaseModel, Field, model_validator, validator
from typing import List, Optional, Any, Union
from enum import Enum
from typing import Dict

AttributeValue = Union[str, bool, int, float, List[Union[str, bool, int, float]],dict[str,Any]]

class Tag(str, Enum):
    GENERAL = "GENERAL"
    VALIDATION = "VALIDATION"
    ROUTING = "ROUTING"
    MANAGING = "MANAGING"
    DECOMPOSITION = "DECOMPOSITION"
    LLM = "LLM"
    TOOLS = "TOOLS"
    CODING = "CODING"
    SUMMARIZATION = "SUMMARIZATION"
    RETRIEVAL = "RETRIEVAL"
    PROMPTING = "PROMPTING"
    CONTENT = "CONTENT"
    CONVERSATIONAL = "CONVERSATIONAL"
    QNA = "QNA"
    CLASSIFICATION = "CLASSIFICATION"
    TRANSLATION = "TRANSLATION"
    IMAGING = "IMAGING"
    AUDIO = "AUDIO"
    VIDEO = "VIDEO"



class Element(BaseModel):
    element_id: str = None
       
    name: Optional[str] = Field(description="The display name of the data element", default=None)
    description: Optional[str] = Field(
        description="Description of the data element in natural language", default=None
    )
    tags: Optional[List[Union[Tag,str]]] = Field(
        default=None, description="The tags that can be used to classify the data element"
    )
    attributes: dict[str, AttributeValue] = Field(
        description="A dictionary of data element specific fields", default_factory=dict
    )
    
    # Override model_dump to add the 'type' field
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        # Get the regular serialized dictionary
        data = super().model_dump(**kwargs)
        
        # Add the type field based on the class name
        data['type'] = self.__class__.__name__
        
        return data
    
    @classmethod
    def generate_class_name(cls) -> str:
        """Generate the prefix to use for element IDs based on the class name."""
        return cls.__name__
    
    def generate_id_prefix(self) -> str:
        """Generate a complete element ID using the prefix."""
        # Call the class method on the class directly, not on self
        prefix = self.__class__.generate_class_name()
        return prefix
    
    
    @model_validator(mode='after')
    def set_element_id(self):
        if self.element_id is None:
            self.element_id = f"{self.generate_id_prefix()}-{uuid.uuid4()}"
        return self
    
  
