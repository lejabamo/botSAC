import os
import secrets
import time
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Header, Query, Depends, Response, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import app.services as services
from backend.oracle_service import get_user_by_id

app = FastAPI(title="BotSAC API Enterprise", version="1.0.0")

# Restrict CORS to local frontend origins
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None

# Almacén de sesiones seguras activas en el servidor
# token -> { "username": str, "rol_principal": str, "name": str, "created_at": float, "expires_at": float }
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_EXPIRATION_SECONDS = 8 * 3600  # 8 horas de vigencia

def get_current_user(
    authorization: Optional[str] = Header(None),
    x_sac_token: Optional[str] = Header(None, alias="X-SAC-Token"),
    x_sac_user: Optional[str] = Header(None, alias="X-SAC-User"),
    token: Optional[str] = Query(None),
    botsac_session: Optional[str] = Cookie(None)
) -> dict:
    """
    Dependencia de seguridad canónica:
    Valida la identidad del usuario EXCLUSIVAMENTE a partir de una sesión autenticada en el servidor.
    Rechaza tajantemente cualquier intento de acceso no autenticado o manipulación de identidad por cabeceras.
    """
    # 1. Extraer el token de sesión emitido por el servidor
    session_token = None
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.split("Bearer ", 1)[1].strip()
    elif x_sac_token:
        session_token = x_sac_token.strip()
    elif botsac_session:
        session_token = botsac_session.strip()
    elif token:
        session_token = token.strip()

    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Autenticación requerida: sesión no iniciada o token de autenticación ausente."
        )

    # 2. Verificar existencia y vigencia de la sesión en el servidor
    session_data = ACTIVE_SESSIONS.get(session_token)
    if not session_data:
        raise HTTPException(
            status_code=401,
            detail="Sesión inválida o expirada en el servidor. Inicie sesión nuevamente."
        )

    if time.time() > session_data.get("expires_at", 0):
        ACTIVE_SESSIONS.pop(session_token, None)
        raise HTTPException(
            status_code=401,
            detail="La sesión ha expirado por inactividad. Inicie sesión nuevamente."
        )

    # 3. Detectar y bloquear cualquier intento de suplantación mediante cabeceras manipulables
    authenticated_username = session_data["username"]
    if x_sac_user:
        client_claimed = x_sac_user.strip().lower()
        if client_claimed and client_claimed != authenticated_username:
            raise HTTPException(
                status_code=403,
                detail=f"Intento de suplantación detectado: la sesión activa pertenece a '{authenticated_username}', no a '{client_claimed}'."
            )

    # 4. Validar perfil institucional oficial activo en Oracle
    user_info = get_user_by_id(authenticated_username)
    if not user_info:
        raise HTTPException(
            status_code=403,
            detail=f"Usuario institucional '{authenticated_username}' inactivo o no autorizado en Oracle."
        )

    user_info["session_token"] = session_token
    return user_info

INSTITUTIONAL_CREDENTIALS = {
    "ljbastidas": os.getenv("BOTSAC_PASS_LJBASTIDAS", ""),
    "djdelgado": os.getenv("SAC_PASS", ""),
    "adiaz": os.getenv("BOTSAC_PASS_ADIAZ", "")
}

@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    """
    Valida credenciales contra el catálogo institucional Oracle SAC_USUARIOS
    y verifica la contraseña correspondiente.
    Genera una sesión segura en el servidor y emite el token criptográfico y cookie HttpOnly.
    """
    u_id = req.username.strip().lower()
    if not u_id:
        raise HTTPException(status_code=400, detail="Nombre de usuario requerido.")

    user_info = get_user_by_id(u_id)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail=f"Acceso denegado: el usuario institucional '{u_id}' no está registrado o no está activo en BotSAC."
        )

    # Verificación de contraseña institucional
    expected_pass = INSTITUTIONAL_CREDENTIALS.get(u_id)
    if expected_pass:
        if not req.password or req.password.strip() != expected_pass:
            raise HTTPException(
                status_code=401,
                detail="Contraseña incorrecta para el usuario institucional."
            )

    # Crear sesión de servidor segura
    session_token = secrets.token_urlsafe(32)
    now = time.time()
    ACTIVE_SESSIONS[session_token] = {
        "username": user_info["id_usuario"],
        "rol_principal": user_info["rol_principal"],
        "name": user_info["nombres_completos"],
        "created_at": now,
        "expires_at": now + SESSION_EXPIRATION_SECONDS
    }

    # Establecer cookie HttpOnly protegida
    response.set_cookie(
        key="botsac_session",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,  # En producción con HTTPS se habilita True
        path="/",
        max_age=SESSION_EXPIRATION_SECONDS
    )

    return {
        "status": "ok",
        "token": session_token,
        "username": user_info["id_usuario"],
        "name": user_info["nombres_completos"],
        "role": "Líder de Oficina" if user_info["rol_principal"] == "LIDER_OFICINA" else "Funcionario",
        "rol_principal": user_info["rol_principal"]
    }

@app.post("/api/auth/logout")
def logout(
    response: Response,
    authorization: Optional[str] = Header(None),
    x_sac_token: Optional[str] = Header(None, alias="X-SAC-Token"),
    botsac_session: Optional[str] = Cookie(None)
):
    """
    Invalida de forma destructiva e inmediata la sesión en el servidor y elimina la cookie.
    """
    session_token = None
    if authorization and authorization.startswith("Bearer "):
        session_token = authorization.split("Bearer ", 1)[1].strip()
    elif x_sac_token:
        session_token = x_sac_token.strip()
    elif botsac_session:
        session_token = botsac_session.strip()

    if session_token and session_token in ACTIVE_SESSIONS:
        del ACTIVE_SESSIONS[session_token]

    response.delete_cookie(key="botsac_session", path="/")
    return {"status": "ok", "detail": "Sesión invalidada exitosamente en el servidor."}

@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["id_usuario"],
        "name": current_user["nombres_completos"],
        "role": "Líder de Oficina" if current_user["rol_principal"] == "LIDER_OFICINA" else "Funcionario",
        "rol_principal": current_user["rol_principal"]
    }

@app.get("/api/inbox")
def get_inbox(current_user: dict = Depends(get_current_user)):
    try:
        return services.get_inbox_data(user_account=current_user["id_usuario"])
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener bandeja: {str(e)}")

class ApproveRequest(BaseModel):
    notes: Optional[str] = None

@app.get("/api/inbox/archived")
def get_archived_inbox(current_user: dict = Depends(get_current_user)):
    try:
        from backend.oracle_service import get_archived_inbox_from_oracle
        return get_archived_inbox_from_oracle(user_account=current_user["id_usuario"])
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando archivo histórico: {str(e)}")

@app.post("/api/radicados/{radicado}/approve")
def approve_radicado(radicado: str, req: Optional[ApproveRequest] = None, current_user: dict = Depends(get_current_user)):
    if current_user.get("rol_principal") != "LIDER_OFICINA":
        raise HTTPException(status_code=403, detail="Acción restringida: solo un Líder de Oficina puede aprobar y despachar radicados institucionales.")
    try:
        from backend.oracle_service import approve_radicado_in_oracle
        notes = req.notes if req else None
        res = approve_radicado_in_oracle(
            radicado_id=radicado,
            user_account=current_user["id_usuario"],
            user_name=current_user["nombres_completos"],
            notes=notes
        )
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al aprobar radicado: {str(e)}")

@app.get("/api/radicados/{radicado}")
def get_radicado(radicado: str, current_user: dict = Depends(get_current_user)):
    try:
        detail = services.get_radicado_detail(radicado, user_account=current_user["id_usuario"])
        if not detail:
            raise HTTPException(status_code=404, detail="Radicado no encontrado")
        return detail
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando detalle: {str(e)}")

@app.get("/api/radicados/{radicado}/documents/{document_id}")
def get_document_meta(radicado: str, document_id: str, current_user: dict = Depends(get_current_user)):
    try:
        detail = services.get_radicado_detail(radicado, user_account=current_user["id_usuario"])
        if not detail:
            raise HTTPException(status_code=404, detail="Radicado no encontrado")
            
        for doc in detail.get("documents", []):
            if doc.get("id") == document_id or doc.get("sha256") == document_id or doc.get("filename") == document_id:
                return doc
                
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))

@app.get("/api/radicados/{radicado}/documents/{document_id}/view")
def view_document(radicado: str, document_id: str, current_user: dict = Depends(get_current_user)):
    try:
        resolved = services.get_document_file_path(radicado, document_id, user_account=current_user["id_usuario"])
        if not resolved:
            raise HTTPException(status_code=404, detail="Archivo visualizable no encontrado")
            
        file_path, display_name = resolved
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="El archivo físico no existe")
            
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=display_name,
            headers={"Content-Disposition": f'inline; filename="{display_name}"'}
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))

@app.post("/api/sync/lightweight")
def trigger_sync_lightweight(current_user: dict = Depends(get_current_user)):
    if current_user.get("rol_principal") != "LIDER_OFICINA":
        raise HTTPException(status_code=403, detail="Acción restringida: solo un Líder de Oficina puede sincronizar la bandeja institucional.")
    try:
        from scripts.sync_sac_por_aprobar_lightweight import sync_sac_por_aprobar_lightweight
        result = sync_sac_por_aprobar_lightweight(max_pages=2, headless=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en sincronización liviana: {str(e)}")

@app.post("/api/watchdog/run")
def trigger_watchdog_run(current_user: dict = Depends(get_current_user)):
    if current_user.get("rol_principal") != "LIDER_OFICINA":
        raise HTTPException(status_code=403, detail="Acción restringida: solo un Líder de Oficina puede ejecutar el Watchdog institucional.")
    try:
        from backend.watchdog_service import run_watchdog_sync
        u_id = current_user["id_usuario"]
        u_pass = INSTITUTIONAL_CREDENTIALS.get(u_id)
        result = run_watchdog_sync(max_pages=5, headless=True, sac_user=u_id, sac_pass=u_pass)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando Watchdog SAC: {str(e)}")

@app.post("/api/batch/process")
def trigger_batch_process(batch_size: int = 3, current_user: dict = Depends(get_current_user)):
    if current_user.get("rol_principal") != "LIDER_OFICINA":
        raise HTTPException(status_code=403, detail="Acción restringida: solo un Líder de Oficina puede procesar bloques de expedientes en masa.")
    try:
        from backend.batch_processor import process_batch_block
        u_id = current_user["id_usuario"]
        u_pass = INSTITUTIONAL_CREDENTIALS.get(u_id)
        result = process_batch_block(batch_size=batch_size, headless=True, sac_user=u_id, sac_pass=u_pass)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar bloque en Oracle: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=True)
