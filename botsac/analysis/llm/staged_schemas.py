from pydantic import BaseModel
from typing import List, Optional, Literal

# Common
class Evidence(BaseModel):
    source_document: str
    page: Optional[int] = None
    excerpt: str
    confidence: float

# FASE A
class RequestItem(BaseModel):
    id: int
    text: str

class RequestAnalysis(BaseModel):
    problem: str
    location: str
    institution: str
    requests: List[RequestItem]

# FASE B
class DocumentAnalysis(BaseModel):
    document_id: str
    classification: str
    summary: str
    key_dates: List[str]
    key_entities: List[str]

# FASE C: (Logic phase, no strict LLM schema needed, returns string document_id or "AMBIGUOUS")

# FASE D
class ResponseAnalysis(BaseModel):
    response_summary: str
    actions_reported: List[str]
    commitments: List[str]
    dates: List[str]
    claims_requiring_support: List[str]

# FASE E
class EvidenceClaim(BaseModel):
    claim: str
    support_status: Literal["SUPPORTED", "NOT_SUPPORTED", "NOT_DETERMINED"]
    sources: List[Evidence]

class EvidenceAnalysis(BaseModel):
    claims: List[EvidenceClaim]

# FASE F
class ComparisonItem(BaseModel):
    request_id: int
    status: Literal["ATENDIDA", "PARCIAL", "NO_EVIDENCIADA", "NO_DETERMINADA"]
    explanation: str
    evidence: List[Evidence]

class ComparisonAnalysis(BaseModel):
    items: List[ComparisonItem]

# FASE G
class FinalAnalysis(BaseModel):
    executive_summary: str
    alerts: List[str]
    review_flags: List[str]
