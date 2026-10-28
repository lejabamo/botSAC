import os
import oracledb
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Cargar variables de entorno (desde la raíz o carpeta backend)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
load_dotenv()

# Inicializar modo Thick para Oracle (requerido para Native Network Encryption institucional)
INSTANTCLIENT_DIR = os.getenv(
    "ORACLE_CLIENT_LIB_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instantclient", "instantclient_19_32")
)

if os.path.exists(INSTANTCLIENT_DIR):
    try:
        oracledb.init_oracle_client(lib_dir=INSTANTCLIENT_DIR)
        print(f"[Oracle] Thick Mode inicializado correctamente desde: {INSTANTCLIENT_DIR}")
    except Exception as e:
        print(f"[Oracle] Aviso al inicializar Instant Client: {e}")

# Credenciales de Oracle
ORACLE_USER = os.getenv("ORACLE_USER", "BOTSAC")
ORACLE_PASS = os.getenv("ORACLE_PASS", "")
ORACLE_HOST = os.getenv("ORACLE_HOST", "172.16.0.10")
ORACLE_PORT = os.getenv("ORACLE_PORT", "1521")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE", "pdb_dev.educauca.gov.co")

if ORACLE_HOST and ORACLE_SERVICE:
    SQLALCHEMY_DATABASE_URL = f"oracle+oracledb://{ORACLE_USER}:{ORACLE_PASS}@{ORACLE_HOST}:{ORACLE_PORT}/?service_name={ORACLE_SERVICE}"
else:
    ORACLE_DSN = os.getenv("ORACLE_DSN", "172.16.0.10:1521/pdb_dev.educauca.gov.co")
    SQLALCHEMY_DATABASE_URL = f"oracle+oracledb://{ORACLE_USER}:{ORACLE_PASS}@{ORACLE_DSN}"

try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=5,
        max_overflow=5,
        pool_timeout=15,
        pool_recycle=60,
        pool_pre_ping=True
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
except Exception as e:
    print(f"Advertencia: No se pudo conectar a Oracle: {e}.")
    engine = None
    SessionLocal = None
    Base = declarative_base()

def get_db():
    if not SessionLocal:
        raise Exception("Base de datos no disponible")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
