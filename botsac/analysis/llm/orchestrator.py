import os
import json
import time
import hashlib
from typing import Dict, Any, List, Optional
from botsac.analysis.llm.ollama import OllamaClient
from botsac.analysis.llm.staged_schemas import (
    RequestAnalysis, DocumentAnalysis, ResponseAnalysis, 
    EvidenceAnalysis, ComparisonAnalysis, FinalAnalysis
)
from pydantic import BaseModel

class StagedAnalyzer:
    def __init__(self):
        self.client = OllamaClient()
        self.model = os.getenv("LLM_MODEL", "llama3.1:latest")
        self.pipeline_version = "v1"
        self.prompt_version = "v1"
        self.metrics = {
            "stages": {},
            "total_latency_ms": 0,
            "total_calls": 0,
            "validation_errors": 0
        }
    
    def _generate_cache_key(self, content: str) -> str:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return f"{content_hash}_{self.prompt_version}_{self.model}"
        
    def _check_cache(self, cache_dir: str, cache_key: str) -> Optional[Dict]:
        if not cache_dir:
            return None
        cache_path = os.path.join(cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return None
        
    def _save_cache(self, cache_dir: str, cache_key: str, data: Dict):
        if not cache_dir:
            return
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{cache_key}.json")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def _invoke_worker(
        self, 
        stage_name: str, 
        prompt: str, 
        schema_model: BaseModel, 
        cache_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        
        cache_key = self._generate_cache_key(prompt)
        cached_result = self._check_cache(cache_dir, cache_key)
        
        start_time = time.time()
        
        if cached_result:
            latency = time.time() - start_time
            self._update_metrics(stage_name, latency, True, "CACHED")
            return {"status": "success", "data": cached_result, "cached": True}
            
        # Llamar a LLM
        schema_json = json.dumps(schema_model.model_json_schema(), ensure_ascii=False)
        full_prompt = f"{prompt}\n\nResponde ÚNICAMENTE con JSON válido usando este esquema:\n{schema_json}"
        
        self.metrics["total_calls"] += 1
        result = self.client.generate_structured(self.model, full_prompt)
        
        latency = time.time() - start_time
        
        if result.get("status") == "success":
            raw_data = result.get("response")
            try:
                validated_data = schema_model.model_validate(raw_data).model_dump()
                self._save_cache(cache_dir, cache_key, validated_data)
                self._update_metrics(stage_name, latency, True, "SUCCESS")
                return {"status": "success", "data": validated_data, "cached": False}
            except Exception as e:
                self.metrics["validation_errors"] += 1
                self._update_metrics(stage_name, latency, False, "VALIDATION_ERROR")
                return {"status": "error", "error": f"Pydantic Validation: {str(e)}", "raw": raw_data}
        else:
            self._update_metrics(stage_name, latency, False, "LLM_ERROR")
            return {"status": "error", "error": result.get("error")}

    def _update_metrics(self, stage: str, latency_sec: float, success: bool, status: str):
        ms = round(latency_sec * 1000, 2)
        self.metrics["stages"][stage] = {
            "latency_ms": ms,
            "success": success,
            "status": status
        }
        self.metrics["total_latency_ms"] += ms

    def analyze_request(self, solicitud_text: str, cache_dir: str = None) -> Dict:
        prompt = f"Analiza esta solicitud ciudadana:\n\n{solicitud_text}"
        return self._invoke_worker("REQUEST_ANALYSIS", prompt, RequestAnalysis, cache_dir)
        
    def analyze_document(self, doc_id: str, doc_text: str, cache_dir: str = None) -> Dict:
        prompt = f"Analiza este documento individual (ID: {doc_id}):\n\n{doc_text}"
        return self._invoke_worker(f"DOCUMENT_ANALYSIS_{doc_id}", prompt, DocumentAnalysis, cache_dir)
        
    def analyze_response(self, request_data: Dict, doc_text: str, cache_dir: str = None) -> Dict:
        req_json = json.dumps(request_data, ensure_ascii=False)
        prompt = f"Esta es la solicitud original:\n{req_json}\n\nEste es el documento de respuesta emitido:\n{doc_text}\n\nExtrae la información de la respuesta."
        return self._invoke_worker("RESPONSE_ANALYSIS", prompt, ResponseAnalysis, cache_dir)
        
    def analyze_evidence(self, response_data: Dict, docs_text_list: List[str], cache_dir: str = None) -> Dict:
        resp_json = json.dumps(response_data.get("claims_requiring_support", []), ensure_ascii=False)
        docs_context = "\n---\n".join(docs_text_list)
        prompt = f"Busca evidencia en estos documentos:\n{docs_context}\n\nPara las siguientes afirmaciones de la respuesta:\n{resp_json}"
        return self._invoke_worker("EVIDENCE_ANALYSIS", prompt, EvidenceAnalysis, cache_dir)
        
    def compare_request_response(self, req_data: Dict, resp_data: Dict, ev_data: Dict, cache_dir: str = None) -> Dict:
        req_json = json.dumps(req_data, ensure_ascii=False)
        resp_json = json.dumps(resp_data, ensure_ascii=False)
        ev_json = json.dumps(ev_data, ensure_ascii=False)
        
        prompt = f"Compara la solicitud con la respuesta dada la evidencia.\n\nSOLICITUD:\n{req_json}\n\nRESPUESTA:\n{resp_json}\n\nEVIDENCIA:\n{ev_json}\n\nDetermina el estado de cada punto de la solicitud."
        return self._invoke_worker("COMPARISON", prompt, ComparisonAnalysis, cache_dir)
        
    def synthesize_case(self, req_data: Dict, resp_data: Dict, ev_data: Dict, comp_data: Dict, meta: Dict, cache_dir: str = None) -> Dict:
        context = {
            "metadata": meta,
            "request": req_data,
            "response": resp_data,
            "evidence": ev_data,
            "comparison": comp_data
        }
        ctx_json = json.dumps(context, ensure_ascii=False)
        prompt = f"Genera un resumen ejecutivo final del caso usando estos datos procesados (sin ver los documentos completos):\n\n{ctx_json}"
        return self._invoke_worker("SYNTHESIS", prompt, FinalAnalysis, cache_dir)
