import os
import subprocess
import pytest
from botsac.analysis.llm.ollama import OllamaClient

def check_hardware():
    hardware_info = {"gpu": "NO DETECTADA", "vram": "NO DETERMINADO"}
    try:
        # Check NVIDIA GPU
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], 
                                capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            hardware_info["gpu"] = result.stdout.strip().replace('\n', ' | ')
    except FileNotFoundError:
        pass
    
    return hardware_info

def test_12a_ollama_local():
    print("\n[START] Iniciando TEST 12A: DESCUBRIR RUNTIME OLLAMA LOCAL")
    
    client = OllamaClient()
    
    print("[STEP] 1. Comprobando Endpoint y Versión...")
    health = client.health()
    if health.get("status") != "ok":
        print(f"\n[ALERT] Ollama no responde en {client.base_url}")
        print("==================================================")
        print("REPORT: TEST 12A: BLOCKED")
        print("Ollama version: N/A")
        print(f"endpoint: {client.base_url} (inactivo)")
        print("modelos disponibles: N/A")
        print("==================================================")
        pytest.fail("Ollama no responde")
        
    version = health.get("version")
    print(f"[OK] Ollama {version} detectado (Latencia: {health.get('latency_ms')}ms)")
    
    print("[STEP] 2. Consultando modelos locales...")
    models_data = client.list_models()
    
    if not models_data:
        print("\n[ALERT] NO_LOCAL_MODEL_AVAILABLE")
        print("==================================================")
        print("REPORT: TEST 12A: BLOCKED")
        print(f"Ollama version: {version}")
        print(f"endpoint: {client.base_url}")
        print("modelos disponibles: 0")
        print("==================================================")
        pytest.fail("No hay modelos locales disponibles")
        
    print(f"[OK] {len(models_data)} modelos encontrados:")
    model_list = []
    
    # Extract details
    for m in models_data:
        name = m.get("name")
        size_gb = round(m.get("size", 0) / (1024**3), 2)
        details = m.get("details", {})
        family = details.get("family", "")
        quant = details.get("parameter_size", "")
        
        info = f"- {name} ({size_gb}GB | {family} | {quant})"
        model_list.append(info)
        print(info)
        
    # Sort by size to pick the smallest
    sorted_models = sorted(models_data, key=lambda x: x.get("size", 0))
    smallest_model = sorted_models[0].get("name")
    size_smallest_gb = round(sorted_models[0].get("size", 0) / (1024**3), 2)
    
    print(f"\n[STEP] 3. Detectando Hardware...")
    hw = check_hardware()
    print(f"[HW] GPU: {hw['gpu']}")
    
    print(f"\n[STEP] 4. Prueba mínima de inferencia estructurada (Modelo: {smallest_model})...")
    prompt = "Responde únicamente con JSON:\n{\"status\":\"ok\"}"
    gen_result = client.generate_structured(smallest_model, prompt)
    
    if gen_result.get("status") == "success":
        response_json = gen_result.get("response")
        latency = gen_result.get("latency_ms")
        print(f"[OK] Inferencia completada en {latency}ms")
        print(f"[DATA] Respuesta validada: {response_json}")
        status_final = "PASS"
    else:
        print(f"[FAIL] Error en inferencia: {gen_result.get('error')}")
        status_final = "FAIL"
        
    print("\n==================================================")
    print(f"REPORT: TEST 12A: {status_final}")
    print(f"Ollama version: {version}")
    print(f"endpoint: {client.base_url}")
    print(f"modelos disponibles: {len(models_data)}")
    print(f"modelo probado: {smallest_model}")
    print(f"tamaño: {size_smallest_gb} GB")
    print(f"CPU/GPU detectada: {hw['gpu']}")
    if gen_result.get("status") == "success":
        print(f"latencia inferencia: {gen_result.get('latency_ms')} ms")
        print(f"resultado del JSON: {gen_result.get('response')}")
    print("archivos creados/modificados: botsac/analysis/llm/ollama.py, .env.example, tests/test_12a_ollama_local.py")
    print("==================================================")
    
    if status_final == "FAIL":
        pytest.fail("Falló la generación de prueba")

if __name__ == "__main__":
    test_12a_ollama_local()
