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
    # Reutilizar el user-agent validado de TEST 1
    # NO pasamos storage_state para forzar un login real
    return {
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    }

def test_04_sac_post_login_discovery(page: Page):
    """
    TEST 4: RESOLVER SESIÓN ACTIVA Y LLEGAR AL PANEL
    Realiza login, acepta modal si existe, y mapea la arquitectura de frames.
    """
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales o URL en .env"

    start_time = time.time()
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 4...")

    try:
        # 1. Login Real
        print("Navegando al portal SAC...")
        page.goto(SAC_URL, wait_until="domcontentloaded")
        
        print("Seleccionando SE CAUCA...")
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        
        btn_aceptar_entidad = page.locator('a#sub_form_b')
        if btn_aceptar_entidad.is_visible():
            btn_aceptar_entidad.click()
            
        print("Ingresando credenciales...")
        page.wait_for_selector('input#id_sc_field_login', timeout=15000)
        page.locator('input#id_sc_field_login').fill(SAC_USER)
        page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
        
        print("Enviando login...")
        page.locator('input.btn-login[value="Ingresar"]').click()
        
        # 2. Detectar y Manejar Modal de Sesión Activa
        print("Verificando modal de sesión activa (esperando 5-8s)...")
        page.wait_for_timeout(5000)
        
        modal_handled = False
        btn_aceptar_modal = False
        
        # A veces el modal es un SweetAlert en la página principal, a veces un iframe ThickBox.
        # Vamos a buscar en todos los frames actuales.
        for f in page.frames:
            try:
                # Buscamos botones de Aceptar o Continuar
                # Expresión regular o selectores CSS
                locators = [
                    f.locator("button:has-text('Aceptar')"),
                    f.locator("a:has-text('Aceptar')"),
                    f.locator("input[type='button'][value='Aceptar']"),
                    f.locator("input[type='submit'][value='Aceptar']"),
                    f.locator("button:has-text('Continuar')"),
                    f.locator("a:has-text('Continuar')"),
                    f.locator("input[type='button'][value='Continuar']"),
                    f.locator("input[type='submit'][value='Continuar']")
                ]
                
                for loc in locators:
                    if loc.count() > 0:
                        first_loc = loc.first
                        if first_loc.is_visible():
                            print(f"[SESSION_CONTINUE] Modal detectado en frame '{f.name}'. Pulsando botón Aceptar/Continuar...")
                            first_loc.click()
                            modal_handled = True
                            btn_aceptar_modal = True
                            break
            except Exception as e:
                pass
            
            if modal_handled:
                break
                
        if modal_handled:
            print("Esperando la carga del panel post-modal...")
            page.wait_for_timeout(5000)
            page.wait_for_load_state("load")
        else:
            print("No se detectó modal de sesión activa (o ya cerró automáticamente).")
            page.wait_for_load_state("load")

        # Dar tiempo extra para que el SAC arme el panel
        page.wait_for_timeout(5000)
        
        post_url = page.url
        post_title = page.title()
        
        print(f"\n[INFO] URL Inmediatamente post-login: {post_url}")
        print(f"[INFO] Título de página: {post_title}")
        
        # 3. Mapeo de Frames
        frames = page.frames
        print(f"[INFO] Cantidad de frames descubiertos: {len(frames)}")
        
        frames_data = []
        target_frame = None
        target_selector = None
        target_text = None
        
        for idx, f in enumerate(frames):
            f_url = f.url
            f_name = f.name
            f_title = f.title()
            parent = f.parent_frame
            parent_name = parent.name if parent else "none"
            
            frame_info = {
                "index": idx,
                "name": f_name,
                "url": f_url,
                "parent": parent_name,
                "title": f_title,
                "menu_found": False
            }
            
            print(f"\n--- FRAME {idx} ---")
            print(f"URL: {f_url}")
            print(f"Name: {f_name}")
            print(f"Parent: {parent_name}")
            
            try:
                # Buscar "Mis Sub-Dependencias"
                # A veces es un 'a', un 'span', un 'li'
                menu_locators = [
                    f.locator("text=\"Mis Sub-Dependencias\"").first,
                    f.locator("a:has-text('Mis Sub-Dependencias')").first,
                    f.locator("li:has-text('Mis Sub-Dependencias')").first,
                    f.locator("span:has-text('Mis Sub-Dependencias')").first
                ]
                
                for loc in menu_locators:
                    if loc.count() > 0 and loc.is_visible():
                        target_frame = f
                        frame_info["menu_found"] = True
                        
                        tag = loc.evaluate("el => el.tagName").lower()
                        el_id = loc.evaluate("el => el.id")
                        el_class = loc.evaluate("el => el.className")
                        el_href = loc.evaluate("el => el.getAttribute('href')")
                        el_text = loc.text_content().strip()
                        
                        target_text = el_text
                        
                        if el_id:
                            target_selector = f"{tag}#{el_id}"
                        elif el_href:
                            target_selector = f"{tag}[href='{el_href}']"
                        else:
                            target_selector = f"{tag}:has-text('{el_text}')"
                            
                        print(f"[ÉXITO] 'Mis Sub-Dependencias' encontrado en FRAME {idx}!")
                        print(f"Selector deducido: {target_selector}")
                        print(f"Texto: {target_text}")
                        break
            except Exception as e:
                print(f"Error inspeccionando frame {idx}: {e}")
                
            frames_data.append(frame_info)
            
        # 4. Guardar evidencia (Data)
        os.makedirs(os.path.join("data", "logs"), exist_ok=True)
        with open(os.path.join("data", "logs", "test_04_frames.json"), "w", encoding="utf-8") as json_file:
            json.dump(frames_data, json_file, indent=4)
            
        # 5. Screenshot de éxito
        page.screenshot(path=os.path.join("data", "logs", "test_04_success.png"))
        
        # Report variables to stdout for parsing
        print(f"\n[REPORT] TEST 4: {'PASS' if target_frame else 'FAIL'}")
        print(f"[REPORT] Modal Detectado: {'Sí' if modal_handled else 'No'}")
        print(f"[REPORT] Botón Aceptar identificado: {'Sí' if btn_aceptar_modal else 'No'}")
        print(f"[REPORT] Aceptar ejecutado: {'Sí' if btn_aceptar_modal else 'No'}")
        print(f"[REPORT] URL Final: {post_url}")
        print(f"[REPORT] Título: {post_title}")
        print(f"[REPORT] Cantidad de Frames: {len(frames)}")
        print(f"[REPORT] Frame del menú: {target_frame.name if target_frame else 'Ninguno'}")
        print(f"[REPORT] Selector deducido: {target_selector if target_selector else 'Ninguno'}")
        
        assert target_frame is not None, "No se encontró 'Mis Sub-Dependencias' en ningún frame post-login."
        
        print("\n[VERIFY] El menú ha sido descubierto exitosamente sin realizar acciones mutativas ni interactuar prematuramente.")
        
    except Exception as e:
        page.screenshot(path=os.path.join("data", "logs", "test_04_error.png"))
        print(f"\n[ERROR] Ocurrió una anomalía: {e}")
        raise
