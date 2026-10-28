import os
import json
from datetime import datetime
import pytest

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def test_27_dashboard_data():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 27: VERIFICACIÓN DATA DASHBOARD...")
    
    # 1. Dashboard file existe
    assert os.path.exists("app/dashboard.py"), "No se encontró el código del dashboard Streamlit"
    
    # 2. Inbox data existe
    inbox_path = "data/dashboard_inbox.json"
    assert os.path.exists(inbox_path), "Falta dashboard_inbox.json (Ejecuta test 29 primero)"
    with open(inbox_path, "r", encoding="utf-8") as f:
        inbox_data = json.load(f)
    assert len(inbox_data) > 0, "La bandeja está vacía"
    
    # 2.5 Verificar codificación UTF-8
    inbox_str = json.dumps(inbox_data)
    assert "Ã³" not in inbox_str, "El JSON contiene 'Ã³', la codificación sigue corrupta."
    assert "Ã¡" not in inbox_str, "El JSON contiene 'Ã¡', la codificación sigue corrupta."
    
    # 3. botsac_review.json existe
    review_path = f"data/analysis/{ACQUISITION_ID}/{RADICADO}/botsac_review.json"
    assert os.path.exists(review_path), "Falta botsac_review.json"
    
    # Simular carga
    with open(review_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # 4. radicado correcto
    assert data.get("radicado") == RADICADO
    
    # 5. campos administrativos presentes
    assert data.get("municipality")
    assert data.get("subject")
    assert data.get("status_sac")
    assert data.get("requester")
    
    # 6. documentos presentes
    docs = data.get("documents", [])
    assert len(docs) == 2, "Se esperaban 2 documentos"
    
    # 7. trazabilidad presente
    assert len(data.get("trace", [])) > 0, "No hay traza"
    
    # 8. PDF paths válidos
    for doc in docs:
        pdf_path = os.path.join("data", "documents", ACQUISITION_ID, RADICADO, doc.get("filename", ""))
        assert os.path.exists(pdf_path), f"PDF no encontrado: {pdf_path}"
        
    # 9. no se realiza llamada al LLM
    with open("app/dashboard.py", "r", encoding="utf-8") as f:
        code = f.read()
        assert "OllamaClient" not in code, "El dashboard importa el cliente LLM"
        assert "generate_structured" not in code, "El dashboard ejecuta LLM"
        
    # Reporte
    print("\n==================================================")
    print("REPORT: TEST 27: DASHBOARD TASK WORKING")
    print("Inbox data: OK")
    print("Data integrity: OK")
    print("Zero-LLM verification: OK")
    print("PDF local paths: OK")
    print("==================================================\nPASS")

if __name__ == "__main__":
    test_27_dashboard_data()
