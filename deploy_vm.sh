#!/usr/bin/env bash
# ==============================================================================
# Script de Despliegue Automatizado para BotSAC en Máquina Virtual Linux
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

# 3. Comprobar conectividad hacia el servidor Oracle (172.16.0.10:1521)
ORACLE_HOST="${ORACLE_HOST:-172.16.0.10}"
ORACLE_PORT="${ORACLE_PORT:-1521}"
echo "Verificando conectividad hacia Oracle Database ($ORACLE_HOST:$ORACLE_PORT)..."
if timeout 3 bash -c "</dev/tcp/$ORACLE_HOST/$ORACLE_PORT" 2>/dev/null; then
    echo "✓ Conectividad TCP hacia Oracle exitosa."
else
    echo "⚠️ Advertencia: No se pudo abrir conexión directa al puerto $ORACLE_PORT en $ORACLE_HOST."
    echo "Asegúrate de que la VM tenga las rutas y reglas de firewall autorizadas."
fi

# 4. Crear directorios para persistencia de datos
mkdir -p data/documents data/analysis data/logs data/locks
chmod -R 775 data 2>/dev/null || true
echo "✓ Directorios de almacenamiento persistente preparados."

# 5. Construir y levantar contenedores Docker
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

echo "======================================================================"
echo "           ¡DESPLIEGUE DE BOTSAC COMPLETADO CON ÉXITO!                "
echo "======================================================================"
echo "-> Aplicación Web (Frontend): http://$(hostname -I | awk '{print $1}')/ o http://localhost/"
echo "-> API REST Backend:          http://$(hostname -I | awk '{print $1}'):8000/api/inbox"
echo "-> Logs de ejecución:         docker compose logs -f"
echo "======================================================================"
