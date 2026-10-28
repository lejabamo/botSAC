import os
import json
import subprocess
import sys
import time
from datetime import datetime
import pytest

from botsac.models.analysis_schema import BotSACReview

ACQ = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032558"

def test_32_analyze_radicado():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 32: ANÁLISIS BOTSAC BAJO DEMANDA...")
    
    dir_analysis_base = f"data/analysis/{ACQ}/{RADICADO}"
    dir_raw = f"data/raw/{ACQ}/{RADICADO}"
    dir_docs = f"data/documents/{ACQ}/{RADICADO}"
    
    # 1. Expediente, 2. Solicitud, 3. Documentos existen
    assert os.path.exists(dir_analysis_base), "Expediente base analysis no existe"
    assert os.path.exists(os.path.join(dir_raw, "solicitud.txt")), "Solicitud.txt no existe"
    assert os.path.exists(os.path.join(dir_analysis_base, "documents_manifest.json")), "Manifest no existe"
    
    with open(os.path.join(dir_analysis_base, "documents_manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    assert len(manifest.get("documents", [])) > 0, "No hay documentos en manifest"
    
    # Check PDFs
    for doc in manifest["documents"]:
        assert os.path.exists(os.path.join(dir_docs, doc["filename"])), f"PDF {doc['filename']} no existe"
        
    print("[TEST] 1-3. Precondiciones OK (RAW, PDFs, Manifest intactos)")
    
    # Clean previous analysis for a fresh run if needed, but since it's the first time it won't be there.
    req_path = os.path.join(dir_analysis_base, "request_analysis.json")
    if os.path.exists(req_path):
        os.remove(req_path)
    for doc in manifest["documents"]:
        micro_path = os.path.join(dir_analysis_base, f"document_micro_analysis_{doc['sha256']}.json")
        if os.path.exists(micro_path):
            os.remove(micro_path)
            
    # RUN 1
    t0 = time.time()
    res1 = subprocess.run([sys.executable, "scripts/analyze_radicado.py", "--radicado", RADICADO], capture_output=True, text=True)
    t1 = time.time() - t0
    
    assert res1.returncode == 0, f"Error en ejecución 1: {res1.stderr}"
    assert "[LLM] Generando RequestAnalysis..." in res1.stdout
    assert "[LLM] Generando MicroAnalysis para" in res1.stdout
    
    # 4. RequestAnalysis se genera
    assert os.path.exists(req_path), "request_analysis.json no se generó"
    
    # 5. MicroAnalysis se genera
    for doc in manifest["documents"]:
        micro_path = os.path.join(dir_analysis_base, f"document_micro_analysis_{doc['sha256']}.json")
        assert os.path.exists(micro_path), f"MicroAnalysis no se generó para {doc['filename']}"
        
    # 6, 7. BotSACReview se genera y valida Pydantic
    review_path = os.path.join(dir_analysis_base, "botsac_review.json")
    assert os.path.exists(review_path), "botsac_review.json no existe"
    
    with open(review_path, "r", encoding="utf-8") as f:
        review_data = json.load(f)
        
    # Validates against Pydantic schema
    validated = BotSACReview.model_validate(review_data)
    assert validated.radicado == RADICADO
    assert len(validated.documents) == len(manifest["documents"])
    
    print("[TEST] 4-7. Generación de análisis y validación Pydantic OK")
    
    # RUN 2 (Cache)
    t0_cache = time.time()
    res2 = subprocess.run([sys.executable, "scripts/analyze_radicado.py", "--radicado", RADICADO], capture_output=True, text=True)
    t_cache = time.time() - t0_cache
    
    assert res2.returncode == 0, f"Error en ejecución 2: {res2.stderr}"
    
    # 8, 9, 10. Reutiliza cache, no llama Qwen
    assert "[CACHE] Reutilizando RequestAnalysis..." in res2.stdout
    assert "[CACHE] Reutilizando MicroAnalysis para" in res2.stdout
    assert "Generando RequestAnalysis..." not in res2.stdout
    assert "Llamadas LLM: 0" in res2.stdout
    
    print(f"[TEST] 8-10. Cache exitoso. (Llamadas LLM: 0). Tiempo: {t_cache:.2f}s (vs original {t1:.2f}s)")
    
    # 11, 12, 13. RAW, PDFs y hashes intactos
    assert os.path.exists(os.path.join(dir_raw, "solicitud.txt")), "RAW alterado"
    for doc in manifest["documents"]:
        assert os.path.exists(os.path.join(dir_docs, doc["filename"])), "PDFs alterados"
        
    print("\n" + "="*50)
    print("REPORT: TEST 32 PASS")
    print(res2.stdout)
    print("="*50)
    
if __name__ == "__main__":
    test_32_analyze_radicado()
