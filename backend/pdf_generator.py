import os
import sys
from typing import Optional
import pymupdf

def generate_official_response_pdf(radicado_id: str, response_text: str, output_path: str, funcionario: str = "") -> str:
    """
    Genera un documento PDF oficial institucional a partir del borrador de respuesta
    proyectado por el funcionario en SAC.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = pymupdf.open()
    
    # Dimensiones A4 (595 x 842 puntos)
    page_w, page_h = 595, 842
    margin_x = 54
    top_margin = 60
    bottom_margin = 60
    usable_w = page_w - (2 * margin_x)
    usable_h = page_h - top_margin - bottom_margin

    # Limpiar y preparar texto
    clean_text = response_text.replace('\r\n', '\n').strip()
    
    # Dividir texto en párrafos
    paragraphs = clean_text.split('\n')
    
    page = doc.new_page(width=page_w, height=page_h)
    
    # Encabezado institucional
    page.insert_text((margin_x, 50), "GOBERNACIÓN DEL DEPARTAMENTO DEL CAUCA", fontsize=11, fontname="helv", color=(0.08, 0.2, 0.38))
    page.insert_text((margin_x, 63), "SECRETARÍA DE EDUCACIÓN Y CULTURA - SUBPROCESO DE INFRAESTRUCTURA", fontsize=8.5, fontname="helv", color=(0.35, 0.35, 0.35))
    page.draw_line((margin_x, 70), (page_w - margin_x, 70), color=(0.12, 0.3, 0.55), width=1.5)
    
    # Badge oficial
    badge_rect = pymupdf.Rect(page_w - margin_x - 180, 42, page_w - margin_x, 64)
    page.draw_rect(badge_rect, color=(0.12, 0.5, 0.35), fill=(0.93, 0.98, 0.95), width=0.8)
    page.insert_text((page_w - margin_x - 172, 56), f"PROYECTO OFICIAL SAC: {radicado_id}", fontsize=7.5, fontname="helv", color=(0.12, 0.5, 0.35))

    # Área de contenido
    content_rect = pymupdf.Rect(margin_x, 90, page_w - margin_x, page_h - 75)
    
    # Insertar el texto formateado
    rc = page.insert_textbox(content_rect, clean_text, fontsize=9.5, fontname="helv", color=(0.12, 0.12, 0.12), lineheight=1.35)
    
    # Si sobra texto (overflow), crear segunda página
    if rc < 0:
        # Texto restante
        remaining_text = clean_text[int(len(clean_text) * 0.7):]
        page2 = doc.new_page(width=page_w, height=page_h)
        page2.insert_text((margin_x, 50), f"GOBERNACIÓN DEL CAUCA - CONTINUACIÓN RADICADO {radicado_id}", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        page2.draw_line((margin_x, 60), (page_w - margin_x, 60), color=(0.7, 0.7, 0.7), width=0.8)
        content_rect2 = pymupdf.Rect(margin_x, 80, page_w - margin_x, page_h - 75)
        page2.insert_textbox(content_rect2, remaining_text, fontsize=9.5, fontname="helv", color=(0.12, 0.12, 0.12), lineheight=1.35)

    # Pie de página en todas las páginas
    for idx, p in enumerate(doc):
        p.draw_line((margin_x, page_h - 55), (page_w - margin_x, page_h - 55), color=(0.8, 0.8, 0.8), width=0.5)
        p.insert_text((margin_x, page_h - 42), f"Borrador oficial para aprobación institucional · Funcionario: {funcionario or 'Área Técnica'}", fontsize=7.5, fontname="helv", color=(0.45, 0.45, 0.45))
        p.insert_text((page_w - margin_x - 70, page_h - 42), f"Página {idx+1} de {len(doc)}", fontsize=7.5, fontname="helv", color=(0.45, 0.45, 0.45))

    doc.save(output_path)
    doc.close()
    return output_path

def generate_petitioner_doc_pdf(radicado_id: str, title: str, subtitle: str, body_text: str, output_path: str, sender: str = "", date_str: str = "") -> str:
    """
    Genera un documento PDF institucional con los anexos y comunicaciones del peticionario.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    doc = pymupdf.open()
    page_w, page_h = 595, 842
    margin_x = 54

    page = doc.new_page(width=page_w, height=page_h)

    # Header
    page.insert_text((margin_x, 50), title.upper(), fontsize=10.5, fontname="helv", color=(0.1, 0.2, 0.4))
    if subtitle:
        page.insert_text((margin_x, 64), subtitle, fontsize=8.5, fontname="helv", color=(0.35, 0.35, 0.35))
    page.draw_line((margin_x, 72), (page_w - margin_x, 72), color=(0.12, 0.3, 0.55), width=1.5)

    # Metadatos del envío
    meta_y = 92
    if sender:
        page.insert_text((margin_x, meta_y), f"Remitente: {sender}", fontsize=8.5, fontname="helv", color=(0.15, 0.15, 0.15))
        meta_y += 14
    if date_str:
        page.insert_text((margin_x, meta_y), f"Fecha de radicación: {date_str} · Radicado SAC: {radicado_id}", fontsize=8.5, fontname="helv", color=(0.4, 0.4, 0.4))
        meta_y += 16

    page.draw_line((margin_x, meta_y), (page_w - margin_x, meta_y), color=(0.85, 0.85, 0.85), width=0.8)
    meta_y += 15

    # Contenido principal
    content_rect = pymupdf.Rect(margin_x, meta_y, page_w - margin_x, page_h - 60)
    page.insert_textbox(content_rect, body_text, fontsize=9.5, fontname="helv", color=(0.1, 0.1, 0.1), lineheight=1.4)

    # Footer
    page.draw_line((margin_x, page_h - 45), (page_w - margin_x, page_h - 45), color=(0.8, 0.8, 0.8), width=0.5)
    page.insert_text((margin_x, page_h - 32), f"Documento oficial del peticionario registrado en SAC · Expediente {radicado_id}", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))
    page.insert_text((page_w - margin_x - 60, page_h - 32), "Página 1 de 1", fontsize=7.5, fontname="helv", color=(0.5, 0.5, 0.5))

    doc.save(output_path)
    doc.close()
    return output_path
