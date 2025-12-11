from abc import ABC, abstractclassmethod, abstractmethod
from pydantic import BaseModel, ConfigDict,Field, model_validator
from typing import Generic, List,Any, Dict, Type, TypeVar
from agent_analytics.core.data.base_data_manager import DataManager
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
from abc import ABC, abstractmethod
import traceback

InputT = TypeVar('InputT', bound=BaseModel)
OutputT = TypeVar('OutputT', bound=BaseModel)


class ExecutionStatus(str,Enum):
    """Possible states of analytics execution"""
    SUCCESS = "success"
    FAILURE = "failure"
    IN_PROGRESS = "in_progress"
    TIMEOUT = "timeout"
    INVALID_CONFIG = "invalid_config"


class ExecutionError(BaseModel):
    error_type: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    stacktrace: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def from_exception(cls, e: Exception, include_stacktrace: bool = True) -> 'ExecutionError':
        return cls(
            error_type=e.__class__.__name__,
            message=str(e),
            stacktrace=traceback.format_exc() if include_stacktrace else None
        )


class ExecutionResult(BaseModel, Generic[OutputT]):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    result_id: str = None 
    analytics_id: str
    status: ExecutionStatus = Field(..., description="Execution status of the analytics")
    error: Optional[ExecutionError] = None
    execution_time: Optional[float] = None
    start_time: datetime = None 
    end_time: Optional[datetime] = None
    config_used: Optional[Dict[str, Any]] = None
    input_data_used: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    
    # This is the field developers should use
    output: Optional[OutputT] = Field(None, exclude=True)  # exclude=True means it won't appear in model_dump()
    
    # This is the field that gets serialized
    output_result: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def validate_output(self) -> 'ExecutionResult':
        if self.status == ExecutionStatus.SUCCESS:
            if self.output is None and not self.output_result:
                raise ValueError("Either output_model must be provided or output_result must be non-empty when status is SUCCESS")
            if self.output is not None:
                # Access the actual model instance
                model_instance = self.output
                if isinstance(model_instance, BaseModel):
                    self.output_result = model_instance.model_dump()
                else:
                    raise ValueError("output_model must be a Pydantic BaseModel instance")
        elif self.output is not None:
            raise ValueError("output_model should not be provided when status is not SUCCESS")
        return self

    def __init__(self, **data):
        if 'start_time' not in data:
            data['start_time'] = datetime.utcnow()
        super().__init__(**data)
        if not self.result_id:
            timestamp = self.start_time.strftime("%Y%m%d%H%M%S.%f")
            self.result_id = f"{self.analytics_id}_{timestamp}" 
                        
    def complete_execution(self, execution_time: float):
        self.execution_time = execution_time
        self.end_time = datetime.utcnow()

class BaseAnalyticsPlugin(Generic[InputT, OutputT], ABC):
    """Base class for analytics implementations"""
    @classmethod
    @abstractmethod
    def get_input_model(cls) -> Type[InputT]:
        """Must be implemented to return the Pydantic model for input validation"""
        raise NotImplementedError("Subclasses must implement get_input_model")
        
    @classmethod
    @abstractmethod
    def get_output_model(cls) -> Type[OutputT]:
        """Must be implemented to return the Pydantic model for input validation"""
        raise NotImplementedError("Subclasses must implement get_input_model")
    
    @abstractmethod
    async def _execute(self, analytics_id: str, data_manager: DataManager, input_data: InputT, config: Dict[str, Any]) -> ExecutionResult[OutputT]:
        """
        Internal execution method to be implemented by concrete analytics classes.
        
        Args:
            analytics_id: ID of the analytics being executed
            data_manager: Data manager instance for data operations
            input_data: Dictionary containing input data
            config: Dictionary containing configuration parameters
            
        Returns:
            ExecutionResult object containing execution status and results
        """
        pass

    async def execute(self, analytics_id: str, data_manager: DataManager, input_data: Dict[str, Any], config: Dict[str, Any]) -> ExecutionResult[OutputT]:
        """
        Public execute method that ensures proper initialization of ExecutionResult.
        
        Args:
            analytics_id: ID of the analytics being executed
            data_manager: Data manager instance for data operations
            input_data: Dictionary containing input data
            config: Dictionary containing configuration parameters
            
        Returns:
            ExecutionResult object with guaranteed initialization of required fields
        """
        
        try:
            # Validate and convert input to typed model
            input_model = self.get_input_model()
            typed_input = input_model.model_validate(input_data)
            
            # Execute with typed input
            result = await self._execute(analytics_id, data_manager, typed_input, config)                        
            
            # Ensure required fields are set
            if not result.config_used:
                result.config_used = config
            if not result.input_data_used:
                result.input_data_used = input_data
                
            # analytics_id should always match the one provided
            result.analytics_id = analytics_id
            
            return result
            
        except Exception as e:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError.from_exception(e)
            )
            
    