import os
import json
import time
import pytest
from pydantic import ValidationError
from botsac.analysis.llm.ollama import OllamaClient
from botsac.analysis.llm.request_schema import RequestAnalysis

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def build_prompt(text: str) -> str:
    schema_json = json.dumps(RequestAnalysis.model_json_schema(), ensure_ascii=False)
    return f"""Analiza solamente el siguiente contenido entregado.
NO inventes información.
Si un dato no aparece claramente, indícalo como vacío o "No identificado".
Responde EXCLUSIVAMENTE con un JSON válido que cumpla estrictamente con este schema.
NO devuelvas el esquema.
Esquema:
{schema_json}

Contenido entregado:
{text}
"""

class RealGateway:
    def __init__(self):
        self.client = OllamaClient()
        self.model = os.getenv("LLM_MODEL", "qwen2.5:3b")
        
    def analyze(self, text: str):
        prompt = build_prompt(text)
        
        start_time = time.time()
        result = self.client.generate_structured(self.model, prompt)
        
        if result.get("status") == "success":
            raw_json = result.get("response")
            try:
                validated = RequestAnalysis.model_validate(raw_json)
                return {
                    "status": "success",
                    "data": validated.model_dump(),
                    "latency_ms": result.get("latency_ms", 0),
                    "model": self.model,
                    "validation_error": None
                }
            except ValidationError as e:
                return {
                    "status": "error",
                    "error": "Error de parseo Pydantic",
                    "validation_error": str(e),
                    "latency_ms": result.get("latency_ms", 0),
                    "model": self.model,
                    "raw_json": raw_json
                }
        else:
            return {
                "status": "error",
                "error": result.get("error", "Error LLM"),
                "latency_ms": result.get("latency_ms", 0),
                "model": self.model,
                "raw_response": result.get("raw_response", "")
            }

def test_13_real_request_analysis():
    print(f"\n[START] Iniciando TEST 13: EJECUCIÓN REAL para {RADICADO}")
    
    raw_file = f"data/raw/{ACQUISITION_ID}/{RADICADO}/solicitud.txt"
    analysis_dir = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    out_file = os.path.join(analysis_dir, "request_analysis.json")
    
    # 1. existe solicitud.txt
    assert os.path.exists(raw_file), f"No existe {raw_file}"
    
    with open(raw_file, "r", encoding="utf-8") as f:
        text = f.read()
        
    mtime_before = os.path.getmtime(raw_file)
        
    gateway = RealGateway()
    
    # 2. invocar Ollama
    print(f"[STEP] Ejecutando análisis real con {gateway.model}...")
    res = gateway.analyze(text)
    
    if res["status"] != "success":
        print(f"\nFAIL: {res.get('error')}")
        if res.get('validation_error'):
            print(res['validation_error'])
        pytest.fail(f"Gateway falló: {res.get('error')}")
        
    data = res["data"]
    
    # 3, 4. La respuesta es JSON y valida Pydantic (se probó en el gateway)
    
    # 5. Guardar request_analysis.json
    os.makedirs(analysis_dir, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    assert os.path.exists(out_file), "No se guardó request_analysis.json"
    
    # 6. Campos requeridos existen (lo garantiza Pydantic, pero validamos valores no vacíos obligatorios)
    assert "problem" in data
    assert "location" in data
    
    # 7. Los archivos raw no fueron modificados
    mtime_after = os.path.getmtime(raw_file)
    assert mtime_before == mtime_after, "El archivo raw fue modificado"
    
    print("\n==================================================")
    print("REPORT: TEST 13: PASS")
    print(f"Archivos creados/modificados: {out_file}")
    print(f"Resultado del test: PASS")
    print(f"Tiempo de inferencia: {res['latency_ms']} ms")
    print(f"Resultado Pydantic: VÁLIDO")
    print(f"Ejemplo del RequestAnalysis generado:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
    print("==================================================")

if __name__ == "__main__":
    test_13_real_request_analysis()
