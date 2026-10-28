from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SedeBase(BaseModel):
    nombre_institucion: str
    municipio: str
    nombre_sede: str

class SedeResponse(SedeBase):
    id_sede: int
    id_radicado: str
    class Config:
        from_attributes = True

class RadicadoBase(BaseModel):
    id_radicado: str
    asunto: str
    municipio: Optional[str] = None
    funcionario_asignado: Optional[str] = None
    remitente: Optional[str] = None
    categoria: Optional[str] = None
    fecha_creacion: Optional[datetime] = None
    fecha_vencimiento: Optional[datetime] = None
    estado_sac: Optional[str] = None
    estado_botsac: str = "POR_GESTIONAR"
    resumen_contexto: Optional[str] = None
    respuesta_sugerida: Optional[str] = None
    es_vencido: int = 0

class RadicadoCreate(RadicadoBase):
    pass

class RadicadoResponse(RadicadoBase):
    created_at: datetime
    updated_at: datetime
    sedes: List[SedeResponse] = []
    
    class Config:
        from_attributes = True
