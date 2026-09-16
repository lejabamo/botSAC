import os
import json
from datetime import datetime
import pytest

from botsac.models.analysis_schema import BotSACReview, ReviewDocument, ReviewAlert, ReviewTrace

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def test_24_botsac_review():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 24: CONSOLIDACIÓN DETERMINISTA...")
    
    dir_analysis = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    
    # Entradas
    # 1. metadata
    metadata_path = "data/logs/test_09_first_case.json"
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)
            # test_09_first_case saved "row_data" and "details_data"
            details = log_data.get("details_data", {})
            metadata = {
                "radicado": RADICADO,
                "subject": details.get("ASUNTO", "No disponible"),
                "status_sac": details.get("ESTADO", "No disponible")
            }
    if not metadata:
        metadata = {"radicado": RADICADO, "subject": "Desconocido", "status_sac": "ASIGNADO"}
        
    # 2. request_analysis
    req_analysis_path = os.path.join(dir_analysis, "request_analysis.json")
    assert os.path.exists(req_analysis_path), "Falta request_analysis.json"
    with open(req_analysis_path, "r", encoding="utf-8") as f:
        req_analysis = json.load(f)
        
    # 5. documents_manifest
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
        detail="Se extrajo el resumen, municipio y solicitante."
    ))
    
    # Procesar documentos
    for idx, doc_entry in enumerate(manifest.get("documents", [])):
        file_hash = doc_entry.get("sha256")
        filename = doc_entry.get("filename")
        status = doc_entry.get("extraction_status")
        
        # Alertas documentales deterministas
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
            
            # Recolectar fechas
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

    # Novedades (ver si hay respuesta, estado ASIGNADO, etc)
    if metadata.get("status_sac") == "ASIGNADO":
        alerts.append(ReviewAlert(
            type="Estado Asignado",
            description="El radicado se encuentra asignado sin finalizar.",
            source="SAC_METADATA"
        ))
        
    trace.append(ReviewTrace(
        source_type="SAC_METADATA",
        source_ref="SAC",
        detail="Se obtuvo el estado y asunto general."
    ))
    
    # 6. Crear BotSACReview
    review = BotSACReview(
        radicado=RADICADO,
        subject=metadata.get("subject", ""),
        status_sac=metadata.get("status_sac", ""),
        municipality=req_analysis.get("location", ""),
        requester=req_analysis.get("institution", ""),
        request_summary=req_analysis.get("summary", ""),
        documents=documents,
        key_dates=key_dates,
        alerts=alerts,
        trace=trace
    )
    
    assert len(review.documents) == 2, "Se esperaban 2 documentos consolidados."
    assert review.radicado == RADICADO
    assert review.key_dates
    
    # 7. Persistencia
    out_path = os.path.join(dir_analysis, "botsac_review.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(review.model_dump(), f, indent=2, ensure_ascii=False)
        
    assert os.path.exists(out_path)
    
    # RAW intactos
    pdf_files = [f for f in os.listdir(f"data/documents/{ACQUISITION_ID}/{RADICADO}") if f.endswith(".pdf")]
    assert len(pdf_files) == 2, "Los RAW originales no existen o fueron modificados"

    # Inspección Humana
    print("\n==================================================")
    print("FICHA DE REVISIÓN - BotSAC V1")
    print("==================================================")
    print(f"RADICADO:    {review.radicado}")
    print(f"ESTADO:      {review.status_sac}")
    print(f"MUNICIPIO:   {review.municipality}")
    print(f"SOLICITANTE: {review.requester}")
    print(f"ASUNTO:      {review.subject}")
    print(f"RESUMEN:     {review.request_summary}")
    print("\n--- DOCUMENTOS ---")
    for doc in review.documents:
        print(f"DOC: {doc.filename}")
        print(f"   Tipo: {doc.document_type}")
        print(f"   Páginas: {doc.pages}")
        print(f"   Resumen: {doc.summary}")
    print("\n--- FECHAS CLAVE ---")
    for date in review.key_dates:
        print(f"DATE: {date}")
    print("\n--- ALERTAS ---")
    if not review.alerts:
        print("Ninguna.")
    for alert in review.alerts:
        print(f"ALERT [{alert.type}] {alert.description} (Fuente: {alert.source})")
    print("\n--- TRAZA ---")
    for tr in review.trace:
        print(f"TRACE {tr.source_type} -> {tr.source_ref}: {tr.detail}")
    print("==================================================\nPASS")

if __name__ == "__main__":
    test_24_botsac_review()
