import streamlit as st
import json
import os
import time
import subprocess
import sys
import scripts.queue_manager as qm

st.set_page_config(page_title="BotSAC - Bandeja de Trabajo", layout="wide", initial_sidebar_state="collapsed")

INBOX_PATH = "data/dashboard_inbox.json"

def load_inbox():
    if os.path.exists(INBOX_PATH):
        with open(INBOX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def get_last_update():
    if os.path.exists(INBOX_PATH):
        t = os.path.getmtime(INBOX_PATH)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))
    return "Nunca"

def load_radicado_data(radicado_id):
    ACQ_ID = "ACQ-20260915-0001"
    base_dir = f"data/analysis/{ACQ_ID}/{radicado_id}"
    
    if not os.path.exists(f"{base_dir}/botsac_review.json"):
        return False, {}, None, None, None
        
    with open(f"{base_dir}/botsac_review.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    hashes = {}
    if os.path.exists(f"{base_dir}/documents_manifest.json"):
        with open(f"{base_dir}/documents_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
            docs_list = manifest.get("documents", []) if isinstance(manifest, dict) else manifest
            for doc in docs_list:
                fname = doc.get("filename", doc.get("original_name", ""))
                hashes[fname] = doc.get("sha256", "")
                
    req_analysis = None
    if os.path.exists(f"{base_dir}/request_analysis.json"):
        with open(f"{base_dir}/request_analysis.json", "r", encoding="utf-8") as f:
            req_analysis = json.load(f)
            
    micro_analyses = {}
    for fname in os.listdir(base_dir):
        if fname.startswith("document_micro_analysis_"):
            h = fname.split("_")[-1].replace(".json", "")
            with open(f"{base_dir}/{fname}", "r", encoding="utf-8") as f:
                micro_analyses[h] = json.load(f)
                
    raw_content = ""
    if os.path.exists(f"{base_dir}/raw/metadata_sac.json"):
        with open(f"{base_dir}/raw/metadata_sac.json", "r", encoding="utf-8") as f:
            raw_content = json.dumps(json.load(f), indent=2, ensure_ascii=False)
            
    return True, data, hashes, req_analysis, micro_analyses, raw_content

def display_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        st.error("No se encontró el documento PDF.")
        return
    import base64
    with open(pdf_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def view_inbox():
    st.markdown("<h2 style='margin-bottom:0;'>Bandeja de trabajo</h2>", unsafe_allow_html=True)
    st.caption(f"Sub-Dependencia: Infraestructura Educativa | Última actualización: {get_last_update()}")
    
    col_sync, _ = st.columns([1, 4])
    with col_sync:
        if st.button("Actualizar bandeja", use_container_width=True):
            with st.spinner("Sincronizando radicados..."):
                subprocess.run([sys.executable, "scripts/sync_inbox.py"])
            st.rerun()
            
    inbox_data = load_inbox()
    if not inbox_data:
        st.warning("No se encontraron radicados en la bandeja.")
        return

    # Metrics
    queue_status = qm.get_all_status()
    
    listos, preparando, errores = 0, 0, 0
    radicados_estado = {}
    
    ACQ_ID = "ACQ-20260915-0001"
    for rad in inbox_data:
        r_id = rad.get("radicado")
        q_info = queue_status.get(r_id, {})
        raw_estado = q_info.get("estado", "PENDIENTE")
        
        has_analysis = os.path.exists(f"data/analysis/{ACQ_ID}/{r_id}/botsac_review.json")
        if has_analysis:
            visible_estado = "LISTO"
            listos += 1
        elif raw_estado in ["ERROR"]:
            visible_estado = "ERROR"
            errores += 1
        else:
            visible_estado = "PREPARANDO"
            preparando += 1
            
        radicados_estado[r_id] = visible_estado

    st.markdown(f"<div style='background-color:#f1f5f9; padding: 10px 15px; border-radius:6px; font-weight:600; color:#334155; margin-bottom:20px; font-size:1.05rem;'>{len(inbox_data)} pendientes SAC &nbsp;|&nbsp; <span style='color:#10b981;'>{listos} listos</span> &nbsp;|&nbsp; <span style='color:#f59e0b;'>{preparando} preparando</span> &nbsp;|&nbsp; <span style='color:#ef4444;'>{errores} error</span></div>", unsafe_allow_html=True)

    # UI Style
    st.markdown("""
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.inbox-card-marker) {
            position: relative;
            background-color: white;
            transition: all 0.2s;
            padding: 0 !important;
            margin-bottom: 12px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.inbox-card-marker):hover {
            border-color: #10b981 !important;
            background-color: #f0fdf4 !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.inbox-card-disabled):hover {
            border-color: #e5e7eb !important;
            background-color: #f9fafb !important;
            box-shadow: none;
        }
        /* Remover padding global no deseado */
        .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px; }
        .top-stats {
            background-color: #f8fafc;
            padding: 8px 15px;
            border-radius: 6px;
            font-size: 0.9rem;
            color: #475569;
            margin-bottom: 15px;
            display: flex;
            gap: 20px;
        }
        
        div.stButton > button {
            width: 100%;
            height: auto !important;
            padding: 18px 20px !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 8px !important;
            background-color: #ffffff !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            justify-content: flex-start !important;
            text-align: left !important;
            transition: all 0.1s !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
            margin-bottom: 4px !important;
        }
        div.stButton > button:hover {
            border-color: #10b981 !important;
            background-color: #f0fdf4 !important;
            box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.1) !important;
        }
        div.stButton > button:disabled {
            background-color: #f9fafb !important;
            cursor: not-allowed !important;
        }
        
        /* Asegurar que los contenedores internos del botón tengan 100% de ancho y alineación izquierda */
        div.stButton > button > div {
            width: 100% !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
        }
        div.stButton > button > div > span {
            width: 100% !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
        }
        div.stButton > button div[data-testid="stMarkdownContainer"] {
            width: 100% !important;
            text-align: left !important;
        }
        div.stButton > button p {
            text-align: left !important;
            width: 100% !important;
            margin: 0 !important;
            white-space: pre-wrap !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    for idx, rad in enumerate(inbox_data):
        r_id = rad.get("radicado")
        estado_visible = radicados_estado.get(r_id, "PREPARANDO")
        
        vencido_str = "🔴 VENCIDO\n\n" if "VENCIDO" in str(rad.get("dias_plazo", "")).upper() else ""
        estado_icon = "✅" if estado_visible == "LISTO" else "❌" if estado_visible == "ERROR" else "⏳"
        
        resumen_preview = ""
        stats_preview_str = ""
        
        if estado_visible == "LISTO":
            has_data, data, hashes, req_analysis, micro_analyses, _ = load_radicado_data(r_id)
            if has_data:
                sum_text = req_analysis.get('summary', '') if req_analysis else data.get('request_summary', '')
                if sum_text:
                    resumen_preview = sum_text[:180] + ('...' if len(sum_text) > 180 else '')
                else:
                    resumen_preview = "Sin análisis detallado."
                
                docs_count = len(data.get("documents", []))
                hallazgos_count = 0
                if micro_analyses:
                    for m in micro_analyses.values():
                        if isinstance(m, dict) and m.get("key_facts"):
                            hallazgos_count += len([f for f in m["key_facts"] if f != "No identificado"])
                alerts_count = len(data.get("alerts", []))
                
                stats_preview_str = f"{docs_count} documentos · {hallazgos_count} hallazgos · {alerts_count} alertas"

        asunto_str = str(rad.get('asunto', 'N/A')).upper()
        municipio = rad.get("municipio", "No disponible")
        funcionario = rad.get("funcionario", "No disponible")
        
        if estado_visible == "PREPARANDO":
            resumen_preview = "BotSAC está preparando este radicado en segundo plano..."
        elif estado_visible == "ERROR":
            resumen_preview = "Hubo un error preparando este radicado. Haz clic para reintentar."

        # Construcción del texto Markdown para el botón
        label = f"**{r_id}**  ·  {estado_icon} {estado_visible}\n\n"
        if vencido_str: label += vencido_str
        label += f"**{asunto_str}**\n\n"
        label += f"{municipio} · {funcionario}\n\n"
        label += f"{resumen_preview}\n\n"
        if stats_preview_str: label += f"{stats_preview_str}"
        
        if estado_visible == "LISTO":
            if st.button(label, key=f"btn_{r_id}", use_container_width=True):
                st.session_state.active_radicado = r_id
                st.session_state.current_view = "DETAIL"
                st.session_state.inbox_metadata = rad
                st.rerun()
        elif estado_visible == "PREPARANDO":
            st.button(label, key=f"btn_{r_id}", use_container_width=True, disabled=True)
        elif estado_visible == "ERROR":
            if st.button(label, key=f"btn_{r_id}", use_container_width=True):
                qm.update_status(r_id, "PENDIENTE", error_detail="Reintento manual", add_intent=False)
                st.rerun()

def view_detail():
    radicado_id = st.session_state.active_radicado
    inbox_metadata = st.session_state.get("inbox_metadata", {})
    
    st.markdown("""
        <style>
        .detail-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8px; }
        .detail-title { font-size: 1.6rem; font-weight: 800; color: #111827; margin:0; line-height:1.2; }
        .detail-subject { font-size: 1.1rem; font-weight: 600; color: #374151; margin-top:2px; }
        .detail-meta { font-size: 0.85rem; color: #4b5563; text-align: right; }
        .alert-strip { background-color: #f1f5f9; padding: 6px 12px; border-radius: 4px; border: 1px solid #e2e8f0; font-size: 0.85rem; font-weight: 700; color: #334155; margin-bottom: 12px; }
        
        div[data-testid="column"]:nth-of-type(1) { padding-right: 15px; }
        div[data-testid="column"]:nth-of-type(2) { border-left: 1px solid #e2e8f0; padding-left: 20px; }
        
        .section-title { font-size: 0.85rem; font-weight: 800; color: #475569; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #f1f5f9; padding-bottom: 4px; }
        .fact-bullet { font-size: 0.9rem; color: #1f2937; margin-bottom: 6px; line-height: 1.4; }
        .fact-bullet b { color: #0f172a; }
        
        /* Estilos de los botones nativos para que parezcan tarjetas compactas */
        div.stButton > button {
            width: 100%;
            height: auto !important;
            padding: 12px 15px !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 6px !important;
            background-color: #ffffff !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            justify-content: flex-start !important;
            text-align: left !important;
            transition: all 0.1s !important;
            margin-bottom: 4px !important;
        }
        div.stButton > button:hover {
            border-color: #10b981 !important;
            background-color: #f0fdf4 !important;
        }
        div.stButton > button > div {
            width: 100% !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
        }
        div.stButton > button > div > span {
            width: 100% !important;
            display: flex !important;
            justify-content: flex-start !important;
            align-items: flex-start !important;
        }
        div.stButton > button div[data-testid="stMarkdownContainer"] {
            width: 100% !important;
            text-align: left !important;
        }
        div.stButton > button p {
            text-align: left !important;
            width: 100% !important;
            margin: 0 !important;
            white-space: pre-wrap !important;
            line-height: 1.4 !important;
        }
        
        p { margin-bottom: 10px !important; }
        </style>
    """, unsafe_allow_html=True)
    # NAVIGATION
    c_nav1, c_nav2, c_nav3 = st.columns([1, 8, 1])
    with c_nav2:
        if st.button("🏠 Bandeja", use_container_width=True):
            st.session_state.current_view = "INBOX"
            st.session_state.viewing_doc = None
            st.rerun()

    # LOAD DATA
    has_data, data, hashes, req_analysis, micro_analyses, raw_content = load_radicado_data(radicado_id)
    if not has_data:
        st.error("No se encontraron los datos de análisis para este radicado.")
        return
    
    ACQ = ""
    for d in os.listdir("data/documents"):
        if os.path.exists(f"data/documents/{d}/{radicado_id}"): ACQ = d; break

    # VISOR DOCUMENTAL FULL-SCREEN OVERRIDE
    if st.session_state.get("viewing_doc"):
        doc = st.session_state.viewing_doc
        doc_hash = hashes.get(doc.get("filename"), "Hash_Desconocido")
        st.button("⬅ Volver al Resumen", on_click=lambda: st.session_state.update(viewing_doc=None))
        st.subheader(doc.get("filename"))
        
        ext = os.path.splitext(doc.get("filename", ""))[1].lower()
        if ext in [".doc", ".docx"] or doc.get("document_type", "").lower() == "word":
            pdf_path = os.path.abspath(f"data/analysis/{ACQ}/{radicado_id}/documents/{doc_hash}_derivado.pdf")
            if not os.path.exists(pdf_path):
                st.info("No se encontró el PDF derivado para este documento Word.")
                return
        else:
            pdf_path = os.path.abspath(f"data/documents/{ACQ}/{radicado_id}/{doc.get('filename')}")
            
        display_pdf(pdf_path)
        return

    # PREPARE DATA
    subject = data.get("subject") if data else inbox_metadata.get("asunto", "N/A")
    estado = data.get("status_sac") if data else inbox_metadata.get("estado", "N/A")
    plazo = data.get("plazo") if data and data.get("plazo") else (inbox_metadata.get("dias_plazo", "") or "N/A")
    municipality = data.get("municipality") if data else inbox_metadata.get("municipio", "Pendiente")
    assigned = inbox_metadata.get("asignado", "") or inbox_metadata.get("funcionario", "N/A")
    fecha_c = inbox_metadata.get("fecha_creacion", "N/A")
    
    docs = data.get("documents", [])
    alerts = data.get("alerts", [])
    
    hallazgos_count = 0
    all_facts = []
    if micro_analyses:
        for dh, m in micro_analyses.items():
            if isinstance(m, dict) and m.get("key_facts"):
                facts = [f for f in m["key_facts"] if f != "No identificado"]
                hallazgos_count += len(facts)
                all_facts.extend([(dh, f) for f in facts])

    # HEADER
    st.markdown(f"""
    <div class="detail-header">
        <div>
            <div class="detail-title">{radicado_id}</div>
            <div class="detail-subject">{str(subject).upper()}</div>
        </div>
        <div class="detail-meta">
            Estado SAC: <b>{estado}</b><br/>
            Funcionario: {assigned}<br/>
            {fecha_c}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # STRIP COMPACTA
    strip_items = []
    if "VENCIDO" in str(plazo).upper(): strip_items.append("🔴 VENCIDO")
    if not req_analysis or "SIN RESPUESTA" in str(estado).upper(): strip_items.append("⚠️ SIN RESPUESTA")
    strip_items.append(f"{len(docs)} DOCUMENTOS")
    strip_items.append(f"{hallazgos_count} HALLAZGOS")
    for a in alerts:
        strip_items.append(f"🚩 {a.get('type')}")
        
    st.markdown(f"<div class='alert-strip'>{' &middot; '.join(strip_items)}</div>", unsafe_allow_html=True)
    
    # COLUMNAS 44% / 56%
    col_izq, col_der = st.columns([44, 56])
    
    with col_izq:
        st.markdown("<div class='section-title'>RESUMEN EJECUTIVO</div>", unsafe_allow_html=True)
        if req_analysis:
            st.markdown(f"<p style='font-size:0.95rem; line-height:1.4;'>{req_analysis.get('summary', '')}</p>", unsafe_allow_html=True)
            if req_analysis.get('requests'):
                st.markdown("<div class='section-title' style='margin-top:10px;'>SOLICITA</div>", unsafe_allow_html=True)
                for req in req_analysis.get('requests', []):
                    st.markdown(f"<div class='fact-bullet'>• {req}</div>", unsafe_allow_html=True)
        else:
            st.write(data.get("request_summary", "Sin análisis detallado."))
            
        st.markdown("<div class='section-title' style='margin-top:12px;'>DATOS CLAVE</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='fact-bullet'>• Municipio: <b>{municipality}</b></div>", unsafe_allow_html=True)
        if data.get("requester"):
            st.markdown(f"<div class='fact-bullet'>• Remitente: <b>{data.get('requester')}</b></div>", unsafe_allow_html=True)
            
        if all_facts:
            st.markdown("<div class='section-title' style='margin-top:12px;'>HALLAZGOS CLAVE</div>", unsafe_allow_html=True)
            for dh, fact in all_facts[:6]:
                doc_name = next((d.get("filename") for d in docs if hashes.get(d.get("filename")) == dh), "Documento")
                short_name = doc_name[:20] + "..." if len(doc_name) > 20 else doc_name
                st.markdown(f"<div class='fact-bullet'>◆ {fact} <span style='font-size:0.75rem; color:#9ca3af;'>({short_name})</span></div>", unsafe_allow_html=True)
        
    with col_der:
        st.markdown("<div class='section-title'>DOCUMENTOS ADJUNTOS</div>", unsafe_allow_html=True)
        if not docs:
            st.info("Sin documentos")
        else:
            for i, doc in enumerate(docs):
                fname = doc.get("filename", "")
                dhash = hashes.get(fname, "")
                micro = micro_analyses.get(dhash, {})
                tipo = micro.get('document_type', doc.get('document_type', 'Desconocido'))
                paginas = len(doc.get("pages", [1]))
                
                label_doc = f"📄 **{fname}**\n\n{tipo.upper()} · {paginas} página{'s' if paginas!=1 else ''} · ✅ Preparado"
                
                if st.button(label_doc, key=f"doc_{dhash}", use_container_width=True):
                    st.session_state.viewing_doc = doc
                    st.rerun()

    st.write("")
    with st.expander("Evidencia y trazabilidad ▸"):
        if data and data.get("trace"):
            for trace in data.get("trace", []):
                st.markdown(f"- **{trace.get('source_type')}**: {trace.get('detail')}")
                
    with st.expander("Contenido original SAC ▸"):
        st.markdown(f"<div style='font-family: monospace; white-space: pre-wrap; font-size: 0.85rem;'>{raw_content}</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    query_params = st.query_params
    if "rad" in query_params:
        if "current_view" not in st.session_state or st.session_state.active_radicado != query_params["rad"]:
            st.session_state.current_view = "DETAIL"
            st.session_state.active_radicado = query_params["rad"]
            
    if "current_view" not in st.session_state: st.session_state.current_view = "INBOX"
    if "active_radicado" not in st.session_state: st.session_state.active_radicado = None
    if "viewing_doc" not in st.session_state: st.session_state.viewing_doc = None

    if st.session_state.current_view == "INBOX": view_inbox()
    elif st.session_state.current_view == "DETAIL": view_detail()
