import os
import json
import pytest
from datetime import datetime
from botsac.analysis.llm.analyzer import AnalysisInput, DocumentInput, analyze_case

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def test_12b_first_llm_analysis():
    print(f"\n[START] Iniciando TEST 12B: ANÁLISIS REAL CON OLLAMA para {RADICADO}")
    
    base_dir = f"data/ingested/{ACQUISITION_ID}/{RADICADO}"
    raw_dir = f"data/raw/{ACQUISITION_ID}/{RADICADO}"
    analysis_dir = f"data/analysis/{ACQUISITION_ID}/{RADICADO}/analysis_v1"
    
    os.makedirs(analysis_dir, exist_ok=True)
    
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
        # Extraídos en test 11 (estaban en data/analysis/ACQ.../document_1_extracted.txt)
        txt_path = os.path.join(f"data/analysis/{ACQUISITION_ID}/{RADICADO}", f"document_{i+1}_extracted.txt")
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
    
    print(f"[STEP] Llamando al LLM Local (Ollama)...")
    
    result = analyze_case(analysis_input)
    
    if result.get("status") != "success":
        print(f"\n[FAIL] {result.get('error')}")
        pytest.fail("Fallo en inferencia o validación")
        
    analysis_data = result.get("analysis")
    
    print("\n[OK] Inferencia completada y validada por Pydantic.")
    print(f"Latencia Preparación: {result.get('latency_prep_ms')} ms")
    print(f"Latencia Inferencia: {result.get('latency_inf_ms')} ms")
    print(f"Latencia Total: {result.get('latency_total_ms')} ms")
    
    # Escribir Artefactos
    analysis_meta = {
        "analysis_id": f"ANALYSIS-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "provider": result.get("provider"),
        "model": result.get("model"),
        "timestamp": datetime.now().isoformat(),
        "prompt_version": "analysis_v1",
        "latency_ms": result.get("latency_total_ms"),
        "validation_status": "success"
    }
    
    with open(os.path.join(analysis_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(analysis_meta, f, indent=2, ensure_ascii=False)
        
    with open(os.path.join(analysis_dir, "document_classification.json"), "w", encoding="utf-8") as f:
        json.dump(analysis_data.get("document_classification"), f, indent=2, ensure_ascii=False)
        
    with open(os.path.join(analysis_dir, "comparison.json"), "w", encoding="utf-8") as f:
        json.dump(analysis_data.get("matriz_comparativa"), f, indent=2, ensure_ascii=False)
        
    with open(os.path.join(analysis_dir, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(analysis_data.get("timeline"), f, indent=2, ensure_ascii=False)
        
    # Summary Markdown
    es = analysis_data.get("executive_summary")
    summary_md = f"""# Resumen Ejecutivo - {es.get('radicado')}

**MUNICIPIO**: {es.get('municipio')}
**INSTITUCIÓN**: {es.get('institucion')}

## SOLICITUD
{es.get('solicitud')}

## RESPUESTA
{es.get('respuesta')}

## SOPORTES
{es.get('soportes')}

## VACÍOS
{es.get('vacios')}

## ALERTAS
{es.get('alertas')}
"""
    with open(os.path.join(analysis_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_md)
        
    print("\n==================================================")
    print("REPORT: TEST 12B: PASS")
    print(f"modelo utilizado: {result.get('model')}")
    print(f"tiempo prep: {result.get('latency_prep_ms')} ms")
    print(f"tiempo inferencia: {result.get('latency_inf_ms')} ms")
    print(f"clasificación: {len(analysis_data.get('document_classification'))} documentos")
    print(f"pretensiones: {len(analysis_data.get('pretensiones'))}")
    print(f"analysis_id: {analysis_meta.get('analysis_id')}")
    print(f"ubicación de resultados: {analysis_dir}/")
    print("==================================================")
    
if __name__ == "__main__":
    test_12b_first_llm_analysis()
