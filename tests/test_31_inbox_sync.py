import os
import json
import subprocess
import sys
from datetime import datetime

def test_31_inbox_sync():
    print("Testing inbox sync (Prompt 31)...")
    
    # Run the script
    result = subprocess.run([sys.executable, "scripts/sync_inbox.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"sync_inbox.py failed: {result.stderr}"
    
    inbox_path = "data/dashboard_inbox.json"
    assert os.path.exists(inbox_path), "Dashboard inbox JSON not found"
    
    with open(inbox_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    assert isinstance(data, list), "Inbox data should be a list"
    assert len(data) <= 20, f"Expected at most 20 radicados, got {len(data)}"
    
    radicados = [item["radicado"] for item in data]
    assert len(radicados) == len(set(radicados)), "Found duplicate radicados"
    
    for item in data:
        assert "funcionario" in item, "Missing 'funcionario' in item"
        assert "usuario_funcionario" in item, "Missing 'usuario_funcionario' in item"
        assert "radicado" in item, "Missing 'radicado' in item"
        assert "estado" in item, "Missing 'estado' in item"
        # Validate UTF-8 by checking if a string has been garbled (basic heuristic)
        assert "\ufffd" not in item["funcionario"], "Found garbled UTF-8 character"
        assert "\xc3" not in item["funcionario"], "Found un-decoded latin1 character"

    # Date ordering check (descending)
    def parse_dt(dstr):
        try: return datetime.strptime(dstr, "%d/%m/%Y")
        except: return datetime.min
        
    dates = [parse_dt(item.get("fecha_creacion", "")) for item in data]
    for i in range(1, len(dates)):
        assert dates[i-1] >= dates[i], "Dates are not sorted descendingly"
        
    print(f"Sync inbox test passed. Length: {len(data)}")

if __name__ == "__main__":
    test_31_inbox_sync()
