from pydantic import Field
from typing import Optional
from .iunits import IUnit

class Runnable(IUnit):
    input_schema: Optional[str] = Field(None, description="Stringified input parameters JSON Schema")
    output_schema: Optional[str] = Field(None, description="Stringified output parameters JSON Schema")
