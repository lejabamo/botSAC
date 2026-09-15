from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class EvidenceSource(BaseModel):
    document_id: str
    filename: Optional[str] = None
    page: Optional[int] = None
    excerpt: str

class DocumentClassification(BaseModel):
    document_id: str
    filename: str
    classification: Literal["SOLICITUD", "RESPUESTA", "SOPORTE", "CORRESPONDENCIA", "ANEXO", "OTRO"]
    reason: str
    confidence: float

class SolicitudResumen(BaseModel):
    problema: str
    municipio: str
    institucion: str
    sede: Optional[str] = None
    solicitud_principal: str
    actuaciones_solicitadas: List[str]

class Pretension(BaseModel):
    id: int
    texto: str
    source_document: str
    source_location: str

class RespuestaResumen(BaseModel):
    status: Literal["IDENTIFICADA", "NO_IDENTIFICADA"]
    descripcion_general: Optional[str] = None
    actuacion_informada: Optional[str] = None
    resultados: Optional[str] = None
    fechas_mencionadas: List[str] = []
    compromisos: List[str] = []

class PretensionStatus(BaseModel):
    pretension_id: int
    estado: Literal["ATENDIDA", "PARCIAL", "NO_EVIDENCIADA", "NO_DETERMINADA"]
    respuesta_asociada: Optional[str] = None
    evidence: List[EvidenceSource] = []

class SoporteDocumental(BaseModel):
    afirmacion: str
    estado: Literal["SOPORTADO", "NO_SOPORTADO", "NO_DETERMINADO"]
    evidence: List[EvidenceSource] = []

class TimelineEvent(BaseModel):
    fecha: str
    evento: str
    documento: str
    pagina: Optional[int] = None

class Alerta(BaseModel):
    tipo: str
    descripcion: str
    evidence: List[EvidenceSource] = []

class ExecutiveSummary(BaseModel):
    radicado: str
    municipio: str
    institucion: str
    solicitud: str
    respuesta: str
    soportes: str
    vacios: str
    alertas: str

class LLMAnalysisResult(BaseModel):
    document_classification: List[DocumentClassification]
    solicitud_resumen: SolicitudResumen
    pretensiones: List[Pretension]
    respuesta_resumen: RespuestaResumen
    matriz_comparativa: List[PretensionStatus]
    soportes: List[SoporteDocumental]
    timeline: List[TimelineEvent]
    alertas: List[Alerta]
    executive_summary: ExecutiveSummary
