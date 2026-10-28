import os
import sys
import time
import json
import hashlib
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright, expect
from dotenv import load_dotenv
import pypdf

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")
ACQUISITION_ID = "ACQ-20260915-0001" # Mantener el mismo para el MVP

def fix_encoding(text):
    if not isinstance(text, str): return text
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def convert_word_to_pdf(doc_path, pdf_path):
    import subprocess
    import tempfile
    ps_script = f"""
$ErrorActionPreference = "Stop"
try {{
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open('{os.path.abspath(doc_path)}')
    $doc.SaveAs([ref]'{os.path.abspath(pdf_path)}', [ref]17)
    $doc.Close()
}} catch {{
    Write-Error $_.Exception.Message
}} finally {{
    if ($word) {{ $word.Quit() }}
}}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as f:
        f.write(ps_script)
        temp_ps1 = f.name
        
    try:
        # TIMEOUT AÑADIDO PARA EVITAR BLOQUEO DE 8 HORAS
        result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", temp_ps1], capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode == 0 and os.path.exists(pdf_path):
            return True, "MS Word (COM via PowerShell)", "OK"
        else:
            return False, "MS Word (COM via PowerShell)", f"Error: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "MS Word (COM via PowerShell)", "Error: Timeout (60s) excedido. Posible bloqueo de macros/diálogo."
    finally:
        os.remove(temp_ps1)

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def log_timing(radicado_id, msg):
    os.makedirs("data", exist_ok=True)
    with open("data/acquisition_timing.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {radicado_id} - {msg}\n")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
def heartbeat(radicado_id, etapa, docs_found=0, docs_downloaded=0):
    try:
        sys.path.append(os.path.abspath("."))
        import scripts.queue_manager as qm
        msg = f"ETAPA={etapa} | DOCS_FOUND={docs_found} | DOCS_DL={docs_downloaded}"
        qm.update_status(radicado_id, "ADQUIRIENDO", error_detail=msg)
    except: pass

def acquire_radicado(radicado_id, target_funcionario=None, usuario_funcionario=None):
    inbox_path = "data/dashboard_inbox.json"
    inbox_data = []
    if os.path.exists(inbox_path):
        with open(inbox_path, "r", encoding="utf-8") as f:
            inbox_data = json.load(f)
            
    if not target_funcionario:
        if usuario_funcionario:
            for item in inbox_data:
                if item.get("usuario_funcionario") == usuario_funcionario and item.get("radicado") == radicado_id:
                    target_funcionario = item.get("funcionario")
                    break
                    
        if not target_funcionario:
            for item in inbox_data:
                if item.get("radicado") == radicado_id:
                    target_funcionario = item.get("funcionario")
                    break
                    
    if not target_funcionario:
        print(f"[ERROR] El radicado {radicado_id} o funcionario esperado no se pudo resolver desde los parámetros o el inbox.")
        sys.exit(1)
            
    print(f"\n[INFO] Iniciando adquisición dirigida para: {radicado_id} (Asignado a: {target_funcionario})")
    log_timing(radicado_id, "inicio")
    heartbeat(radicado_id, "INICIO")

    print("[1] iniciar navegador - INICIO")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        page = context.new_page()
        print("[1] iniciar navegador - OK")

        try:
            # LOGIN
            print("[2] login - INICIO")
            heartbeat(radicado_id, "LOGIN")
            page.goto(SAC_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
            page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
            if page.locator('a#sub_form_b').is_visible():
                page.locator('a#sub_form_b').click()
            page.wait_for_selector('input#id_sc_field_login', timeout=15000)
            page.locator('input#id_sc_field_login').fill(SAC_USER)
            page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
            page.locator('input.btn-login[value="Ingresar"]').click()
            print("[2] login - OK")
            log_timing(radicado_id, "login")
            
            print("[3] sesión activa/modal - INICIO")
            page.wait_for_timeout(5000)
            modal_handled = False
            for f in page.frames:
                try:
                    for loc_str in ["button:has-text('Aceptar')", "a:has-text('Aceptar')", "input[type='button'][value='Aceptar']"]:
                        loc = f.locator(loc_str)
                        if loc.count() > 0 and loc.first.is_visible():
                            loc.first.click()
                            modal_handled = True
                            break
                except: pass
                if modal_handled: break
                
            page.wait_for_load_state("load")
            page.wait_for_timeout(5000)
            print("[3] sesión activa/modal - OK")
            
            # PASO 2: Mis Sub-Dependencias
            print("[4] navegar a dependencia - INICIO")
            heartbeat(radicado_id, "NAVEGACION")
            menu_clicked = False
            timeout_end = time.time() + 30
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        loc = f.locator("text='Mis Sub-Dependencias'")
                        if loc.count() > 0:
                            for i in range(loc.count()):
                                if loc.nth(i).is_visible():
                                    loc.nth(i).evaluate("el => el.click()")
                                    menu_clicked = True
                                    break
                    except: pass
                    if menu_clicked: break
                if menu_clicked: break
                page.wait_for_timeout(1000)
                
            if not menu_clicked:
                raise Exception("Timeout esperando 'Mis Sub-Dependencias'")
                
            page.wait_for_timeout(3000)
            
            # PASO 3: Por Dependencias (REQUERIMIENTOS)
            otras_dep_frame = None
            selector_req = "text='REQUERIMIENTOS'"
            timeout_end = time.time() + 30
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        if "Semaforo" in f.url and f.locator(selector_req).count() > 0:
                            otras_dep_frame = f
                            break
                    except: pass
                if otras_dep_frame: break
                page.wait_for_timeout(1000)
                
            if not otras_dep_frame:
                print("--- DEBUG FRAMES ---")
                for i, f in enumerate(page.frames):
                    print(f"FRAME {i} | name='{f.name}' | url='{f.url}'")
                    # Intentar buscar el texto Mis Sub-Dependencias para ver si el click no surtió efecto
                    try:
                        loc_menu = f.locator("text='Mis Sub-Dependencias'")
                        if loc_menu.count() > 0:
                            print(f"FRAME {i} tiene 'Mis Sub-Dependencias' (¿Quizás el click no funcionó o falta esperar más?)")
                    except: pass
                print("--------------------")
                raise Exception("Timeout esperando iframe Semaforo")
                    
            try:
                otras_dep_frame.locator(selector_req).first.click(timeout=3000, force=True)
            except:
                otras_dep_frame.locator(selector_req).first.evaluate("el => el.click()")
            
            # PASO 4: Infraestructura Educativa
            asignados_frame = None
            target_dep = "Infraestructura Educativa"
            timeout_end = time.time() + 30
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        if f.locator("text=/ASIGNADOS POR DEPENDENCIAS/i").count() > 0:
                            asignados_frame = f
                            break
                    except: pass
                if asignados_frame: break
                page.wait_for_timeout(1000)
                
            if not asignados_frame:
                raise Exception("Timeout esperando frame ASIGNADOS POR DEPENDENCIAS")
                    
            loc_dep = asignados_frame.locator(f"text=/{target_dep}/i")
            try:
                loc_dep.first.click(timeout=5000)
            except:
                loc_dep.first.evaluate("el => el.click()")
            print("[4] navegar a dependencia - OK")
            log_timing(radicado_id, "navegación")
                
            # PASO 5: Funcionario Específico
            print("[5] seleccionar funcionario - INICIO")
            heartbeat(radicado_id, "LISTADO")
            funcionarios_frame = None
            timeout_end = time.time() + 30
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        if f.locator("text=/ASIGNADOS POR FUNCIONARIOS/i").count() > 0 and f.locator("tr").count() > 3:
                            funcionarios_frame = f
                            break
                    except: pass
                if funcionarios_frame: break
                page.wait_for_timeout(1000)
                
            if not funcionarios_frame:
                raise Exception("Timeout esperando frame ASIGNADOS POR FUNCIONARIOS")
                
            rows = funcionarios_frame.locator("tr").all()
            target_link = None
            
            for row in rows:
                if target_funcionario in row.inner_text().strip():
                    links = row.locator("a").all()
                    # Recolectar todos los enlaces con número > 0
                    valid_links = []
                    for l in links:
                        text = l.inner_text().strip()
                        if text.isdigit() and int(text) > 0:
                            valid_links.append(l)
                            
                    # Priorizar el que tenga 'venc' en el href, o el último (suele ser vencidos/sin finalizar)
                    for l in valid_links:
                        href = l.evaluate("el => el.getAttribute('href')") or l.evaluate("el => el.getAttribute('onclick')") or ""
                        if "venc" in href.lower():
                            target_link = l
                            break
                    
                    if not target_link and len(valid_links) > 0:
                        target_link = valid_links[-1] # Probar con el último que suele ser el más específico
                        
                    if target_link: break
                        
            if not target_link:
                raise Exception(f"No se pudo encontrar enlace para el funcionario {target_funcionario}")
                
            try:
                target_link.click(timeout=5000)
            except:
                target_link.evaluate("el => el.click()")
            print("[5] seleccionar funcionario - OK")
            log_timing(radicado_id, "listado")
                
            # PASO 6: Buscar el Radicado
            print("[6] localizar radicado - INICIO")
            heartbeat(radicado_id, "DETALLE")
            vencidos_frame = None
            timeout_end = time.time() + 30
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        if ("FunOpeAdm_RequerimientosOtrasDependencias" in f.url or "FunAdm_RequerimientosAsignados_Funcionarios" in f.url) and f.locator("tr").count() > 5:
                            vencidos_frame = f
                            break
                    except: pass
                if vencidos_frame: break
                page.wait_for_timeout(1000)
                
            if not vencidos_frame:
                raise Exception("Timeout esperando frame de la cuadrícula de radicados")
                
            v_rows = vencidos_frame.locator("tr").all()
            
            target_rad_link = vencidos_frame.locator(f"a:has-text('{radicado_id}')").first
            if target_rad_link.count() == 0:
                target_rad_link = vencidos_frame.locator(f"text='{radicado_id}'").first
                
            # Pagination loop
            max_pages = 10
            page_count = 0
            while target_rad_link.count() == 0 and page_count < max_pages:
                next_btn = vencidos_frame.locator("a#sc_b_avc_bot").first
                if next_btn.count() > 0 and next_btn.is_visible() and "disabled" not in (next_btn.get_attribute("class") or ""):
                    try:
                        next_btn.click(timeout=5000)
                    except:
                        next_btn.evaluate("el => el.click()")
                    page.wait_for_timeout(3000)
                    
                    target_rad_link = vencidos_frame.locator(f"a:has-text('{radicado_id}')").first
                    if target_rad_link.count() == 0:
                        target_rad_link = vencidos_frame.locator(f"text='{radicado_id}'").first
                    page_count += 1
                else:
                    break
                
            if target_rad_link.count() == 0:
                raise Exception(f"No se encontró el radicado {radicado_id} en la lista después de {page_count+1} páginas.")
                
            try:
                target_rad_link.click(timeout=5000)
            except:
                target_rad_link.evaluate("el => el.click()")
            print("[6] localizar radicado - OK")
            log_timing(radicado_id, "detalle")
                
            # PASO 7: Extraer Detalle
            print("[7] abrir radicado - INICIO")
            detalle_frame = None
            timeout_end = time.time() + 30
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        if "FunOpeAdm_Requerimiento_Consulta" in f.url:
                            detalle_frame = f
                            break
                    except: pass
                if detalle_frame: break
                page.wait_for_timeout(1000)
                
            if not detalle_frame:
                raise Exception(f"No se pudo cargar la vista de detalle de {radicado_id}")
                
            try:
                detalle_frame.locator("body").wait_for(timeout=10000)
            except: pass
            print("[7] abrir radicado - OK")
                
            dir_ingested = f"data/ingested/{ACQUISITION_ID}/{radicado_id}"
            dir_raw = f"data/raw/{ACQUISITION_ID}/{radicado_id}"
            dir_docs = f"data/documents/{ACQUISITION_ID}/{radicado_id}"
            dir_analysis_docs = f"data/analysis/{ACQUISITION_ID}/{radicado_id}/documents"
            dir_analysis_base = f"data/analysis/{ACQUISITION_ID}/{radicado_id}"
            
            for d in [dir_ingested, dir_raw, dir_docs, dir_analysis_docs, dir_analysis_base]:
                os.makedirs(d, exist_ok=True)
                
            metadata = {}
            content_text = ""
            novedades_list = []
            downloaded_files = []
            hashes = {}
            
            # Metadata
            print("[8] adquirir metadata - INICIO")
            labels = detalle_frame.locator("td.scFormLabelOdd").all()
            for lbl in labels:
                try:
                    lbl_text = fix_encoding(lbl.inner_text().strip())
                    if not lbl_text: continue
                    next_td = lbl.locator("xpath=following-sibling::td").first
                    if next_td.count() > 0:
                        val_span = next_td.locator("span[id^='id_read_on_']").first
                        if val_span.count() > 0:
                            metadata[lbl_text] = fix_encoding(val_span.inner_text().strip())
                except: pass
            
            with open(f"{dir_raw}/metadata_sac.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)
                
            print("[8] adquirir metadata - OK")
                
            # Content
            try:
                content_span = detalle_frame.locator("span#id_read_on_contenido").first
                if content_span.count() > 0:
                    content_text = fix_encoding(content_span.inner_text().strip())
                with open(f"{dir_raw}/solicitud.txt", "w", encoding="utf-8") as f:
                    f.write(content_text)
            except: pass
            
            # Novedades
            novedades_frame = None
            for f in page.frames:
                if "FunOpeAdm_Novedad_Consulta" in f.url:
                    novedades_frame = f
                    break
                    
            if novedades_frame:
                novedades_frame.locator("body").wait_for(timeout=10000)
                nov_rows = novedades_frame.locator("tr").all()
                for r in nov_rows:
                    class_attr = r.evaluate("el => el.getAttribute('class')") or ""
                    if "scGridFieldOdd" in class_attr or "scGridFieldEven" in class_attr:
                        cells = r.locator("td").all()
                        valid_cells = [c for c in cells if c.inner_text().strip() or c.locator("img, span").count() > 0]
                        if valid_cells:
                            row_data = [fix_encoding(c.inner_text().strip()) for c in valid_cells]
                            novedades_list.append({"raw_row": row_data})
                            
                with open(f"{dir_raw}/novedades.json", "w", encoding="utf-8") as f:
                    json.dump(novedades_list, f, indent=2, ensure_ascii=False)
                    
            # Documentos
            print("[9] adquirir documentos - INICIO")
            adjuntos_frame = None
            document_list = []
            heartbeat(radicado_id, "DOCUMENTOS", 0, 0)
            for f in page.frames:
                if "FunOpeAdm_Adjunto_Consulta" in f.url:
                    adjuntos_frame = f
                    break
                    
            if adjuntos_frame:
                adjuntos_frame.locator("body").wait_for(timeout=10000)
                num_rows = adjuntos_frame.locator("tr").count()
                
                for i in range(num_rows):
                    max_retries = 3
                    for attempt in range(max_retries):
                        current_adj_frame = None
                        for f in page.frames:
                            if "FunOpeAdm_Adjunto_Consulta" in f.url:
                                current_adj_frame = f
                                break
                        if not current_adj_frame:
                            page.wait_for_timeout(1000)
                            continue
                            
                        try:
                            current_adj_frame.locator("body").wait_for(timeout=10000)
                            r = current_adj_frame.locator("tr").nth(i)
                            class_attr = r.evaluate("el => el.getAttribute('class')") or ""
                            if "scGridFieldOdd" in class_attr or "scGridFieldEven" in class_attr:
                                cells = r.locator("td").all()
                                valid_cells = [c for c in cells if c.inner_text().strip() or c.locator("a").count() > 0]
                                if valid_cells:
                                    row_data = [fix_encoding(c.inner_text().strip()) for c in valid_cells]
                                    
                                    link = None
                                    for c in valid_cells:
                                        a_tags = c.locator("a").all()
                                        for a in a_tags:
                                            href_val = a.evaluate("el => el.getAttribute('href')") or ""
                                            if "documento" in href_val.lower() or "descargar" in href_val.lower() or "javascript:" in href_val:
                                                link = a
                                                break
                                        if link: break
                                        
                                    if link:
                                        try:
                                            with page.expect_download(timeout=15000) as download_info:
                                                link.click()
                                            download = download_info.value
                                            original_name = fix_encoding(download.suggested_filename)
                                            base_name, ext = os.path.splitext(original_name)
                                            local_path = os.path.join(dir_docs, original_name)
                                            
                                            # Solo agregar sufijo numérico si el archivo ya fue descargado en esta misma sesión
                                            counter = 1
                                            while any(d["local_path"] == local_path for d in downloaded_files):
                                                local_path = os.path.join(dir_docs, f"{base_name}_{counter}{ext}")
                                                counter += 1
                                                
                                            download.save_as(local_path)
                                            file_hash = calculate_sha256(local_path)
                                            downloaded_files.append({"original_name": original_name, "local_path": local_path, "sha256": file_hash})
                                            hashes[original_name] = file_hash
                                            
                                            log_timing(radicado_id, f"descarga_fin {original_name}")
                                            heartbeat(radicado_id, "DOCUMENTOS_DESCARGANDO", num_rows, len(downloaded_files))
                                            
                                            # Simulate text extraction
                                            pages_extracted = []
                                            extraction_status = "success"
                                            try:
                                                if ext.lower() == ".pdf":
                                                    with open(local_path, "rb") as f_pdf:
                                                        reader = pypdf.PdfReader(f_pdf)
                                                        for p_idx in range(len(reader.pages)):
                                                            text = reader.pages[p_idx].extract_text() or ""
                                                            if not text.strip(): text = "[NO_TEXT_FOUND_OR_IMAGE_ONLY]"
                                                            pages_extracted.append({"page_number": p_idx+1, "text": fix_encoding(text.strip()), "text_length": len(text.strip())})
                                                elif ext.lower() in [".doc", ".docx"]:
                                                    fallback_pdf_path = os.path.join(dir_analysis_docs, f"{file_hash}_derivado.pdf")
                                                    success, tool, msg = convert_word_to_pdf(local_path, fallback_pdf_path)
                                                    
                                                    derivado_hash = calculate_sha256(fallback_pdf_path) if success else None
                                                    conversion_trace = {
                                                        "original_file": original_name,
                                                        "original_ext": ext,
                                                        "derived_pdf": f"{file_hash}_derivado.pdf" if success else None,
                                                        "original_hash": file_hash,
                                                        "derived_hash": derivado_hash,
                                                        "converter_tool": tool,
                                                        "tool_version": "Office16",
                                                        "conversion_date": datetime.now().isoformat(),
                                                        "status": "OK" if success else f"ERROR_CONTROLADO - {msg}"
                                                    }
                                                    with open(os.path.join(dir_analysis_docs, f"{file_hash}_conversion.json"), "w", encoding="utf-8") as f_trace:
                                                        json.dump(conversion_trace, f_trace, indent=2, ensure_ascii=False)
                                                    
                                                    if success:
                                                        extraction_status = f"success_converted_via_{tool.replace(' ', '_')}"
                                                        # Extraer texto del PDF recién creado
                                                        with open(fallback_pdf_path, "rb") as f_pdf:
                                                            reader = pypdf.PdfReader(f_pdf)
                                                            for p_idx in range(len(reader.pages)):
                                                                text = reader.pages[p_idx].extract_text() or ""
                                                                if not text.strip(): text = "[NO_TEXT_FOUND_OR_IMAGE_ONLY]"
                                                                pages_extracted.append({"page_number": p_idx+1, "text": fix_encoding(text.strip()), "text_length": len(text.strip())})
                                                    else:
                                                        extraction_status = f"failed_conversion: {msg}"
                                                        pages_extracted.append({"page_number": 1, "text": "[FORMATO OFFICE - ERROR DE CONVERSIÓN LOCAL]", "text_length": 0})
                                                        
                                                else:
                                                    extraction_status = "unsupported_format_fallback"
                                                    pages_extracted.append({"page_number": 1, "text": "[CONTENIDO BINARIO - IMAGEN O DESCONOCIDO]", "text_length": 0})
                                            except Exception as e:
                                                extraction_status = f"failed: {e}"
                                                
                                            extraction_data = {
                                                "document": {"filename": original_name, "sha256": file_hash, "page_count": len(pages_extracted), "extraction_status": extraction_status},
                                                "pages": pages_extracted,
                                                "processing_type": "NATIVE_TEXT"
                                            }
                                            
                                            with open(os.path.join(dir_analysis_docs, f"{file_hash}.json"), "w", encoding="utf-8") as f_out:
                                                json.dump(extraction_data, f_out, indent=2, ensure_ascii=False)
                                                
                                        except Exception as e:
                                            print(f"Error descargando: {e}")
                                            
                                    document_list.append({"raw_row": row_data, "filename": original_name if link else None})
                            break # Exito en el procesamiento de esta fila, salir del retry loop
                        except Exception as e:
                            err_str = str(e).lower()
                            if "detached" in err_str or "destroyed" in err_str or "attached" in err_str:
                                print(f"[REINTENTO {attempt+1}/{max_retries}] Frame detached evaluando fila {i}. Reintentando...")
                                page.wait_for_timeout(2000)
                                if attempt == max_retries - 1:
                                    print(f"Error evaluando fila {i} de adjuntos tras max reintentos: {e}")
                                continue
                            else:
                                print(f"Error evaluando fila {i}: {e}")
                                break # Error distinto, abortar fila
                        
            print("[9] adquirir documentos - OK")
            log_timing(radicado_id, f"documentos = {num_rows}")
            log_timing(radicado_id, f"descargas_completas = {len(downloaded_files)}")

            # Save basic review stub so the dashboard knows it exists
            print("[10] guardar expediente - INICIO")
            # We skip LLM here! We just create a botsac_review.json containing basic info
            review_data = {
                "radicado": radicado_id,
                "subject": metadata.get("ASUNTO", "Sin asunto"),
                "status_sac": metadata.get("ESTADO", "Desconocido"),
                "requester": metadata.get("SOLICITANTE", metadata.get("REMITENTE", metadata.get("ENTIDAD", "Desconocido"))),
                "municipality": metadata.get("MUNICIPIO", metadata.get("CIUDAD/MUNICIPIO", metadata.get("UBICACION", metadata.get("CIUDAD", "Pendiente")))),
                "plazo": metadata.get("PLAZO", metadata.get("DIAS", metadata.get("VENCIMIENTO", ""))),
                "request_summary": content_text,
                "key_dates": [],
                "documents": [],
                "alerts": [],
                "trace": [{"source_type": "SYSTEM", "source_ref": "Acquisition", "detail": "Expediente descargado."}]
            }
            
            for doc in downloaded_files:
                ext = os.path.splitext(doc["original_name"])[1].lower()
                if ext == ".pdf": doc_type = "PDF"
                elif ext in [".doc", ".docx"]: doc_type = "Word"
                elif ext in [".xls", ".xlsx"]: doc_type = "Excel"
                elif ext in [".png", ".jpg", ".jpeg"]: doc_type = "Imagen"
                elif ext: doc_type = f"Archivo {ext.upper()}"
                else: doc_type = "Desconocido"

                review_data["documents"].append({
                    "filename": doc["original_name"],
                    "document_type": doc_type,
                    "summary": "Documento adquirido. Análisis pendiente.",
                    "pages": list(range(1)) # Dummy to show it has content
                })
                
            with open(f"{dir_analysis_base}/botsac_review.json", "w", encoding="utf-8") as f:
                json.dump(review_data, f, indent=4, ensure_ascii=False)
                
            # Manifest
            manifest_data = {"documents": []}
            for doc in downloaded_files:
                manifest_data["documents"].append({"filename": doc["original_name"], "sha256": doc["sha256"]})
            with open(f"{dir_analysis_base}/documents_manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=4, ensure_ascii=False)

            print("[10] guardar expediente - OK")
            print("\n[SUCCESS] Adquisición completada.")
            log_timing(radicado_id, "adquisición completa")
            heartbeat(radicado_id, "ADQUISICION_COMPLETA", num_rows, len(downloaded_files))
        except Exception as e:
            print(f"[ERROR] Fallo en la adquisición: {e}")
            log_timing(radicado_id, f"ERROR: {e}")
            heartbeat(radicado_id, "ERROR")
            sys.exit(1)
        finally:
            print("[11] cerrar navegador - INICIO")
            browser.close()
            print("[11] cerrar navegador - OK")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--radicado", required=True)
    parser.add_argument("--funcionario", required=False)
    parser.add_argument("--usuario-funcionario", dest="usuario_funcionario", required=False)
    args = parser.parse_args()
    acquire_radicado(args.radicado, args.funcionario, args.usuario_funcionario)
