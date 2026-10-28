import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List, Set, Optional
from sqlalchemy import text

sys.path.append(os.path.abspath("."))
from backend.database import engine
from backend.canonical_etl import CanonicalETL, log_etl

WATCHDOG_LOG = "data/watchdog.log"

def log_watchdog(msg: str):
    os.makedirs("data", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [WATCHDOG] {msg}"
    print(line)
    with open(WATCHDOG_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def reconcile_por_aprobar(live_sac_ids: Set[str], coverage_complete: bool, user_account: Optional[str] = None) -> List[str]:
    """
    Reconcilia los radicados en Oracle contra la lista viva de SAC para el usuario en sesión.
    SOLO se permite conciliar si coverage_complete == True (todas las páginas fueron verificadas).
    Cualquier radicado que en Oracle esté como 'POR APROBAR' para este usuario, pero que ya NO aparezca
    en la cuadrícula viva de SAC 'POR APROBAR', significa que ya fue aprobado / despachado en SAC.
    Se actualiza en Oracle como ESTADO_SAC = 'TRAMITADO' para sacarlo de la bandeja de trabajo.
    """
    if not coverage_complete:
        log_watchdog("Aviso: Cobertura incompleta o parcial de páginas. Se omite reconciliación destructiva de TRAMITADO por seguridad.")
        return []

    marked_tramitados: List[str] = []

    select_sql = text("""
        SELECT ID_RADICADO, ESTADO_SAC, ASUNTO
        FROM SAC_RADICADOS
        WHERE ESTADO_SAC = 'POR APROBAR'
          AND (:u_acc IS NULL OR ID_USUARIO_ASIGNADO = :u_acc)
    """)

    update_sql = text("""
        UPDATE SAC_RADICADOS
        SET ESTADO_SAC = 'TRAMITADO',
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID_RADICADO = :id
    """)

    with engine.connect() as conn:
        rows = conn.execute(select_sql, {"u_acc": user_account}).fetchall()
        for r in rows:
            rad_id = r[0]
            if rad_id not in live_sac_ids:
                conn.execute(update_sql, {"id": rad_id})
                marked_tramitados.append(rad_id)
                log_watchdog(f"Radicado {rad_id} ya fue respondido y aprobado en SAC -> Marcado como TRAMITADO en Oracle.")

        conn.commit()

    return marked_tramitados

def run_watchdog_sync(
    max_pages: int = 10,
    acquire_pdfs: bool = True,
    target_pdf_sample: int = 3,
    headless: bool = True,
    sac_user: Optional[str] = None,
    sac_pass: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ejecuta el ciclo de sincronización canónica y reconciliación de BotSAC:
    1. Ejecuta CanonicalETL con paginación completa para la cuenta del usuario autenticado.
    2. Persiste metadatos e inserta nuevos radicados asignados a su usuario.
    3. Descarga y valida PDFs oficiales reales.
    4. Reconcilia de forma segura solo si la cobertura de páginas fue completa.
    """
    t_start = time.time()
    active_user = sac_user or os.getenv("SAC_USER", "institucional")
    log_watchdog(f"Iniciando ciclo canónico de verificación y reconciliación Watchdog para usuario '{active_user}'...")

    etl = CanonicalETL(sac_user=sac_user, sac_pass=sac_pass)
    pipeline_result = etl.run_full_pipeline(
        max_pages=max_pages,
        acquire_pdfs=acquire_pdfs,
        target_pdf_sample=target_pdf_sample
    )

    if pipeline_result.get("status") == "LOCKED":
        return pipeline_result

    if pipeline_result.get("status") != "SUCCESS":
        return {
            "status": "ERROR",
            "error": pipeline_result.get("error", "Error desconocido en pipeline"),
            "timings": pipeline_result.get("timings", {})
        }

    # Obtener IDs vivos extraídos de la cuadrícula SAC
    live_ids: Set[str] = {item["radicado"] for item in pipeline_result.get("items", []) if item.get("radicado")}
    ora_stats = pipeline_result.get("oracle_stats", {})
    is_complete = pipeline_result.get("is_complete", False)
    marked_tramitados: List[str] = []

    if is_complete:
        marked_tramitados = reconcile_por_aprobar(live_ids, coverage_complete=True, user_account=sac_user)
        if marked_tramitados:
            log_watchdog(f"Conciliación automática: {len(marked_tramitados)} radicado(s) tramitados fuera de la bandeja: {marked_tramitados}")

    elapsed = round(time.time() - t_start, 2)
    log_watchdog(f"Ciclo Watchdog finalizado en {elapsed}s. "
                 f"Total extraído: {pipeline_result.get('total_extraido', 0)} | "
                 f"Páginas: {pipeline_result.get('pages_count', 0)} | "
                 f"PDFs verificados: {pipeline_result.get('verified_responses_count', 0)}")

    return {
        "status": "SUCCESS",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": elapsed,
        "total_anunciado": pipeline_result.get("total_anunciado"),
        "total_extraido": pipeline_result.get("total_extraido"),
        "desfase": pipeline_result.get("desfase"),
        "is_complete": pipeline_result.get("is_complete"),
        "pages_count": pipeline_result.get("pages_count"),
        "verified_responses_count": pipeline_result.get("verified_responses_count"),
        "tramitados_count": len(marked_tramitados),
        "reconciled_tramitados": marked_tramitados,
        "oracle_stats": ora_stats,
        "timings": pipeline_result.get("timings")
    }

if __name__ == "__main__":
    res = run_watchdog_sync(max_pages=3, acquire_pdfs=True, target_pdf_sample=1, headless=True)
    print("Resultado Watchdog:", res)
