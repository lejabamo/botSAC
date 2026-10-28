#!/usr/bin/env bash
# ==============================================================================
# Script de Despliegue Automatizado para BotSAC en Máquina Virtual Linux (Debian 13)
# Gobernación del Cauca - BotSAC Enterprise
# ==============================================================================
set -e

echo "======================================================================"
echo "          INICIANDO DESPLIEGUE DE BOTSAC ENTERPRISE EN VM             "
echo "======================================================================"

# 1. Comprobar instalación de Docker y Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker no está instalado en esta máquina virtual."
    echo "Instálalo ejecutando: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ ERROR: Docker Compose no está instalado."
    exit 1
fi
echo "✓ Docker y Docker Compose detectados correctamente."

# 2. Comprobar existencia del archivo .env
if [ ! -f .env ]; then
    echo "⚠️ AVISO: Archivo .env no encontrado. Generando desde .env.example..."
    cp .env.example .env
    echo "❗ Por favor configura tus credenciales reales de Oracle y SAC en el archivo .env antes de continuar."
    exit 1
fi
echo "✓ Archivo de configuración .env presente."

# 3. Comprobar conectividad hacia el servidor Oracle Linux (172.16.0.10:1521)
ORACLE_HOST="${ORACLE_HOST:-172.16.0.10}"
ORACLE_PORT="${ORACLE_PORT:-1521}"
echo "Verificando conectividad hacia Servidor Oracle Linux ($ORACLE_HOST:$ORACLE_PORT)..."
if timeout 3 bash -c "</dev/tcp/$ORACLE_HOST/$ORACLE_PORT" 2>/dev/null; then
    echo "✓ Conectividad TCP hacia Oracle exitosa."
else
    echo "⚠️ Advertencia: No se pudo abrir conexión directa al puerto $ORACLE_PORT en $ORACLE_HOST."
    echo "Asegúrate de que la VM tenga las rutas y reglas de firewall autorizadas en Oracle Linux (firewalld)."
fi

# 4. Crear directorios para persistencia de datos
mkdir -p data/documents data/analysis data/logs data/locks
chmod -R 775 data 2>/dev/null || true
echo "✓ Directorios de almacenamiento persistente preparados."

# 5. Construir y levantar contenedores Docker (Frontend, Backend, Worker, Ollama)
echo "Construyendo y levantando contenedores con Docker Compose..."
if docker compose version &> /dev/null; then
    docker compose down 2>/dev/null || true
    docker compose up -d --build
    docker compose ps
else
    docker-compose down 2>/dev/null || true
    docker-compose up -d --build
    docker-compose ps
fi

# 6. Inicialización del Motor de Inteligencia Artificial (Ollama - qwen2.5:3b)
echo "Verificando estado del motor LLM en el contenedor botsac-ollama..."
sleep 5
MODEL_NAME="${LLM_MODEL:-qwen2.5:3b}"
if docker compose version &> /dev/null; then
    DC_CMD="docker compose"
else
    DC_CMD="docker-compose"
fi

if $DC_CMD exec -T ollama ollama list 2>/dev/null | grep -q "$MODEL_NAME"; then
    echo "✓ Modelo LLM '$MODEL_NAME' ya está cargado y listo en almacenamiento persistente."
else
    echo "Descargando modelo LLM '$MODEL_NAME' dentro del servidor (primer despliegue)..."
    $DC_CMD exec -T ollama ollama pull "$MODEL_NAME" || {
        echo "⚠️ Aviso: No se pudo completar la descarga automática inmediata de '$MODEL_NAME'."
        echo "Puedes ejecutar manualmente más tarde: docker compose exec ollama ollama pull $MODEL_NAME"
    }
fi

echo "======================================================================"
echo "           ¡DESPLIEGUE DE BOTSAC COMPLETADO CON ÉXITO!                "
echo "======================================================================"
echo "-> Aplicación Web (Frontend): http://$(hostname -I | awk '{print $1}')/ o http://localhost/"
echo "-> API REST Backend:          http://$(hostname -I | awk '{print $1}'):8000/api/inbox"
echo "-> Motor LLM Ollama:          http://$(hostname -I | awk '{print $1}'):11434/"
echo "-> Logs de ejecución:         docker compose logs -f"
echo "======================================================================"
