# MANUAL DE INSTALACIÓN Y DESPLIEGUE EN PRODUCCIÓN
## Sistema BotSAC Enterprise — Gobernación del Cauca
### Guía Técnica Especializada para Infraestructura:
* **Servidor Central de Base de Datos:** **Oracle Linux (UEK / Red Hat Family)**
* **Máquina Virtual de Aplicación:** **Debian 13 (Trixie)**

---

## 1. RESUMEN EJECUTIVO Y ARQUITECTURA DE INFRAESTRUCTURA

El sistema **BotSAC** opera bajo una topología distribuida de alta disponibilidad:
1. **Servidor Principal (Oracle Linux):** Aloja el motor de base de datos institucional Oracle 19c/21c con la PDB `pdb_dev.educauca.gov.co` en la IP `172.16.0.10`.
2. **Máquina Virtual de Aplicación (Debian 13 Trixie):** Aloja los contenedores de producción de BotSAC (Frontend Web Nginx, Backend API FastAPI y Agente Worker continuo de ingesta) orquestados mediante Docker Compose.

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
│                                                         │                   │
│  ┌───────────────────────────┐                          │                   │
│  │       botsac-worker       │                          │                   │
│  │ (Daemon Ingesta/Watchdog) │ ─────────────────────────┘                   │
│  └───────────────────────────┘                          │                   │
│                                                         │                   │
│  Volumen Persistente: /opt/botSAC/data                  │                   │
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

---

## 2. PARÁMETROS Y DATOS DE CONFIGURACIÓN OFICIALES

Estos son los valores oficiales e inviolables que deben configurarse en el archivo `.env` de la VM Debian 13:

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

### 2.4 Motor de Inteligencia Artificial (LLM)
* **Proveedor:** `ollama`
* **URL:** `http://localhost:11434` *(o IP del host Ollama si está en un servidor separado)*
* **Modelo:** `qwen2.5:3b`

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

# Si se desea restringir exclusivamente a la IP de la VM Debian 13 (Ejemplo IP_DEBIAN=172.16.0.50):
# sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="172.16.0.50" port port="1521" protocol="tcp" accept'

# Recargar reglas activas
sudo firewall-cmd --reload

# Confirmar estado
sudo firewall-cmd --list-ports
```

---

## 4. INSTALACIÓN Y PUESTA EN MARCHA EN LA VM (DEBIAN 13 TRIXIE)

Siga estos pasos como administrador en la máquina virtual **Debian 13**:

### PASO 1: Acceso SSH y Preparación de Privilegios (`sudo`)
En instalaciones limpias de Debian, a veces `sudo` no está instalado o el usuario no pertenece al grupo `sudo`. Si es necesario, ingrese como `root`:
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
Debian 13 dispone de paquetes nativos totalmente optimizados, o puede emplear el repositorio oficial de Docker:

#### Opción Recomendada (Instalador Oficial Docker Engine):
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
*(Nota: Cierre sesión y vuelva a ingresar por SSH para que el grupo `docker` tome efecto sin `sudo`).*

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
Cree el archivo de configuración con los datos oficiales de Oracle y SAC:
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

# Motor LLM (Inteligencia Artificial)
LLM_PROVIDER=ollama
LLM_BASE_URL=http://localhost:11434
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

O ejecute directamente los comandos de Docker Compose:
```bash
mkdir -p data/documents data/analysis data/logs data/locks
chmod -R 775 data

docker compose up -d --build
```

---

### PASO 7: Configuración del Firewall en Debian 13 (UFW)
Proteja la máquina virtual permitiendo solo los puertos de servicio:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # Frontend Web BotSAC
sudo ufw allow 8000/tcp  # API Backend (opcional si se consulta directamente)
sudo ufw enable
```

---

## 5. VALIDACIÓN Y PRUEBAS DE ACEPTACIÓN (SMOKE TESTS)

### 5.1 Estado de los Contenedores
```bash
docker compose ps
```
Debe mostrar los 3 contenedores activos:
* `botsac-frontend` — `Up` (Puerto `0.0.0.0:80->80/tcp`)
* `botsac-backend` — `Up (healthy)` (Puerto `0.0.0.0:8000->8000/tcp`)
* `botsac-worker` — `Up` (Daemon continuo de extracción y watchdog)

### 5.2 Test de la API REST (Backend conectado a Oracle)
```bash
curl -s http://localhost:8000/api/inbox | jq .
```
Debe listar la estructura JSON de los radicados consultados directamente desde la base de datos Oracle en el servidor Oracle Linux.

### 5.3 Test del Frontend Web (Nginx)
```bash
curl -I http://localhost/
```
Debe retornar `HTTP/1.1 200 OK`.

### 5.4 Inspección de Logs en Vivo
```bash
# Ver logs del backend (conexiones Oracle y endpoints)
docker compose logs -f --tail=50 backend

# Ver logs del agente continuo (ciclos de extracción y conciliación)
docker compose logs -f --tail=50 worker
```

---

## 6. VALIDACIÓN FUNCIONAL EN EL NAVEGADOR

Abra en su navegador de estación de trabajo institucional:
```
http://<IP_DEBIAN_13>/
```

### Casos de Prueba Clave:
1. **Acceso con `ljbastidas` / `SuperS4c`:**
   - La bandeja debe mostrar en la parte superior los radicados en estado `✓ LISTO` (con documentos y análisis extraídos).
   - Los radicados recién encolados aparecen al final con estado `📋 EN COLA SAC`.
   - Botón `Aprobar y Archivar`: Solo habilitado para radicados listos.
   - Pestaña `📁 Tramitados`: Muestra el historial de radicados aprobados.
2. **Acceso con `djdelgado` / `Bucheli_123`:**
   - Visualiza estrictamente los radicados asignados a su subdependencia.
   - Se confirma el aislamiento multi-tenant y la imposibilidad de suplantación.

---

## 7. MANTENIMIENTO Y OPERACIONES CONTINUAS EN DEBIAN 13

### Actualizar a una Nueva Versión (CI/CD Git)
```bash
cd /opt/botSAC
git pull origin main
docker compose up -d --build
```

### Reiniciar el Sistema
```bash
cd /opt/botSAC
docker compose restart
```

### Monitoreo de Recursos en Tiempo Real
```bash
docker stats
```

### Respaldo de Documentos Locales y Trazas
```bash
tar -czvf /opt/backup_botsac_$(date +%Y%m%d_%H%M%S).tar.gz /opt/botSAC/data
```

---

## 8. MATRIZ DE RESOLUCIÓN DE INCIDENCIAS (ORACLE LINUX + DEBIAN 13)

| Incidencia | Origen Técnico | Solución Específica |
| :--- | :--- | :--- |
| `ORA-12170: TNS:Connect timeout` | `firewalld` en Oracle Linux bloquea el puerto 1521. | En el servidor Oracle Linux ejecutar: `sudo firewall-cmd --permanent --add-port=1521/tcp && sudo firewall-cmd --reload`. |
| `nc -zv 172.16.0.10 1521` reporta *Connection refused* | El listener de Oracle está caído o no escucha en la IP de red. | En Oracle Linux ejecutar `lsnrctl status` y verificar `listener.ora` para que escuche en `0.0.0.0` o `172.16.0.10`. |
| Error `libaio1` o `libaio1t64` al compilar imagen | Transición de 64-bit time_t en Debian 13. | Resuelto en el `Dockerfile` de BotSAC (`apt-get install libaio1 || apt-get install libaio1t64`). |
| `ORA-01017: invalid username/password` | Credenciales discrepantes en `.env`. | Comprobar que en `/opt/botSAC/.env` figure `ORACLE_USER=BOTSAC` y `ORACLE_PASS=SedCauca**`. |
| Frontend inaccesible desde otra máquina | Puerto 80 bloqueado en Debian 13. | Ejecutar en Debian 13: `sudo ufw allow 80/tcp`. |

---
*Documento de Ingeniería — Gobernación del Cauca | BotSAC Enterprise.*
