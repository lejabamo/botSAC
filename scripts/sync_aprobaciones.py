import os
import sys
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

def fix_encoding(text):
    if not isinstance(text, str): return text
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except:
        return datetime.min

def run_sync_aprobaciones():
    print(f"\n[{datetime.now().isoformat()}] INICIANDO EXTRACCIÓN DE CASOS POR APROBAR...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Headless=False para que el usuario pueda ver si lo desea
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        # LOGIN
        page.goto(SAC_URL, wait_until="domcontentloaded")
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        if page.locator('a#sub_form_b').is_visible():
            page.locator('a#sub_form_b').click()
        page.locator('input#id_sc_field_login').fill(SAC_USER)
        page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
        page.locator('input.btn-login[value="Ingresar"]').click()
        
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
        
        print("Buscando Dashboard principal y la sección Pendientes de Revisar - Aprobar...")
        
        # Encontrar el enlace de POR APROBAR en el dashboard
        dashboard_frame = None
        target_link = None
        
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    # Buscar el enlace o botón que dice "POR APROBAR" o "34 POR APROBAR"
                    locs = f.locator("text=/POR APROBAR/i").all()
                    for loc in locs:
                        if loc.is_visible():
                            # Revisar si es un enlace o tiene ancestro a
                            if loc.evaluate("el => el.tagName").upper() == "A" or loc.evaluate("el => el.getAttribute('onclick')"):
                                target_link = loc
                            elif loc.locator("xpath=ancestor::a").count() > 0:
                                target_link = loc.locator("xpath=ancestor::a").first
                            elif loc.locator("xpath=ancestor::tr").count() > 0:
                                target_link = loc.locator("xpath=ancestor::tr").first
                            else:
                                target_link = loc
                                
                            if target_link:
                                dashboard_frame = f
                                break
                except: pass
                if target_link: break
            if target_link: break
            page.wait_for_timeout(1000)
            
        if not target_link:
            print("[ERROR] No se encontró la opción 'POR APROBAR' en el dashboard.")
            browser.close()
            return
            
        print("[INFO] Enlace POR APROBAR encontrado. Haciendo click...")
        try:
            target_link.click(timeout=5000)
        except:
            target_link.evaluate("el => el.click()")
            
        print("Esperando la carga de la vista CONSULTA - POR APROBAR...")
        aprobaciones_frame = None
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    # Buscamos específicamente un frame que contenga la cabecera RADICADO
                    if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO'), td:has-text('Radicado')").count() > 0:
                        aprobaciones_frame = f
                        break
                except: pass
            if aprobaciones_frame: break
            page.wait_for_timeout(1000)
            
        if not aprobaciones_frame:
            print("[ERROR] No se pudo cargar la vista de CONSULTA - POR APROBAR.")
            browser.close()
            return
            
        print("[INFO] Vista CONSULTA - POR APROBAR cargada. Extrayendo radicados...")
        
        extracted_items = []
        
        # Mapeo de columnas
        v_rows = aprobaciones_frame.locator("tr").all()
        headers_texts = []
        col_indices = {}
        
        for r in v_rows:
            try:
                # Si la fila contiene una tabla anidada, es un wrapper y debemos omitirla
                if r.locator("table").count() > 0:
                    continue
                    
                th_cells = r.locator("xpath=./td | ./th").all()
                if len(th_cells) > 3:
                    texts = [th.inner_text().strip().upper() for th in th_cells]
                    # Solo consideramos que es el header si tiene RADICADO y ASUNTO
                    has_rad = any("RADICADO" in t for t in texts)
                    if has_rad:
                        headers_texts = texts
                        for i, h in enumerate(headers_texts):
                            if "RADICADO" in h: col_indices["radicado"] = i
                            elif "ASUNTO" in h: col_indices["asunto"] = i
                            elif "FECHA CREACIÓN" in h or "FECHA CREACION" in h: col_indices["fecha_creacion"] = i
                            elif "CIUDADANO" in h: col_indices["ciudadano"] = i
                            elif "TIPO DE REQUERIMIENTO" in h: col_indices["categoria"] = i
                            elif "FECHA VENCIMIENTO" in h: col_indices["fecha_vencimiento"] = i
                            elif "FUNCIONARIO ASIGNADO" in h: col_indices["funcionario"] = i
                            elif "DÍAS DE PLAZO" in h or "DIAS DE PLAZO" in h or "DÍAS" in h or "DIAS" in h: col_indices["dias_plazo"] = i
                            elif "RESPUESTA" in h: col_indices["respuesta_btn"] = i
                        break
            except: pass
                
        print(f"[INFO] Columnas identificadas: {col_indices}")
        
        row_elements = []
        for r in v_rows:
            try:
                # Omitir wrappers con tablas anidadas
                if r.locator("table").count() > 0:
                    continue
                    
                # Verificamos si la fila tiene datos en la columna de radicado
                cells = r.locator("xpath=./td").all()
                if len(cells) > col_indices.get("radicado", 0):
                    text = cells[col_indices["radicado"]].inner_text().strip()
                    if text and text != "RADICADO" and len(text) > 5:
                        row_elements.append(r)
            except: pass
            
        print(f"[INFO] Se encontraron {len(row_elements)} casos por aprobar en la página actual.")
        
        # Extraer data de la tabla principal
        for r in row_elements:
            cells = r.locator("xpath=./td").all()
            valid_cells = [c for c in cells if c.inner_text().strip() or c.inner_text() == ""]
            
            # Use max index to avoid index out of bounds
            max_idx = max(col_indices.values()) if col_indices else 0
            if len(cells) > max_idx:
                cell_texts = [c.inner_text().strip() for c in cells]
                
                rad_idx = col_indices.get("radicado", -1)
                rad_val = cell_texts[rad_idx] if rad_idx != -1 and rad_idx < len(cell_texts) else ""
                
                if not rad_val or rad_val.upper() == "RADICADO": continue
                
                asunto_idx = col_indices.get("asunto", -1)
                fecha_creacion_idx = col_indices.get("fecha_creacion", -1)
                ciudadano_idx = col_indices.get("ciudadano", -1)
                categoria_idx = col_indices.get("categoria", -1)
                fecha_venc_idx = col_indices.get("fecha_vencimiento", -1)
                funcionario_idx = col_indices.get("funcionario", -1)
                dias_plazo_idx = col_indices.get("dias_plazo", -1)
                
                # Buscar el botón de respuesta en la primera celda
                resp_btn_idx = col_indices.get("respuesta_btn", 0)
                links = cells[resp_btn_idx].locator("a, img, button").all()
                btn_href = None
                target_btn = None
                for l in links:
                    href = l.evaluate("el => el.getAttribute('href')") or l.evaluate("el => el.getAttribute('onclick')") or ""
                    if href:
                        btn_href = href
                        target_btn = l
                        break
                        
                extracted_items.append({
                    "radicado": fix_encoding(rad_val),
                    "asunto": fix_encoding(cell_texts[asunto_idx]) if asunto_idx != -1 else "",
                    "estado": "EN TRAMITE",
                    "plazo": "15 DÍAS HÁBILES",
                    "fecha_creacion": fix_encoding(cell_texts[fecha_creacion_idx]) if fecha_creacion_idx != -1 else "",
                    "remitente": fix_encoding(cell_texts[ciudadano_idx]) if ciudadano_idx != -1 else "",
                    "categoria": fix_encoding(cell_texts[categoria_idx]) if categoria_idx != -1 else "Trámite",
                    "fecha_vencimiento": fix_encoding(cell_texts[fecha_venc_idx]) if fecha_venc_idx != -1 else "",
                    "funcionario": fix_encoding(cell_texts[funcionario_idx]) if funcionario_idx != -1 else "",
                    "usuario_funcionario": fix_encoding(cell_texts[funcionario_idx]) if funcionario_idx != -1 else "",
                    "dias_plazo": fix_encoding(cell_texts[dias_plazo_idx]) if dias_plazo_idx != -1 else "",
                    "etapa_tramite": "EN_PROCESO",
                    "etapa_label": "BotSAC extrayendo respuesta ⏳",
                    "target_btn": target_btn,
                    "btn_href": btn_href,
                    "respuesta_actual": "Extrayendo..."
                })

        # Save initial 'EN_PROCESO' state to dashboard_inbox.json
        inbox_path = "data/dashboard_inbox.json"
        existing_data = []
        if os.path.exists(inbox_path):
            with open(inbox_path, "r", encoding="utf-8") as f:
                try: existing_data = json.load(f)
                except: pass
                
        new_radicados_set = {item["radicado"] for item in extracted_items}
        final_data = [d for d in existing_data if d.get("radicado") not in new_radicados_set]
        
        # Serialize without playwright elements
        safe_items = []
        for it in extracted_items:
            safe_it = dict(it)
            safe_it.pop("target_btn", None)
            safe_it.pop("btn_href", None)
            safe_items.append(safe_it)
            
        with open(inbox_path, "w", encoding="utf-8") as f:
            json.dump(safe_items + final_data, f, indent=4, ensure_ascii=False)
            
        print("[INFO] Casos guardados como EN_PROCESO. Iniciando extracción detallada...")

        # Ahora navegamos en cada radicado para extraer el texto de la respuesta
        for i, item in enumerate(extracted_items):
            print(f"\n[{i+1}/{len(extracted_items)}] Extrayendo respuesta para radicado {item['radicado']}...")
            
            if not aprobaciones_frame:
                print(f"[WARN] No se encontró el frame para abrir {item['radicado']}")
                item["respuesta_actual"] = "Error: Tabla no disponible."
                continue
                
            try:
                # Buscar dinámicamente la fila del radicado en la tabla actual
                row_loc = aprobaciones_frame.locator(f"tr:has(td:has-text('{item['radicado']}'))").first
                btn_loc = row_loc.locator("a, img, button").first
                btn_loc.click(timeout=5000)
            except:
                try:
                    btn_loc.evaluate("el => el.click()")
                except:
                    print(f"[WARN] No se pudo hacer clic en el radicado {item['radicado']}")
                    item["respuesta_actual"] = "Error: No se pudo abrir."
                    continue
                
            detalle_frame = None
            timeout_end = time.time() + 20
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        # Ensure we are in the detail view and NOT the dashboard list
                        is_detail_view = f.locator("span[id^='id_read_on_']").count() > 0 or f.locator("td.scFormLabelOdd").count() > 5
                        if is_detail_view:
                            text = f.locator("body").inner_text(timeout=200).upper()
                            if item["radicado"] in text:
                                detalle_frame = f
                                break
                    except: pass
                if detalle_frame: break
                page.wait_for_timeout(1000)
                
            if not detalle_frame:
                print(f"[ERROR] No cargó el detalle para {item['radicado']}")
                item["respuesta_actual"] = "Error: No cargó el detalle de respuesta."
                # Volver intentando recargar la página o volver a la tabla si es posible
                continue
                
            # Extraer la respuesta
            respuesta_text = ""
            # Buscar en id_read_on_respuesta
            for possible_id in ["respuesta", "respuesta_funcionario", "respuesta_dependencia", "observacion", "observaciones", "comentario", "comentarios", "texto_respuesta"]:
                span = detalle_frame.locator(f"span#id_read_on_{possible_id}")
                if span.count() > 0:
                    respuesta_text = span.first.inner_text().strip()
                    if respuesta_text: break
                    
            if not respuesta_text:
                # Buscar en la tabla donde el label sea RESPUESTA
                labels = detalle_frame.locator("td.scFormLabelOdd").all()
                for lbl in labels:
                    try:
                        lbl_text = lbl.inner_text().strip().upper()
                        if "RESPUESTA" in lbl_text or "OBSERVACI" in lbl_text:
                            next_td = lbl.locator("xpath=following-sibling::td").first
                            if next_td.count() > 0:
                                val_span = next_td.locator("span[id^='id_read_on_']").first
                                if val_span.count() > 0:
                                    respuesta_text = val_span.inner_text().strip()
                                    if respuesta_text: break
                    except: pass
                    
            if not respuesta_text:
                # Fallback: Extraer todo el contenido y buscar el cuerpo del correo/oficio
                try:
                    respuesta_text = detalle_frame.locator("body").inner_text()
                    if len(respuesta_text) > 2000 and "CONSULTA" in respuesta_text:
                        respuesta_text = "Se extrajo un texto demasiado grande, probablemente hubo un error de navegación."
                except: pass
                
            if len(respuesta_text) > 5000:
                respuesta_text = respuesta_text[:5000] + "... (Truncado)"

            print(f"[SUCCESS] Respuesta extraída ({len(respuesta_text)} caracteres).")
            item["respuesta_actual"] = fix_encoding(respuesta_text)
            
            # Clicar en VOLVER para regresar a la lista
            try:
                volver_btn = detalle_frame.locator("text=/Volver/i, text=/VOLVER/i").locator("xpath=ancestor-or-self::a | ancestor-or-self::button | ancestor-or-self::td")
                if volver_btn.count() > 0:
                    volver_btn.first.click(timeout=5000)
                else:
                    page.go_back(wait_until="domcontentloaded", timeout=10000)
            except:
                try: page.go_back(wait_until="domcontentloaded", timeout=10000)
                except: pass
                
            # Esperar a que la tabla vuelva a cargar y reubicar el frame
            page.wait_for_timeout(3000)
            aprobaciones_frame = None
            timeout_end_frame = time.time() + 15
            while time.time() < timeout_end_frame:
                for f in page.frames:
                    try:
                        if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO'), td:has-text('Radicado')").count() > 0:
                            aprobaciones_frame = f
                            break
                    except: pass
                if aprobaciones_frame: break
                page.wait_for_timeout(1000)
                
            if not aprobaciones_frame:
                # Recuperación garantizada: Recargar todo el SAC_URL y volver al dashboard
                print("[WARN] No se pudo reubicar el frame. Recargando el dashboard completamente...")
                try:
                    page.goto(SAC_URL, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    
                    # Si vemos el formulario de login, iniciamos sesión nuevamente
                    if page.locator('input#id_sc_field_login').count() > 0:
                        print("[INFO] Re-iniciando sesión para continuar...")
                        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
                        if page.locator('a#sub_form_b').is_visible():
                            page.locator('a#sub_form_b').click()
                        page.locator('input#id_sc_field_login').fill(SAC_USER)
                        page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
                        page.locator('input.btn-login[value="Ingresar"]').click()
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
                        page.wait_for_timeout(5000)
                    
                    target_link = None
                    for f in page.frames:
                        locs = f.locator("text=/POR APROBAR/i").all()
                        for loc in locs:
                            if loc.is_visible():
                                if loc.evaluate("el => el.tagName").upper() == "A" or loc.evaluate("el => el.getAttribute('onclick')"):
                                    target_link = loc
                                elif loc.locator("xpath=ancestor::a").count() > 0:
                                    target_link = loc.locator("xpath=ancestor::a").first
                                elif loc.locator("xpath=ancestor::tr").count() > 0:
                                    target_link = loc.locator("xpath=ancestor::tr").first
                                else:
                                    target_link = loc
                                if target_link: break
                        if target_link: break
                        
                    if target_link:
                        try: target_link.click(timeout=5000)
                        except: target_link.evaluate("el => el.click()")
                        
                        # Esperar a que cargue el frame de nuevo
                        timeout_recovery = time.time() + 15
                        while time.time() < timeout_recovery:
                            for f in page.frames:
                                try:
                                    if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO'), td:has-text('Radicado')").count() > 0:
                                        aprobaciones_frame = f
                                        break
                                except: pass
                            if aprobaciones_frame: break
                            page.wait_for_timeout(1000)
                except: pass
            
            # Remove Playwright Elements before saving to JSON
            safe_item = dict(item)
            safe_item.pop("target_btn", None)
            safe_item.pop("btn_href", None)
            
            safe_item["etapa_tramite"] = "FALTA_APROBACION"
            safe_item["etapa_label"] = "Contestado (Falta Aprobación)"
            
            # Update the item in the local JSON
            if os.path.exists(inbox_path):
                with open(inbox_path, "r", encoding="utf-8") as f:
                    try: current_data = json.load(f)
                    except: current_data = []
                    
                for idx_d, d in enumerate(current_data):
                    if d.get("radicado") == safe_item["radicado"]:
                        current_data[idx_d] = safe_item
                        break
                        
                with open(inbox_path, "w", encoding="utf-8") as f:
                    json.dump(current_data, f, indent=4, ensure_ascii=False)

        browser.close()
        
    print(f"\n[INFO] Se extrajeron {len(extracted_items)} casos exitosamente.")
    print("[SUCCESS] Extracción y actualización finalizada correctamente.")

if __name__ == "__main__":
    run_sync_aprobaciones()
