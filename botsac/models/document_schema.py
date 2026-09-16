from pydantic import BaseModel
from typing import List

class DocumentSource(BaseModel):
    filename: str
    sha256: str
    page_count: int
    extraction_status: str
    
class DocumentPage(BaseModel):
    filename: str
    page_number: int
    text: str
    text_length: int
    status: str = "success"
    
class DocumentExtractionResult(BaseModel):
    document: DocumentSource
    pages: List[DocumentPage]
    processing_type: str
