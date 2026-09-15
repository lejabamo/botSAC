import os
import time
import json
import pytest
from datetime import datetime
from playwright.sync_api import Page
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

def test_08_sac_primer_funcionario_vencidos(page: Page):
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales"
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 8: PRIMER FUNCIONARIO CON VENCIDOS...")
    
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
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    text = f.locator("body").inner_text().upper()
                    url = f.url.lower()
                    if "VENCIDOS" in text or "VENCIDO" in url or "RADICADO" in text or "BUSQUEDA" in url:
                        if f.locator("tr").count() > 5:
                            vencidos_frame = f
                            break
                except: pass
            if vencidos_frame:
                break
            page.wait_for_timeout(1000)
            
        assert vencidos_frame is not None, "No se detectó la transición a la vista de radicados/Vencidos."
        print(f"\n[VERIFIED] Destino de Vencidos alcanzado en frame: {vencidos_frame.name} (URL: {vencidos_frame.url})")
        
        user_open_record = {
            "dependency": "Infraestructura Educativa",
            "user": {
                "name": target_name,
                "username": target_name,
                "overdue_count": target_vencidos_count,
                "source_frame": funcionarios_frame.name,
                "source_url": funcionarios_frame.url
            },
            "navigation": {
                "action": action_method,
                "target_frame": vencidos_frame.name,
                "target_url": vencidos_frame.url,
                "target_section": "Vencidos"
            }
        }
        print("\n[FUNCTIONAL_USER_OPEN]", json.dumps(user_open_record, indent=2))
        
        os.makedirs("data/logs", exist_ok=True)
        page.screenshot(path="data/logs/test_08_success.png")
        
        with open("data/logs/test_08_target_user.json", "w", encoding="utf-8") as f:
            json.dump(user_open_record, f, indent=4, ensure_ascii=False)
            
        new_map_entry = {
            "from": target_module_funcionarios,
            "action": f"Funcionario: {target_name} (Vencidos: {target_vencidos_count})",
            "to": "Vencidos_Grid",
            "visible_title": "Vencidos / Radicados"
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
            
        print("\n[REPORT] TEST 8: PASS")
        
    except Exception as e:
        os.makedirs(os.path.join("data", "logs"), exist_ok=True)
        page.screenshot(path=os.path.join("data", "logs", "test_08_navigation_error.png"))
        
        # Dump HTML/TEXT for debugging
        html_dump = ""
        text_dump = ""
        for idx, f in enumerate(page.frames):
            try:
                html_dump += f"\n<!-- FRAME {idx} ({f.name} - {f.url}) -->\n"
                html_dump += f.content()
                text_dump += f"\n--- FRAME {idx} ({f.name}) ---\n"
                text_dump += f.locator("body").inner_text()
            except: pass
            
        with open(os.path.join("data", "logs", "test_07_nav_fail_html.txt"), "w", encoding="utf-8") as dump_file:
            dump_file.write(html_dump)
        with open(os.path.join("data", "logs", "test_07_nav_fail_text.txt"), "w", encoding="utf-8") as dump_file:
            dump_file.write(text_dump)
            
        navigation_map["steps"].append({"status": "error", "message": str(e)})
        with open(os.path.join("data", "logs", "test_07_navigation_map_error.json"), "w", encoding="utf-8") as f:
            json.dump(navigation_map, f, indent=4)
            
        print(f"\n[ERROR] TEST 7: FAIL -> {e}")
        raise
