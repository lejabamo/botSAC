from pydantic import BaseModel
from typing import List

class EvidenceCheck(BaseModel):
    field: str
    value: str
    supported: bool
    evidence: str
    reason: str

class RequestEvidenceReport(BaseModel):
    checks: List[EvidenceCheck]
