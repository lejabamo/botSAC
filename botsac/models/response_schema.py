from pydantic import BaseModel
from typing import Optional, List

class ResponseSource(BaseModel):
    content: str
    source: str

class ResponseDiscovery(BaseModel):
    status: str
    source_type: str
    source_reference: Optional[str] = None
    response_found: bool
    confidence: str
    evidence: List[str]
