# metric classes
from pydantic import BaseModel


class metricRecorder(BaseModel):
    type: str = "failure"
    name: str = None
    value: str = None
    message: str = None
