import os
import json
import time
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from .schemas import LLMAnalysisResult
from .ollama import OllamaClient

load_dotenv()

class LLMProviderNotConfiguredException(Exception):
    pass

class DocumentInput:
    def __init__(self, document_id: str, filename: str, text: str, page: Optional[int] = None):
        self.document_id = document_id
        self.filename = filename
        self.text = text
        self.page = page

class AnalysisInput:
    def __init__(self, radicado: str, metadata: Dict[str, Any], solicitud_text: str, documents: List[DocumentInput]):
        self.radicado = radicado
        self.metadata = metadata
        self.solicitud_text = solicitud_text
        self.documents = documents

def get_configured_provider() -> Optional[str]:
    if os.getenv("LLM_PROVIDER") == "ollama":
        return "ollama"
    return None

def build_prompt(analysis_input: AnalysisInput) -> str:
    schema = LLMAnalysisResult.model_json_schema()
    
    docs_text = ""
    for d in analysis_input.documents:
        docs_text += f"\n--- DOCUMENTO ID: {d.document_id} | FILENAME: {d.filename} ---\n{d.text}\n"
        
    prompt = f"""Eres un analista documental experto de BotSAC. Tu objetivo es analizar un expediente y extraer la información basándote ESTRICTAMENTE en la evidencia proporcionada.
NO INVENTES NADA. Si algo no consta, usa 'NO_DETERMINADA' o 'NO_EVIDENCIADA'.

### METADATA DEL CASO
Radicado: {analysis_input.radicado}
Metadatos: {json.dumps(analysis_input.metadata, ensure_ascii=False)}

### SOLICITUD ORIGINAL
{analysis_input.solicitud_text}

### DOCUMENTOS ADJUNTOS
{docs_text}

### INSTRUCCIONES DE SALIDA
Debes responder ÚNICAMENTE con un objeto JSON válido que cumpla estrictamente con este esquema JSON:
{json.dumps(schema, ensure_ascii=False)}

Asegúrate de que cada afirmación tenga su respectivo `source_evidence`.
"""
    return prompt

def analyze_case(analysis_input: AnalysisInput) -> Dict[str, Any]:
    provider = get_configured_provider()
    
    if provider != "ollama":
        raise LLMProviderNotConfiguredException("LLM_PROVIDER_NOT_CONFIGURED")
        
    client = OllamaClient()
    model = os.getenv("LLM_MODEL", "llama3.1:latest")
    
    # 1. Preparación
    start_prep = time.time()
    prompt = build_prompt(analysis_input)
    prep_time = time.time() - start_prep
    
    # 2. Inferencia
    start_inf = time.time()
    gen_result = client.generate_structured(model, prompt)
    inf_time = time.time() - start_inf
    
    if gen_result.get("status") == "success":
        raw_resp = gen_result.get("response")
        
        # Validar Pydantic
        try:
            validated = LLMAnalysisResult.model_validate(raw_resp)
            return {
                "status": "success",
                "provider": "ollama",
                "model": model,
                "analysis": validated.model_dump(),
                "latency_prep_ms": round(prep_time * 1000, 2),
                "latency_inf_ms": round(inf_time * 1000, 2),
                "latency_total_ms": round((prep_time + inf_time) * 1000, 2)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Fallo en validación Pydantic: {str(e)}",
                "raw_response": raw_resp
            }
            
    return {
        "status": "error",
        "error": gen_result.get("error")
    }
