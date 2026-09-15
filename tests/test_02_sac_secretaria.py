import os
import time
import pytest
from datetime import datetime
from playwright.sync_api import Page, expect
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # Set a robust user agent to avoid WAF blocks (reused from TEST 1)
    return {
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    }

def test_02_sac_secretaria(page: Page):
    """
    TEST 2: SELECCIÓN REAL DE SE CAUCA.
    Abre el portal y selecciona SE CAUCA utilizando el selector por texto visible.
    Verifica que la selección quedó aplicada correctamente.
    """
    assert SAC_URL, "SAC_URL no configurada en .env"

    start_time = time.time()
    
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 2...")
    print(f"Navegando a: {SAC_URL}")

    try:
        # Navegar a la página
        page.goto(SAC_URL, wait_until="domcontentloaded")
        
        # 1. Localizar y comprobar el selector
        select_locator = page.locator('select#id_sc_field_entidad')
        select_locator.wait_for(state="visible", timeout=15000)
        
        # Comprobar que es un select evaluando su tagName
        tag_name = select_locator.evaluate("el => el.tagName").lower()
        assert tag_name == "select", f"El elemento no es un select, es {tag_name}"
        
        # Inspeccionar cantidad de opciones
        options_count = select_locator.locator("option").count()
        print(f"Opciones encontradas en el dropdown: {options_count}")
        assert options_count > 1, "El dropdown no tiene suficientes opciones."

        # 2. Seleccionar "SE CAUCA" por su label/texto visible
        # Se prefiere text/label en lugar de un value hardcodeado o índice.
        # select_option(label="SE CAUCA") selecciona basándose en el texto de la opción.
        selected_values = select_locator.select_option(label="SE CAUCA")
        
        # Esperar un poco a que posibles mutaciones del DOM o eventos onChange ocurran
        page.wait_for_timeout(2000)

        # 3. Verificación
        expect(select_locator).to_be_visible()
        
        # Obtener el valor actualmente seleccionado a través del DOM
        current_value = select_locator.input_value()
        
        # Obtener el texto visible asociado a ese valor
        current_text = select_locator.locator(f'option[value="{current_value}"]').text_content()

        assert "SE CAUCA" in current_text, f"El texto seleccionado es '{current_text}', se esperaba 'SE CAUCA'"

        nav_time = time.time() - start_time
        final_url = page.url

        print(f"Texto seleccionado: {current_text.strip()}")
        print(f"Value seleccionado: {current_value}")
        print(f"URL final: {final_url}")
        print(f"Tiempo de la operación: {nav_time:.2f} segundos")

        # 4. Guardar screenshot
        screenshot_path = os.path.join("data", "logs", "test_02_success.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"Evidencia DOM verificada exitosamente. Screenshot guardado en {screenshot_path}")

    except Exception as e:
        screenshot_path = os.path.join("data", "logs", "test_02_error.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"[{datetime.now().isoformat()}] ERROR en TEST 2: {e}")
        print(f"Screenshot del error guardado en {screenshot_path}")
        raise
