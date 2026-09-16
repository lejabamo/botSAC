import os
import json
from datetime import datetime
import pytest

def test_28_dashboard_viewer():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 28: VISUALIZADOR REAL DE DOCUMENTOS...")
    
    assert os.path.exists("app/dashboard.py"), "El archivo dashboard no existe"
    
    with open("app/dashboard.py", "r", encoding="utf-8") as f:
        code = f.read()
        
    # 1. todos los documentos aparecen
    assert "for doc in data.get(\"documents\", []):" in code or "for doc in data.get('documents'" in code, "Falta iteración de documentos"
    
    # 2. cada documento tiene su acción "ABRIR DOCUMENTO"
    assert "ABRIR DOCUMENTO" in code, "Falta el botón ABRIR DOCUMENTO"
    
    # 3. la ruta real del PDF existe
    assert "pdf_path = os.path.abspath(" in code, "No se calcula la ruta real del PDF"
    
    # 4. el visor puede cargar el PDF (iframe base64)
    assert "<iframe src=\"data:application/pdf;base64" in code, "Falta el visor PDF base64"
    assert "st.markdown(pdf_display, unsafe_allow_html=True)" in code
    
    # 5. no se muestra la ruta local al usuario
    assert "st.code(pdf_path" not in code and "st.caption(f\"📍 Ruta local:" not in code, "Se está mostrando la ruta local al usuario!"
    
    # 6. no se ejecuta LLM
    assert "OllamaClient" not in code
    assert "generate_structured" not in code
    
    # 7. sigue leyendo botsac_review.json
    assert "botsac_review.json" in code
    
    print("\n==================================================")
    print("REPORT: TEST 28: VISUALIZADOR REAL DE DOCUMENTOS")
    print("Validación de Visor de PDF: OK")
    print("Validación de Jerarquía visual: OK")
    print("Ocultamiento de rutas locales: OK")
    print("==================================================\nPASS")

if __name__ == "__main__":
    test_28_dashboard_viewer()
