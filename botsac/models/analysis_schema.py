from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DocumentSummary(BaseModel):
    filename: str
    purpose: str
    summary: str
    pages: List[int]

class Alert(BaseModel):
    type: str
    description: str
    severity: str

class AnalysisEvidence(BaseModel):
    claim: str
    filename: str
    page_number: int
    source_text: str

class RadicadoAnalysis(BaseModel):
    radicado: str
    summary: str
    topic: str
    citizen_or_sender: str
    institution_or_entity: str
    municipality: str
    key_facts: List[str]
    documents_summary: List[DocumentSummary]
    important_dates: List[str]
    alerts: List[Alert]
    evidence: List[AnalysisEvidence]

class DocumentMicroAnalysis(BaseModel):
    document_type: str
    summary: str
    key_facts: List[str]
    dates: List[str]
    pages_referenced: List[int]

class ReviewDocument(BaseModel):
    filename: str
    document_type: str
    summary: str
    pages: List[int]

class ReviewAlert(BaseModel):
    type: str
    description: str
    source: str

class ReviewTrace(BaseModel):
    source_type: str
    source_ref: str
    detail: str

class BotSACReview(BaseModel):
    radicado: str
    subject: str
    status_sac: str
    municipality: str
    requester: str
    request_summary: str
    documents: List[ReviewDocument]
    key_dates: List[str]
    alerts: List[ReviewAlert]
    trace: List[ReviewTrace]
    category: Optional[str] = None
    instituciones_sedes: Optional[List[Dict[str, Any]]] = None
    etapa_tramite: Optional[str] = None
    etapa_label: Optional[str] = None

