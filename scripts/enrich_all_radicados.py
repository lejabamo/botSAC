import os
import sys
import json
import glob
import re

sys.path.insert(0, os.path.abspath("."))

from botsac.analysis.document_extractor import (
    extract_municipalities,
    extract_requester,
    extract_dates,
    extract_radicado_knowledge,
    extract_institutions
)

ACQ = "ACQ-20260915-0001"
BASE_DIR = f"data/analysis/{ACQ}"
INBOX_FILE = "data/dashboard_inbox.json"

def find_custom_doc_info(fname: str, doc_map: dict):
    if not doc_map:
        return None
    if fname in doc_map:
        return doc_map[fname]
    norm_f = re.sub(r'[^a-zA-Z0-9]', '', fname.lower())
    for k, v in doc_map.items():
        norm_k = re.sub(r'[^a-zA-Z0-9]', '', k.lower())
        if norm_f == norm_k or norm_k in norm_f or norm_f in norm_k:
            return v
    if "correo" in fname.lower():
        for k, v in doc_map.items():
            if "correo" in k.lower():
                return v
    if any(w in fname.lower() for w in ["oficio", "reporte", "informe", "solicitud", "riesgo", "anexo"]):
        for k, v in doc_map.items():
            if any(w in k.lower() for w in ["oficio", "reporte", "informe", "solicitud", "riesgo", "anexo"]):
                return v
    return None

def enrich_all():
    print(f"=== INICIANDO ENRIQUECIMIENTO DOCUMENTAL BOTSAC PARA {ACQ} ===")
    
    if not os.path.exists(BASE_DIR):
        print(f"[ERROR] Directorio {BASE_DIR} no existe.")
        return
        
    radicados = sorted([r for r in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, r))])
    print(f"Radicados encontrados: {len(radicados)}")
    
    inbox_map = {}
    if os.path.exists(INBOX_FILE):
        with open(INBOX_FILE, "r", encoding="utf-8") as f:
            inbox_list = json.load(f)
            for item in inbox_list:
                inbox_map[item.get("radicado")] = item

    for rad in radicados:
        rad_dir = os.path.join(BASE_DIR, rad)
        doc_dir = os.path.join(rad_dir, "documents")
        
        # 1. Gather all documents text
        docs = []
        if os.path.exists(doc_dir):
            for f in sorted(glob.glob(os.path.join(doc_dir, "*.json"))):
                if "_conversion" in f:
                    continue
                try:
                    with open(f, "r", encoding="utf-8") as jf:
                        d = json.load(jf)
                        doc_info = d.get("document", {})
                        fname = doc_info.get("filename", os.path.basename(f))
                        dhash = doc_info.get("sha256", os.path.splitext(os.path.basename(f))[0].replace("_ocr", ""))
                        pages = d.get("pages", [])
                        text = "\n".join([p.get("text", "") for p in pages])
                        if text.strip():
                            docs.append({
                                "filename": fname,
                                "sha256": dhash,
                                "text": text,
                                "pages_count": len(pages),
                                "is_ocr": "_ocr" in f
                            })
                except Exception as e:
                    print(f"  [WARN] Error leyendo {f}: {e}")
                    
        combined_text = "\n\n".join([d["text"] for d in docs])
        email_text = "\n".join([d["text"] for d in docs if "correo" in d["filename"].lower()])
        
        # Include solicitud.txt if present
        solicitud_path = os.path.join(f"data/raw/{ACQ}/{rad}", "solicitud.txt")
        if os.path.exists(solicitud_path):
            with open(solicitud_path, "r", encoding="utf-8") as sf:
                sol_text = sf.read()
                combined_text += f"\n\n=== SOLICITUD.TXT ===\n{sol_text}"
                if not email_text:
                    email_text = sol_text

        inbox_item = inbox_map.get(rad, {})
        OFFICIAL_ASSIGNMENTS = {
            "CAU2026ER034611": "ANDREA VANESSA DIAZ CHAMORRO",
            "CAU2026ER032549": "ANDREA VANESSA DIAZ CHAMORRO",
            "CAU2026ER032723": "HUGO EMIRO GUACA GIRON",
            "CAU2026ER023281": "JUAN MANUEL BRAVO REALPE",
            "CAU2026ER032558": "GINNA MARCELA MACIAS MARTINEZ",
            "CAU2026ER032204": "GINNA MARCELA MACIAS MARTINEZ",
            "CAU2026ER032277": "GINNA MARCELA MACIAS MARTINEZ",
            "CAU2026ER032385": "JAIRO CLAUDIO LOPEZ",
            "CAU2026ER032305": "HUGO EMIRO GUACA GIRON",
            "CAU2026ER032164": "CRISTHIAN GERARDO GUZMAN MELLIZO",
            "CAU2026ER031812": "HUGO EMIRO GUACA GIRON",
            "CAU2026ER023971": "HAMER EDUARDO ACOSTA RENGIFO",
            "CAU2026ER020962": "ANDRES ERNESTO RENGIFO RENGIFO"
        }
        official_func = OFFICIAL_ASSIGNMENTS.get(rad, inbox_item.get("funcionario", "ANDREA VANESSA DIAZ CHAMORRO"))

        munis = extract_municipalities(combined_text, default_muni)
        sender = extract_requester(combined_text, email_text, default_req)
        dates = extract_dates(combined_text)
        knowledge = extract_radicado_knowledge(rad, combined_text, munis, sender, funcionario=official_func)
        
        muni_str = ", ".join(munis) if munis else "Pendiente"
        category = knowledge.get("category", "Mantenimiento e Infraestructura")
        instituciones_sedes = knowledge.get("instituciones_sedes", [])
        doc_summaries_map = knowledge.get("doc_summaries", {})
        
        # 2. Update request_analysis.json
        req_file = os.path.join(rad_dir, "request_analysis.json")
        req_data = {
            "category": category,
            "problem": "Afectación por sismo / deterioro de infraestructura escolar",
            "location": muni_str,
            "institution": ", ".join([inst.get("institucion", "") for inst in instituciones_sedes]),
            "instituciones_sedes": instituciones_sedes,
            "requests": knowledge["requests"],
            "summary": knowledge["summary"]
        }
        with open(req_file, "w", encoding="utf-8") as f:
            json.dump(req_data, f, ensure_ascii=False, indent=2)
            
        # 3. Update document_micro_analysis files
        manifest_path = os.path.join(rad_dir, "documents_manifest.json")
        manifest_docs = []
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest_data = json.load(mf)
                manifest_docs = manifest_data.get("documents", []) if isinstance(manifest_data, dict) else manifest_data

        for mdoc in manifest_docs:
            dhash = mdoc.get("sha256")
            fname = mdoc.get("filename", "")
            micro_file = os.path.join(rad_dir, f"document_micro_analysis_{dhash}.json")
            
            # Find matching doc findings
            doc_findings = [f["fact"] for f in knowledge["findings"] if fname in f.get("source_doc", "") or f.get("source_doc", "") in fname]
            if not doc_findings:
                doc_findings = [f["fact"] for f in knowledge["findings"]]
                
            custom_doc_info = find_custom_doc_info(fname, doc_summaries_map)

            if custom_doc_info:
                doc_type = custom_doc_info.get("document_type", "Documento Técnico")
                doc_sum = custom_doc_info.get("summary", f"Documento oficial '{fname}' relativo a {muni_str}.")
            else:
                doc_type = "Informe de Afectaciones por Sismo" if "sismo" in fname.lower() or "sismo" in combined_text.lower() else "Documento Técnico Adjunto"
                if "correo" in fname.lower():
                    doc_type = "Correo Electrónico de Remisión Oficial"
                elif "oficio" in fname.lower():
                    doc_type = "Oficio Remisorio Oficial"
                elif "derecho" in fname.lower() or "peticion" in fname.lower():
                    doc_type = "Derecho de Petición"
                elif "riesgo" in fname.lower():
                    doc_type = "Reporte de Situación de Riesgo Escolar"
                doc_sum = f"Documento oficial '{fname}' aportado al expediente de {muni_str} para revisión de infraestructura."

            micro_data = {
                "document_type": doc_type,
                "summary": doc_sum,
                "key_facts": doc_findings if doc_findings else [f"Documento {fname} analizado."],
                "dates": dates[:3] if dates else ["2026"],
                "pages_referenced": [1]
            }
            with open(micro_file, "w", encoding="utf-8") as f:
                json.dump(micro_data, f, ensure_ascii=False, indent=2)

        # 4. Update botsac_review.json
        review_file = os.path.join(rad_dir, "botsac_review.json")
        if os.path.exists(review_file):
            with open(review_file, "r", encoding="utf-8") as rf:
                rev_data = json.load(rf)
                
            rev_data["municipality"] = muni_str
            rev_data["requester"] = sender
            rev_data["category"] = category
            rev_data["request_summary"] = knowledge["summary"]
            rev_data["instituciones_sedes"] = instituciones_sedes
            rev_data["key_dates"] = dates[:3]
            
            # Update review documents with real summary & doc_type
            for rdoc in rev_data.get("documents", []):
                fn = rdoc.get("filename", "")
                custom_info = find_custom_doc_info(fn, doc_summaries_map)
                            
                if custom_info:
                    rdoc["document_type"] = custom_info.get("document_type", rdoc.get("document_type", "Documento"))
                    rdoc["summary"] = custom_info.get("summary", "")
                else:
                    if "correo" in fn.lower():
                        rdoc["document_type"] = "Correo de Remisión"
                        rdoc["summary"] = f"Remisión oficial del expediente institucional de {muni_str}."
                    elif "sismo" in fn.lower():
                        rdoc["document_type"] = "Reporte de Afectaciones por Sismo"
                        rdoc["summary"] = f"Informe de daños y averías por eventos sísmicos en {muni_str}."
                    elif "riesgo" in fn.lower():
                        rdoc["document_type"] = "Reporte de Riesgo Escolar"
                        rdoc["summary"] = f"Diagnóstico de riesgo escolar en sedes educativas de {muni_str}."
                    elif "oficio" in fn.lower():
                        rdoc["document_type"] = "Oficio Remisorio"
                        rdoc["summary"] = f"Oficio remitido a las autoridades educativas sobre la situación en {muni_str}."
                    elif "derecho" in fn.lower() or "peticion" in fn.lower():
                        rdoc["document_type"] = "Derecho de Petición"
                        rdoc["summary"] = "Acción formal en derecho solicitando intervención urgente."
                    else:
                        rdoc["document_type"] = "Documento Técnico Adjunto"
                        rdoc["summary"] = f"Anexo técnico de soporte para {muni_str}."
                    
            rev_data["etapa_tramite"] = knowledge.get("etapa_tramite", "SIN_DILIGENCIAR")
            rev_data["etapa_label"] = knowledge.get("etapa_label", "Sin Diligenciar")
            
            with open(review_file, "w", encoding="utf-8") as rf:
                json.dump(rev_data, rf, ensure_ascii=False, indent=2)
                
        # 5. Update inbox item
        if rad in inbox_map:
            inbox_map[rad]["municipio"] = muni_str
            inbox_map[rad]["remitente"] = sender
            inbox_map[rad]["categoria"] = category
            inbox_map[rad]["instituciones_sedes"] = instituciones_sedes
            inbox_map[rad]["etapa_tramite"] = knowledge.get("etapa_tramite", "SIN_DILIGENCIAR")
            inbox_map[rad]["etapa_label"] = knowledge.get("etapa_label", "Sin Diligenciar")
            
        print(f"  [OK] {rad}: Cat={category} | Muni={muni_str} | Etapa={knowledge.get('etapa_tramite')} | Sedes={len(instituciones_sedes)}")

    # Save updated inbox
    if inbox_map and os.path.exists(INBOX_FILE):
        new_inbox_list = list(inbox_map.values())
        with open(INBOX_FILE, "w", encoding="utf-8") as f:
            json.dump(new_inbox_list, f, ensure_ascii=False, indent=2)
        print(f"  [OK] Actualizado {INBOX_FILE} con municipios, remitentes y categorías extraídas.")
        
    print(f"\n=== ENRIQUECIMIENTO COMPLETADO EXITOSAMENTE PARA {len(radicados)} RADICADOS ===")

if __name__ == "__main__":
    enrich_all()
