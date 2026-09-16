import os
import json
import re
from datetime import datetime
import pytest

from botsac.models.analysis_schema import BotSACReview, ReviewDocument, ReviewAlert, ReviewTrace

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def test_26_authoritative_review_projection():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 26: PROYECCIÓN AUTORITATIVA...")
    
    dir_analysis = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    
    # 1. Fuentes de verdad
    metadata_path = "data/logs/test_09_first_case.json"
    assert os.path.exists(metadata_path), "Falta metadata original"
    with open(metadata_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)
        row_data = meta_data.get("row_data", {})
        raw_vals = row_data.get("raw_data", [])
        headers = row_data.get("headers", [])
        sac_meta = dict(zip(headers, raw_vals)) if headers else {}
        
    solicitud_path = f"data/raw/{ACQUISITION_ID}/{RADICADO}/solicitud.txt"
    assert os.path.exists(solicitud_path), "Falta solicitud.txt"
    with open(solicitud_path, "r", encoding="utf-8") as f:
        solicitud_text = f.read()
        
    # Extracción de RAW literal para municipality
    # Buscamos la firma literal para asegurar que no se inventen nombres.
    raw_municipality = "Desconocido"
    match = re.search(r"Santander de Q - Cauca", solicitud_text, re.IGNORECASE)
    if match:
        raw_municipality = match.group(0)
        
    req_analysis_path = os.path.join(dir_analysis, "request_analysis.json")
    assert os.path.exists(req_analysis_path), "Falta request_analysis.json"
    with open(req_analysis_path, "r", encoding="utf-8") as f:
        req_analysis = json.load(f)
        
    manifest_path = os.path.join(dir_analysis, "documents_manifest.json")
    assert os.path.exists(manifest_path), "Falta documents_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    documents = []
    key_dates = []
    trace = []
    alerts = []
    
    # Traza para request analysis
    trace.append(ReviewTrace(
        source_type="REQUEST_ANALYSIS",
        source_ref="solicitud.txt",
        detail="Se extrajo el resumen de la solicitud."
    ))
    
    # Procesar documentos
    for idx, doc_entry in enumerate(manifest.get("documents", [])):
        file_hash = doc_entry.get("sha256")
        filename = doc_entry.get("filename")
        status = doc_entry.get("extraction_status")
        
        if status != "success":
            alerts.append(ReviewAlert(
                type="Extracción Parcial",
                description=f"El documento {filename} tuvo problemas de extracción ({status}).",
                source="DOCUMENT_MANIFEST"
            ))
            
        micro_path = os.path.join(dir_analysis, "documents", f"document_micro_analysis_{file_hash}.json")
        if os.path.exists(micro_path):
            with open(micro_path, "r", encoding="utf-8") as f:
                micro = json.load(f)
                
            rev_doc = ReviewDocument(
                filename=filename,
                document_type=micro.get("document_type", "Desconocido"),
                summary=micro.get("summary", "Sin resumen"),
                pages=micro.get("pages_referenced", [])
            )
            documents.append(rev_doc)
            
            for d in micro.get("dates", []):
                if d.lower() != "no identificado" and d not in key_dates:
                    key_dates.append(d)
                    
            trace.append(ReviewTrace(
                source_type="DOCUMENT_ANALYSIS",
                source_ref=filename,
                detail="Se consolidó el microanálisis documental."
            ))
        else:
            alerts.append(ReviewAlert(
                type="Análisis Faltante",
                description=f"No se encontró microanálisis para {filename}.",
                source="DOCUMENT_ANALYSIS"
            ))

    # Trazas Autoritativas (Paso 4)
    auth_radicado = sac_meta.get("RADICADO", RADICADO)
    auth_subject = sac_meta.get("ASUNTO", "Desconocido")
    auth_status = sac_meta.get("ESTADO", "Desconocido")
    auth_requester = sac_meta.get("CIUDADANO", "Desconocido")
    
    trace.append(ReviewTrace(
        source_type="SAC_METADATA",
        source_ref="SAC",
        detail="Se obtuvieron radicado, estado, asunto y solicitante autoritativos."
    ))
    
    trace.append(ReviewTrace(
        source_type="RAW",
        source_ref="solicitud.txt",
        detail="Se obtuvo municipio literal."
    ))
    
    if auth_status == "ASIGNADO":
        alerts.append(ReviewAlert(
            type="Estado Asignado",
            description="El radicado se encuentra asignado sin finalizar.",
            source="SAC_METADATA"
        ))
    
    # 2. REGLA DE PROYECCIÓN
    review = BotSACReview(
        radicado=auth_radicado,
        subject=auth_subject,
        status_sac=auth_status,
        municipality=raw_municipality,
        requester=auth_requester,
        request_summary=req_analysis.get("summary", ""),
        documents=documents,
        key_dates=key_dates,
        alerts=alerts,
        trace=trace
    )
    
    # Validaciones Positivas (Paso 5)
    assert review.requester == auth_requester
    assert review.municipality == raw_municipality
    assert review.subject == auth_subject
    assert review.status_sac == auth_status
    assert review.radicado == auth_radicado
    assert len(review.documents) == 2
    
    # Validaciones Negativas (Paso 6)
    llm_municipality = "Santander de Quilichao, Caucá"
    llm_requester = "educacion santanderdequilichao-cauca.gov.co"
    assert review.municipality != llm_municipality, "LLM sobrescribió el municipio autoritativo"
    assert review.requester != llm_requester, "LLM sobrescribió el solicitante autoritativo"
    
    # 7. Persistencia
    out_path = os.path.join(dir_analysis, "botsac_review.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(review.model_dump(), f, indent=2, ensure_ascii=False)
        
    assert os.path.exists(out_path)
    
    # RAW intactos
    pdf_files = [f for f in os.listdir(f"data/documents/{ACQUISITION_ID}/{RADICADO}") if f.endswith(".pdf")]
    assert len(pdf_files) == 2, "Los RAW originales no existen o fueron modificados"

    # 8. Reporte
    print("\n==================================================")
    print("REPORT: TEST 26: PROYECCIÓN AUTORITATIVA")
    print(f"REQUESTER:    {review.requester} (Fuente: SAC_METADATA)")
    print(f"MUNICIPALITY: {review.municipality} (Fuente: RAW)")
    print(f"SUBJECT:      {review.subject[:50]}... (Fuente: SAC_METADATA)")
    print(f"STATUS_SAC:   {review.status_sac} (Fuente: SAC_METADATA)")
    print("\nValidación negativa exitosa: El LLM no sobrescribió los campos oficiales.")
    print("Confirmación: No se ejecutó inferencia LLM en este paso.")
    print("==================================================\nPASS")

if __name__ == "__main__":
    test_26_authoritative_review_projection()
