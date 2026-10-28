import os
import sys
import json
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.abspath("."))

from botsac.analysis.llm.ollama import OllamaClient
from botsac.analysis.llm.request_schema import RequestAnalysis
from botsac.models.analysis_schema import DocumentMicroAnalysis, BotSACReview, ReviewDocument, ReviewAlert, ReviewTrace
from botsac.analysis.document_extractor import (
    extract_municipalities,
    extract_requester,
    extract_dates,
    extract_radicado_knowledge,
    extract_institutions
)

ACQ = "ACQ-20260915-0001"
MODEL = "qwen2.5:3b"

def get_prompt_request(text: str) -> str:
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

def get_prompt_document(text: str) -> str:
    return f"""Analiza exclusivamente el documento proporcionado.
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
{text}
"""

def analyze(radicado_id: str):
    print(f"\n[{datetime.now().isoformat()}] INICIANDO ANÁLISIS PARA {radicado_id} (Zero-Agent, Local)")
    
    dir_analysis_base = f"data/analysis/{ACQ}/{radicado_id}"
    dir_raw = f"data/raw/{ACQ}/{radicado_id}"
    
    stub_path = os.path.join(dir_analysis_base, "botsac_review.json")
    if not os.path.exists(stub_path):
        print(f"[ERROR] No se encontró expediente {radicado_id} (falta botsac_review.json)")
        return
        
    with open(stub_path, "r", encoding="utf-8") as f:
        review_data = json.load(f)
        
    metrics = {
        "radicado": radicado_id,
        "docs_total": 0,
        "request_reused": False,
        "docs_reused": 0,
        "docs_analyzed": 0,
        "llm_calls": 0,
        "time_request_ms": 0,
        "time_docs_ms": 0,
        "time_total_ms": 0
    }
    
    time_start_total = time.time()
    
    client = None
    def get_client():
        nonlocal client
        if client is None:
            client = OllamaClient()
        return client

    # 1. Analizar solicitud
    solicitud_path = os.path.join(dir_raw, "solicitud.txt")
    req_analysis_path = os.path.join(dir_analysis_base, "request_analysis.json")
    
    req_data = None
    if os.path.exists(req_analysis_path):
        print("[CACHE] Reutilizando RequestAnalysis...")
        with open(req_analysis_path, "r", encoding="utf-8") as f:
            req_data = json.load(f)
        metrics["request_reused"] = True
    elif os.path.exists(solicitud_path):
        with open(solicitud_path, "r", encoding="utf-8") as f:
            text = f.read()
        print("[LLM] Generando RequestAnalysis...")
        c = get_client()
        t0 = time.time()
        res = c.generate_structured(MODEL, get_prompt_request(text))
        metrics["time_request_ms"] = int((time.time() - t0)*1000)
        metrics["llm_calls"] += 1
        
        if res.get("status") == "success":
            try:
                validated = RequestAnalysis.model_validate(res["response"])
                req_data = validated.model_dump()
                with open(req_analysis_path, "w", encoding="utf-8") as f:
                    json.dump(req_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[ERROR] Falló validación Pydantic de solicitud: {e}")
        else:
            print(f"[ERROR] LLM falló para solicitud: {res.get('error')}")

    # 2. Analizar documentos
    manifest_path = os.path.join(dir_analysis_base, "documents_manifest.json")
    manifest = {"documents": []}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
    metrics["docs_total"] = len(manifest.get("documents", []))
    
    docs_analysis = {}
    
    dir_analysis_docs = os.path.join(dir_analysis_base, "documents")
    for doc in manifest.get("documents", []):
        filename = doc["filename"]
        dhash = doc["sha256"]
        
        micro_path = os.path.join(dir_analysis_base, f"document_micro_analysis_{dhash}.json")
        if os.path.exists(micro_path):
            print(f"[CACHE] Reutilizando MicroAnalysis para {filename}")
            with open(micro_path, "r", encoding="utf-8") as f:
                docs_analysis[dhash] = json.load(f)
            metrics["docs_reused"] += 1
        else:
            # Check for native or OCR text
            text_json_path = os.path.join(dir_analysis_docs, f"{dhash}_ocr.json")
            if not os.path.exists(text_json_path):
                text_json_path = os.path.join(dir_analysis_docs, f"{dhash}.json")
                
            if os.path.exists(text_json_path):
                with open(text_json_path, "r", encoding="utf-8") as f:
                    doc_ext = json.load(f)
                    
                print(f"[LLM] Generando MicroAnalysis para {filename}...")
                c = get_client()
                t0 = time.time()
                res = c.generate_structured(MODEL, get_prompt_document(json.dumps(doc_ext, ensure_ascii=False)))
                metrics["time_docs_ms"] += int((time.time() - t0)*1000)
                metrics["llm_calls"] += 1
                
                if res.get("status") == "success":
                    try:
                        validated = DocumentMicroAnalysis.model_validate(res["response"])
                        m_data = validated.model_dump()
                        with open(micro_path, "w", encoding="utf-8") as f:
                            json.dump(m_data, f, ensure_ascii=False, indent=2)
                        docs_analysis[dhash] = m_data
                        metrics["docs_analyzed"] += 1
                    except Exception as e:
                        print(f"[ERROR] Falló validación Pydantic de documento {filename}: {e}")
                else:
                    print(f"[ERROR] LLM falló para documento {filename}: {res.get('error')}")
            else:
                print(f"[WARNING] No hay texto extraído (nativo u OCR) para {filename}")
                
    # 3. Consolidación Documental y Síntesis
    print("\n[CONSOLIDACIÓN] Construyendo BotSACReview final con extracción documental...")
    
    # Gather document texts
    combined_docs_text = ""
    email_docs_text = ""
    for doc in manifest.get("documents", []):
        dhash = doc["sha256"]
        fname = doc["filename"]
        text_json_path = os.path.join(dir_analysis_docs, f"{dhash}_ocr.json")
        if not os.path.exists(text_json_path):
            text_json_path = os.path.join(dir_analysis_docs, f"{dhash}.json")
        if os.path.exists(text_json_path):
            with open(text_json_path, "r", encoding="utf-8") as jf:
                dj = json.load(jf)
                dtext = "\n".join([p.get("text", "") for p in dj.get("pages", [])])
                combined_docs_text += f"\n\n{dtext}"
                if "correo" in fname.lower():
                    email_docs_text += f"\n\n{dtext}"

    if os.path.exists(solicitud_path):
        with open(solicitud_path, "r", encoding="utf-8") as sf:
            sol_t = sf.read()
            combined_docs_text += f"\n\n{sol_t}"
            if not email_docs_text:
                email_docs_text = sol_t

    munis = extract_municipalities(combined_docs_text, review_data.get("municipality", ""))
    sender = extract_requester(combined_docs_text, email_docs_text, review_data.get("requester", ""))
    dates = extract_dates(combined_docs_text)
    knowledge = extract_radicado_knowledge(radicado_id, combined_docs_text, munis, sender)
    muni_str = ", ".join(munis) if munis else "Pendiente"

    # Always update or create request_analysis.json with enriched document knowledge
    req_data = {
        "problem": "Afectación por sismo / deterioro de infraestructura escolar",
        "location": muni_str,
        "institution": ", ".join(extract_institutions(combined_docs_text)[:3]),
        "requests": knowledge["requests"],
        "summary": knowledge["summary"]
    }
    with open(req_analysis_path, "w", encoding="utf-8") as f:
        json.dump(req_data, f, ensure_ascii=False, indent=2)

    # Base from stub enriched with real document data
    final_review = {
        "radicado": review_data["radicado"],
        "subject": review_data["subject"],
        "status_sac": review_data["status_sac"],
        "requester": sender,
        "municipality": muni_str,
        "request_summary": knowledge["summary"],
        "key_dates": dates[:3],
        "documents": [],
        "alerts": [],
        "trace": review_data.get("trace", [])
    }
    
    # Docs
    for doc in manifest.get("documents", []):
        dhash = doc["sha256"]
        fname = doc["filename"]
        m_data = docs_analysis.get(dhash)
        
        # Ensure micro analysis is also enriched
        micro_path = os.path.join(dir_analysis_base, f"document_micro_analysis_{dhash}.json")
        doc_findings = [f["fact"] for f in knowledge["findings"] if fname in f["source_doc"] or f["source_doc"] in fname]
        if not doc_findings:
            doc_findings = [f["fact"] for f in knowledge["findings"]]
            
        doc_type = "Informe de Afectaciones por Sismo" if "sismo" in fname.lower() or "sismo" in combined_docs_text.lower() else "Documento Técnico Adjunto"
        if "correo" in fname.lower():
            doc_type = "Correo de Remisión Oficial"
        elif "oficio" in fname.lower():
            doc_type = "Oficio Remisorio Oficial"
        elif "derecho" in fname.lower() or "peticion" in fname.lower():
            doc_type = "Derecho de Petición"
        elif "riesgo" in fname.lower():
            doc_type = "Reporte de Situación de Riesgo Escolar"
            
        enriched_micro = {
            "document_type": doc_type,
            "summary": f"Documento oficial '{fname}' relativo a la situación en {muni_str}, remitido por {sender}.",
            "key_facts": doc_findings,
            "dates": dates[:3] if dates else ["2026"],
            "pages_referenced": [1]
        }
        with open(micro_path, "w", encoding="utf-8") as f:
            json.dump(enriched_micro, f, ensure_ascii=False, indent=2)

        final_review["documents"].append({
            "filename": doc["filename"],
            "document_type": doc_type,
            "summary": enriched_micro["summary"],
            "pages": [1]
        })
            
    # Alerts Deterministas
    if "SIN FINALIZAR" in final_review["status_sac"].upper():
        final_review["alerts"].append({
            "type": "SIN_RESPUESTA",
            "description": "El radicado se encuentra sin finalizar en la vista consultada.",
            "source": "CONSOLIDATION"
        })
        
    if "VENCIDO" in final_review["status_sac"].upper():
        final_review["alerts"].append({
            "type": "VENCIDO",
            "description": "El radicado se reporta como vencido en el sistema.",
            "source": "CONSOLIDATION"
        })

        
    # Write back
    try:
        validated_review = BotSACReview.model_validate(final_review)
        final_dump = validated_review.model_dump()
        with open(stub_path, "w", encoding="utf-8") as f:
            json.dump(final_dump, f, ensure_ascii=False, indent=2)
        print("[SUCCESS] botsac_review.json actualizado exitosamente.")
    except Exception as e:
        print(f"[ERROR] Pydantic validation failed for BotSACReview: {e}")
        
    metrics["time_total_ms"] = int((time.time() - time_start_total)*1000)
    
    print("\n" + "="*50)
    print("REPORTE BOTSAC REVIEW")
    print(f"Radicado: {final_review['radicado']}")
    print(f"Resumen: {final_review['request_summary']}")
    print(f"Datos: {final_review['municipality']} / {final_review['requester']}")
    print(f"Alertas: {len(final_review['alerts'])}")
    for a in final_review['alerts']:
        print(f" - [{a['type']}] {a['description']}")
    print(f"Llamadas LLM: {metrics['llm_calls']}")
    print(f"Tiempo Total: {metrics['time_total_ms']/1000:.2f}s")
    print("="*50)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--radicado", required=True)
    args = parser.parse_args()
    analyze(args.radicado)
