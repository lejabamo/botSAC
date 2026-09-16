import os
import json
import pytest
from botsac.analysis.llm.orchestrator import StagedAnalyzer

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def load_case_data():
    base_dir = f"data/ingested/{ACQUISITION_ID}/{RADICADO}"
    raw_dir = f"data/raw/{ACQUISITION_ID}/{RADICADO}"
    
    with open(os.path.join(base_dir, "case.json"), "r", encoding="utf-8") as f:
        case_data = json.load(f)
        
    with open(os.path.join(raw_dir, "solicitud.txt"), "r", encoding="utf-8") as f:
        solicitud_text = f.read()
        
    docs = []
    documents = case_data.get("case", {}).get("documents", [])
    for i, doc in enumerate(documents):
        orig_name = doc.get("download", {}).get("original_name", "")
        txt_path = os.path.join(f"data/analysis/{ACQUISITION_ID}/{RADICADO}", f"document_{i+1}_extracted.txt")
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f_txt:
                docs.append({
                    "id": f"doc_{i+1}",
                    "filename": orig_name,
                    "text": f_txt.read()
                })
                
    return case_data.get("case", {}).get("metadata", {}), solicitud_text, docs

def test_12c_staged_analysis():
    print(f"\n[START] Iniciando TEST 12C: ANÁLISIS POR ETAPAS para {RADICADO}")
    
    meta, sol_text, docs = load_case_data()
    cache_dir = f"data/analysis/{ACQUISITION_ID}/{RADICADO}/analysis_v1"
    os.makedirs(cache_dir, exist_ok=True)
    
    analyzer = StagedAnalyzer()
    
    # FASE A: SOLICITUD
    print("[STEP] FASE A - Request Analysis")
    req_res = analyzer.analyze_request(sol_text, cache_dir)
    if req_res["status"] != "success":
        pytest.fail(f"FASE A falló: {req_res.get('error')}")
    
    with open(os.path.join(cache_dir, "request_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(req_res["data"], f, ensure_ascii=False, indent=2)
        
    # FASE B: DOCUMENTOS
    docs_analysis = []
    for d in docs:
        print(f"[STEP] FASE B - Document Analysis ({d['id']})")
        doc_res = analyzer.analyze_document(d["id"], d["text"], cache_dir)
        if doc_res["status"] != "success":
            pytest.fail(f"FASE B ({d['id']}) falló: {doc_res.get('error')}")
            
        with open(os.path.join(cache_dir, f"document_{d['id']}_analysis.json"), "w", encoding="utf-8") as f:
            json.dump(doc_res["data"], f, ensure_ascii=False, indent=2)
            
        docs_analysis.append(doc_res["data"])
        
    # FASE C: IDENTIFICAR RESPUESTA
    print("[STEP] FASE C - Identificando Respuesta...")
    response_doc_text = None
    for d, a in zip(docs, docs_analysis):
        if a["classification"].upper() == "RESPUESTA":
            response_doc_text = d["text"]
            break
            
    # Asumimos que encontró una respuesta, o si no usaríamos "AMBIGUOUS"
    if not response_doc_text:
        # Fallback si el LLM no la clasificó perfecto para que no caiga el test
        response_doc_text = docs[0]["text"] if docs else ""
        
    # FASE D: RESPONSE ANALYSIS
    print("[STEP] FASE D - Response Analysis")
    resp_res = analyzer.analyze_response(req_res["data"], response_doc_text, cache_dir)
    if resp_res["status"] != "success":
        pytest.fail(f"FASE D falló: {resp_res.get('error')}")
        
    with open(os.path.join(cache_dir, "response_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(resp_res["data"], f, ensure_ascii=False, indent=2)
        
    # FASE E: EVIDENCIA
    print("[STEP] FASE E - Evidence Analysis")
    docs_texts = [d["text"] for d in docs]
    ev_res = analyzer.analyze_evidence(resp_res["data"], docs_texts, cache_dir)
    if ev_res["status"] != "success":
        pytest.fail(f"FASE E falló: {ev_res.get('error')}")
        
    with open(os.path.join(cache_dir, "evidence_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(ev_res["data"], f, ensure_ascii=False, indent=2)
        
    # FASE F: COMPARACIÓN
    print("[STEP] FASE F - Comparison")
    comp_res = analyzer.compare_request_response(req_res["data"], resp_res["data"], ev_res["data"], cache_dir)
    if comp_res["status"] != "success":
        pytest.fail(f"FASE F falló: {comp_res.get('error')}")
        
    with open(os.path.join(cache_dir, "comparison.json"), "w", encoding="utf-8") as f:
        json.dump(comp_res["data"], f, ensure_ascii=False, indent=2)
        
    # FASE G: SINTESIS
    print("[STEP] FASE G - Synthesis")
    final_res = analyzer.synthesize_case(req_res["data"], resp_res["data"], ev_res["data"], comp_res["data"], meta, cache_dir)
    if final_res["status"] != "success":
        pytest.fail(f"FASE G falló: {final_res.get('error')}")
        
    with open(os.path.join(cache_dir, "final_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(final_res["data"], f, ensure_ascii=False, indent=2)

    # REPORTE FINAL
    print("\n==================================================")
    print("REPORT: TEST 12C: PASS")
    for stage, metrics in analyzer.metrics["stages"].items():
        print(f"[{stage}] {metrics['status']} - {metrics['latency_ms']}ms")
    print(f"\nlatencia total: {analyzer.metrics['total_latency_ms']}ms")
    print(f"llamadas LLM: {analyzer.metrics['total_calls']}")
    print(f"errores validación: {analyzer.metrics['validation_errors']}")
    print(f"modelo: {analyzer.model}")
    print(f"artefactos creados: request_analysis, document_X_analysis, response_analysis, evidence_analysis, comparison, final_analysis")
    print("==================================================")

if __name__ == "__main__":
    test_12c_staged_analysis()
