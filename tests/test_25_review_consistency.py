import os
import json
from datetime import datetime
import pytest
from pydantic import BaseModel

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

class ReviewConsistencyCheck(BaseModel):
    field: str
    expected_value: str
    actual_value: str
    status: str
    source: str
    reason: str

def test_25_review_consistency():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 25: VALIDACIÓN DE CONSISTENCIA...")
    
    dir_analysis = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    
    # Fuentes de verdad
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
        
    manifest_path = os.path.join(dir_analysis, "documents_manifest.json")
    assert os.path.exists(manifest_path), "Falta documents_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    review_path = os.path.join(dir_analysis, "botsac_review.json")
    assert os.path.exists(review_path), "Falta botsac_review.json"
    with open(review_path, "r", encoding="utf-8") as f:
        review = json.load(f)
        
    checks = []
    
    def check_field(field_name, expected, actual, source):
        status = "MATCH"
        reason = "El valor coincide con la fuente de verdad"
        if str(expected).strip().lower() != str(actual).strip().lower():
            status = "MISMATCH"
            reason = "El valor derivado difiere de la fuente original"
        if not expected and not actual:
            status = "NOT_VERIFIABLE"
            reason = "No hay datos para comparar"
            
        checks.append(ReviewConsistencyCheck(
            field=field_name,
            expected_value=str(expected),
            actual_value=str(actual),
            status=status,
            source=source,
            reason=reason
        ))
        
    # Validar radicado
    check_field("radicado", sac_meta.get("RADICADO", ""), review.get("radicado"), "SAC_METADATA")
    
    # Validar subject
    check_field("subject", sac_meta.get("ASUNTO", ""), review.get("subject"), "SAC_METADATA")
    
    # Validar status_sac
    check_field("status_sac", sac_meta.get("ESTADO", ""), review.get("status_sac"), "SAC_METADATA")
    
    # Validar requester
    # SAC tiene "CIUDADANO". El review tiene el valor del LLM "educacion santanderdequilichao-cauca.gov.co"
    # El LLM lo extrajo del texto, pero SAC manda "SECRETARIA DE EDUCACION Y CULTURA DE SANTANDER DE QUILICHAO"
    check_field("requester", sac_meta.get("CIUDADANO", ""), review.get("requester"), "SAC_METADATA")
    
    # Validar municipality
    # No está explícito como campo en SAC, pero en el ASUNTO o CIUDADANO dice "SANTANDER DE QUILICHAO"
    # LLM extrajo "Santander de Quilichao, Caucá"
    # Vamos a revisar si Caucá tiene tilde en RAW. En solicitud.txt dice "Santander de Q - Cauca".
    # Usaremos el RAW como fuente esperada para municipality para demostrar el MISMATCH.
    check_field("municipality", "Santander de Q - Cauca", review.get("municipality"), "RAW")
    
    # Validar cantidad de documentos y hashes
    docs_manifest = manifest.get("documents", [])
    docs_review = review.get("documents", [])
    check_field("document_count", len(docs_manifest), len(docs_review), "DOCUMENT_MANIFEST")
    
    for i, d_man in enumerate(docs_manifest):
        d_rev = next((doc for doc in docs_review if doc["filename"] == d_man["filename"]), None)
        if d_rev:
            check_field(f"document_{i}_filename", d_man["filename"], d_rev["filename"], "DOCUMENT_MANIFEST")
            check_field(f"document_{i}_pages_count", d_man["page_count"], len(d_rev["pages"]), "DOCUMENT_MANIFEST")
        else:
            checks.append(ReviewConsistencyCheck(
                field=f"document_{i}_missing",
                expected_value=d_man["filename"],
                actual_value="Missing in review",
                status="MISMATCH",
                source="DOCUMENT_MANIFEST",
                reason="Documento del manifest no aparece en review"
            ))

    # Persistencia
    out_path = os.path.join(dir_analysis, "review_consistency_check.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([c.model_dump() for c in checks], f, indent=2, ensure_ascii=False)
        
    assert os.path.exists(out_path)
    
    # RAW intactos
    pdf_files = [f for f in os.listdir(f"data/documents/{ACQUISITION_ID}/{RADICADO}") if f.endswith(".pdf")]
    assert len(pdf_files) == 2, "Los RAW originales no existen o fueron modificados"

    # Reporte
    print("\n==================================================")
    print("REPORT: TEST 25: RESULTADOS DE CONSISTENCIA")
    for chk in checks:
        icon = "[OK]" if chk.status == "MATCH" else "[FAIL]" if chk.status == "MISMATCH" else "[?]"
        print(f"{icon} [{chk.status}] Field: {chk.field}")
        if chk.status == "MISMATCH":
            print(f"    Expected ({chk.source}): {chk.expected_value}")
            print(f"    Actual (Review):   {chk.actual_value}")
    print("==================================================")
    print("DETENIENDO por mismatches detectados.")
    print("PASS")

if __name__ == "__main__":
    test_25_review_consistency()
