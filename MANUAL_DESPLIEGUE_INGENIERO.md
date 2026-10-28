# MANUAL DE INSTALACIÓN Y DESPLIEGUE EN PRODUCCIÓN
## Sistema BotSAC Enterprise — Gobernación del Cauca
### Guía Técnica Especializada para Infraestructura:
* **Servidor Central de Base de Datos:** **Oracle Linux (UEK / Red Hat Family)**
* **Máquina Virtual de Aplicación:** **Debian 13 (Trixie)**

---

## 1. RESUMEN EJECUTIVO Y ARQUITECTURA DE INFRAESTRUCTURA

El sistema **BotSAC** opera bajo una arquitectura distribuida, autónoma y autocontenida:
1. **Servidor Principal (Oracle Linux):** Aloja el motor de base de datos institucional Oracle 19c/21c con la PDB `pdb_dev.educauca.gov.co` en la IP `172.16.0.10:1521`.
2. **Máquina Virtual de Aplicación (Debian 13 Trixie):** Aloja los **4 contenedores Docker** del stack completo (Web Frontend Nginx, Backend API FastAPI, Worker Agente Continuo y **Motor de Inferencia de Inteligencia Artificial Ollama**).

### Diagrama de Contenedores en la Máquina Virtual Debian 13:
```
                      [ RED CORPORATIVA / CLIENTES WEB ]
                                       │
                                       ▼ (Puerto 80 / 443)
┌─────────────────────────────────────────────────────────────────────────────┐
│ MÁQUINA VIRTUAL LINUX — DEBIAN 13 (TRIXIE)                                  │
│                                                                             │
│  ┌───────────────────────────┐         ┌─────────────────────────────────┐  │
│  │     botsac-frontend       │ ──────> │         botsac-backend          │  │
│  │   (React SPA + Nginx)     │ /api/*  │       (FastAPI + Uvicorn)       │  │
│  │        Puerto 80          │         │           Puerto 8000           │  │
│  └───────────────────────────┘         └─────────────────────────────────┘  │
│                                                  │             │            │
│                                                  │             ▼            │
│  ┌───────────────────────────┐                   │    ┌──────────────────┐  │
│  │       botsac-worker       │ ──────────────────┘    │  botsac-ollama   │  │
│  │ (Daemon Ingesta/Watchdog) │ ─────────────────────> │   (qwen2.5:3b)   │  │
│  └───────────────────────────┘                        │   Puerto 11434   │  │
│                                                       └──────────────────┘  │
│                                                                │            │
│  Volúmenes Persistentes:                                       │            │
│  - /opt/botSAC/data (Documentos, análisis, logs, trazas)       ▼            │
│  - ollama_models (Modelos de IA descargados persistentes) ─────┘            │
└─────────────────────────────────────────────────────────┼───────────────────┘
                                                          │
                                                          ▼ (Puerto 1521 TCP)
                        ┌──────────────────────────────────────┐
                        │ SERVIDOR PRINCIPAL — ORACLE LINUX    │
                        │ IP: 172.16.0.10                      │
                        │ Puerto Listener: 1521                │
                        │ PDB: pdb_dev.educauca.gov.co         │
                        │ Schema / User: BOTSAC                │
                        │ Firewall: firewalld (1521/tcp OPEN)  │
                        └──────────────────────────────────────┘
```

> **IMPORTANTE — AUTONOMÍA DEL SERVIDOR:**
> El motor de Inteligencia Artificial (LLM) **NO se ejecuta en máquinas locales de desarrollo ni depende de la estación de trabajo**. Corre como un microservicio interno dockerizado (`botsac-ollama`) dentro de la propia Máquina Virtual en el servidor Debian 13. El backend y el worker se comunican con él a través de la red privada interna de Docker en `http://ollama:11434`.

---

## 2. PARÁMETROS Y DATOS DE CONFIGURACIÓN OFICIALES

Estos son los valores oficiales e inviolables que deben configurarse en el archivo `/opt/botSAC/.env` de la VM Debian 13:

### 2.1 Conexión a Base de Datos Oracle Institucional (Servidor Oracle Linux)
* **IP Servidor Oracle Linux:** `172.16.0.10`
* **Puerto Listener:** `1521`
* **Nombre de Servicio / PDB:** `pdb_dev.educauca.gov.co`
* **DSN Completo:** `172.16.0.10:1521/pdb_dev.educauca.gov.co`
* **Usuario (Schema):** `BOTSAC`
* **Contraseña:** `SedCauca**`

### 2.2 Conexión a Plataforma SAC v2 (Gobernación del Cauca)
* **URL Login Oficial:** `https://sac2.gestionsecretariasdeeducacion.gov.co/app_Login/`
* **Usuario SAC Base:** `djdelgado`
* **Contraseña SAC Base:** `Bucheli_123`

### 2.3 Cuentas Iniciales para Validación de Aislamiento y Aprobación
1. **Líder de Oficina:**
   * **Usuario:** `ljbastidas` (Leonardo Javier Bastidas Moreno)
   * **Contraseña:** `SuperS4c`
   * **Rol:** Inbox Zero, visualización de documentos analizados, aprobación y archivo a `📁 Tramitados`.
2. **Subdependencia Infraestructura Educativa:**
   * **Usuario:** `djdelgado`
   * **Contraseña:** `Bucheli_123`
   * **Rol:** Gestión de solicitudes asignadas.

### 2.4 Motor de Inteligencia Artificial (LLM Dockerizado en el Servidor)
* **Proveedor:** `ollama`
* **URL de Red Interna Docker:** `http://ollama:11434`
* **Modelo IA Seleccionado:** `qwen2.5:3b`
* **Persistencia:** Volumen Docker `ollama_models` (no se pierde al reiniciar contenedores).

---

## 3. ACCIONES PREVIAS EN EL SERVIDOR PRINCIPAL (ORACLE LINUX)

Antes de desplegar en la VM Debian 13, el administrador o DBA en el servidor **Oracle Linux** debe verificar la disponibilidad del listener y las reglas del firewall corporativo:

### 3.1 Comprobar el Listener de Oracle
En la consola de Oracle Linux (usuario `oracle`):
```bash
lsnrctl status
```
*Validación:* El servicio `pdb_dev.educauca.gov.co` debe figurar en estado `READY` asociado al endpoint `PORT=1521`.

### 3.2 Habilitar Puerto 1521 en Firewalld (Oracle Linux)
Como usuario `root` en el servidor Oracle Linux:
```bash
# Permitir tráfico TCP en el puerto 1521 permanente
sudo firewall-cmd --permanent --add-port=1521/tcp

# Recargar reglas activas
sudo firewall-cmd --reload

# Confirmar estado
sudo firewall-cmd --list-ports
```

---

## 4. INSTALACIÓN Y PUESTA EN MARCHA EN LA VM (DEBIAN 13 TRIXIE)

Siga estos pasos como administrador en la máquina virtual **Debian 13**:

### PASO 1: Acceso SSH y Preparación de Privilegios (`sudo`)
En instalaciones limpias de Debian, si `sudo` no está configurado, ingrese como `root`:
```bash
su -
apt update && apt install -y sudo curl git netcat-openbsd ca-certificates gnupg lsb-release htop ufw
usermod -aG sudo tu_usuario
exit
```
Conéctese nuevamente con su usuario habitual:
```bash
ssh tu_usuario@<IP_DEBIAN_13>
```

---

### PASO 2: Instalar Docker y Docker Compose en Debian 13
```bash
# Descargar e instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo rm get-docker.sh

# Añadir el usuario al grupo docker
sudo usermod -aG docker $USER

# Iniciar y habilitar el servicio Docker
sudo systemctl enable --now docker

# Validar versión
docker --version
docker compose version
```
*(Cierre sesión y vuelva a ingresar por SSH para que el grupo `docker` tome efecto sin `sudo`).*

---

### PASO 3: Clonar el Repositorio de Producción Sanitizado
```bash
cd /opt
sudo git clone https://github.com/lejabamo/botSAC.git
sudo chown -R $USER:$USER /opt/botSAC
cd /opt/botSAC
```

---

### PASO 4: Configurar el Archivo `.env` de Producción
Cree el archivo de configuración con los datos oficiales:
```bash
cat << 'EOF' > /opt/botSAC/.env
# ==============================================================================
# CONFIGURACIÓN DE PRODUCCIÓN - BOTSAC ENTERPRISE
# Servidor Central: Oracle Linux (172.16.0.10:1521)
# Servidor de Aplicación: Debian 13 (Trixie)
# ==============================================================================

# Credenciales SAC v2 Oficial
SAC_USER=djdelgado
SAC_PASS=Bucheli_123
SAC_URL=https://sac2.gestionsecretariasdeeducacion.gov.co/app_Login/

# Credenciales de Usuarios BotSAC
BOTSAC_PASS_LJBASTIDAS=SuperS4c

# Motor LLM (Dockerizado con Ollama en el Servidor Debian 13)
LLM_PROVIDER=ollama
LLM_BASE_URL=http://ollama:11434
LLM_MODEL=qwen2.5:3b

# Base de Datos Oracle Institucional (Oracle Linux)
ORACLE_USER=BOTSAC
ORACLE_PASS=SedCauca**
ORACLE_HOST=172.16.0.10
ORACLE_PORT=1521
ORACLE_SERVICE=pdb_dev.educauca.gov.co
ORACLE_DSN=172.16.0.10:1521/pdb_dev.educauca.gov.co
EOF
```

Asegurar permisos estrictos en Debian 13:
```bash
chmod 600 /opt/botSAC/.env
```

---

### PASO 5: Verificación de Red desde Debian 13 hacia Oracle Linux
Antes de levantar los contenedores, valide que Debian 13 tiene ruta abierta hacia el listener en Oracle Linux:
```bash
nc -zv 172.16.0.10 1521
```
*Salida exitosa:*
`Connection to 172.16.0.10 1521 port [tcp/*] succeeded!`

Valide salida HTTPS hacia el portal SAC:
```bash
curl -I https://sac2.gestionsecretariasdeeducacion.gov.co/app_Login/
```
*Salida exitosa:* Cabecera HTTP `200 OK`.

---

### PASO 6: Despliegue Automatizado con Docker Compose
Ejecute el script de despliegue automatizado:
```bash
chmod +x deploy_vm.sh
./deploy_vm.sh
```

El script se encargará automáticamente de:
1. Construir las imágenes de Backend y Frontend.
2. Iniciar los 4 contenedores (`botsac-ollama`, `botsac-backend`, `botsac-frontend`, `botsac-worker`).
3. Descargar e inicializar el modelo `qwen2.5:3b` dentro del contenedor `botsac-ollama`.

---

### PASO 7: Configuración del Firewall en Debian 13 (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # Frontend Web BotSAC
sudo ufw allow 8000/tcp  # API Backend
sudo ufw enable
```

---

## 5. VALIDACIÓN Y PRUEBAS DE ACEPTACIÓN (SMOKE TESTS)

### 5.1 Estado de los 4 Contenedores
```bash
docker compose ps
```
Debe mostrar los 4 microservicios en estado `Up` / `healthy`:
* `botsac-ollama` — `Up (healthy)` (Puerto `0.0.0.0:11434->11434/tcp`)
* `botsac-backend` — `Up (healthy)` (Puerto `0.0.0.0:8000->8000/tcp`)
* `botsac-frontend` — `Up` (Puerto `0.0.0.0:80->80/tcp`)
* `botsac-worker` — `Up` (Daemon continuo de extracción y watchdog)

### 5.2 Test del Motor de Inteligencia Artificial (Ollama en el Servidor)
```bash
# Verificar que el modelo qwen2.5:3b está cargado en el contenedor
docker compose exec ollama ollama list

# Test rápido de inferencia interna desde el servidor
curl -s http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:3b",
  "prompt": "Responde con la palabra OK si estás activo en el servidor de la Gobernación del Cauca.",
  "stream": false
}' | jq .response
```

### 5.3 Test de la API REST Backend (Conectada a Oracle Linux)
```bash
curl -s http://localhost:8000/api/inbox | jq .
```
Debe listar los radicados obtenidos en vivo desde la base de datos Oracle institucional.

### 5.4 Test del Frontend Web (Nginx)
```bash
curl -I http://localhost/
```
Debe retornar `HTTP/1.1 200 OK`.

---

## 6. VALIDACIÓN FUNCIONAL EN EL NAVEGADOR

Abra en su navegador dentro de la red corporativa:
```
http://<IP_DEBIAN_13>/
```

### Casos de Validación:
1. **Usuario `ljbastidas` / `SuperS4c`:**
   - Visualiza en primer lugar los radicados procesados con IA en estado `✓ LISTO`.
   - Botón `Aprobar y Archivar` habilitado únicamente para radicados listos.
   - Pestaña `📁 Tramitados`: Histórico de radicados despachados.
2. **Usuario `djdelgado` / `Bucheli_123`:**
   - Visualiza únicamente sus radicados asignados (aislamiento multi-tenant estricto).

---

## 7. MANTENIMIENTO Y OPERACIONES CONTINUAS EN EL SERVIDOR

### Descargar Modelos Adicionales en Ollama
```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

### Actualizar la Aplicación desde GitHub
```bash
cd /opt/botSAC
git pull origin main
docker compose up -d --build
```

### Ver Logs del LLM o del Worker en Tiempo Real
```bash
# Logs del motor de IA
docker compose logs -f --tail=50 ollama

# Logs del agente extractor
docker compose logs -f --tail=50 worker
```

---

## 8. MATRIZ DE RESOLUCIÓN DE INCIDENCIAS

| Incidencia | Origen Técnico | Solución Específica |
| :--- | :--- | :--- |
| `ORA-12170: TNS:Connect timeout` | `firewalld` en Oracle Linux bloquea el puerto 1521. | En el servidor Oracle Linux: `sudo firewall-cmd --permanent --add-port=1521/tcp && sudo firewall-cmd --reload`. |
| `Connection refused: http://ollama:11434` | El contenedor de Ollama no ha terminado de arrancar. | Verificar con `docker compose ps` y `docker compose logs ollama`. |
| El modelo `qwen2.5:3b` no responde | No se completó la descarga del modelo. | Ejecutar: `docker compose exec ollama ollama pull qwen2.5:3b`. |
| Error `libaio1t64` al construir backend | Transición 64-bit time_t en Debian 13. | Resuelto en Dockerfile (`apt-get install libaio1 || apt-get install libaio1t64`). |
| `ORA-01017: invalid username/password` | Credenciales discrepantes en `.env`. | Verificar `ORACLE_USER=BOTSAC` y `ORACLE_PASS=SedCauca**` en `/opt/botSAC/.env`. |

---
*Documento de Ingeniería — Gobernación del Cauca | BotSAC Enterprise.*
