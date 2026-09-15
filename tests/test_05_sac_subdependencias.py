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

def test_05_sac_subdependencias(page: Page):
    """
    TEST 5: NAVEGAR A MIS SUB-DEPENDENCIAS
    Realiza login, acepta modal, hace click en el menú y verifica transición.
    """
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales o URL en .env"

    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 5...")

    try:
        # 1. Login Real y Modal (Reutilizando TEST 4)
        print("Navegando al portal SAC...")
        page.goto(SAC_URL, wait_until="domcontentloaded")
        
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        
        btn_aceptar_entidad = page.locator('a#sub_form_b')
        if btn_aceptar_entidad.is_visible():
            btn_aceptar_entidad.click()
            
        page.wait_for_selector('input#id_sc_field_login', timeout=15000)
        page.locator('input#id_sc_field_login').fill(SAC_USER)
        page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
        
        page.locator('input.btn-login[value="Ingresar"]').click()
        
        print("Esperando 5s para verificar modal de sesión activa...")
        page.wait_for_timeout(5000)
        
        modal_handled = False
        for f in page.frames:
            try:
                locators = [
                    f.locator("button:has-text('Aceptar')"),
                    f.locator("a:has-text('Aceptar')"),
                    f.locator("input[type='button'][value='Aceptar']"),
                    f.locator("input[type='submit'][value='Aceptar']"),
                    f.locator("button:has-text('Continuar')"),
                    f.locator("a:has-text('Continuar')")
                ]
                for loc in locators:
                    if loc.count() > 0 and loc.first.is_visible():
                        print(f"[SESSION_CONTINUE] Pulsando botón en frame {f.name}...")
                        loc.first.click()
                        modal_handled = True
                        break
            except:
                pass
            if modal_handled: break
                
        if modal_handled:
            page.wait_for_timeout(5000)
            page.wait_for_load_state("load")
        else:
            page.wait_for_load_state("load")

        page.wait_for_timeout(5000)
        
        url_antes = page.url
        title_antes = page.title()
        frames_antes = len(page.frames)
        
        print(f"\n[INFO] ANTES DEL CLICK:")
        print(f"URL: {url_antes}")
        print(f"Título: {title_antes}")
        print(f"Frames: {frames_antes}")
        
        # 2. Localizar y clickear "Mis Sub-Dependencias"
        selector_menu = "a[tab-title='Mis Sub-Dependencias']"
        menu_loc = page.locator(selector_menu).first
        
        assert menu_loc.count() > 0, f"No se encontró el menú con {selector_menu}"
        
        print("Haciendo click en 'Mis Sub-Dependencias' mediante JS...")
        menu_loc.evaluate("el => el.click()")
        
        # 3. Esperar transición (10s para dar tiempo a Scriptcase de cargar la vista)
        print("Esperando transición...")
        page.wait_for_timeout(10000)
        
        url_despues = page.url
        title_despues = page.title()
        frames_despues = len(page.frames)
        
        print(f"\n[INFO] DESPUÉS DEL CLICK:")
        print(f"URL: {url_despues}")
        print(f"Título: {title_despues}")
        print(f"Frames: {frames_despues}")
        
        # 4. Mapeo de Frames Post-Click y Evidencia DOM
        frames_data = []
        target_frame_found = None
        evidencia_dom = "No encontrada"
        
        os.makedirs(os.path.join("data", "logs"), exist_ok=True)
        html_file = open(os.path.join("data", "logs", "test_05_post_click.html"), "w", encoding="utf-8")
        
        html_file.write(f"<!-- MAIN FRAME HTML -->\n{page.content()}\n")
        
        for idx, f in enumerate(page.frames):
            f_url = f.url
            f_name = f.name
            parent = f.parent_frame.name if f.parent_frame else "none"
            
            frame_info = {
                "index": idx,
                "name": f_name,
                "url": f_url,
                "parent": parent
            }
            frames_data.append(frame_info)
            
            try:
                content = f.content()
                html_file.write(f"\n<!-- FRAME {idx} ({f_name}) HTML -->\n{content}\n")
                
                text_content = f.locator("body").inner_text()
                
                # Identificamos el frame de la vista destino por su URL
                if "Fun_Semaforo_OtrasDependencias" in f_url or "Fun_SubDependencias" in f_url:
                    print(f"¡FRAME DESTINO ENCONTRADO!: {f_name} (Index: {idx})")
                    target_frame_found = f_name if f_name else f"frame_index_{idx}"
                    evidencia_dom = text_content[:200].replace('\n', ' ')
            except Exception as e:
                pass
                
        html_file.close()
        
        with open(os.path.join("data", "logs", "test_05_frames.json"), "w", encoding="utf-8") as json_file:
            json.dump(frames_data, json_file, indent=4)
            
        page.screenshot(path=os.path.join("data", "logs", "test_05_success.png"))
        
        print("\n[REPORT] TEST 5: PASS" if target_frame_found else "\n[REPORT] TEST 5: FAIL (No evidence found)")
        print(f"[REPORT] Selector Click: {selector_menu}")
        print(f"[REPORT] URL Antes: {url_antes}")
        print(f"[REPORT] URL Después: {url_despues}")
        print(f"[REPORT] Título Antes: {title_antes}")
        print(f"[REPORT] Título Después: {title_despues}")
        print(f"[REPORT] Frames Antes: {frames_antes}")
        print(f"[REPORT] Frames Después: {frames_despues}")
        print(f"[REPORT] Frame Destino: {target_frame_found}")
        print(f"[REPORT] Evidencia DOM: {evidencia_dom}")
        
        # We will not strictly assert on target_frame_found if it failed because we want to see the report, 
        # but to mark the test as failed for pytest we assert at the end.
        assert target_frame_found is not None, "No se detectó evidencia de la vista 'Mis Sub-Dependencias'"
        
    except Exception as e:
        page.screenshot(path=os.path.join("data", "logs", "test_05_error.png"))
        print(f"\n[ERROR] {e}")
        raise
