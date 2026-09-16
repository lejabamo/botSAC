import os
import json
import base64
import streamlit as st

st.set_page_config(page_title="BotSAC - Task Working", layout="wide")

ACQ = "ACQ-20260915-0001"
RAD = "CAU2026ER032723"
REVIEW_PATH = f"data/analysis/{ACQ}/{RAD}/botsac_review.json"
MANIFEST_PATH = f"data/analysis/{ACQ}/{RAD}/documents_manifest.json"

def load_data():
    if not os.path.exists(REVIEW_PATH):
        return None, {}
    with open(REVIEW_PATH, "r", encoding="utf-8") as f:
        review_data = json.load(f)
        
    hashes = {}
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            for d in manifest.get("documents", []):
                hashes[d["filename"]] = d["sha256"]
                
    return review_data, hashes

def display_pdf(file_path):
    if not os.path.exists(file_path):
        st.error("Archivo PDF no encontrado localmente.")
        return
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def deduplicate_dates(dates):
    dates = sorted(dates, key=len, reverse=True)
    unique_dates = []
    for d in dates:
        if not any(d.lower() in existing.lower() for existing in unique_dates):
            unique_dates.append(d)
    return unique_dates

def main():
    data, hashes = load_data()
    if not data:
        st.warning(f"No se encontró la ficha consolidada en: {REVIEW_PATH}")
        return

    if "viewing_doc" not in st.session_state:
        st.session_state.viewing_doc = None

    if st.session_state.viewing_doc:
        doc = st.session_state.viewing_doc
        doc_hash = hashes.get(doc.get("filename"), "Hash desconocido")
        short_hash = doc_hash[:8] + "..." + doc_hash[-8:] if len(doc_hash) > 16 else doc_hash
        
        st.button("⬅ Volver al Radicado", on_click=lambda: st.session_state.update(viewing_doc=None))
        
        st.subheader(doc.get("filename"))
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Páginas:** {len(doc.get('pages', []))}")
        c2.write("**Extracción:** Nativa/OCR")
        c3.write(f"**SHA-256:** `{short_hash}`")
        
        pdf_path = os.path.abspath(f"data/documents/{ACQ}/{RAD}/{doc.get('filename')}")
        display_pdf(pdf_path)
        return

    # PASO 5 - JERARQUÍA (1. Identificación)
    st.title("Revisión de Radicado")
    
    col_id1, col_id2 = st.columns([1, 2])
    col_id1.metric("Radicado", data.get("radicado"))
    col_id2.markdown(f"### {data.get('subject')}")
    
    st.markdown(f"**Solicitante:** {data.get('requester')} &nbsp;&nbsp;|&nbsp;&nbsp; **Municipio:** {data.get('municipality')}")
    st.divider()

    # 2. Resumen
    st.header("Resumen de la Solicitud")
    st.info(data.get("request_summary"))
    raw_dates = data.get("key_dates", [])
    if raw_dates:
        st.markdown("**Fechas clave:** " + ", ".join(deduplicate_dates(raw_dates)))

    st.divider()

    # 3. Estado de atención
    st.header("Estado de Atención")
    c_est1, c_est2 = st.columns(2)
    c_est1.markdown(f"**Estado SAC:** `{data.get('status_sac')}`")
    
    # Respuesta registrada determinista sin alarmas
    c_est2.markdown("**Registro de respuesta:**")
    c_est2.info("ℹ️ Sin respuesta registrada en la vista consultada")

    st.divider()

    # 4. Documentos
    st.header(f"Documentos Adjuntos ({len(data.get('documents', []))})")
    
    for doc in data.get("documents", []):
        with st.container(border=True):
            d_col1, d_col2 = st.columns([4, 1])
            with d_col1:
                # Nombre corto o truncado visualmente
                short_name = doc.get("filename")
                if len(short_name) > 60:
                    short_name = short_name[:57] + "..."
                st.subheader(f"📄 {short_name}")
                st.markdown(f"**Tipo:** {doc.get('document_type')} | **Páginas:** {len(doc.get('pages', []))} | **Extracción:** Nativa/OCR")
                st.write(doc.get("summary"))
            with d_col2:
                st.write("") # Spacer
                if st.button("ABRIR DOCUMENTO", key=f"btn_{doc.get('filename')}"):
                    st.session_state.viewing_doc = doc
                    st.rerun()

    st.divider()

    # 5. Alertas
    st.header("Alertas")
    alerts = [a for a in data.get("alerts", []) if a.get("type") != "Estado Asignado"]
    if not alerts:
        st.success("No hay alertas críticas de procesamiento.")
    else:
        for alert in alerts:
            st.error(f"**[{alert.get('type')}]** {alert.get('description')}")

    st.divider()

    # 6. Trazabilidad
    with st.expander("Ver trazabilidad técnica"):
        for trace in data.get("trace", []):
            st.markdown(f"- **{trace.get('source_type')}** (`{trace.get('source_ref')}`): {trace.get('detail')}")

if __name__ == "__main__":
    main()
