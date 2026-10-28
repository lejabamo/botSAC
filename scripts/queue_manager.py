import sqlite3
import os
import datetime

DB_PATH = "data/botsac_queue.db"

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            radicado TEXT PRIMARY KEY,
            funcionario TEXT,
            usuario_funcionario TEXT,
            estado TEXT,
            fecha_creacion TEXT,
            fecha_inicio TEXT,
            fecha_actualizacion TEXT,
            intentos INTEGER DEFAULT 0,
            error_detail TEXT,
            acq_id TEXT,
            tiempo_adquisicion REAL DEFAULT 0.0,
            tiempo_analisis REAL DEFAULT 0.0,
            tiempo_total REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

def add_to_queue(radicado, funcionario, usuario_funcionario, acq_id="ACQ-20260915-0001"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT estado FROM queue WHERE radicado = ?", (radicado,))
    row = cursor.fetchone()
    
    if not row:
        import os
        has_analysis = os.path.exists(f"data/analysis/{acq_id}/{radicado}/botsac_review.json")
        initial_state = 'LISTO' if has_analysis else 'PENDIENTE'
        
        now = datetime.datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO queue (radicado, funcionario, usuario_funcionario, estado, fecha_creacion, fecha_actualizacion, intentos, acq_id)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, (radicado, funcionario, usuario_funcionario, initial_state, now, now, acq_id))
    conn.commit()
    conn.close()

def add_batch_to_queue(items, acq_id="ACQ-20260915-0001"):
    """
    Optimized block loading (bulk insert) for queue items.
    items should be a list of dictionaries with 'radicado', 'funcionario', and 'usuario_funcionario'
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get existing
    radicados = [item['radicado'] for item in items]
    placeholders = ','.join(['?'] * len(radicados))
    
    existing_set = set()
    if radicados:
        cursor.execute(f"SELECT radicado FROM queue WHERE radicado IN ({placeholders})", radicados)
        existing_set = {row['radicado'] for row in cursor.fetchall()}
    
    import os
    now = datetime.datetime.now().isoformat()
    to_insert = []
    
    for item in items:
        if item['radicado'] not in existing_set:
            has_analysis = os.path.exists(f"data/analysis/{acq_id}/{item['radicado']}/botsac_review.json")
            initial_state = 'LISTO' if has_analysis else 'PENDIENTE'
            to_insert.append((
                item['radicado'], item['funcionario'], item['usuario_funcionario'],
                initial_state, now, now, acq_id
            ))
            
    if to_insert:
        cursor.executemany("""
            INSERT INTO queue (radicado, funcionario, usuario_funcionario, estado, fecha_creacion, fecha_actualizacion, intentos, acq_id)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """, to_insert)
    
    conn.commit()
    conn.close()


def get_next_pending():
    conn = get_connection()
    try:
        conn.execute("BEGIN EXCLUSIVE")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM queue 
            WHERE estado = 'PENDIENTE' 
            ORDER BY fecha_creacion DESC 
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if row:
            now = datetime.datetime.now().isoformat()
            cursor.execute("""
                UPDATE queue 
                SET estado = 'ADQUIRIENDO', fecha_inicio = ?, intentos = intentos + 1 
                WHERE radicado = ?
            """, (now, row["radicado"]))
            conn.commit()
            res = dict(row)
        else:
            conn.commit()
            res = None
            
        return res
    except Exception as e:
        conn.rollback()
        print(f"[QUEUE] Error al obtener siguiente: {e}")
        return None
    finally:
        conn.close()

def update_status(radicado, estado, error_detail="", add_intent=False, t_acq=None, t_ana=None, t_tot=None):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    
    updates = ["estado = ?", "fecha_actualizacion = ?", "error_detail = ?"]
    params = [estado, now, error_detail]
    
    if add_intent:
        updates.append("intentos = intentos + 1")
    if estado in ["ADQUIRIENDO", "ANALIZANDO"] and add_intent:
        updates.append("fecha_inicio = ?")
        params.append(now)
        
    if t_acq is not None:
        updates.append("tiempo_adquisicion = ?")
        params.append(t_acq)
    if t_ana is not None:
        updates.append("tiempo_analisis = ?")
        params.append(t_ana)
    if t_tot is not None:
        updates.append("tiempo_total = ?")
        params.append(t_tot)
        
    params.append(radicado)
    
    query = f"UPDATE queue SET {', '.join(updates)} WHERE radicado = ?"
    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()

def recover_abandoned():
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
        UPDATE queue 
        SET estado = 'PENDIENTE', 
            fecha_actualizacion = ?, 
            error_detail = 'Recuperado tras reinicio inesperado' 
        WHERE estado IN ('ADQUIRIENDO', 'ANALIZANDO')
    """, (now,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def get_all_status():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT radicado, estado, intentos, error_detail, acq_id FROM queue")
    rows = cursor.fetchall()
    conn.close()
    return {row["radicado"]: dict(row) for row in rows}

init_db()
