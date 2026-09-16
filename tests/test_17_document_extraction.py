import os
import glob
import json
import hashlib
from datetime import datetime
import pypdf
import pytest

from botsac.models.document_schema import DocumentSource, DocumentPage, DocumentExtractionResult

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def test_17_document_extraction():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 17: DOCUMENT EXTRACTION...")
    
    dir_docs = f"data/documents/{ACQUISITION_ID}/{RADICADO}"
    dir_analysis_docs = f"data/analysis/{ACQUISITION_ID}/{RADICADO}/documents"
    
    assert os.path.exists(dir_docs), f"El directorio de documentos no existe: {dir_docs}"
    os.makedirs(dir_analysis_docs, exist_ok=True)
    
    pdf_files = glob.glob(os.path.join(dir_docs, "*.pdf"))
    assert len(pdf_files) == 2, f"Se esperaban 2 PDFs originales, se encontraron {len(pdf_files)}"
    
    manifest_entries = []
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"\n[DOCUMENT] Procesando: {filename}")
        
        # 1. Hashing y metadata base
        file_hash = calculate_sha256(pdf_path)
        file_size = os.path.getsize(pdf_path)
        
        # 2. Extracción de texto con pypdf
        pages_extracted = []
        extraction_status = "success"
        
        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                page_count = len(reader.pages)
                
                for i in range(page_count):
                    page = reader.pages[i]
                    text = page.extract_text() or ""
                    
                    if not text.strip():
                        text = "[NO_TEXT_FOUND_OR_IMAGE_ONLY]"
                        
                    pages_extracted.append(DocumentPage(
                        filename=filename,
                        page_number=i + 1,
                        text=text.strip(),
                        text_length=len(text.strip())
                    ))
        except Exception as e:
            extraction_status = f"failed: {str(e)}"
            page_count = 0
            
        doc_source = DocumentSource(
            filename=filename,
            sha256=file_hash,
            page_count=page_count,
            extraction_status=extraction_status
        )
        
        extraction = DocumentExtractionResult(
            document=doc_source,
            pages=pages_extracted,
            processing_type="NATIVE_TEXT"
        )
        
        # 3. Guardar JSON individual
        out_json_path = os.path.join(dir_analysis_docs, f"{file_hash}.json")
        with open(out_json_path, "w", encoding="utf-8") as out_f:
            json.dump(extraction.model_dump(), out_f, indent=2, ensure_ascii=False)
            
        # 4. Traza en consola y verificación
        assert os.path.exists(out_json_path), f"No se guardó el análisis para {filename}"
        
        total_text_length = sum(p.text_length for p in extraction.pages)
        print(f"  -> SHA256: {file_hash}")
        print(f"  -> Tamaño: {file_size} bytes")
        print(f"  -> Páginas: {page_count}")
        print(f"  -> Texto extraído: ~{total_text_length} caracteres")
        print(f"  -> Estado: {extraction_status}")
        
        manifest_entries.append({
            "filename": filename,
            "relative_path": f"documents/{file_hash}.json",
            "extension": ".pdf",
            "size_bytes": file_size,
            "sha256": file_hash,
            "page_count": page_count,
            "text_extracted": total_text_length > 0,
            "extraction_status": extraction_status
        })
        
    # 5. Guardar Manifest
    manifest_path = os.path.join(f"data/analysis/{ACQUISITION_ID}/{RADICADO}", "documents_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"documents": manifest_entries}, f, indent=2, ensure_ascii=False)
        
    assert os.path.exists(manifest_path), "No se guardó documents_manifest.json"
    
    print("\n==================================================")
    print("REPORT: TEST 17: PASS")
    print(f"Documentos procesados: {len(manifest_entries)}")
    for m in manifest_entries:
        print(f" - {m['filename']}")
        print(f"   Páginas: {m['page_count']} | Estado: {m['extraction_status']}")
        print(f"   SHA256: {m['sha256'][:8]}... | Texto: {'SÍ' if m['text_extracted'] else 'NO'}")
    print(f"Manifiesto guardado en: {manifest_path}")
    print("==================================================")

if __name__ == "__main__":
    test_17_document_extraction()
