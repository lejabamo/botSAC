import os
import re
import json
import time
import pytest
from botsac.analysis.llm.evidence_schema import EvidenceCheck, RequestEvidenceReport

ACQUISITION_ID = "ACQ-20260915-0001"
RADICADO = "CAU2026ER032723"

def normalize_text(text: str) -> set:
    if not text:
        return set()
    # Convert to lowercase and remove non-alphanumeric chars
    clean = re.sub(r'[^\w\s]', ' ', text.lower())
    # Split into words and remove tiny words
    words = {w for w in clean.split() if len(w) > 3}
    return words

def check_evidence(field: str, value: str, raw_text: str) -> EvidenceCheck:
    if not value or value.lower() in ["no identificado", "vacío", ""]:
        return EvidenceCheck(
            field=field,
            value=value,
            supported=True,
            evidence="N/A",
            reason="Valor vacío o no identificado, se asume correcto si no hay invención"
        )
        
    val_words = normalize_text(value)
    raw_words = normalize_text(raw_text)
    
    if not val_words:
        # Puros conectores o palabras cortas
        return EvidenceCheck(
            field=field,
            value=value,
            supported=False,
            evidence="",
            reason="Valor demasiado corto o sin palabras significativas para validar"
        )
        
    intersection = val_words.intersection(raw_words)
    overlap_ratio = len(intersection) / len(val_words)
    
    # Heurística simple: 
    # Si coinciden al menos el 50% de las palabras significativas, lo damos por soportado.
    if overlap_ratio >= 0.5:
        return EvidenceCheck(
            field=field,
            value=value,
            supported=True,
            evidence=", ".join(list(intersection)[:5]) + ("..." if len(intersection)>5 else ""),
            reason=f"Coincidencia de {len(intersection)}/{len(val_words)} palabras clave ({(overlap_ratio*100):.1f}%)"
        )
    else:
        # Check substring as fallback
        clean_val = re.sub(r'\s+', ' ', value.lower()).strip()
        clean_raw = re.sub(r'\s+', ' ', raw_text.lower()).strip()
        if clean_val in clean_raw:
            return EvidenceCheck(
                field=field,
                value=value,
                supported=True,
                evidence="Fragmento exacto encontrado",
                reason="Coincidencia por subcadena exacta"
            )
            
        return EvidenceCheck(
            field=field,
            value=value,
            supported=False,
            evidence="",
            reason=f"Solo {len(intersection)}/{len(val_words)} palabras coinciden ({(overlap_ratio*100):.1f}%). Falló subcadena."
        )

def test_14_evidence_check():
    print(f"\n[START] Iniciando TEST 14: VALIDACIÓN DE EVIDENCIA para {RADICADO}")
    
    raw_file = f"data/raw/{ACQUISITION_ID}/{RADICADO}/solicitud.txt"
    analysis_dir = f"data/analysis/{ACQUISITION_ID}/{RADICADO}"
    in_file = os.path.join(analysis_dir, "request_analysis.json")
    out_file = os.path.join(analysis_dir, "request_evidence_check.json")
    
    # 1. request_analysis.json y solicitud.txt existen
    assert os.path.exists(raw_file), f"No existe {raw_file}"
    assert os.path.exists(in_file), f"No existe {in_file}"
    
    mtime_before = os.path.getmtime(raw_file)
    
    with open(raw_file, "r", encoding="utf-8") as f:
        raw_text = f.read()
        
    with open(in_file, "r", encoding="utf-8") as f:
        analysis_data = json.load(f)
        
    start_time = time.time()
    
    checks = []
    
    # 2. Validar campos
    for field in ["problem", "location", "institution", "summary"]:
        val = analysis_data.get(field, "")
        checks.append(check_evidence(field, val, raw_text))
        
    requests = analysis_data.get("requests", [])
    for i, req in enumerate(requests):
        checks.append(check_evidence(f"request[{i}]", req, raw_text))
        
    report = RequestEvidenceReport(checks=checks)
    
    # 4. Guardar archivo
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)
        
    latency = round((time.time() - start_time) * 1000, 2)
    
    # Verificaciones Test
    assert os.path.exists(out_file), "No se generó el archivo de validación"
    mtime_after = os.path.getmtime(raw_file)
    assert mtime_before == mtime_after, "El archivo raw fue alterado!"
    
    # Reporte
    supported = []
    unsupported = []
    for c in report.checks:
        if c.supported:
            supported.append(f"{c.field} ({c.reason}) -> Evidencia: {c.evidence}")
        else:
            unsupported.append(f"{c.field} ({c.reason}) -> Valor: '{c.value}'")
            
    print("\n==================================================")
    print("REPORT: TEST 14: PASS")
    print(f"Archivos creados: {out_file}")
    print(f"Tiempo de ejecución: {latency} ms")
    
    print("\n--- CAMPOS SOPORTADOS ---")
    for s in supported:
        print(f"[PASS] {s}")
        
    print("\n--- CAMPOS NO SOPORTADOS ---")
    for u in unsupported:
        print(f"[FAIL] {u}")
        
    print("==================================================")

if __name__ == "__main__":
    test_14_evidence_check()
