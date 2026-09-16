import os
import json
import time
from datetime import datetime
import pytest

from botsac.models.analysis_schema import DocumentMicroAnalysis
from botsac.analysis.llm.ollama import OllamaClient

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"
DOC_HASH = "8beb968af3f522584b54e4566f5ae34ae0a7ff7a6f8610ba1a9783522f1a5164"
MODEL = "qwen2.5:3b"

def test_23_document2_micro_analysis():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 23: MICROANÁLISIS DEL SEGUNDO DOCUMENTO...")
    
    dir_analysis = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    json_path = os.path.join(dir_analysis, "documents", f"{DOC_HASH}.json")
    
    # 1. JSON Nativo existe
    assert os.path.exists(json_path), "Falta el JSON de extracción nativa del documento"
    with open(json_path, "r", encoding="utf-8") as f:
        doc_data = json.load(f)
        
    doc_text = json.dumps(doc_data, indent=2, ensure_ascii=False)
    
    # 2. Qwen responde
    client = OllamaClient()
    health = client.health()
    assert health.get("status") == "ok", "LLM Gateway no responde"
    
    # 3. Preparar Prompt (idéntico a test 22)
    prompt = f"""Analiza exclusivamente el documento proporcionado.
Devuelve solamente un objeto JSON.
No inventes información.
Si no puedes identificar algo, usa 'No identificado'.
key_facts debe contener únicamente hechos explícitos del documento.
dates debe contener únicamente fechas explícitas.
pages_referenced debe contener únicamente números de página donde encontraste información relevante.

La estructura exacta del JSON a devolver debe ser:
{{
  "document_type": "str",
  "summary": "str",
  "key_facts": ["str"],
  "dates": ["str"],
  "pages_referenced": [1]
}}

DOCUMENTO:
{doc_text}
"""
    
    print(f"[LLM] Solicitando microanálisis a {MODEL}...")
    result = client.generate_structured(MODEL, prompt)
    
    assert result.get("status") == "success", f"Fallo LLM: {result.get('error')}"
    
    # 3. JSON Válido
    response_json = result.get("response", {})
    assert isinstance(response_json, dict), "La respuesta no es un diccionario JSON"
    
    # 4. Pydantic Válido
    try:
        analysis = DocumentMicroAnalysis(**response_json)
    except Exception as e:
        pytest.fail(f"El JSON devuelto no cumple el contrato Pydantic: {e}\nJSON: {response_json}")
        
    # 5. Validación básica
    for page in analysis.pages_referenced:
        assert 1 <= page <= 1, f"Página referenciada inválida (sólo hay 1 pág): {page}"
        
    assert len(analysis.key_facts) > 0, "No se extrajeron key_facts"
    assert analysis.summary.strip(), "Resumen vacío"
    
    for d in analysis.dates:
        if d.lower() != "no identificado":
            print(f"[VERIFY] Date found: {d}")
            
    # 6. Persistencia
    out_path = os.path.join(dir_analysis, "documents", f"document_micro_analysis_{DOC_HASH}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis.model_dump(), f, indent=2, ensure_ascii=False)
        
    assert os.path.exists(out_path)
    
    # PDF original intacto
    orig_filename = doc_data.get("document", {}).get("filename", "")
    pdf_path = os.path.join("data", "documents", ACQUISITION_ID, RADICADO, orig_filename)
    assert os.path.exists(pdf_path), f"El PDF RAW no existe: {pdf_path}"
    
    # Reporte
    latency = result.get("latency_ms", 0) / 1000.0
    print("\n==================================================")
    print("REPORT: TEST 23: EVALUACIÓN MANUAL")
    print(f"Tiempo de inferencia: {latency:.2f} segundos")
    print(f"Tipo de Documento: {analysis.document_type}")
    print(f"Resumen: {analysis.summary}")
    print(f"Hechos principales: {analysis.key_facts}")
    print(f"Fechas: {analysis.dates}")
    print(f"Páginas referenciadas: {analysis.pages_referenced}")
    print("==================================================")

if __name__ == "__main__":
    test_23_document2_micro_analysis()
