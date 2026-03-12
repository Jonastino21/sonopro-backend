# ─────────────────────────────────────────
# SONOPRO — Schémas Pydantic
# ─────────────────────────────────────────

from pydantic import BaseModel
from typing import Optional

class EnhanceResponse(BaseModel):
    fileId:   str
    duration: float
    preset:   str
    format:   str
    bitDepth: int

class ErrorResponse(BaseModel):
    detail: str

class HealthResponse(BaseModel):
    status:  str
    version: str = "1.0.0"