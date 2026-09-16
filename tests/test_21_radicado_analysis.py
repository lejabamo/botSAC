import os
import json
import time
from datetime import datetime
import pytest

from botsac.models.analysis_schema import RadicadoAnalysis
from botsac.analysis.llm.ollama import OllamaClient

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"
MODEL = "qwen2.5:3b"

def test_21_radicado_analysis():
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 21: ANÁLISIS INTEGRAL...")
    
    dir_analysis = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    context_path = os.path.join(dir_analysis, "radicado_context.json")
    
    # 1. Comprobar contexto
    assert os.path.exists(context_path), "Falta el radicado_context.json"
    with open(context_path, "r", encoding="utf-8") as f:
        context_data = json.load(f)
        
    context_text = json.dumps(context_data, indent=2, ensure_ascii=False)
    
    # 2. LLM Gateway funciona
    client = OllamaClient()
    health = client.health()
    assert health.get("status") == "ok", "LLM Gateway no responde"
    
    # 3. Preparar Prompt
    prompt = f"""Eres un analista documental experto de la Secretaría de Educación.
Analiza el siguiente contexto documental de un radicado y genera una ficha de revisión en formato JSON ESTRICTO.

REGLAS IMPORTANTES:
1. Solo usa información explícita en el contexto. No inventes datos.
2. Extrae las fechas, personas e instituciones reales.
3. Diferencia entre HECHO explícito y lo que no es posible identificar (devuelve "No identificado" o lista vacía).
4. El JSON de salida DEBE tener la siguiente estructura exacta:
{{
  "radicado": "CAU...",
  "summary": "Resumen claro y objetivo de lo que trata el radicado.",
  "topic": "Tema central o asunto (e.g. SOLICITUD DE INFRAESTRUCTURA, QUEJA, REPORTE).",
  "citizen_or_sender": "Persona o entidad que envía la comunicación.",
  "institution_or_entity": "Institución involucrada.",
  "municipality": "Municipio si se menciona.",
  "key_facts": ["Hecho 1", "Hecho 2"],
  "documents_summary": [
    {{
      "filename": "nombre del archivo",
      "purpose": "Propósito del documento dentro del radicado",
      "summary": "Resumen del contenido del documento",
      "pages": [1, 2]
    }}
  ],
  "important_dates": ["Fecha 1: Evento"],
  "alerts": [
    {{
      "type": "tipo de alerta (Incompleto, Ilegible, Contradictorio, etc)",
      "description": "Descripción de la alerta",
      "severity": "ALTA|MEDIA|BAJA"
    }}
  ],
  "evidence": [
    {{
      "claim": "Afirmación hecha en key_facts o summary",
      "filename": "Nombre del archivo fuente",
      "page_number": 1,
      "source_text": "Cita textual breve que lo demuestra"
    }}
  ]
}}

CONTEXTO DEL RADICADO:
{context_text}

Produce EXCLUSIVAMENTE el JSON resultante, sin bloques de código markdown, sin explicaciones.
"""
    
    # Llamada al LLM
    print(f"[LLM] Solicitando análisis a {MODEL} (esto puede tardar unos segundos)...")
    result = client.generate_structured(MODEL, prompt)
    
    assert result.get("status") == "success", f"Fallo LLM: {result.get('error')}"
    
    # 3. JSON Válido
    response_json = result.get("response", {})
    assert isinstance(response_json, dict), "La respuesta no es un diccionario JSON"
    
    # 4. Pydantic Válido
    try:
        analysis = RadicadoAnalysis(**response_json)
    except Exception as e:
        pytest.fail(f"El JSON devuelto no cumple el contrato Pydantic: {e}\nJSON: {response_json}")
        
    # 5. Evidencias validas
    if len(analysis.key_facts) > 0:
        assert len(analysis.evidence) > 0, "No hay evidencia respaldando los key_facts"
        
    # Validar que los filenames y pages existen en el contexto
    valid_filenames = [d["filename"] for d in context_data["documentos"]]
    valid_filenames.append("solicitud.txt")
    valid_filenames.append("novedades.json")
    
    for ev in analysis.evidence:
        assert ev.filename in valid_filenames, f"El filename {ev.filename} no es válido."
        assert ev.page_number >= 0, f"Page number {ev.page_number} inválido."
        assert ev.source_text.strip(), "Source text vacío"
        
    # 10. Persistencia
    out_path = os.path.join(dir_analysis, "radicado_analysis.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis.model_dump(), f, indent=2, ensure_ascii=False)
        
    assert os.path.exists(out_path)
    
    # 11. Reporte
    latency = result.get("latency_ms", 0) / 1000.0
    
    print("\n==================================================")
    print("REPORT: TEST 21: PASS")
    print(f"Tiempo de inferencia: {latency:.2f} segundos")
    print(f"Resumen: {analysis.summary}")
    print(f"Documentos identificados: {len(analysis.documents_summary)}")
    for d in analysis.documents_summary:
        print(f" - {d.filename}: {d.purpose}")
    print(f"Alertas: {len(analysis.alerts)}")
    for a in analysis.alerts:
        print(f" - [{a.severity}] {a.type}: {a.description}")
    print(f"Cantidad de evidencias extraídas: {len(analysis.evidence)}")
    print("Resultado Pydantic: Válido")
    print("==================================================")

if __name__ == "__main__":
    test_21_radicado_analysis()
