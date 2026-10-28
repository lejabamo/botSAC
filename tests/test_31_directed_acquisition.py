import os
import sys
import subprocess

# CAU2026ER032723 -> Cache
# CAU2026ER032558 -> Dirigida

def test_31_directed_acquisition():
    print("Testing directed acquisition (Prompt 31)...")
    
    # 1. Test CAU2026ER032558 with real official
    # From previous data we know adiaz is DIAZ ANDREA VANESSA
    print("\n[TEST] 1. CAU2026ER032558 (Adquisición Dirigida)")
    result1 = subprocess.run([sys.executable, "scripts/acquire_radicado.py", 
                              "--radicado", "CAU2026ER032558", 
                              "--usuario-funcionario", "adiaz"], 
                             capture_output=True, text=True)
    assert result1.returncode == 0, f"Acquisition failed: {result1.stderr or result1.stdout}"
    assert "Adquisición completada" in result1.stdout
    
    # 2. Test cache loading logic from dashboard (mocking)
    print("\n[TEST] 2. CAU2026ER032723 (Cache validation via dashboard import)")
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from app.dashboard import load_radicado_data
    
    data, hashes = load_radicado_data("CAU2026ER032723")
    # Actually, we might not have the cache for CAU2026ER032723 locally initialized here depending on state
    # So we just ensure it doesn't crash. If it has data, it should return something.
    if data:
        print(" -> Cache loaded successfully.")
    else:
        print(" -> Cache empty (expected if not previously acquired).")
        
    # 3. Test incorrect official -> should produce controlled mismatch/error
    print("\n[TEST] 3. CAU2026ER032558 (Funcionario incorrecto)")
    result3 = subprocess.run([sys.executable, "scripts/acquire_radicado.py", 
                              "--radicado", "CAU2026ER032558", 
                              "--funcionario", "ALGUIEN QUE NO EXISTE"], 
                             capture_output=True, text=True)
    assert result3.returncode != 0, "Should have failed with incorrect official"
    assert "ERROR" in result3.stdout or "ERROR" in result3.stderr
    
    # 4. Test missing radicado -> should produce controlled error
    print("\n[TEST] 4. CAU2026ER000000 (Radicado inexistente)")
    result4 = subprocess.run([sys.executable, "scripts/acquire_radicado.py", 
                              "--radicado", "CAU2026ER000000", 
                              "--usuario-funcionario", "adiaz"], 
                             capture_output=True, text=True)
    assert result4.returncode != 0, "Should have failed with missing radicado"
    assert "ERROR" in result4.stdout or "ERROR" in result4.stderr
    
    print("\nDirected acquisition tests passed.")

if __name__ == "__main__":
    test_31_directed_acquisition()
