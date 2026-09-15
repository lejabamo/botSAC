import os
import time
import json
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

def test_06_sac_dependencia(page: Page):
    """
    TEST 6: ASIGNADOS POR DEPENDENCIAS -> INFRAESTRUCTURA EDUCATIVA
    Localiza la fila de Infraestructura Educativa y extrae sus datos sin hacer click.
    """
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales o URL en .env"

    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 6...")

    try:
        # 1. Login y Navegación (Reutilizado TEST 4 y 5)
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
        
        # Modal de sesión
        modal_handled = False
        for f in page.frames:
            try:
                locators = [
                    f.locator("button:has-text('Aceptar')"), f.locator("a:has-text('Aceptar')"),
                    f.locator("input[type='button'][value='Aceptar']"), f.locator("input[type='submit'][value='Aceptar']"),
                    f.locator("button:has-text('Continuar')"), f.locator("a:has-text('Continuar')")
                ]
                for loc in locators:
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
        
        # Click en "Mi Dependencia"
        menu_loc = page.locator("a[tab-title='Mi Dependencia']")
        assert menu_loc.count() > 0, "No se encontró el menú Mi Dependencia"
        menu_loc.first.evaluate("el => el.click()")
        
        # 2. Localización de la tabla
        print("Esperando transición del módulo (10s)...")
        page.wait_for_timeout(10000)
        
        # 3. Localización de la Dependencia (Infraestructura Educativa)
        target_text = "Infraestructura Educativa"
        
        dep_frame = None
        dep_row = None
        headers = []
        row_values = []
        detail_action = None
        
        timeout_at = time.time() + 20
        while time.time() < timeout_at and not dep_frame:
            for idx, f in enumerate(page.frames):
                try:
                    row_loc = f.locator(f"tr:has-text('{target_text}')")
                    if row_loc.count() > 0:
                        for i in range(row_loc.count()):
                            row = row_loc.nth(i)
                            cells = row.locator("td, th")
                            if cells.count() > 1:
                                dep_frame = f
                                dep_row = row
                                
                                try:
                                    table_loc = row.locator("xpath=ancestor::table").first
                                    header_cells = table_loc.locator("tr").first.locator("td, th")
                                    headers = [header_cells.nth(j).inner_text().strip() for j in range(header_cells.count())]
                                except:
                                    headers = []
                                    
                                row_values = [cells.nth(j).inner_text().strip() for j in range(cells.count())]
                                
                                links_in_row = row.locator("a")
                                if links_in_row.count() > 0:
                                    first_link = links_in_row.first
                                    detail_action = {
                                        "tag": "a",
                                        "text": first_link.inner_text().strip(),
                                        "href": first_link.evaluate("el => el.getAttribute('href')"),
                                        "onclick": first_link.evaluate("el => el.getAttribute('onclick')")
                                    }
                                else:
                                    onclick_els = row.locator("[onclick]")
                                    if onclick_els.count() > 0:
                                        el = onclick_els.first
                                        detail_action = {
                                            "tag": el.evaluate("el => el.tagName"),
                                            "text": el.inner_text().strip(),
                                            "onclick": el.evaluate("el => el.getAttribute('onclick')")
                                        }
                                        
                                break
                        if dep_frame:
                            break
                except:
                    pass
                    
            if not dep_frame:
                page.wait_for_timeout(2000)
                
        # Guardar Evidencia
        os.makedirs(os.path.join("data", "logs"), exist_ok=True)
        page.screenshot(path=os.path.join("data", "logs", "test_06_success.png"))
        evidence_json = {
            "name": target_text,
            "frame": dep_frame.name if dep_frame else None,
            "frame_url": dep_frame.url if dep_frame else None,
            "selector": f"tr:has-text('{target_text}')",
            "columns": row_values,
            "headers": headers,
            "detail_action": detail_action,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(os.path.join("data", "logs", "test_06_dependency.json"), "w", encoding="utf-8") as json_file:
            json.dump(evidence_json, json_file, indent=4)
            
        print(f"\n[REPORT] TEST 6: {'PASS' if dep_frame else 'FAIL'}")
        print(f"[REPORT] Encabezados: {headers}")
        print(f"[REPORT] Fila encontrada: {'Sí' if dep_row else 'No'}")
        print(f"[REPORT] Valores reales: {row_values}")
        print(f"[REPORT] Acción identificada: {detail_action}")
        
        assert dep_frame is not None, f"No se encontró la fila con texto '{target_text}' después del drill-down."
        
    except Exception as e:
        page.screenshot(path=os.path.join("data", "logs", "test_06_error.png"))
        
        # Dump HTML of all frames to help debug what was actually on screen
        html_dump = ""
        text_dump = ""
        for idx, f in enumerate(page.frames):
            try:
                html_dump += f"\n<!-- FRAME {idx} ({f.name} - {f.url}) -->\n"
                html_dump += f.content()
                text_dump += f"\n--- FRAME {idx} ({f.name}) ---\n"
                text_dump += f.locator("body").inner_text()
            except:
                pass
        with open(os.path.join("data", "logs", "test_06_final_html.txt"), "w", encoding="utf-8") as dump_file:
            dump_file.write(html_dump)
        with open(os.path.join("data", "logs", "test_06_final_text.txt"), "w", encoding="utf-8") as dump_file:
            dump_file.write(text_dump)
            
        print(f"\n[ERROR] {e}")
        raise
