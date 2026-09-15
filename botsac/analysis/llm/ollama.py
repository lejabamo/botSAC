import os
import json
import time
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")

class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def health(self) -> Dict[str, Any]:
        start = time.time()
        try:
            resp = requests.get(f"{self.base_url}/api/version", timeout=5)
            latency = time.time() - start
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "status": "ok",
                    "version": data.get("version"),
                    "latency_ms": round(latency * 1000, 2)
                }
            return {"status": "error", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("models", [])
            return []
        except:
            return []

    def generate_structured(self, model: str, prompt: str) -> Dict[str, Any]:
        start = time.time()
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=600)
            latency = time.time() - start
            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get("response", "")
                
                try:
                    parsed_json = json.loads(response_text)
                    return {
                        "status": "success",
                        "response": parsed_json,
                        "latency_ms": round(latency * 1000, 2)
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "error",
                        "error": "Respuesta no es JSON válido",
                        "raw_response": response_text
                    }
            return {"status": "error", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
