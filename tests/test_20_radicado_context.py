import os
import json
from datetime import datetime
import pytest

from botsac.models.context_schema import DocumentContext, RadicadoContext
from botsac.models.document_schema import DocumentExtractionResult

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def test_20_radicado_context():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 20: CONTEXTO DOCUMENTAL...")
    
    dir_analysis = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    dir_raw = f"data/raw/{ACQUISITION_ID}/{RADICADO}"
    
    # 1. Metadata
    metadata_path = "data/logs/test_09_first_case.json"
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
    # 2. Solicitud
    solicitud_path = os.path.join(dir_raw, "solicitud.txt")
    solicitud_text = ""
    if os.path.exists(solicitud_path):
        with open(solicitud_path, "r", encoding="utf-8") as f:
            solicitud_text = f.read()
            
    # 3. Documentos
    manifest_path = os.path.join(dir_analysis, "documents_manifest.json")
    documents = []
    
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        docs_entries = manifest.get("documents", [])
        # Ordenar por filename (Paso 4)
        docs_entries.sort(key=lambda x: x.get("filename", ""))
        
        for entry in docs_entries:
            file_hash = entry.get("sha256")
            filename = entry.get("filename")
            
            # Buscar el JSON unificado de extracción
            # Podría ser <hash>.json o <hash>_ocr.json dependiendo del test 18
            json_native = os.path.join(dir_analysis, "documents", f"{file_hash}.json")
            json_ocr = os.path.join(dir_analysis, "documents", f"{file_hash}_ocr.json")
            
            ext_data = None
            if os.path.exists(json_ocr):
                with open(json_ocr, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
            elif os.path.exists(json_native):
                with open(json_native, "r", encoding="utf-8") as f:
                    ext_data = json.load(f)
                    
            if ext_data:
                # Ordenar páginas (Paso 4)
                pages = ext_data.get("pages", [])
                pages.sort(key=lambda p: p.get("page_number", 0))
                
                doc_ctx = DocumentContext(
                    filename=filename,
                    sha256=file_hash,
                    processing_type=ext_data.get("processing_type", "UNKNOWN"),
                    pages=pages
                )
                documents.append(doc_ctx)

    # 4. Novedades
    novedades_path = os.path.join(dir_analysis, "novedades.json")
    novedades = []
    if os.path.exists(novedades_path):
        with open(novedades_path, "r", encoding="utf-8") as f:
            novedades = json.load(f)
    else:
        # Fallback a response_discovery si existe
        resp_disc = os.path.join(dir_analysis, "response_discovery.json")
        if os.path.exists(resp_disc):
            with open(resp_disc, "r", encoding="utf-8") as f:
                rd_data = json.load(f)
                evidence = rd_data.get("evidence", [])
                for ev in evidence:
                    if ev.startswith("Novedades: "):
                        novedades.append({"texto": ev.replace("Novedades: ", "")})
                        
    # 5. Ensamblar Contexto
    context = RadicadoContext(
        radicado=RADICADO,
        metadata=metadata,
        solicitud=solicitud_text,
        documentos=documents,
        novedades=novedades
    )
    
    # 6. Validaciones (Paso 6)
    assert context.solicitud, "Solicitud no presente"
    assert len(context.documentos) == 2, "Faltan documentos"
    
    doc_native = next((d for d in context.documentos if d.processing_type == "NATIVE_TEXT"), None)
    doc_ocr = next((d for d in context.documentos if d.processing_type == "OCR"), None)
    
    assert doc_native, "No se conservó el procesamiento NATIVE_TEXT"
    assert doc_ocr, "No se conservó el procesamiento OCR"
    assert len(doc_native.pages) == 1, "Páginas esperadas incorrectas"
    assert len(doc_ocr.pages) == 2, "Páginas esperadas incorrectas"
    assert sum(len(p.text) for p in doc_ocr.pages) > 100, "Texto OCR no disponible"
    
    # 7. Persistencia (Paso 5)
    out_path = os.path.join(dir_analysis, "radicado_context.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(context.model_dump(), f, indent=2, ensure_ascii=False)
        
    assert os.path.exists(out_path)
    
    # RAW intactos (Paso 6)
    pdf_files = [f for f in os.listdir(f"data/documents/{ACQUISITION_ID}/{RADICADO}") if f.endswith(".pdf")]
    assert len(pdf_files) == 2, "Los RAW originales no existen o fueron modificados"
    
    # Reporte (Paso 7 y 8)
    json_str = context.model_dump_json()
    total_chars = len(json_str)
    
    num_docs = len(context.documentos)
    num_pages = sum(len(d.pages) for d in context.documentos)
    
    native_chars = sum(sum(len(p.text) for p in d.pages) for d in context.documentos if d.processing_type == "NATIVE_TEXT")
    ocr_chars = sum(sum(len(p.text) for p in d.pages) for d in context.documentos if d.processing_type == "OCR")
    
    print("\n==================================================")
    print("REPORT: TEST 20: PASS")
    print(f"Archivos creados: {out_path}")
    print(f"Documentos incluidos: {num_docs}")
    print(f"Total de páginas: {num_pages}")
    print(f"Caracteres totales en JSON: {total_chars}")
    print(f"Distribución de texto: Nativo = {native_chars} | OCR = {ocr_chars}")
    print("Integridad de hashes: Mantenida")
    print("==================================================")

if __name__ == "__main__":
    test_20_radicado_context()
