from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

@dataclass
class Acquisition:
    id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    dependency: Optional[str] = None
    status_filter: Optional[str] = None
    user: Optional[str] = None
    total_found: int = 0
    total_processed: int = 0
    total_success: int = 0
    total_errors: int = 0

@dataclass
class Dependency:
    id: str
    name: str

@dataclass
class User:
    id: str
    name: str
    assigned_count: int = 0

@dataclass
class SacDocument:
    document_id: str
    radicado: str
    original_name: str
    local_path: str
    extension: str
    size: int
    sha256: str
    downloaded_at: datetime

@dataclass
class SacEvent:
    timestamp: datetime
    type: str
    source: str
    description: str
    metadata: dict = field(default_factory=dict)

@dataclass
class SacCase:
    radicado: str
    funcionario: str
    dependencia: str
    categoria: str
    metadata: dict
    solicitud: str
    documentos: List[SacDocument] = field(default_factory=list)
    novedades: List[SacEvent] = field(default_factory=list)
    source_url: Optional[str] = None
    acquisition_id: Optional[str] = None
    captured_at: Optional[datetime] = None
