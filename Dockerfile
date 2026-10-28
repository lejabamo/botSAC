FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema requeridas para Oracle Client y utilidades
# Compatible con Debian 12 (libaio1) y Debian 13 Trixie / Ubuntu 24.04 (libaio1t64)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && (apt-get install -y --no-install-recommends libaio1 2>/dev/null || apt-get install -y --no-install-recommends libaio1t64 2>/dev/null || true) \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar módulos del proyecto
COPY app/ ./app/
COPY backend/ ./backend/
COPY botsac/ ./botsac/
COPY scripts/ ./scripts/

# Crear estructura de carpetas para datos locales y logs
RUN mkdir -p data/documents data/analysis data/logs data/locks

EXPOSE 8000

# Ejecutar el servidor FastAPI
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
