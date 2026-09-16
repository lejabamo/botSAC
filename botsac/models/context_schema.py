from pydantic import BaseModel
from typing import List, Dict, Any
from botsac.models.document_schema import DocumentPage

class DocumentContext(BaseModel):
    filename: str
    sha256: str
    processing_type: str
    pages: List[DocumentPage]

class RadicadoContext(BaseModel):
    radicado: str
    metadata: Dict[str, Any]
    solicitud: str
    documentos: List[DocumentContext]
    novedades: List[Dict[str, Any]]
