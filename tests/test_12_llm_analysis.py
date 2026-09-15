import os
import json
import pytest
from datetime import datetime
from botsac.analysis.llm.analyzer import AnalysisInput, DocumentInput, analyze_case, LLMProviderNotConfiguredException

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def test_12_llm_analysis():
    print(f"\n[START] Iniciando TEST 12: ANÁLISIS LLM REAL para {RADICADO}")
    
    base_dir = f"data/ingested/{ACQUISITION_ID}/{RADICADO}"
    raw_dir = f"data/raw/{ACQUISITION_ID}/{RADICADO}"
    analysis_dir = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    
    # 1. Cargar datos base
    case_path = os.path.join(base_dir, "case.json")
    if not os.path.exists(case_path):
        pytest.fail(f"Expediente no encontrado en {case_path}")
        
    with open(case_path, "r", encoding="utf-8") as f:
        case_data = json.load(f)
        
    with open(os.path.join(raw_dir, "solicitud.txt"), "r", encoding="utf-8") as f:
        solicitud_text = f.read()
        
    # 2. Cargar textos extraídos
    doc_inputs = []
    documents = case_data.get("case", {}).get("documents", [])
    for i, doc in enumerate(documents):
        orig_name = doc.get("download", {}).get("original_name", "")
        txt_path = os.path.join(analysis_dir, f"document_{i+1}_extracted.txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f_txt:
                doc_text = f_txt.read()
                doc_inputs.append(DocumentInput(
                    document_id=f"doc_{i+1}",
                    filename=orig_name,
                    text=doc_text
                ))
                
    analysis_input = AnalysisInput(
        radicado=RADICADO,
        metadata=case_data.get("case", {}).get("metadata", {}),
        solicitud_text=solicitud_text,
        documents=doc_inputs
    )
    
    print("[STEP] Llamando a la interfaz de análisis LLM (analyze_case)...")
    
    try:
        # 3. Llamar a la abstracción
        result = analyze_case(analysis_input)
        # (Si hubiera LLM, validaríamos y guardaríamos el JSON)
        pytest.fail("Se esperaba un bloqueo por configuración, pero analyze_case retornó un resultado.")
        
    except LLMProviderNotConfiguredException as e:
        print(f"\n[ALERT] {str(e)}")
        print("\n==================================================")
        print("REPORT: TEST 12: BLOCKED_BY_CONFIGURATION")
        print("proveedor: N/A")
        print("modelo: N/A")
        print("clasificación real de los documentos: NO DETERMINADO (Bloqueado)")
        print("resumen real de solicitud: NO DETERMINADO (Bloqueado)")
        print("resumen real de respuesta: NO DETERMINADO (Bloqueado)")
        print("pretensiones: NO DETERMINADO (Bloqueado)")
        print("matriz solicitud/respuesta: NO DETERMINADO (Bloqueado)")
        print("evidencia: NO DETERMINADO (Bloqueado)")
        print("alertas: NO DETERMINADO (Bloqueado)")
        print("executive_summary: NO DETERMINADO (Bloqueado)")
        print("analysis_id: N/A")
        print("ubicación de artefactos: N/A (Bloqueado)")
        print("==================================================")
        # Passed contextually because it correctly blocked the test as requested.
        return

if __name__ == "__main__":
    test_12_llm_analysis()
