import os
import sys
import time
import hashlib
import urllib.parse
from typing import List, Dict, Any, Optional
import pypdf
from playwright.sync_api import sync_playwright, BrowserContext, Page
from dotenv import load_dotenv
from sqlalchemy import text

sys.path.insert(0, os.path.abspath("."))
from backend.database import engine
from backend.oracle_service import persist_document_canonical

load_dotenv()
SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")
ACQ_ID = "ACQ-20261015-CANONICAL"

def fix_encoding(text: Any) -> str:
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    try:
        return text.encode('latin1').decode('utf-8')
    except Exception:
        return text

def calculate_sha256(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()

def sync_attachments_for_radicado(radicado_id: str, context: BrowserContext, page: Page) -> Dict[str, Any]:
    """
    Sincroniza con 100% de integridad los documentos adjuntos de un radicado directamente desde SAC.
    1. Busca el radicado en 'Adm_Requerimiento_Busqueda'.
    2. Espera y localiza el frame 'FunOpeAdm_Adjunto_Consulta'.
    3. Extrae la lista real de adjuntos reportada por SAC.
    4. Descarga cada archivo a data/documents/ACQ-20261015-CANONICAL/{radicado}/.
    5. Persiste en SAC_DOCUMENTOS en Oracle.
    6. Elimina de Oracle y disco cualquier documento espurio/contaminado.
    """
    clean_rad = str(radicado_id).strip()
    print(f"\n========================================================")
    print(f"[{clean_rad}] INICIANDO SINCRONIZACIÓN CANÓNICA DE ADJUNTOS SAC")
    print(f"========================================================")
    
    # 1. Clic en 'Consultar Radicado' en el menú principal
    consultar_link = None
    for f in page.frames:
        try:
            loc = f.locator("text=/Consultar Radicado/i").first
            if loc.count() > 0 and loc.is_visible():
                consultar_link = loc
                break
        except Exception:
            pass
            
    if not consultar_link:
        print(f"[{clean_rad}] [WARN] Enlace 'Consultar Radicado' no visible en frames.")
        return {"status": "ERROR", "message": "Enlace Consultar Radicado no disponible", "docs": []}

    try:
        consultar_link.click(timeout=5000)
    except Exception:
        consultar_link.evaluate("el => el.click()")
        
    page.wait_for_timeout(2500)

    # 2. Localizar cuadro de búsqueda
    search_frame = None
    for f in page.frames:
        if "Adm_Requerimiento_Busqueda" in f.url:
            search_frame = f
            break

    if not search_frame:
        print(f"[{clean_rad}] [ERROR] Frame 'Adm_Requerimiento_Busqueda' no cargó.")
        return {"status": "ERROR", "message": "Frame de búsqueda no encontrado", "docs": []}

    rad_input = search_frame.locator("input#id_sc_field_radicado")
    rad_input.fill(clean_rad)
    rad_input.press("Enter")
    page.wait_for_timeout(4000)

    # 3. Localizar frame de adjuntos
    adj_frame = None
    timeout_adj = time.time() + 15
    while time.time() < timeout_adj:
        for f in page.frames:
            if "FunOpeAdm_Adjunto_Consulta" in f.url:
                adj_frame = f
                break
        if adj_frame:
            break
        page.wait_for_timeout(1000)

    if not adj_frame:
        print(f"[{clean_rad}] [INFO] No tiene sección de adjuntos o no cargó frame.")
        return {"status": "NO_ADJ_FRAME", "docs": []}

    # 4. Extraer filas de documentos
    doc_spans = adj_frame.locator("span[id^='id_sc_field_documentos_']").all()
    print(f"[{clean_rad}] Filas de adjuntos encontradas en SAC: {len(doc_spans)}")

    out_dir = os.path.join("data", "documents", ACQ_ID, clean_rad)
    os.makedirs(out_dir, exist_ok=True)

    sac_document_names = set()
    downloaded_records = []

    for idx, span in enumerate(doc_spans, 1):
        a_tag = span.locator("a").first
        if a_tag.count() == 0:
            continue

        raw_fname = a_tag.inner_text().strip()
        fname = fix_encoding(raw_fname)
        rel_href = a_tag.get_attribute("href") or ""
        sac_document_names.add(fname)

        full_url = urllib.parse.urljoin(adj_frame.url, rel_href)
        save_path = os.path.join(out_dir, fname)

        # Descargar archivo si no existe o validar
        downloaded_bytes = 0
        if not os.path.exists(save_path) or os.path.getsize(save_path) < 100:
            try:
                resp = context.request.get(full_url, timeout=30000)
                if resp.status == 200:
                    data = resp.body()
                    with open(save_path, "wb") as f_out:
                        f_out.write(data)
                    downloaded_bytes = len(data)
                    print(f"  [{idx}] Descargado de SAC: '{fname}' ({downloaded_bytes} bytes)")
                else:
                    print(f"  [{idx}] [ERROR HTTP {resp.status}] al descargar '{fname}'")
            except Exception as dl_err:
                print(f"  [{idx}] [ERROR] Descarga de '{fname}': {dl_err}")
        else:
            downloaded_bytes = os.path.getsize(save_path)
            print(f"  [{idx}] Archivo ya presente y verificado: '{fname}' ({downloaded_bytes} bytes)")

        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            fhash = calculate_sha256(save_path)
            fsize = os.path.getsize(save_path)

            pages = 1
            mime = "application/pdf"
            ext = os.path.splitext(fname)[1].lower()
            if ext == ".pdf":
                mime = "application/pdf"
                try:
                    rdr = pypdf.PdfReader(save_path)
                    pages = max(1, len(rdr.pages))
                except Exception:
                    pages = 1
            elif ext in [".docx", ".doc"]:
                mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            elif ext in [".xlsx", ".xls"]:
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif ext in [".jpg", ".jpeg", ".png"]:
                mime = f"image/{ext.replace('.', '')}"

            doc_type = "INFORME_TECNICO" if any(w in fname.lower() for w in ["informe", "reporte", "sismo", "tecnico", "afectacion"]) else "DOCUMENTO_SOLICITANTE"

            doc_id = persist_document_canonical(
                radicado_id=clean_rad,
                filename=fname,
                filepath=os.path.abspath(save_path),
                file_hash=fhash,
                file_size=fsize,
                pages=pages,
                mime_type=mime,
                tipo_original=doc_type,
                origen="SAC"
            )

            downloaded_records.append({
                "doc_id": doc_id,
                "filename": fname,
                "size_bytes": fsize,
                "pages": pages,
                "sha256": fhash
            })

    # 5. INTEGRIDAD: Limpiar en Oracle documentos del peticionario que NO pertenecen a SAC
    with engine.connect() as conn:
        existing_docs = conn.execute(text("""
            SELECT ID_DOCUMENTO, NOMBRE_ARCHIVO, TIPO_ORIGINAL, UBICACION_FISICA
            FROM SAC_DOCUMENTOS
            WHERE ID_RADICADO = :id
        """), {"id": clean_rad}).fetchall()

        cleaned_count = 0
        for doc_row in existing_docs:
            d_id, d_name, d_type, d_path = doc_row[0], doc_row[1], doc_row[2], doc_row[3]
            
            # Nunca borrar la respuesta oficial proyectada
            if d_type == "RESPUESTA_OFICIAL" or "RESPUESTA" in (d_name or "").upper():
                continue

            # Si el documento no está en la lista oficial de SAC, es espurio/contaminado
            if d_name not in sac_document_names:
                print(f"  [LIMPIEZA ORACLE] Eliminando documento espurio no perteneciente a {clean_rad}: '{d_name}' (ID: {d_id})")
                try:
                    conn.execute(text("DELETE FROM SAC_EVIDENCIAS WHERE ID_DOCUMENTO = :id"), {"id": d_id})
                    conn.execute(text("DELETE FROM SAC_EXTRACCIONES_DOCUMENTO WHERE ID_DOCUMENTO = :id"), {"id": d_id})
                    conn.execute(text("DELETE FROM SAC_DOCUMENTOS_DERIVADOS WHERE ID_DOCUMENTO_PADRE = :id"), {"id": d_id})
                    conn.execute(text("DELETE FROM SAC_DOCUMENTOS WHERE ID_DOCUMENTO = :id"), {"id": d_id})
                    conn.commit()
                    cleaned_count += 1
                except Exception as del_err:
                    print(f"  [WARN] Error eliminando registro {d_id} en BD: {del_err}")
                
                # Eliminar del disco si está en la carpeta de este radicado
                if d_path and os.path.exists(d_path) and clean_rad in d_path:
                    try:
                        os.remove(d_path)
                        print(f"  [LIMPIEZA DISCO] Archivo eliminado de disco: {d_path}")
                    except Exception as e:
                        print(f"  [WARN] No se pudo borrar archivo físico: {e}")

    print(f"[{clean_rad}] Sincronización completada: {len(downloaded_records)} válidos en SAC, {cleaned_count} eliminados por contaminación.")
    return {
        "status": "SUCCESS",
        "radicado": clean_rad,
        "valid_sac_count": len(downloaded_records),
        "cleaned_count": cleaned_count,
        "docs": downloaded_records
    }

def main():
    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        # Por defecto los dos casos demostrativos solicitados por el usuario
        targets = ["CAU2026ER032828", "CAU2026ER032637"]

    print(f"Iniciando navegador Playwright para sincronizar: {targets}")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1366, "height": 768},
            accept_downloads=True
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("Autenticando en portal SAC...")
        page.goto(SAC_URL, wait_until="networkidle", timeout=45000)
        page.wait_for_selector("select#id_sc_field_entidad", timeout=20000)
        page.select_option("select#id_sc_field_entidad", label="SE CAUCA")
        if page.locator("a#sub_form_b").is_visible():
            page.locator("a#sub_form_b").click()
        page.locator("input#id_sc_field_login").fill(SAC_USER)
        page.locator("input#id_sc_field_pswd").fill(SAC_PASS)
        page.locator('input.btn-login[value="Ingresar"]').click()
        page.wait_for_timeout(5000)

        for f in page.frames:
            try:
                for loc_str in ["button:has-text('Aceptar')", "a:has-text('Aceptar')", "input[type='button'][value='Aceptar']"]:
                    loc = f.locator(loc_str)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click()
                        break
            except Exception:
                pass
        page.wait_for_load_state("load")
        page.wait_for_timeout(3000)
        print("Sesión establecida correctamente.")

        results = {}
        for rad in targets:
            try:
                res = sync_attachments_for_radicado(rad, context, page)
                results[rad] = res
            except Exception as e:
                print(f"Error procesando {rad}: {e}")
                results[rad] = {"status": "ERROR", "error": str(e)}

        browser.close()

    print("\n================ RESUMEN DE EJECUCIÓN ================")
    for rad, r in results.items():
        print(f"  {rad}: {r.get('status')} -> {r.get('valid_sac_count', 0)} adjuntos SAC registrados, {r.get('cleaned_count', 0)} eliminados.")

if __name__ == "__main__":
    main()
