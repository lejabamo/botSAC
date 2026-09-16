import os
import json
import hashlib
from datetime import datetime
import fitz  # PyMuPDF
from rapidocr_onnxruntime import RapidOCR
import pytest

from botsac.models.document_schema import DocumentSource, DocumentPage, DocumentExtractionResult

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"
THRESHOLD_CHARS_PER_PAGE = 150

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def test_18_ocr_extraction():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 18: OCR SELECTIVO...")
    
    dir_analysis = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    manifest_path = os.path.join(dir_analysis, "documents_manifest.json")
    dir_docs = f"data/documents/{ACQUISITION_ID}/{RADICADO}"
    
    assert os.path.exists(manifest_path), "Falta el documents_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    ocr_engine = RapidOCR()
    
    for doc in manifest.get("documents", []):
        filename = doc["filename"]
        file_hash = doc["sha256"]
        page_count = doc["page_count"]
        
        # Leemos el JSON de extracción previa para saber el total de texto
        extraction_json = os.path.join(dir_analysis, "documents", f"{file_hash}.json")
        if not os.path.exists(extraction_json):
            continue
            
        with open(extraction_json, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
            
        total_text_length = sum(p.get("text_length", 0) for p in prev_data.get("pages", []))
        
        # PASO 1 - CRITERIO DE ACTIVACIÓN
        needs_ocr = False
        if page_count > 0:
            avg_chars = total_text_length / page_count
            if avg_chars < THRESHOLD_CHARS_PER_PAGE:
                needs_ocr = True
                
        # PASO 2 y 3 - OCR (Sólo al documento 2 en esta prueba)
        # Identificamos el doc 2 por su hash o su longitud
        if "OF A MEN" not in filename:
            assert not needs_ocr or avg_chars > THRESHOLD_CHARS_PER_PAGE, "Documento 1 no debe ejecutar OCR"
            print(f"[SKIP] Documento {filename} no requiere OCR (Promedio chars: {avg_chars:.2f})")
            continue
            
        assert needs_ocr, "Documento 2 DEBE activar needs_ocr"
        print(f"\n[OCR] Iniciando procesamiento para {filename}...")
        
        pdf_path = os.path.join(dir_docs, filename)
        orig_hash = calculate_sha256(pdf_path)
        
        pdf_doc = fitz.open(pdf_path)
        
        ocr_pages = []
        overall_status = "success"
        total_ocr_text_length = 0
        
        for i in range(len(pdf_doc)):
            page = pdf_doc.load_page(i)
            # Renderizar página a imagen (zoom 2x para mejor resolución)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            
            # Convertir pixmap a bytes de imagen (PNG)
            img_bytes = pix.tobytes("png")
            
            # Ejecutar OCR
            result, _ = ocr_engine(img_bytes)
            
            # result es una lista de [caja_envolvente, texto, confianza]
            if result:
                page_text = "\n".join([line[1] for line in result])
                status = "success"
            else:
                page_text = ""
                status = "no_text_found"
                
            page_text_length = len(page_text)
            total_ocr_text_length += page_text_length
            
            ocr_pages.append(DocumentPage(
                filename=filename,
                page_number=i + 1,
                text=page_text,
                text_length=page_text_length,
                status=status
            ))
            print(f"  -> Pág {i+1}: {page_text_length} caracteres extraídos.")
            
        pdf_doc.close()
        
        doc_source = DocumentSource(
            filename=filename,
            sha256=file_hash,
            page_count=page_count,
            extraction_status=overall_status
        )
        
        ocr_extraction = DocumentExtractionResult(
            document=doc_source,
            pages=ocr_pages,
            processing_type="OCR"
        )
        
        # Validar SHA-256 no cambió
        final_hash = calculate_sha256(pdf_path)
        assert orig_hash == final_hash, "El PDF fue modificado durante el OCR"
        
        # Guardar resultados
        out_ocr_path = os.path.join(dir_analysis, "documents", f"{file_hash}_ocr.json")
        with open(out_ocr_path, "w", encoding="utf-8") as f:
            json.dump(ocr_extraction.model_dump(), f, indent=2, ensure_ascii=False)
            
        print("\n==================================================")
        print("REPORT: TEST 18: PASS")
        print(f"Documento procesado: {filename}")
        print(f"Páginas: {page_count}")
        print(f"Caracteres antes de OCR: {total_text_length}")
        print(f"Caracteres después de OCR: {total_ocr_text_length}")
        print(f"Estado de OCR: {overall_status}")
        print(f"SHA-256 original intacto: {orig_hash}")
        print("==================================================")

if __name__ == "__main__":
    test_18_ocr_extraction()
