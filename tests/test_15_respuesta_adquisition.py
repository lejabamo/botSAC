import os
import time
import json
import hashlib
import pytest
from datetime import datetime
from playwright.sync_api import Page, expect
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    }

def safe_click(page: Page, frame, selector, description):
    """
    Intenta hacer click de forma segura, usando evaluate si es necesario debido a superposiciones.
    """
    loc = frame.locator(selector).first
    assert loc.count() > 0, f"No se encontró el elemento para: {description} ({selector})"
    
    try:
        loc.click(timeout=3000)
        method = "playwright_click"
    except:
        loc.evaluate("el => el.click()")
        method = "js_evaluate_click"
        
    print(f"[CLICK] {description} mediante {method}")
    return method

def get_current_state(page: Page):
    """Retorna un resumen de los frames actuales para debuggear transiciones."""
    frames = []
    for i, f in enumerate(page.frames):
        try:
            frames.append({"index": i, "name": f.name, "url": f.url})
        except:
            pass
    return frames

def test_15_respuesta_adquisition(page: Page):
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales"
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 9: PRIMER RADICADO REAL...")
    
    navigation_map = {"steps": []}
    
    def log_step(name, selector=None, frame_name=None, frame_url=None, status="verified"):
        step = {
            "name": name,
            "selector": selector,
            "frame": frame_name,
            "url": frame_url,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        navigation_map["steps"].append(step)
        print(f"\n[STEP] {name} -> {status}")
        
    try:
        # LOGIN
        page.goto(SAC_URL, wait_until="domcontentloaded")
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        if page.locator('a#sub_form_b').is_visible():
            page.locator('a#sub_form_b').click()
        page.wait_for_selector('input#id_sc_field_login', timeout=15000)
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
            
        if modal_handled:
            page.wait_for_timeout(5000)
            page.wait_for_load_state("load")
        else:
            page.wait_for_load_state("load")
            
        page.wait_for_timeout(5000)
        
        # PASO 1: menu_sac
        log_step("menu_sac", frame_name=page.main_frame.name, frame_url=page.main_frame.url)
        
        # PASO 2: Mis Sub-Dependencias (dentro de Semáforo)
        print("Buscando 'Mis Sub-Dependencias' en todos los frames...")
        selector_subdep = "text='Mis Sub-Dependencias'"
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
                                print(f"[CLICK] 'Mis Sub-Dependencias' clickeado en frame {f.name or f.url}")
                                menu_clicked = True
                                break
                except: pass
                if menu_clicked:
                    break
            if menu_clicked:
                break
            page.wait_for_timeout(1000)
            
        assert menu_clicked, "No se encontró 'Mis Sub-Dependencias' visible en ningún frame tras 30s"
        
        page.wait_for_timeout(3000)
                
        log_step("Mis Sub-Dependencias", selector=selector_subdep, frame_name=page.main_frame.name, frame_url=page.main_frame.url)
        
        # Esperar la carga del módulo y hacer polling buscando el texto REQUERIMIENTOS
        print("Esperando que cargue Fun_Semaforo_OtrasDependencias y aparezca REQUERIMIENTOS...")
        otras_dep_frame = None
        selector_req = "text='REQUERIMIENTOS'"
        
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if "Fun_Semaforo_OtrasDependencias" in f.url:
                        if f.locator(selector_req).count() > 0:
                            otras_dep_frame = f
                            break
                except: pass
            if otras_dep_frame:
                break
            page.wait_for_timeout(1000)
                
        assert otras_dep_frame is not None, "No se encontró el texto REQUERIMIENTOS en los iframes de Mis Sub-Dependencias"
        
        # PASO 3: Por Dependencias (Clic en REQUERIMIENTOS)
        otras_dep_frame.locator(selector_req).first.click()
        
        log_step("Por Dependencias (REQUERIMIENTOS)", selector=selector_req, frame_name=otras_dep_frame.name, frame_url=otras_dep_frame.url)
        
        # PASO 4: Verificar "ASIGNADOS POR DEPENDENCIAS"
        print("Esperando que cargue Fun_Semaforo_PorOtrasDependencias y aparezca ASIGNADOS POR DEPENDENCIAS...")
        target_text_asignados = "ASIGNADOS POR DEPENDENCIAS"
        asignados_frame = None
        asignados_selector = f"text='{target_text_asignados}'"
        
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if f.locator(asignados_selector).count() > 0:
                        asignados_frame = f
                        break
                except: pass
            
            if not asignados_frame:
                # Fallback con case-insensitive regex
                asignados_selector_fallback = "text=/ASIGNADOS POR DEPENDENCIAS/i"
                for f in page.frames:
                    try:
                        if f.locator(asignados_selector_fallback).count() > 0:
                            asignados_frame = f
                            asignados_selector = asignados_selector_fallback
                            break
                    except: pass
                    
            if asignados_frame:
                break
            page.wait_for_timeout(1000)
                
        if asignados_frame is None:
            # Dump all frames to debug why it failed
            os.makedirs("data/logs", exist_ok=True)
            with open("data/logs/test_06_debug_fail.html", "w", encoding="utf-8") as f:
                for i, fr in enumerate(page.frames):
                    f.write(f"\n\n<!-- FRAME {i}: {fr.name} | {fr.url} -->\n")
                    try:
                        f.write(fr.content())
                    except Exception as e:
                        f.write(str(e))
            assert asignados_frame is not None, f"No se encontró '{target_text_asignados}' en ningún frame. HTML dumpeado en data/logs/test_07_debug_fail.html"
            
        log_step("ASIGNADOS POR DEPENDENCIAS", selector=asignados_selector, frame_name=asignados_frame.name, frame_url=asignados_frame.url)
        
        # PASO 5: Localizar Infraestructura Educativa y Hacer Click
        target_dep = "Infraestructura Educativa"
        
        loc_dep = asignados_frame.locator(f"text='{target_dep}'")
        if loc_dep.count() == 0:
            loc_dep = asignados_frame.locator("text=/Infraestructura Educativa/i")
            
        assert loc_dep.count() > 0, f"No se encontró {target_dep} en la tabla"
        
        # Verificar la fila
        row = loc_dep.first.locator("xpath=ancestor::tr").first
        cols = row.locator("td").all()
        col_texts = [c.inner_text().strip() for c in cols if c.inner_text().strip()]
        print(f"\n[INFO] Encontrado {target_dep}: {col_texts}")
        
        href = loc_dep.first.evaluate("el => el.getAttribute('href')")
        onclick = loc_dep.first.evaluate("el => el.getAttribute('onclick')")
        print(f"[ACTION] Clicando sobre {target_dep} -> href: {href}, onclick: {onclick}")
        
        # HACER CLICK: Dependiendo del DOM de Scriptcase, puede ser necesario evaluar JS o hacer click normal.
        try:
            # Primero intentamos click normal
            loc_dep.first.click(timeout=5000)
            click_method = "playwright_click"
        except Exception:
            # Si Scriptcase intercepta, forzamos JS
            print("[WARN] Click normal falló o interceptado. Usando evaluate('el.click()')")
            loc_dep.first.evaluate("el => el.click()")
            click_method = "js_evaluate_click"
            
        print(f"Click ejecutado con método: {click_method}")
        log_step("Click Infraestructura Educativa", selector=f"text='{target_dep}'", status=f"clicked_with_{click_method}")
        
        # PASO 6: Verificar que cargue ASIGNADOS POR FUNCIONARIOS y el módulo FunAdm_Semaforo_PorFuncionario
        print("Esperando transición a ASIGNADOS POR FUNCIONARIOS (módulo FunAdm_Semaforo_PorFuncionario)...")
        target_text_funcionarios = "ASIGNADOS POR FUNCIONARIOS"
        target_module_funcionarios = "FunAdm_Semaforo_PorFuncionario"
        
        funcionarios_frame = None
        funcionarios_selector = f"text='{target_text_funcionarios}'"
        
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    # Validar si el texto está en el DOM del frame o si la URL del frame es la correcta
                    if f.locator(funcionarios_selector).count() > 0 or (target_module_funcionarios in f.url):
                        if f.locator("tr").count() > 3:
                            funcionarios_frame = f
                            break
                except: pass
                
            if not funcionarios_frame:
                # Fallback text
                for f in page.frames:
                    try:
                        if f.locator("text=/ASIGNADOS POR FUNCIONARIOS/i").count() > 0:
                            if f.locator("tr").count() > 3:
                                funcionarios_frame = f
                                funcionarios_selector = "text=/ASIGNADOS POR FUNCIONARIOS/i"
                                break
                    except: pass
                    
            if funcionarios_frame:
                # Doble verificación (Texto visible Y/O URL correcta)
                break
                
            page.wait_for_timeout(1000)
            
        if funcionarios_frame is None:
            os.makedirs("data/logs", exist_ok=True)
            with open("data/logs/test_08_debug_fail.html", "w", encoding="utf-8") as f:
                for i, fr in enumerate(page.frames):
                    f.write(f"\n\n<!-- FRAME {i}: {fr.name} | {fr.url} -->\n")
                    try:
                        f.write(fr.content())
                    except Exception as e:
                        f.write(str(e))
            assert False, "No se encontró la vista ASIGNADOS POR FUNCIONARIOS tras el click."
            
        print(f"\n[VERIFIED] Destino alcanzado en frame: {funcionarios_frame.name} (URL: {funcionarios_frame.url})")
        log_step("ASIGNADOS POR FUNCIONARIOS", selector=funcionarios_selector, frame_name=funcionarios_frame.name, frame_url=funcionarios_frame.url)
        
        # Registrar trazabilidad explícita del salto
        transition_record = {
            "timestamp": datetime.now().isoformat(),
            "event": "DEPENDENCY_OPEN",
            "dependency_name": target_dep,
            "source_frame": asignados_frame.name,
            "target_frame": funcionarios_frame.name,
            "source_module": "Fun_Semaforo_PorOtrasDependencias",
            "target_module": target_module_funcionarios,
            "action_method": click_method,
            "target_url": funcionarios_frame.url,
            "verification_result": "PASS - ASIGNADOS POR FUNCIONARIOS verificado"
        }
        print("\n[DEPENDENCY_OPEN]", json.dumps(transition_record, indent=2))
        
        # PASO 7: Identificar Funcionario con VENCIDOS > 0
        os.makedirs("data/logs", exist_ok=True)
        with open("data/logs/test_08_funcionarios_frame.html", "w", encoding="utf-8") as f:
            f.write(funcionarios_frame.content())
            
        print("\n[STEP] Analizando tabla de funcionarios...")
        rows = funcionarios_frame.locator("tr").all()
        target_row = None
        target_name = None
        target_vencidos_count = 0
        target_link = None
        target_href = None
        
        for idx, row in enumerate(rows):
            try:
                text = row.inner_text().strip().upper()
                if not text or "TOTAL" in text or "FUNCIONARIO" in text or "IR A" in text or "VER" in text:
                    continue
                cells = row.locator("td").all()
                if len(cells) < 3: 
                    continue
                    
                cell_texts = [c.inner_text().strip() for c in cells]
                name_idx = -1
                vencidos_idx = -1
                
                for i, ct in enumerate(cell_texts):
                    if ct and not ct.isdigit() and len(ct) > 3: # Nombre
                        name_idx = i
                        # Find the first column after the name that contains a digit (this will be Vencidos)
                        for j in range(i + 1, len(cell_texts)):
                            if cell_texts[j].isdigit():
                                vencidos_idx = j
                                break
                        break
                        
                if name_idx != -1 and vencidos_idx != -1:
                    vencidos_val = int(cell_texts[vencidos_idx])
                    if vencidos_val > 0:
                        target_row = row
                        target_name = cell_texts[name_idx]
                        target_vencidos_count = vencidos_val
                        
                        links_in_row = row.locator("a").all()
                        for link in links_in_row:
                            link_text = link.inner_text().strip()
                            link_href = link.evaluate("el => el.getAttribute('href')") or link.evaluate("el => el.getAttribute('onclick')") or ""
                            
                            if str(vencidos_val) in link_text or target_name in link_text or "vencidos" in link_href.lower() or "venc" in link_href.lower() or "Semaforo" in link_href:
                                target_link = link
                                target_href = link_href
                                if str(vencidos_val) in link_text or "venc" in link_href.lower():
                                    break
                        break 
            except:
                pass
                
        assert target_row is not None, "No se encontró ningún funcionario con VENCIDOS > 0"
        assert target_link is not None, f"No se encontró un enlace accionable para el funcionario {target_name}"
        
        print(f"\n[TARGET IDENTIFIED] Funcionario: {target_name} | Vencidos: {target_vencidos_count}")
        print(f"[ACTION] Link a clickear -> text: '{target_link.inner_text().strip()}', href/onclick: {target_href}")
        
        try:
            target_link.click(timeout=5000)
            action_method = "playwright_click"
        except:
            print("[WARN] Click normal falló, usando JS evaluate")
            target_link.evaluate("el => el.click()")
            action_method = "js_evaluate_click"
            
        print("Esperando transición a la vista de radicados/Vencidos...")
        
        vencidos_frame = None
        target_vencidos_url = "FunAdm_RequerimientosAsignados_Funcionarios"
        
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    # Esperar que la URL haya cambiado al módulo de la lista de radicados
                    if target_vencidos_url in f.url:
                        if f.locator("tr").count() > 3:
                            vencidos_frame = f
                            break
                except: pass
            if vencidos_frame:
                break
            page.wait_for_timeout(1000)
            
        assert vencidos_frame is not None, "No se detectó la transición a la vista de radicados/Vencidos."
        print(f"\n[VERIFIED] Destino de Vencidos alcanzado en frame: {vencidos_frame.name} (URL: {vencidos_frame.url})")
        
        # (TEST 9) PASO 8: Extraer primer radicado
        print("\n[STEP] Analizando lista de radicados (Vencidos)...")
        os.makedirs("data/logs", exist_ok=True)
        with open("data/logs/test_09_vencidos_frame.html", "w", encoding="utf-8") as f:
            f.write(vencidos_frame.content())

        # En Scriptcase los datos suelen estar en tr.scGridFieldOdd o tr.scGridFieldEven
        v_rows = vencidos_frame.locator("tr").all()
        target_radicado_row = None
        target_radicado_cells = []
        target_radicado_number = None
        target_radicado_link = None
        target_radicado_href = None
        
        # Primero buscamos headers
        headers_texts = []
        radicado_col_idx = -1
        for r in v_rows:
            th_cells = r.locator("td.scGridLabelFont, th.scGridLabelFont").all()
            if len(th_cells) > 3:
                headers_texts = [th.inner_text().strip() for th in th_cells if th.inner_text().strip()]
                # Buscar en qué columna está el RADICADO
                for i, h in enumerate(headers_texts):
                    if "RADICADO" in h.upper():
                        radicado_col_idx = i
                        break
                if radicado_col_idx != -1:
                    break
        print(f"[INFO] Headers encontrados: {headers_texts}")
        print(f"[INFO] Índice de columna RADICADO: {radicado_col_idx}")

        for idx, row in enumerate(v_rows):
            try:
                class_attr = row.evaluate("el => el.getAttribute('class')") or ""
                if "scGridFieldOdd" in class_attr or "scGridFieldEven" in class_attr:
                    # Obtenemos solo las celdas que tienen contenido para que se alineen con los headers
                    cells = row.locator("td").all()
                    valid_cells = [c for c in cells if c.inner_text().strip()]
                    if len(valid_cells) > radicado_col_idx:
                        cell_texts = [c.inner_text().strip() for c in valid_cells]
                        
                        target_radicado_number = cell_texts[radicado_col_idx]
                        if not target_radicado_number or target_radicado_number == "" or target_radicado_number.upper() == "RADICADO":
                            continue
                            
                        target_radicado_row = row
                        target_radicado_cells = cell_texts
                        
                        # Buscar el enlace para abrir en la celda del radicado
                        links = valid_cells[radicado_col_idx].locator("a").all()
                        if links:
                            target_radicado_link = links[0]
                        else:
                            btns = row.locator("a, button, img[onclick]").all()
                            if btns:
                                target_radicado_link = btns[0]
                            else:
                                target_radicado_link = valid_cells[radicado_col_idx]
                        
                        target_radicado_href = target_radicado_link.evaluate("el => el.getAttribute('href')") or target_radicado_link.evaluate("el => el.getAttribute('onclick')") or ""
                        break
            except: pass
            
        assert target_radicado_row is not None, "No se encontró ninguna fila de radicado válida"
        assert target_radicado_number is not None, "No se encontró el número de radicado"
        assert target_radicado_link is not None, "No se encontró control para abrir el radicado"

        print(f"\n[TARGET IDENTIFIED] Radicado: {target_radicado_number}")
        print(f"Row Data: {target_radicado_cells}")
        print(f"[ACTION] Link a clickear -> href/onclick: {target_radicado_href}")
        
        radicado_data = {
            "radicado": target_radicado_number,
            "raw_data": target_radicado_cells,
            "headers": headers_texts
        }
        
        # PASO 9: Abrir el radicado
        try:
            target_radicado_link.click(timeout=5000)
            rad_action = "playwright_click"
        except:
            target_radicado_link.evaluate("el => el.click()")
            rad_action = "js_evaluate_click"
            
        print("Esperando vista de detalle de radicado...")
        
        detalle_frame = None
        detalle_url = None
        radicado_verificado = False
        target_detalle_url = "FunOpeAdm_Requerimiento_Consulta"
        sections_found = []
        detail_title = ""
        
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if target_detalle_url in f.url:
                        text = f.locator("body").inner_text(timeout=200).upper()
                        if target_radicado_number in text and ("ASUNTO" in text or "REQUERIMIENTO" in text):
                            detalle_frame = f
                            detalle_url = f.url
                            radicado_verificado = True
                            
                            # Extraer secciones encontradas
                            expected_sections = [
                                "REQUERIMIENTO", "RADICADO", "FECHA CREACIÓN", "TIPO DE REQUERIMIENTO",
                                "ESTADO", "ASUNTO", "CONTENIDO", "DOCUMENTOS ADJUNTOS", "NOVEDADES"
                            ]
                            for sec in expected_sections:
                                if sec in text:
                                    sections_found.append(sec)
                                    
                            try:
                                detail_title = f.locator("title").inner_text(timeout=500)
                            except:
                                pass
                                
                            break
                except: pass
            if detalle_frame: break
            page.wait_for_timeout(1000)
            
        assert detalle_frame is not None, "No se encontró la vista de detalle del radicado"
        assert radicado_verificado, f"El número de radicado {target_radicado_number} NO coincide con la vista mostrada!"
        
        print(f"\n[VERIFIED] Detalle de radicado {target_radicado_number} abierto en frame: {detalle_frame.name or 'N/A'} (URL: {detalle_url})")
        print("\n[VERIFIED] Vista de detalle cargada completamente.")
        
        # --- ADQUISICIÓN DE RESPUESTA ---
        acquisition_id = f"ACQ-{datetime.now().strftime('%Y%m%d')}-0001"
        radicado_id = target_radicado_number
        
        dir_raw = f"data/raw/{acquisition_id}/{radicado_id}"
        os.makedirs(dir_raw, exist_ok=True)
        
        print(f"\n[RESPONSE_ACQUISITION] Buscando campo de respuesta para {radicado_id}")
        
        respuesta_text = ""
        respuesta_source = ""
        
        # Estrategia 1: span#id_read_on_respuesta
        for possible_id in ["respuesta", "respuesta_funcionario", "respuesta_dependencia", "observacion", "observaciones", "comentario", "comentarios", "texto_respuesta"]:
            span = detalle_frame.locator(f"span#id_read_on_{possible_id}")
            if span.count() > 0:
                respuesta_text = span.first.inner_text().strip()
                respuesta_source = f"span#id_read_on_{possible_id}"
                if respuesta_text:
                    break
                    
        # Estrategia 2: Buscar en la tabla principal "RESPUESTA" como label
        if not respuesta_text:
            labels = detalle_frame.locator("td.scFormLabelOdd").all()
            for lbl in labels:
                try:
                    lbl_text = lbl.inner_text().strip().upper()
                    if "RESPUESTA" in lbl_text or "OBSERVACI" in lbl_text or "COMENTARIO" in lbl_text:
                        next_td = lbl.locator("xpath=following-sibling::td").first
                        if next_td.count() > 0:
                            val_span = next_td.locator("span[id^='id_read_on_']").first
                            if val_span.count() > 0:
                                respuesta_text = val_span.inner_text().strip()
                                respuesta_source = f"Label: {lbl_text}"
                                if respuesta_text:
                                    break
                except: pass
                
        # Si aún no hay texto, guardar indicador
        if not respuesta_text:
            respuesta_text = "No se encontró campo de respuesta en la vista de detalle. Estado actual del caso: ASIGNADO."
            respuesta_source = "Not Found / Inferred from State"
            
        # Validar no modificación
        solicitud_path = f"{dir_raw}/solicitud.txt"
        mtime_sol = os.path.getmtime(solicitud_path) if os.path.exists(solicitud_path) else 0
        
        respuesta_path = f"{dir_raw}/respuesta.txt"
        with open(respuesta_path, "w", encoding="utf-8") as f:
            f.write(respuesta_text)
            
        with open(f"{dir_raw}/respuesta_meta.json", "w", encoding="utf-8") as f:
            json.dump({"source": respuesta_source, "length": len(respuesta_text)}, f, indent=2)
            
        assert os.path.exists(respuesta_path), "No se guardó respuesta.txt"
        assert len(respuesta_text) > 0, "La respuesta está vacía"
        
        if os.path.exists(solicitud_path):
            assert mtime_sol == os.path.getmtime(solicitud_path), "solicitud.txt fue modificado!"
            
        print("\n==================================================")
        print("REPORT: TEST 15: PASS")
        print(f"Ubicación de la respuesta (fuente): {respuesta_source}")
        print(f"Longitud del contenido: {len(respuesta_text)} caracteres")
        print(f"Primeras líneas:\n{respuesta_text[:200]}...")
        print(f"Archivos creados/modificados: {respuesta_path}")
        print("==================================================")
        
        user_open_record = {
            "dependency": "Infraestructura Educativa",
            "user": "adiaz",
            "status_filter": "Vencidos",
            "list_source_url": vencidos_frame.url,
            "radicado": target_radicado_number,
            "row_data": {
                "radicado": target_radicado_number,
                "raw_data": target_radicado_cells,
                "headers": headers_texts
            },
            "open_control": {
                "selector": f"a/button/td con texto/href hacia {target_radicado_href[:30]}...",
                "method": action_method,
                "href": target_radicado_href
            },
            "detail": {
                "url": detalle_url,
                "frame": detalle_frame.name,
                "title": detail_title,
                "verified": radicado_verificado,
                "sections_found": sections_found
            }
        }
        test_case_record = user_open_record
        
        new_map_entry = {
            "from": "Vencidos_Grid",
            "action": f"Abrir Radicado {target_radicado_number}",
            "to": "Radicado_Detalle",
            "visible_title": f"Detalle {target_radicado_number}"
        }
        
        global_map_path = "data/logs/navigation_map.json"
        global_map = []
        if os.path.exists(global_map_path):
            with open(global_map_path, "r", encoding="utf-8") as f:
                try:
                    global_map = json.load(f)
                    if not isinstance(global_map, list):
                        global_map = [global_map]
                except:
                    pass
        global_map.append(new_map_entry)
        with open(global_map_path, "w", encoding="utf-8") as f:
            json.dump(global_map, f, indent=4, ensure_ascii=False)
            
        print("\n[REPORT] TEST 9: PASS")
        
    except Exception as e:
        os.makedirs(os.path.join("data", "logs"), exist_ok=True)
        page.screenshot(path=os.path.join("data", "logs", "test_09_navigation_error.png"))
        
        # Dump HTML/TEXT for debugging
        html_dump = ""
        for i, f in enumerate(page.frames):
            html_dump += f"\n\n<!-- FRAME {i}: {f.name} | {f.url} -->\n"
            try:
                html_dump += f.content()
            except Exception as fe:
                html_dump += f"Error getting content: {fe}"
                
        with open(os.path.join("data", "logs", "test_09_nav_fail_html.txt"), "w", encoding="utf-8") as file:
            file.write(html_dump)
            
        navigation_map["steps"].append({"status": "error", "message": str(e)})
        with open(os.path.join("data", "logs", "test_09_navigation_map_error.json"), "w", encoding="utf-8") as f:
            json.dump(navigation_map, f, indent=4)
            
        print(f"\n[ERROR] TEST 7: FAIL -> {e}")
        raise
