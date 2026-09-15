import sys
import pytest
from playwright.sync_api import Page

def test_00_python_venv():
    """
    TEST 0: Python + virtualenv funcionando.
    Verifica la versión de Python (>= 3.12) y que se esté ejecutando en un entorno virtual.
    """
    assert sys.version_info >= (3, 12), f"Python version is {sys.version_info}, requires >= 3.12"
    # Comprobar que estamos en un entorno virtual
    assert sys.prefix != sys.base_prefix, "El código no se está ejecutando dentro de un entorno virtual (.venv)"
    
    print(f"Python Version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"Virtual Env Path: {sys.prefix}")

def test_01_playwright_functional(page: Page):
    """
    TEST 1: Playwright funciona.
    Abre una página en blanco y verifica que Playwright está configurado y el navegador responde.
    """
    page.goto("about:blank")
    assert page.url == "about:blank"
    print("Playwright y el navegador funcionan correctamente.")
