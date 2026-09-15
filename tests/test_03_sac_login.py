import os
import time
import pytest
from datetime import datetime
from playwright.sync_api import Page, expect, BrowserContext
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # Reutilizar el user-agent validado
    return {
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    }

def test_03_sac_login(page: Page, context: BrowserContext):
    """
    TEST 3: LOGIN REAL + PANEL AUTENTICADO.
    Inicia sesión en el SAC y verifica que el panel carga correctamente.
    Guarda el storage state si es exitoso.
    """
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales o URL en .env"

    start_time = time.time()
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 3...")
    
    try:
        # 1. Abrir SAC y seleccionar SE CAUCA
        page.goto(SAC_URL, wait_until="domcontentloaded")
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        
        # 2. Esperar transición (Botón Aceptar)
        btn_aceptar = page.locator('a#sub_form_b')
        if btn_aceptar.is_visible():
            btn_aceptar.click()
            
        # Esperar a que aparezca el campo de login. 
        # La URL puede mantenerse o cambiar, nos guiamos por el DOM.
        page.wait_for_selector('input#id_sc_field_login', timeout=15000)
        
        # 3. Inspeccionar el formulario real
        user_input = page.locator('input#id_sc_field_login')
        pass_input = page.locator('input#id_sc_field_pswd')
        submit_btn = page.locator('input.btn-login[value="Ingresar"]')
        
        expect(user_input).to_be_visible()
        expect(pass_input).to_be_visible()
        expect(submit_btn).to_be_visible()
        
        # 4. Introducir credenciales
        print("Ingresando credenciales [ACTION_BLOCKED: solo lectura permitida para operaciones posteriores]...")
        user_input.fill(SAC_USER)
        pass_input.fill(SAC_PASS)
        submit_btn.click()
        
        # 5. Esperar panel y verificar DOM
        # Esperamos que cargue la nueva página post-login
        page.wait_for_load_state("networkidle", timeout=30000)
        
        # Identificar una condición inequívoca de panel autenticado.
        # En muchos SAC se ve un menú lateral, iframes o texto específico de la entidad.
        # Buscaremos elementos estructurales fuertes como 'Mis Sub-Dependencias' o la presencia de menú.
        
        panel_evidence = ""
        panel_found = False
        
        # Intentamos buscar el texto "Mis Sub-Dependencias"
        try:
            # wait_for_timeout para permitir que los scripts de la página rendericen iframes/menu
            page.wait_for_timeout(3000)
            
            # Buscar en el frame principal
            if page.locator('text="Mis Sub-Dependencias"').count() > 0:
                panel_found = True
                panel_evidence = "Texto 'Mis Sub-Dependencias' encontrado en body"
            else:
                # Buscar dentro de iframes (Scriptcase suele meter el dashboard en iframes)
                for frame in page.frames:
                    if frame.locator('text="Mis Sub-Dependencias"').count() > 0:
                        panel_found = True
                        panel_evidence = f"Texto 'Mis Sub-Dependencias' encontrado en iframe '{frame.name}'"
                        break
        except Exception as e:
            print(f"Advertencia al buscar texto: {e}")
            
        # Si no encontramos el texto exacto, buscamos estructuras del menú de Scriptcase
        if not panel_found:
            if page.locator("iframe").count() > 0:
                panel_found = True
                panel_evidence = f"{page.locator('iframe').count()} iframes encontrados (Estructura típica de menú Scriptcase)"
            elif page.locator(".scMenuTTable").count() > 0 or page.locator("[id^='css3menu']").count() > 0:
                panel_found = True
                panel_evidence = "Menú principal detectado (.scMenuTTable o css3menu)"
                
        assert panel_found, "No se pudo verificar el panel autenticado. Revisa el screenshot del error."
        
        auth_time = time.time() - start_time
        print(f"Panel verificado mediante: {panel_evidence}")
        print(f"URL final: {page.url}")
        print(f"Tiempo de autenticación: {auth_time:.2f} segundos")
        
        # 6. Guardar storage state
        state_path = os.path.join("data", "state", "state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        context.storage_state(path=state_path)
        print("Storage state guardado exitosamente en data/state/state.json")
        
        # Screenshot de éxito (si no expone contraseñas, en este punto ya estamos en el panel)
        screenshot_path = os.path.join("data", "logs", "test_03_success.png")
        page.screenshot(path=screenshot_path)
        print(f"Screenshot guardado en {screenshot_path}")

    except Exception as e:
        screenshot_path = os.path.join("data", "logs", "test_03_error.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"[{datetime.now().isoformat()}] ERROR en TEST 3: {e}")
        print(f"Screenshot del error guardado en {screenshot_path}")
        raise
