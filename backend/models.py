from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, CLOB, Numeric, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class Usuario(Base):
    __tablename__ = "SAC_USUARIOS"
    
    id_usuario = Column(String(50), primary_key=True)
    nombres_completos = Column(String(255), nullable=False)
    rol_principal = Column(String(50))
    estado = Column(String(20), default="ACTIVO")
    created_at = Column(DateTime, server_default=func.sysdate())

class Radicado(Base):
    __tablename__ = "SAC_RADICADOS"

    id_radicado = Column(String(50), primary_key=True, index=True)
    asunto = Column(String(500), nullable=False)
    codigo_dane_municipio = Column(String(10))
    municipio_historico = Column(String(150))
    id_usuario_asignado = Column(String(50), ForeignKey("SAC_USUARIOS.id_usuario"))
    nombre_funcionario_hist = Column(String(150))
    remitente = Column(String(150))
    categoria = Column(String(100))
    dependencia = Column(String(150))
    fecha_creacion = Column(DateTime)
    fecha_vencimiento = Column(DateTime)
    estado_sac = Column(String(50))
    estado_botsac = Column(String(20), default="PENDIENTE")
    es_vencido = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.sysdate())
    updated_at = Column(DateTime, server_default=func.sysdate(), onupdate=func.sysdate())

    sedes = relationship("Sede", back_populates="radicado")
    documentos = relationship("Documento", back_populates="radicado")
    alertas = relationship("Alerta", back_populates="radicado")


class Sede(Base):
    __tablename__ = "SAC_SEDES_AFECTADAS"

    id_sede = Column(Integer, primary_key=True, autoincrement=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    nombre_institucion = Column(String(255))
    codigo_dane_municipio = Column(String(10))
    municipio = Column(String(150))
    nombre_sede = Column(String(255))

    radicado = relationship("Radicado", back_populates="sedes")


class Alerta(Base):
    __tablename__ = "SAC_ALERTAS"

    id_alerta = Column(Integer, primary_key=True, autoincrement=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    tipo_alerta = Column(String(100), nullable=False)
    detalle = Column(String(500))
    severidad = Column(String(20))
    estado_alerta = Column(String(20), default="ACTIVA")
    fecha_creacion = Column(DateTime, server_default=func.sysdate())

    radicado = relationship("Radicado", back_populates="alertas")


class Documento(Base):
    __tablename__ = "SAC_DOCUMENTOS"

    id_documento = Column(String(100), primary_key=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    nombre_archivo = Column(String(255), nullable=False)
    tipo_original = Column(String(50))
    mime_type = Column(String(100))
    tamano_bytes = Column(Numeric)
    paginas = Column(Integer)
    hash_contenido_original = Column(String(64))
    origen = Column(String(50))
    estado_documento = Column(String(20), default="RECIBIDO")
    ubicacion_fisica = Column(String(500))
    fecha_carga = Column(DateTime, server_default=func.sysdate())

    radicado = relationship("Radicado", back_populates="documentos")
    derivados = relationship("DocumentoDerivado", back_populates="documento")
    extracciones = relationship("ExtraccionDocumento", back_populates="documento")


class DocumentoDerivado(Base):
    __tablename__ = "SAC_DOCUMENTOS_DERIVADOS"

    id_derivado = Column(Integer, primary_key=True, autoincrement=True)
    id_documento = Column(String(100), ForeignKey("SAC_DOCUMENTOS.id_documento"))
    tipo_derivado = Column(String(50), nullable=False)
    ruta_derivado = Column(String(500), nullable=False)
    hash_contenido_derivado = Column(String(64))
    herramienta_conversion = Column(String(100))
    version_herramienta = Column(String(50))
    estado_derivado = Column(String(20), default="COMPLETADO")
    fecha_conversion = Column(DateTime, server_default=func.sysdate())

    documento = relationship("Documento", back_populates="derivados")


class ExtraccionDocumento(Base):
    __tablename__ = "SAC_EXTRACCIONES_DOCUMENTO"

    id_extraccion = Column(Integer, primary_key=True, autoincrement=True)
    id_documento = Column(String(100), ForeignKey("SAC_DOCUMENTOS.id_documento"))
    tipo_procesamiento = Column(String(50))
    pagina_num = Column(Integer)
    texto_extraido = Column(CLOB)
    confianza_promedio = Column(Numeric(5, 2))
    version_extractor = Column(String(50))
    estado_extraccion = Column(String(20))
    fecha_extraccion = Column(DateTime, server_default=func.sysdate())

    documento = relationship("Documento", back_populates="extracciones")
    evidencias = relationship("Evidencia", back_populates="extraccion")


class Evidencia(Base):
    __tablename__ = "SAC_EVIDENCIAS"

    id_evidencia = Column(Integer, primary_key=True, autoincrement=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    id_documento = Column(String(100), ForeignKey("SAC_DOCUMENTOS.id_documento"))
    id_extraccion = Column(Integer, ForeignKey("SAC_EXTRACCIONES_DOCUMENTO.id_extraccion"))
    pagina = Column(Integer)
    tipo_fuente = Column(String(50))
    referencia = Column(String(255))
    texto_soporte = Column(CLOB, nullable=False)
    hash_contenido_evidencia = Column(String(64))
    fecha_creacion = Column(DateTime, server_default=func.sysdate())

    extraccion = relationship("ExtraccionDocumento", back_populates="evidencias")
    hallazgos = relationship("Hallazgo", back_populates="evidencia")


class Hallazgo(Base):
    __tablename__ = "SAC_HALLAZGOS"

    id_hallazgo = Column(Integer, primary_key=True, autoincrement=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    id_evidencia = Column(Integer, ForeignKey("SAC_EVIDENCIAS.id_evidencia"))
    hecho_extraido = Column(CLOB, nullable=False)
    nivel_relevancia = Column(String(20))
    confianza_ia = Column(Numeric(5, 2))
    metodo_extraccion = Column(String(50))
    modelo_ia = Column(String(100))
    version_analisis = Column(String(50))
    fecha_hallazgo = Column(DateTime, server_default=func.sysdate())

    evidencia = relationship("Evidencia", back_populates="hallazgos")


class ContextoVersiones(Base):
    __tablename__ = "SAC_CONTEXTO_VERSIONES"

    id_contexto = Column(Integer, primary_key=True, autoincrement=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    numero_version = Column(Integer, nullable=False)
    estado = Column(String(20), default="ACTIVO")
    resumen_materializado = Column(CLOB, nullable=False)
    hash_contenido = Column(String(64), nullable=False)
    id_usuario_creador = Column(String(50), ForeignKey("SAC_USUARIOS.id_usuario"))
    modelo_ia = Column(String(100))
    fecha_creacion = Column(DateTime, server_default=func.sysdate())

    __table_args__ = (UniqueConstraint('id_radicado', 'numero_version', name='uq_ctx_version'),)


class Respuesta(Base):
    __tablename__ = "SAC_RESPUESTAS"

    id_respuesta = Column(Integer, primary_key=True, autoincrement=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    numero_version = Column(Integer, nullable=False)
    estado_respuesta = Column(String(20), nullable=False)
    texto = Column(CLOB, nullable=False)
    id_autor = Column(String(50), ForeignKey("SAC_USUARIOS.id_usuario"))
    id_revisor = Column(String(50), ForeignKey("SAC_USUARIOS.id_usuario"))
    id_aprobador = Column(String(50), ForeignKey("SAC_USUARIOS.id_usuario"))
    id_contexto_utilizado = Column(Integer, ForeignKey("SAC_CONTEXTO_VERSIONES.id_contexto"))
    hash_contenido = Column(String(64), nullable=False)
    hash_registro = Column(String(64), nullable=False)
    observaciones = Column(CLOB)
    id_externo_sac = Column(String(100))
    fecha_creacion = Column(DateTime, server_default=func.sysdate())
    fecha_actualizacion = Column(DateTime)

    __table_args__ = (UniqueConstraint('id_radicado', 'numero_version', name='uq_resp_version'),)


class MemoriaInstitucional(Base):
    __tablename__ = "SAC_MEMORIA_INSTITUCIONAL"

    id_memoria = Column(Integer, primary_key=True, autoincrement=True)
    id_respuesta_origen = Column(Integer, ForeignKey("SAC_RESPUESTAS.id_respuesta"))
    tema = Column(String(255))
    categoria = Column(String(100))
    codigo_dane_municipio = Column(String(10))
    institucion = Column(String(255))
    tipo_requerimiento = Column(String(100))
    resumen = Column(CLOB)
    texto_reutilizable = Column(CLOB, nullable=False)
    estado = Column(String(20), default="ACTIVA")
    id_funcionario_aprobador = Column(String(50), ForeignKey("SAC_USUARIOS.id_usuario"))
    hash_contenido_memoria = Column(String(64))
    fecha_aprobacion = Column(DateTime, server_default=func.sysdate())


class Procesamiento(Base):
    __tablename__ = "SAC_PROCESAMIENTO"

    id_proceso = Column(Integer, primary_key=True, autoincrement=True)
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    id_documento = Column(String(100), ForeignKey("SAC_DOCUMENTOS.id_documento"))
    id_respuesta = Column(Integer, ForeignKey("SAC_RESPUESTAS.id_respuesta"))
    tipo_proceso = Column(String(50), nullable=False)
    estado_proceso = Column(String(20), default="EN_COLA")
    worker_id = Column(String(100))
    intentos = Column(Integer, default=0)
    error_msg = Column(CLOB)
    metadata_tecnica = Column(CLOB)
    fecha_inicio = Column(DateTime)
    fecha_fin = Column(DateTime)
    duracion_segundos = Column(Numeric)

class Trazabilidad(Base):
    __tablename__ = "SAC_TRAZABILIDAD"

    id_traza = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String(100))
    id_usuario_actor = Column(String(50), ForeignKey("SAC_USUARIOS.id_usuario"))
    actor_historico = Column(String(150))
    origen = Column(String(50))
    tipo_evento = Column(String(100), nullable=False)
    objeto = Column(String(50))
    objeto_id = Column(String(100))
    id_radicado = Column(String(50), ForeignKey("SAC_RADICADOS.id_radicado"))
    detalle = Column(CLOB)
    hash_anterior = Column(String(64))
    hash_posterior = Column(String(64))
    fecha_evento = Column(DateTime, server_default=func.sysdate())
