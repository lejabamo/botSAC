import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))
from app.api import app, ACTIVE_SESSIONS

@pytest.fixture
def client():
    return TestClient(app)

PASS_LJ = os.getenv("BOTSAC_PASS_LJBASTIDAS", "SuperS4c")
PASS_DJ = os.getenv("SAC_PASS", "Bucheli_123")
PASS_AD = os.getenv("BOTSAC_PASS_ADIAZ", "Cauca2026*")

def test_login_authentication_and_token_issuance(client):
    """Verifica autenticación oficial contra SAC_USUARIOS en Oracle con emisión de token de sesión."""
    # 1. Usuario real: ljbastidas con su contraseña oficial
    r_user = client.post("/api/auth/login", json={"username": "ljbastidas", "password": PASS_LJ})
    assert r_user.status_code == 200
    data_user = r_user.json()
    assert data_user["username"] == "ljbastidas"
    assert data_user["rol_principal"] == "LIDER_OFICINA"
    assert "token" in data_user
    assert len(data_user["token"]) > 20
    assert "Bastidas" in data_user["name"]
    # Token registrado en ACTIVE_SESSIONS del servidor
    assert data_user["token"] in ACTIVE_SESSIONS
    assert ACTIVE_SESSIONS[data_user["token"]]["username"] == "ljbastidas"

    # 1b. ljbastidas con contraseña errónea -> 401
    r_bad_pass = client.post("/api/auth/login", json={"username": "ljbastidas", "password": "WrongPassword"})
    assert r_bad_pass.status_code == 401
    assert "Contraseña incorrecta" in r_bad_pass.json()["detail"]

    # 2. Usuario djdelgado (Líder de Oficina) con su contraseña
    r_a = client.post("/api/auth/login", json={"username": "djdelgado", "password": PASS_DJ})
    assert r_a.status_code == 200
    data_a = r_a.json()
    assert data_a["username"] == "djdelgado"
    assert data_a["rol_principal"] == "LIDER_OFICINA"
    assert "token" in data_a
    assert "Delly" in data_a["name"] or "Delgado" in data_a["name"]

    # 3. Usuario adiaz (Funcionario) con su contraseña
    r_b = client.post("/api/auth/login", json={"username": "adiaz", "password": PASS_AD})
    assert r_b.status_code == 200
    data_b = r_b.json()
    assert data_b["username"] == "adiaz"
    assert data_b["rol_principal"] == "FUNCIONARIO"
    assert "token" in data_b
    assert "Diaz" in data_b["name"] or "Andrea" in data_b["name"]

    # 4. Usuario no registrado / inexistente -> 401
    r_fake = client.post("/api/auth/login", json={"username": "usuario_inexistente", "password": "AnyPassword"})
    assert r_fake.status_code == 401
    assert "no está registrado" in r_fake.json()["detail"].lower()

def test_unauthenticated_and_spoofed_requests_blocked(client):
    """Verifica que solicitudes sin token o con cabeceras falsificadas sean tajantemente rechazadas."""
    # 1. Petición anónima sin cabeceras
    r_none = client.get("/api/inbox")
    assert r_none.status_code == 401
    assert "Autenticación requerida" in r_none.json()["detail"]

    # 2. Intento de suplantación sin token enviando X-SAC-User: djdelgado -> DEBE SER 401
    r_spoof_dj = client.get("/api/inbox", headers={"X-SAC-User": "djdelgado"})
    assert r_spoof_dj.status_code == 401
    assert "Autenticación requerida" in r_spoof_dj.json()["detail"]

    # 3. Intento de suplantación sin token enviando X-SAC-User: ljbastidas -> DEBE SER 401
    r_spoof_lj = client.get("/api/inbox", headers={"X-SAC-User": "ljbastidas"})
    assert r_spoof_lj.status_code == 401
    assert "Autenticación requerida" in r_spoof_lj.json()["detail"]

    # 4. Intento de acceso mediante parámetro URL ?user=djdelgado -> DEBE SER 401
    r_query_user = client.get("/api/inbox?user=djdelgado")
    assert r_query_user.status_code == 401

    # 5. Token falso o fabricado por el cliente -> 401
    r_bad_token = client.get("/api/inbox", headers={"Authorization": "Bearer token_falso_inventado"})
    assert r_bad_token.status_code == 401
    assert "Sesión inválida" in r_bad_token.json()["detail"]

def test_cross_session_impersonation_blocked(client):
    """
    Verifica que un usuario con sesión válida de ljbastidas no pueda
    suplantar a djdelgado manipulando la cabecera X-SAC-User.
    """
    # Login legítimo de ljbastidas
    r_login = client.post("/api/auth/login", json={"username": "ljbastidas", "password": PASS_LJ})
    token_lj = r_login.json()["token"]

    # Petición enviando token de ljbastidas pero cabecera X-SAC-User: djdelgado -> 403 Forbidden
    r_spoof = client.get("/api/inbox", headers={
        "Authorization": f"Bearer {token_lj}",
        "X-SAC-User": "djdelgado"
    })
    assert r_spoof.status_code == 403
    assert "suplantación" in r_spoof.json()["detail"].lower()

def test_user_a_inbox_scope_lider(client):
    """Usuario djdelgado (Líder) supervisa la totalidad de la bandeja de su oficina con sesión validada."""
    r_login = client.post("/api/auth/login", json={"username": "djdelgado", "password": PASS_DJ})
    token = r_login.json()["token"]

    r = client.get("/api/inbox", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    res = r.json()
    assert res["user"] == "djdelgado"
    assert res["user_role"] == "LIDER_OFICINA"
    assert len(res["items"]) == 70

def test_user_b_inbox_scope_funcionario(client):
    """Usuario adiaz (Funcionario) tiene ámbito estrictamente personal."""
    r_login = client.post("/api/auth/login", json={"username": "adiaz", "password": PASS_AD})
    token = r_login.json()["token"]

    r = client.get("/api/inbox", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    res = r.json()
    assert res["user"] == "adiaz"
    assert res["user_role"] == "FUNCIONARIO"
    assert len(res["items"]) == 13

    # Comprobación negativa: Ningún caso de otro funcionario (ej. jclopez, hguaca, gmacias) debe figurar
    radicados_b = {it["radicado"] for it in res["items"]}
    for it in res["items"]:
        func = (it.get("funcionario") or "").upper()
        assert "DIAZ" in func or func == "ADIAZ"

    assert "CAU2026ER028340" not in radicados_b

def test_user_c_inbox_scope_real_user_ljbastidas(client):
    """Usuario real ljbastidas consulta su bandeja legítimamente en Oracle con sesión validada."""
    r_login = client.post("/api/auth/login", json={"username": "ljbastidas", "password": PASS_LJ})
    token = r_login.json()["token"]

    r = client.get("/api/inbox", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    res = r.json()
    assert res["user"] == "ljbastidas"
    assert res["user_role"] == "LIDER_OFICINA"
    assert "Bastidas" in res.get("user_name", "")

def test_radicado_detail_isolation(client):
    """Verifica que el endpoint de detalle no permita acceso cruzado a expedientes no autorizados."""
    r_login_ad = client.post("/api/auth/login", json={"username": "adiaz", "password": PASS_AD})
    token_ad = r_login_ad.json()["token"]

    r_login_dj = client.post("/api/auth/login", json={"username": "djdelgado", "password": PASS_DJ})
    token_dj = r_login_dj.json()["token"]

    r_login_lj = client.post("/api/auth/login", json={"username": "ljbastidas", "password": PASS_LJ})
    token_lj = r_login_lj.json()["token"]

    # 1. adiaz accede a su propio radicado -> 200 OK
    r_own = client.get("/api/radicados/CAU2026ER032549", headers={"Authorization": f"Bearer {token_ad}"})
    assert r_own.status_code == 200
    assert r_own.json()["radicado"] == "CAU2026ER032549"

    # 2. adiaz intenta acceder a radicado de hguaca (CAU2026ER028340) -> 403 Forbidden
    r_foreign = client.get("/api/radicados/CAU2026ER028340", headers={"Authorization": f"Bearer {token_ad}"})
    assert r_foreign.status_code == 403
    assert "Acceso denegado" in r_foreign.json()["detail"]

    # 3. ljbastidas intenta acceder a radicado de oficina de djdelgado (CAU2026ER028340) -> 403 Forbidden
    r_lj_foreign = client.get("/api/radicados/CAU2026ER028340", headers={"Authorization": f"Bearer {token_lj}"})
    assert r_lj_foreign.status_code == 403
    assert "Acceso denegado" in r_lj_foreign.json()["detail"]

    # 4. djdelgado (Líder supervisora de esa oficina) accede a CAU2026ER028340 -> 200 OK
    r_leader = client.get("/api/radicados/CAU2026ER028340", headers={"Authorization": f"Bearer {token_dj}"})
    assert r_leader.status_code == 200
    assert r_leader.json()["radicado"] == "CAU2026ER028340"

    # 5. Solicitud anónima al detalle (sin cookies ni token) -> 401 Unauthorized
    client.cookies.clear()
    r_anon = client.get("/api/radicados/CAU2026ER032549")
    assert r_anon.status_code == 401

def test_document_download_isolation(client):
    """Verifica que el visor y descarga de documentos impida acceso cruzado."""
    r_login_ad = client.post("/api/auth/login", json={"username": "adiaz", "password": PASS_AD})
    token_ad = r_login_ad.json()["token"]

    r_login_lj = client.post("/api/auth/login", json={"username": "ljbastidas", "password": PASS_LJ})
    token_lj = r_login_lj.json()["token"]

    # adiaz intentando ver documento de radicado ajeno por header -> 403
    r_doc_forbidden = client.get(
        "/api/radicados/CAU2026ER028340/documents/doc_test/view",
        headers={"Authorization": f"Bearer {token_ad}"}
    )
    assert r_doc_forbidden.status_code == 403

    # ljbastidas intentando ver documento con parámetro ?token= -> 403
    r_doc_lj = client.get(f"/api/radicados/CAU2026ER028340/documents/doc_test/view?token={token_lj}")
    assert r_doc_lj.status_code == 403

    # Anónimo intentando ver documento sin token -> 401
    client.cookies.clear()
    r_doc_anon = client.get("/api/radicados/CAU2026ER032549/documents/doc_test/view")
    assert r_doc_anon.status_code == 401

def test_server_logout_invalidates_session(client):
    """Verifica que el cierre de sesión destruya la sesión en el servidor y rechace usos posteriores."""
    # 1. Login
    r_login = client.post("/api/auth/login", json={"username": "ljbastidas", "password": PASS_LJ})
    assert r_login.status_code == 200
    token = r_login.json()["token"]

    # 2. Petición autenticada exitosa
    r_auth = client.get("/api/inbox", headers={"Authorization": f"Bearer {token}"})
    assert r_auth.status_code == 200

    # 3. Cerrar sesión en el servidor
    r_logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r_logout.status_code == 200
    assert "Sesión invalidada" in r_logout.json()["detail"]

    # 4. Token ya no existe en el servidor
    assert token not in ACTIVE_SESSIONS

    # 5. Petición posterior con el mismo token -> 401 Unauthorized
    r_post_logout = client.get("/api/inbox", headers={"Authorization": f"Bearer {token}"})
    assert r_post_logout.status_code == 401
    assert "Sesión inválida" in r_post_logout.json()["detail"]
