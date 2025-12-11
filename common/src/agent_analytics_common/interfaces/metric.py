from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import Field,BaseModel,ConfigDict
from abc import ABCMeta
from typing import Literal,TypeVar,Generic,Tuple
from typing_extensions import TypedDict
from agent_analytics_common.interfaces.relatable_element import RelatableElement


#TODO: 
# 1. additional Metric types?
# 2. theoretically can remove the metric_type but assuming the plugin users will create metrics as json - how do we distinguish? based on value? Also assuming we can have
# different semantic types within the same parent type with the same structure the type might come in handy

T = TypeVar('T')  # Type variable for metric value
D = TypeVar('D', bound=Dict[Any, Any])  # TypeVar for dictionary types

class MetricCategory(str, Enum):
        """
        Levels for report.
        """
        PERFORMANCE = "CRITICAL"
        QUALITY = "ERROR"
        COST = "WARNING"
        HUMAN_IN_THE_LOOP = "HUMAN_IN_THE_LOOP"
        SECURITY = "SECURITY"
        INFO = "INFO"
        DEBUG = "DEBUG"
    
class MetricType(str, Enum):
        """
        Types of metric. 
        """
        NUMERIC = "NUMERIC"
        DISTRIBUTION = "DISTRIBUTION"
        STRING = "STRING"
        TIME_SERIES="TIME_SERIES"
        HISTOGRAM="HISTOGRAM"
        STATISTICS="STATISTICS"
        AGGREGATE="AGGREGATE"

class TimeInterval(TypedDict):
    lower_bound: datetime
    upper_bound: Optional[datetime]      

class MetricScope(BaseModel):
    """
    Scope dictionary for aggregated metrics.
    Contains field names and values indicating the scope of calculation.
    """
    
    time_interval: TimeInterval
    # Allow extra fields

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        },
        extra="allow"
    )
    
    def __init__(self, time_interval: TimeInterval, **kwargs: Any):
        super().__init__(time_interval=time_interval, **kwargs)
    
    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.__dict__.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
  
class Metric(RelatableElement,Generic[T],metaclass=ABCMeta):
    """
    Abstract base class for all metric interfaces.
    """
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None,
        },
        arbitrary_types_allowed=True
    )
    value: T = Field(description="The value associated with the metric")
    metric_type: MetricType
    units: Optional[str] = Field(default=None, description="The units of the metric value")        
    timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="The time the metric was recorded (ISO formatted string)",
    )
    scope: Optional[MetricScope] = Field(default=None, description="The scope for this metric calculation - contains time_interval and other field names/values indicating the scope of calculation")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Metric':
        """Create a builder from a dictionary"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> 'Metric':
        """Create a builder from a JSON string"""
        return cls.model_validate_json(json_str)
    
    def to_json(self) -> str:
        """Convert the metric to JSON string."""
        return self.model_dump_json()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the metric to dictionary."""
        return self.model_dump()

    def generate_id_prefix(self) -> str:
        """Override to use the parent interface class name."""
        # Call the generate_id_prefix on the Issue class directly
        prefix = Metric.generate_class_name()  # This will return "Metric"
        return prefix
    
        # Override model_dump to add the 'type' field and set it to the parent class name 
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        # Get the regular serialized dictionary
        data = super().model_dump(**kwargs)
        
        # Add the type field based on the class name
        data['type'] = 'Metric'
        
        return data

class NumericMetric(Metric[float]):
    """Interface for numeric metrics."""
    metric_type: Literal[MetricType.NUMERIC] = MetricType.NUMERIC     
    value: float = Field(..., description="The numeric value")


class StringMetric(Metric[str]):
    """Interface for string metrics."""
    metric_type: Literal[MetricType.STRING] = MetricType.STRING     
    value: str = Field(..., description="The string value")

class Distribution(Metric[D], Generic[D]):
    """Base class for distribution-like metrics with dictionary values."""
    value: D = Field(..., description="The distribution values")

class DistributionMetric(Distribution[Dict[str, float]]):
    """Interface for distribution metrics."""
    metric_type: Literal[MetricType.DISTRIBUTION] = MetricType.DISTRIBUTION    
    value: Dict[str, float] = Field(..., description="The distribution values")

class AggregateMetric(Metric[List['Metric']]):
    """Interface for aggregate metrics that contain multiple other metrics."""
    metric_type: Literal[MetricType.AGGREGATE] = MetricType.AGGREGATE
    value: List['Metric'] = Field(..., description="List of metrics contained in this aggregate")

@dataclass(frozen=True)  # immutable and hashable
class NumericInterval:
    lower_bound: float
    upper_bound: float
    
    def __hash__(self):
        return hash((self.lower_bound, self.upper_bound))
    
    def __eq__(self, other):
        if not isinstance(other, NumericInterval):
            return False
        return (self.lower_bound == other.lower_bound and 
                self.upper_bound == other.upper_bound)
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization"""
        return {
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'NumericInterval':
        """Create from dictionary for deserialization"""
        return cls(
            lower_bound=data["lower_bound"],
            upper_bound=data["upper_bound"]
        )



class AggregatedStats(TypedDict):
    count: int
    mean: float
    std: Optional[float]
    min: Optional[float]
    max: Optional[float]
    attributes: Optional[Dict]


class BasicStatsMetric(Metric[AggregatedStats]):
    metric_type: Literal[MetricType.STATISTICS] = MetricType.STATISTICS 
    value: AggregatedStats = Field(..., description="The aggregated stats values")
    
    
   

class HistogramMetric(Distribution[Dict[NumericInterval, float]]):
    metric_type: Literal[MetricType.HISTOGRAM] = MetricType.HISTOGRAM 
    value: Dict[NumericInterval, float] = Field(..., description="The histogram values")
    


class TimeSeriesMetric(Metric[List[Tuple[datetime,float]]]):
    metric_type: Literal[MetricType.TIME_SERIES] = MetricType.TIME_SERIES 
    value: List[Tuple[datetime, float]]= Field(..., description="The time series values")
    


