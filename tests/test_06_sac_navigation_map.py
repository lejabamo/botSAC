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

def test_06_sac_navigation_map(page: Page):
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales"
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 6: MAPA DE NAVEGACIÓN...")
    
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
        # El módulo Semáforo carga por defecto, y "Mis Sub-Dependencias" es una de las opciones del menú izquierdo.
        selector_subdep = "text='Mis Sub-Dependencias'"
        page.wait_for_selector(selector_subdep, timeout=10000)
        
        # Hacemos click en el que carga "Fun_Semaforo_OtrasDependencias"
        loc_subdep = page.locator(selector_subdep)
        for i in range(loc_subdep.count()):
            if loc_subdep.nth(i).is_visible():
                loc_subdep.nth(i).evaluate("el => el.click()")
                print(f"[CLICK] Mis Sub-Dependencias (index {i}) para abrir dashboard")
                break
                
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
            assert asignados_frame is not None, f"No se encontró '{target_text_asignados}' en ningún frame. HTML dumpeado en data/logs/test_06_debug_fail.html"
            
        log_step("ASIGNADOS POR DEPENDENCIAS", selector=asignados_selector, frame_name=asignados_frame.name, frame_url=asignados_frame.url)
        
        # PASO 5: Localizar Infraestructura Educativa
        target_dep = "Infraestructura Educativa"
        
        # Guardar HTML del frame para debug por si falla la extracción
        os.makedirs("data/logs", exist_ok=True)
        with open("data/logs/test_06_asignados_frame.html", "w", encoding="utf-8") as f:
            f.write(asignados_frame.content())
            
        loc_dep = asignados_frame.locator(f"text='{target_dep}'")
        
        # Podría estar en mayúsculas
        if loc_dep.count() == 0:
            loc_dep = asignados_frame.locator("text=/Infraestructura Educativa/i")
            
        assert loc_dep.count() > 0, f"No se encontró {target_dep} en la tabla"
        
        # Encontrar la fila (tr) que contiene este texto
        row = loc_dep.first.locator("xpath=ancestor::tr").first
        
        # Extraer las columnas
        cols = row.locator("td").all()
        col_texts = [c.inner_text().strip() for c in cols if c.inner_text().strip()]
        print(f"\n[EXTRACTION] Valores de {target_dep}: {col_texts}")
        
        # Identificar el elemento clicable (usualmente la misma celda o un link dentro de ella)
        href = loc_dep.first.evaluate("el => el.getAttribute('href')")
        onclick = loc_dep.first.evaluate("el => el.getAttribute('onclick')")
        print(f"[EXTRACTION] Elemento Clicable -> href: {href}, onclick: {onclick}")
        
        # Guardar Evidencia
        with open("data/logs/test_06_navigation_map.json", "w", encoding="utf-8") as f:
            json.dump(navigation_map, f, indent=4, ensure_ascii=False)
            
        print("\n[REPORT] TEST 6: PASS")
        
    except Exception as e:
        os.makedirs(os.path.join("data", "logs"), exist_ok=True)
        page.screenshot(path=os.path.join("data", "logs", "test_06_navigation_error.png"))
        
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
            
        with open(os.path.join("data", "logs", "test_06_nav_fail_html.txt"), "w", encoding="utf-8") as dump_file:
            dump_file.write(html_dump)
        with open(os.path.join("data", "logs", "test_06_nav_fail_text.txt"), "w", encoding="utf-8") as dump_file:
            dump_file.write(text_dump)
            
        navigation_map["steps"].append({"status": "error", "message": str(e)})
        with open(os.path.join("data", "logs", "test_06_navigation_map.json"), "w", encoding="utf-8") as f:
            json.dump(navigation_map, f, indent=4)
            
        print(f"\n[ERROR] TEST 6: FAIL -> {e}")
        raise
