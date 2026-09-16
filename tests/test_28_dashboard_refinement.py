import os
from datetime import datetime
import pytest

def test_28_dashboard_refinement():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 28: REFINAMIENTO DASHBOARD...")
    
    assert os.path.exists("app/dashboard.py"), "El archivo dashboard no existe"
    
    with open("app/dashboard.py", "r", encoding="utf-8") as f:
        code = f.read()
        
    # Paso 1
    assert "Revisión de Radicado" in code, "Falta cabecera principal"
    
    # Paso 2
    assert "Resumen de la solicitud" in code, "Falta resumen de la solicitud"
    assert "deduplicate_dates" in code, "Falta lógica de deduplicación de fechas"
    
    # Paso 3
    assert "Estado de atención" in code, "Falta sección estado de atención"
    assert "Sin respuesta registrada en la vista consultada" in code, "Falta alerta exacta sobre la respuesta"
    
    # Paso 4
    assert "with st.container(border=True):" in code, "Los documentos deben estar en tarjetas/contenedores"
    
    # Paso 5
    assert "Ver trazabilidad" in code, "Falta expander de trazabilidad"
    
    # Restricciones
    assert "OllamaClient" not in code
    
    print("\n==================================================")
    print("REPORT: TEST 28: DASHBOARD REFINEMENT")
    print("Validación de componentes estructurales: OK")
    print("Restricciones (Zero-LLM): OK")
    print("==================================================\nPASS")

if __name__ == "__main__":
    test_28_dashboard_refinement()
