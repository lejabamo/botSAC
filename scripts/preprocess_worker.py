import os
import sys
import os
import time
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor
import queue_manager as qm

def process_task(task):
    radicado = task["radicado"]
    funcionario = task["funcionario"]
    usuario_funcionario = task["usuario_funcionario"]
    intentos = task["intentos"]
    
    if intentos >= 3:
        qm.update_status(radicado, "ERROR", error_detail="Máximo de reintentos superado (3).")
        print(f"[WORKER] {radicado} descartado por exceder reintentos.")
        return
        
    print(f"\n[QUEUE] Procesando radicado: {radicado} (Intento {intentos}/3)")
    
    # ACQUISITION STAGE
    print(f"[ACQUIRE] inicio para {radicado}")
    # Status is already 'ADQUIRIENDO' due to queue_manager's thread-safe get
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["PYTHONIOENCODING"] = "utf-8"
    
    cmd_acq = [sys.executable, "scripts/acquire_radicado.py", "--radicado", radicado, "--funcionario", funcionario]
    if usuario_funcionario:
        cmd_acq.extend(["--usuario-funcionario", usuario_funcionario])
        
    start_acq = time.time()
    try:
        result_acq = subprocess.run(cmd_acq, capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
        t_acq = time.time() - start_acq
        if result_acq.returncode != 0:
            print(f"[WORKER] ERROR en adquisición de {radicado}")
            qm.update_status(radicado, "ERROR", error_detail=result_acq.stderr or result_acq.stdout)
            return
        print(f"[ACQUIRE] OK para {radicado} ({t_acq:.1f}s)")
    except subprocess.TimeoutExpired:
        print(f"[WORKER] ERROR Timeout en adquisición de {radicado}")
        qm.update_status(radicado, "ERROR", error_detail="Timeout en adquisición (120s)")
        return
    except Exception as e:
        print(f"[WORKER] ERROR Excepción en adquisición de {radicado}: {e}")
        qm.update_status(radicado, "ERROR", error_detail=str(e))
        return
        
    # ANALYSIS STAGE
    print(f"[ANALYSIS] inicio para {radicado}")
    qm.update_status(radicado, "ANALIZANDO")
    
    cmd_ana = [sys.executable, "scripts/analyze_radicado.py", "--radicado", radicado]
    
    start_ana = time.time()
    try:
        result_ana = subprocess.run(cmd_ana, capture_output=True, text=True, encoding="utf-8", timeout=180, env=env)
        t_ana = time.time() - start_ana
        if result_ana.returncode != 0:
            print(f"[WORKER] ERROR en análisis de {radicado}")
            qm.update_status(radicado, "ERROR", error_detail=result_ana.stderr or result_ana.stdout)
            return
        print(f"[ANALYSIS] OK para {radicado} ({t_ana:.1f}s)")
    except subprocess.TimeoutExpired:
        print(f"[WORKER] ERROR Timeout en análisis de {radicado}")
        qm.update_status(radicado, "ERROR", error_detail="Timeout en análisis (180s)")
        return
    except Exception as e:
        print(f"[WORKER] ERROR Excepción en análisis de {radicado}: {e}")
        qm.update_status(radicado, "ERROR", error_detail=str(e))
        return
        
    # ALL DONE
    t_tot = t_acq + t_ana
    qm.update_status(radicado, "LISTO", error_detail="", t_acq=t_acq, t_ana=t_ana, t_tot=t_tot)
    print(f"[WORKER] LISTO: {radicado} procesado completamente en {t_tot:.1f}s.")

def run_worker(max_workers=3):
    print(f"[WORKER] Iniciando BotSAC Preprocess Worker (Pool de {max_workers} workers)...")
    
    # Recovery on start
    recovered = qm.recover_abandoned()
    if recovered > 0:
        print(f"[WORKER] Recuperados {recovered} radicados de estados inválidos.")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while True:
            task = qm.get_next_pending()
            if not task:
                time.sleep(5)
                continue
                
            executor.submit(process_task, task)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BotSAC Preprocess Worker")
    parser.add_argument("--workers", type=int, default=3, help="Número de workers concurrentes (default: 3)")
    args = parser.parse_args()
    
    try:
        run_worker(max_workers=args.workers)
    except KeyboardInterrupt:
        print("\n[WORKER] Detenido limpiamente.")
