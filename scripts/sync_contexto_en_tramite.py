import os
import sys
import json
import hashlib
from sqlalchemy import text

sys.path.insert(0, os.path.abspath("."))
from backend.oracle_service import engine

def sync_en_tramite():
    print("=== SINCRONIZANDO CONTEXTO PARA RADICADOS EN TRAMITE ===")
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT r.ID_RADICADO, r.ASUNTO, r.MUNICIPIO_HISTORICO
            FROM SAC_RADICADOS r
            WHERE LOWER(r.ID_USUARIO_ASIGNADO) = 'djdelgado' AND r.ESTADO_SAC = 'EN TRAMITE'
        """)).fetchall()

        synced = 0
        for row in rows:
            rad = row[0]
            # Buscar botsac_review.json
            rev_path = None
            for acq in ["ACQ-20261015-CANONICAL", "ACQ-20260915-0001"]:
                p = f"data/analysis/{acq}/{rad}/botsac_review.json"
                if os.path.exists(p):
                    rev_path = p
                    break

            if not rev_path:
                print(f"[SKIP] No review json para {rad}")
                continue

            with open(rev_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            summary = data.get("request_summary") or data.get("summary") or row[1]
            h_ctx = hashlib.sha256(summary.encode("utf-8")).hexdigest()

            # 1. SAC_CONTEXTO_VERSIONES
            existing_ctx = conn.execute(text("SELECT ID_CONTEXTO FROM SAC_CONTEXTO_VERSIONES WHERE ID_RADICADO = :id"), {"id": rad}).fetchone()
            if not existing_ctx:
                conn.execute(text("""
                    INSERT INTO SAC_CONTEXTO_VERSIONES (
                        ID_RADICADO, NUMERO_VERSION, ESTADO, RESUMEN_MATERIALIZADO,
                        HASH_CONTENIDO, ID_USUARIO_CREADOR, MODELO_IA, FECHA_CREACION
                    ) VALUES (
                        :id, 1, 'ACTIVO', :resumen, :h, 'djdelgado', 'BotSAC Canonical Pipeline', SYSTIMESTAMP
                    )
                """), {"id": rad, "resumen": summary, "h": h_ctx})
            else:
                conn.execute(text("""
                    UPDATE SAC_CONTEXTO_VERSIONES SET
                        RESUMEN_MATERIALIZADO = :resumen,
                        HASH_CONTENIDO = :h,
                        FECHA_CREACION = SYSTIMESTAMP
                    WHERE ID_RADICADO = :id
                """), {"id": rad, "resumen": summary, "h": h_ctx})

            # 2. Key data & Municipality
            muni = data.get("municipality") or data.get("key_data", {}).get("municipality") or row[2]
            requester = data.get("requester") or data.get("key_data", {}).get("requester")
            conn.execute(text("""
                UPDATE SAC_RADICADOS SET
                    MUNICIPIO_HISTORICO = NVL(:muni, MUNICIPIO_HISTORICO),
                    REMITENTE = NVL(:req, REMITENTE),
                    ESTADO_BOTSAC = 'LISTO',
                    UPDATED_AT = SYSTIMESTAMP
                WHERE ID_RADICADO = :id
            """), {"id": rad, "muni": muni, "req": requester})

            # 3. Sedes afectadas
            sedes = data.get("instituciones_sedes", [])
            if sedes:
                conn.execute(text("DELETE FROM SAC_SEDES_AFECTADAS WHERE ID_RADICADO = :id"), {"id": rad})
                for s in sedes:
                    inst = s.get("institucion", "Institución Educativa")
                    smuni = s.get("municipio", muni)
                    for sd in s.get("sedes", ["Sede Principal"]):
                        conn.execute(text("""
                            INSERT INTO SAC_SEDES_AFECTADAS (ID_RADICADO, NOMBRE_INSTITUCION, MUNICIPIO, NOMBRE_SEDE)
                            VALUES (:id, :inst, :muni, :sede)
                        """), {"id": rad, "inst": inst, "muni": smuni, "sede": sd})

            # 4. Hallazgos
            findings = data.get("findings", [])
            if findings:
                # Need an evidence record if foreign key exists
                ev_id = conn.execute(text("SELECT NVL(MAX(ID_EVIDENCIA), 1) FROM SAC_EVIDENCIAS")).scalar()
                conn.execute(text("DELETE FROM SAC_HALLAZGOS WHERE ID_RADICADO = :id"), {"id": rad})
                for h in findings:
                    fact = h.get("fact", "") if isinstance(h, dict) else str(h)
                    conn.execute(text("""
                        INSERT INTO SAC_HALLAZGOS (ID_RADICADO, ID_EVIDENCIA, HECHO_EXTRAIDO, NIVEL_RELEVANCIA, CONFIANZA_IA, TIPO_ORIGEN)
                        VALUES (:id, :ev_id, :hecho, 'ALTA', 0.95, 'DOCUMENTO_PETICIONARIO')
                    """), {"id": rad, "ev_id": ev_id, "hecho": fact[:1000]})

            # 5. Alertas
            alerts = data.get("alerts", [])
            if alerts:
                conn.execute(text("DELETE FROM SAC_ALERTAS WHERE ID_RADICADO = :id"), {"id": rad})
                for a in alerts:
                    atype = a.get("type", "ALERTA_TECNICA") if isinstance(a, dict) else "ALERTA_TECNICA"
                    detail = a.get("detail", str(a)) if isinstance(a, dict) else str(a)
                    sev = (a.get("severity", "ADVERTENCIA") if isinstance(a, dict) else "ADVERTENCIA").upper()
                    if sev not in ("CRITICA", "ADVERTENCIA", "INFO"):
                        sev = "ADVERTENCIA"
                    conn.execute(text("""
                        INSERT INTO SAC_ALERTAS (ID_RADICADO, TIPO_ALERTA, DETALLE, SEVERIDAD)
                        VALUES (:id, :tipo, :det, :sev)
                    """), {"id": rad, "tipo": atype[:100], "det": detail[:1000], "sev": sev})

            conn.commit()
            synced += 1
            print(f"[OK] Sincronizado {rad}: {summary[:70]}...")

        print(f"Total EN TRAMITE sincronizados: {synced}/{len(rows)}")

if __name__ == "__main__":
    sync_en_tramite()
