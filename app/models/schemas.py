from pydantic import BaseModel
from typing import Optional

class EnhanceResponse(BaseModel):
    fileId:   str
    duration: float
    preset:   str
    format:   str
    bitDepth: int

class JobStatus(BaseModel):
    fileId:   str
    step:     int
    progress: float
    done:     bool
    error:    Optional[str]
    duration: float

class HealthResponse(BaseModel):
    status:  str
    version: str = "1.0.0"