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
    # Set a robust user agent to avoid WAF blocks
    return {
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    }

def test_01_playwright_sac(page: Page):
    """
    TEST 1: Playwright funcional. 
    Abre Chromium y accede al portal REAL del SAC sin realizar operaciones mutativas.
    """
    assert SAC_URL, "SAC_URL no configurada en .env"

    start_time = time.time()
    requested_url = SAC_URL
    
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 1...")
    print(f"Browser utilizado: Chromium (via Playwright)")
    print(f"URL solicitada: {requested_url}")

    try:
        # Navegar a la página
        response = page.goto(requested_url, wait_until="domcontentloaded")
        
        # El portal redirige a /Secretaria/, esperamos que la red o el selector esté presente.
        # Elemento estable encontrado en el análisis previo: select id="id_sc_field_entidad"
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        
        nav_time = time.time() - start_time
        final_url = page.url
        page_title = page.title()
        
        print(f"URL final: {final_url}")
        print(f"Título de la página: {page_title}")
        print(f"Tiempo de navegación: {nav_time:.2f} segundos")

        # Evidencia inequívoca: el select de secretarías
        # Se escoge porque este dropdown es la puerta de entrada para todas las entidades en el sistema SAC.
        evidencia = page.locator('select#id_sc_field_entidad')
        expect(evidencia).to_be_visible()

        # Guardar screenshot como evidencia del primer funcionamiento real
        screenshot_path = os.path.join("data", "logs", "test_01_success.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"Evidencia DOM verificada exitosamente. Screenshot guardado en {screenshot_path}")

    except Exception as e:
        # Guardar screenshot en caso de error
        screenshot_path = os.path.join("data", "logs", "test_01_error.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"[{datetime.now().isoformat()}] ERROR en TEST 1: {e}")
        print(f"Screenshot del error guardado en {screenshot_path}")
        raise
