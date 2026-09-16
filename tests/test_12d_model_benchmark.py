import os
import json
import time
import subprocess
import pytest
from botsac.analysis.llm.ollama import OllamaClient
from botsac.analysis.llm.staged_schemas import RequestAnalysis

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def check_hardware():
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"], 
                                capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().replace('\n', ' | ')
    except:
        pass
    return "NO DETERMINADO"

def test_12d_model_benchmark():
    print(f"\n[START] Iniciando TEST 12D: BENCHMARK RÁPIDO para {RADICADO}")
    
    raw_dir = f"data/raw/{ACQUISITION_ID}/{RADICADO}"
    logs_dir = "data/logs"
    os.makedirs(logs_dir, exist_ok=True)
    
    with open(os.path.join(raw_dir, "solicitud.txt"), "r", encoding="utf-8") as f:
        solicitud_text = f.read()
        
    client = OllamaClient()
    
    # Check if the desired model is installed
    models = client.list_models()
    model_name = "qwen2.5:3b"
    installed = any(m.get("name") == model_name for m in models)
    if not installed:
        model_name = "qwen2.5:latest" # Just in case it was tagged latest
        installed = any(m.get("name") == model_name for m in models)
    if not installed:
        # Fallback to whatever qwen model is there
        qwen_models = [m.get("name") for m in models if "qwen" in m.get("name").lower()]
        if qwen_models:
            model_name = qwen_models[0]
        else:
            pytest.fail("Ningún modelo qwen instalado para el benchmark.")
            
    print(f"[STEP] Usando modelo: {model_name}")
    
    schema_json = json.dumps(RequestAnalysis.model_json_schema(), ensure_ascii=False)
    # The prompt explicitly forbids the schema echoing by ensuring it produces an instance.
    prompt = f"Analiza esta solicitud ciudadana:\n\n{solicitud_text}\n\nProduce una INSTANCIA JSON válida que cumpla estrictamente con este esquema:\n{schema_json}\nNO devuelvas el esquema, devuelve los datos."
    
    benchmark_record = {
        "model": model_name,
        "size_gb": next((round(m.get("size", 0) / (1024**3), 2) for m in models if m.get("name") == model_name), 0),
        "vram_before": check_hardware(),
        "cold_latency_ms": 0,
        "warm_latency_ms": 0,
        "json_valid": False,
        "pydantic_valid": False,
        "quality": {},
        "status": "FAIL"
    }
    
    # 1. COLD START
    print(f"[STEP] Inferencia Cold Start...")
    res_cold = client.generate_structured(model_name, prompt)
    benchmark_record["cold_latency_ms"] = res_cold.get("latency_ms", 0)
    
    # 2. WARM INFERENCE
    print(f"[STEP] Inferencia Warm...")
    res_warm = client.generate_structured(model_name, prompt)
    benchmark_record["warm_latency_ms"] = res_warm.get("latency_ms", 0)
    
    benchmark_record["vram_after"] = check_hardware()
    
    # Validate final response (using warm response)
    if res_warm.get("status") == "success":
        benchmark_record["json_valid"] = True
        raw_json = res_warm.get("response")
        try:
            validated = RequestAnalysis.model_validate(raw_json)
            benchmark_record["pydantic_valid"] = True
            benchmark_record["quality"] = validated.model_dump()
            
            # Simple heuristic checks
            q = benchmark_record["quality"]
            if q.get("problem") and len(q.get("requests", [])) > 0:
                benchmark_record["status"] = "PASS"
            else:
                benchmark_record["status"] = "FAIL (No extrajo requests o problema)"
        except Exception as e:
            benchmark_record["status"] = f"FAIL Pydantic: {str(e)}"
    else:
        benchmark_record["status"] = f"FAIL JSON/LLM: {res_warm.get('error')}"
        
    log_file = os.path.join(logs_dir, "model_benchmark.json")
    
    # Load existing logs if they exist
    logs_data = {"models": []}
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                logs_data = json.load(f)
        except:
            pass
            
    logs_data["models"].append(benchmark_record)
    
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs_data, f, ensure_ascii=False, indent=2)
        
    print("\n==================================================")
    print(f"REPORT: TEST 12D: {benchmark_record['status']}")
    print(f"modelo: {benchmark_record['model']}")
    print(f"tamaño: {benchmark_record['size_gb']} GB")
    print(f"VRAM inicial: {benchmark_record['vram_before']}")
    print(f"VRAM final: {benchmark_record['vram_after']}")
    print(f"cold latency: {benchmark_record['cold_latency_ms']} ms")
    print(f"warm latency: {benchmark_record['warm_latency_ms']} ms")
    print(f"JSON válido: {benchmark_record['json_valid']}")
    print(f"Pydantic válido: {benchmark_record['pydantic_valid']}")
    print(f"benchmark JSON: {log_file}")
    print("==================================================")
    
    if "FAIL" in benchmark_record["status"]:
        pytest.fail(f"Modelo falló el benchmark: {benchmark_record['status']}")

if __name__ == "__main__":
    test_12d_model_benchmark()
