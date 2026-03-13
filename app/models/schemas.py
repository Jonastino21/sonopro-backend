from pydantic import BaseModel

class EnhanceResponse(BaseModel):
    fileId:   str
    duration: float
    preset:   str
    format:   str
    bitDepth: int

class HealthResponse(BaseModel):
    status:  str
    version: str = "1.0.0"