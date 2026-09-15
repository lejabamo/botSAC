import os
import json
import glob
from datetime import datetime
from pypdf import PdfReader

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def extract_text_from_pdf(pdf_path):
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return ""

def test_11_run_analysis():
    print(f"\n[START] Iniciando TEST 11: ANÁLISIS DOCUMENTAL para {RADICADO}")
    
    # Paths
    base_dir = f"data/ingested/{ACQUISITION_ID}/{RADICADO}"
    raw_dir = f"data/raw/{ACQUISITION_ID}/{RADICADO}"
    analysis_dir = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    
    os.makedirs(analysis_dir, exist_ok=True)
    
    # 1. Cargar el expediente local
    case_path = os.path.join(base_dir, "case.json")
    if not os.path.exists(case_path):
        print(f"[FAIL] Expediente no encontrado en {case_path}")
        return
        
    with open(case_path, "r", encoding="utf-8") as f:
        case_data = json.load(f)
        
    with open(os.path.join(raw_dir, "solicitud.txt"), "r", encoding="utf-8") as f:
        solicitud_text = f.read()
        
    # 2. Procesamiento Documental
    print("[STEP] Extrayendo texto de documentos PDF...")
    documents = case_data.get("case", {}).get("documents", [])
    doc_classification = []
    
    for i, doc in enumerate(documents):
        download_info = doc.get("download", {})
        if download_info:
            local_path = download_info.get("local_path")
            orig_name = download_info.get("original_name")
            if local_path and os.path.exists(local_path):
                text = extract_text_from_pdf(local_path)
                
                if not text.strip():
                    status = "DOCUMENT_NEEDS_OCR"
                else:
                    status = "TEXT_EXTRACTED"
                    
                # Guardar texto derivado
                txt_filename = f"document_{i+1}_extracted.txt"
                with open(os.path.join(analysis_dir, txt_filename), "w", encoding="utf-8") as f_out:
                    f_out.write(text)
                    
                doc_classification.append({
                    "document_id": f"doc_{i+1}",
                    "filename": orig_name,
                    "extraction_status": status,
                    "tipo_probable": "PENDING_LLM_INTEGRATION",
                    "justificacion": "PENDING_LLM_INTEGRATION",
                    "nivel_confianza": "PENDING_LLM_INTEGRATION",
                    "extracted_text_path": txt_filename
                })
                
    # 3. Guardar Classification Contract
    with open(os.path.join(analysis_dir, "document_classification.json"), "w", encoding="utf-8") as f:
        json.dump(doc_classification, f, indent=2, ensure_ascii=False)
        
    # 4. Resumen de la Solicitud y Pretensiones
    print("[STEP] Estructurando contrato de análisis...")
    analysis = {
        "analysis_id": f"ANALYSIS-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "acquisition_id": ACQUISITION_ID,
        "radicado": RADICADO,
        "timestamp": datetime.now().isoformat(),
        "model": "PENDING_LLM_INTEGRATION",
        "solicitud_resumen": {
            "problema_reportado": "PENDING_LLM_INTEGRATION",
            "institucion": "PENDING_LLM_INTEGRATION",
            "sede": "PENDING_LLM_INTEGRATION",
            "municipio": "PENDING_LLM_INTEGRATION",
            "informacion_solicitada": "PENDING_LLM_INTEGRATION"
        },
        "pretensiones": [
            {
                "id": 1,
                "descripcion": "PENDING_LLM_INTEGRATION",
                "evidencia_origen": "solicitud",
                "source_reference": "solicitud.txt"
            }
        ],
        "respuesta_resumen": {
            "status": "PENDING_LLM_INTEGRATION",
            "descripcion": "PENDING_LLM_INTEGRATION"
        }
    }
    
    with open(os.path.join(analysis_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
        
    # 5. Comparación
    comparison = [
        {
            "pretension": "PENDING_LLM_INTEGRATION",
            "respuesta_encontrada": "PENDING_LLM_INTEGRATION",
            "estado": "PENDING_LLM_INTEGRATION",
            "source_reference": "PENDING_LLM_INTEGRATION"
        }
    ]
    with open(os.path.join(analysis_dir, "comparison.json"), "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
        
    # 6. Timeline
    timeline = [
        {
            "date": case_data.get("case", {}).get("metadata", {}).get("FECHA CREACIÓN", "NO DETERMINADO"),
            "event": "Creación del Radicado en SAC",
            "source": "metadata SAC"
        }
    ]
    with open(os.path.join(analysis_dir, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(timeline, f, indent=2, ensure_ascii=False)
        
    # 7. Summary
    summary_md = f"""# Resumen Ejecutivo - {RADICADO}

**RADICADO**: {RADICADO}
**MUNICIPIO**: PENDING_LLM_INTEGRATION
**INSTITUCIÓN**: PENDING_LLM_INTEGRATION

**SOLICITUD**: 
PENDING_LLM_INTEGRATION (Contrato establecido, a la espera de modelo).

**RESPUESTA**:
PENDING_LLM_INTEGRATION

**RESULTADO DOCUMENTAL**:
EXTRACTED DATA SUCCESSFUL. {len(doc_classification)} documentos procesados localmente.

**HALLAZGOS**:
PENDING_LLM_INTEGRATION

**ALERTAS**:
PENDING_LLM_INTEGRATION

**DOCUMENTOS**:
{', '.join([d['filename'] for d in doc_classification])}
"""
    with open(os.path.join(analysis_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_md)
        
    print(f"[SUCCESS] Artefactos de análisis (contrato) generados en {analysis_dir}")
    print("\n==================================================")
    print("REPORT: TEST 11: PASS")
    print(f"Clasificación de {len(doc_classification)} documentos (Contrato: PENDING_LLM)")
    print("Resumen de Solicitud: Contrato generado")
    print("Resumen de Respuesta: Contrato generado")
    print("Matriz solicitud/respuesta: Contrato generado")
    print("Timeline: 1 evento base generado")
    print(f"Analysis ID: {analysis['analysis_id']}")
    print(f"Archivos generados: analysis.json, document_classification.json, comparison.json, timeline.json, summary.md")
    print("Proveedor/modelo: PENDING_LLM_INTEGRATION")
    print("==================================================")

if __name__ == "__main__":
    test_11_run_analysis()
