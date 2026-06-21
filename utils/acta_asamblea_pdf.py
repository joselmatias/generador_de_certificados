"""
acta_asamblea_pdf.py — Generación del Acta de Asamblea Productiva en PDF.

Reutiliza el diseño institucional del reporte DRAC (logo + franja azul) y
estructura las 7 secciones del acta: datos generales, antecedentes, objetivo,
temas abordados, compromisos (tabla), observaciones y cierre/seguimiento.
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    KeepTogether,
)
from reportlab.lib.utils import ImageReader

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "image1.png"

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

AZUL_OSCURO = colors.HexColor("#1F3864")
AZUL_MEDIO  = colors.HexColor("#2E5EA8")
AZUL_CLARO  = colors.HexColor("#D6E4F0")
NEGRO       = colors.black
BLANCO      = colors.white
GRIS_FILA   = colors.HexColor("#F5F5F5")

PAGE_W, PAGE_H = A4
MARGIN_L = 2.0 * cm
MARGIN_R = 2.0 * cm
MARGIN_T = 0.3 * cm
MARGIN_B = 1.5 * cm

LOGO_W     = 2.4 * cm
LOGO_H     = 3.12 * cm
GAP_FRANJA = 0.35 * cm
FRANJA_H   = 1.6 * cm
HEADER_H   = LOGO_H + GAP_FRANJA + FRANJA_H


def _fecha_esp(fecha_iso: str) -> str:
    from datetime import datetime
    try:
        dt = datetime.strptime(fecha_iso[:10], "%Y-%m-%d")
        return f"{dt.day} de {_MESES[dt.month]} de {dt.year}"
    except (ValueError, IndexError):
        return fecha_iso


def _estilos() -> dict:
    base = dict(fontName="Helvetica", fontSize=10, textColor=NEGRO, leading=14, spaceAfter=2)
    return {
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=13,
                                  textColor=AZUL_OSCURO, alignment=TA_CENTER,
                                  spaceBefore=4, spaceAfter=6),
        "sec":    ParagraphStyle("sec",    fontName="Helvetica-Bold", fontSize=10,
                                  textColor=AZUL_OSCURO, spaceBefore=10, spaceAfter=4),
        "cuerpo": ParagraphStyle("cuerpo", **base, alignment=TA_JUSTIFY),
        "dato":   ParagraphStyle("dato",   fontName="Helvetica", fontSize=10,
                                  textColor=NEGRO, leading=14),
        "hdr_w":  ParagraphStyle("hdr_w",  fontName="Helvetica-Bold", fontSize=8,
                                  textColor=BLANCO, leading=11, alignment=TA_CENTER),
        "td":     ParagraphStyle("td",     fontName="Helvetica", fontSize=8,
                                  leading=11, alignment=TA_CENTER),
        "td_l":   ParagraphStyle("td_l",   fontName="Helvetica", fontSize=8,
                                  leading=11, alignment=TA_LEFT),
    }


def _dibujar_encabezado(
    canvas, doc,
    codigo_reporte: str,
    fecha_txt: str,
    lineas_institucion: list[str],
) -> None:
    canvas.saveState()
    top = PAGE_H - MARGIN_T
    logo_x = PAGE_W - MARGIN_R - LOGO_W
    logo_y = top - LOGO_H

    if LOGO_PATH.exists():
        img = ImageReader(str(LOGO_PATH))
        canvas.drawImage(img, logo_x, logo_y, width=LOGO_W, height=LOGO_H,
                         mask="auto", preserveAspectRatio=True)

    franja_y = logo_y - GAP_FRANJA - FRANJA_H
    franja_w = PAGE_W - MARGIN_L - MARGIN_R

    canvas.setFillColor(AZUL_OSCURO)
    canvas.rect(MARGIN_L, franja_y, franja_w, FRANJA_H, fill=1, stroke=0)

    col1_w = franja_w * 0.42
    col2_w = franja_w * 0.32
    col3_w = franja_w - col1_w - col2_w

    canvas.setStrokeColor(colors.HexColor("#4472C4"))
    canvas.setLineWidth(0.5)
    x1 = MARGIN_L + col1_w
    canvas.line(x1, franja_y, x1, franja_y + FRANJA_H)
    x2 = x1 + col2_w
    canvas.line(x2, franja_y, x2, franja_y + FRANJA_H)

    canvas.setStrokeColor(NEGRO)
    canvas.setLineWidth(0.8)
    canvas.rect(MARGIN_L, franja_y, franja_w, FRANJA_H, fill=0, stroke=1)

    canvas.setFillColor(BLANCO)
    canvas.setFont("Helvetica-Bold", 7.5)
    cy = franja_y + FRANJA_H * 0.68
    cx1 = MARGIN_L + col1_w / 2
    for i, linea in enumerate(lineas_institucion[:3]):
        canvas.drawCentredString(cx1, cy - i * 9, linea)

    canvas.setFont("Helvetica-Bold", 9)
    cx2 = x1 + col2_w / 2
    canvas.drawCentredString(cx2, franja_y + FRANJA_H * 0.35, codigo_reporte)

    canvas.setFont("Helvetica-Bold", 7.5)
    cx3 = x2 + col3_w / 2
    canvas.drawCentredString(cx3, franja_y + FRANJA_H * 0.65, "Fecha:")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(cx3, franja_y + FRANJA_H * 0.30, fecha_txt)

    canvas.restoreState()


def _construir_tabla_compromisos(compromisos: list[dict], st: dict) -> Table:
    headers = [
        Paragraph("#", st["hdr_w"]),
        Paragraph("Compromiso", st["hdr_w"]),
        Paragraph("Institución /<br/>responsable(s)", st["hdr_w"]),
        Paragraph("Funcionario responsable<br/>seguimiento - SCE", st["hdr_w"]),
        Paragraph("Fecha tentativa<br/>de ejecución", st["hdr_w"]),
        Paragraph("Estado", st["hdr_w"]),
    ]
    data = [headers]
    for i, c in enumerate(compromisos, 1):
        data.append([
            Paragraph(str(i), st["td"]),
            Paragraph(c.get("texto", ""), st["td_l"]),
            Paragraph(c.get("institucion", ""), st["td"]),
            Paragraph(c.get("funcionario_seguimiento", ""), st["td"]),
            Paragraph(c.get("fecha_tentativa", ""), st["td"]),
            Paragraph(c.get("estado", "Pendiente"), st["td"]),
        ])

    ancho_total = PAGE_W - MARGIN_L - MARGIN_R
    col_widths = [
        ancho_total * 0.05,
        ancho_total * 0.30,
        ancho_total * 0.18,
        ancho_total * 0.20,
        ancho_total * 0.14,
        ancho_total * 0.13,
    ]
    tabla = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND",   (0, 0), (-1, 0), AZUL_MEDIO),
        ("TEXTCOLOR",    (0, 0), (-1, 0), BLANCO),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, r), (-1, r), GRIS_FILA))
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def generar_acta_asamblea_pdf(
    numero_reporte: int,
    year_reporte: int,
    fecha: str,
    hora_inicio: str,
    hora_cierre: str,
    lugar_realizacion: str,
    instituciones_invitadas: str,
    asociacion_agrupacion: str,
    tematica: str,
    antecedentes: str,
    objetivo: str,
    temas_abordados: str,
    compromisos: list[dict],
    observaciones: str,
    cierre_seguimiento: str,
    responsables: list[str],
    responsable_seguimiento: list[str],
    num_asistentes: int,
    lineas_institucion: list[str] | None = None,
    area_elaborado: str = "DRAC",
) -> bytes:
    if lineas_institucion is None:
        lineas_institucion = [
            "Intendencia Regional /",
            "Dirección Regional de",
            "Abogacía de la Competencia",
        ]

    codigo = f"Asamblea Productiva {numero_reporte:03d}-{year_reporte}"
    fecha_txt = _fecha_esp(fecha)

    st = _estilos()
    buf = io.BytesIO()

    frame_y = MARGIN_B
    frame_h = PAGE_H - MARGIN_T - HEADER_H - 0.5 * cm - MARGIN_B
    frame = Frame(MARGIN_L, frame_y, PAGE_W - MARGIN_L - MARGIN_R, frame_h,
                  topPadding=0, bottomPadding=0)

    def _on_page(canvas, doc):
        _dibujar_encabezado(canvas, doc, codigo, fecha_txt, lineas_institucion)

    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=MARGIN_L, rightMargin=MARGIN_R,
                          topMargin=MARGIN_T, bottomMargin=MARGIN_B)
    doc.addPageTemplates([PageTemplate(id="acta", frames=[frame], onPage=_on_page)])

    elems: list = []
    sp = Spacer(1, 8)

    # Título
    elems.append(Paragraph("ACTA DE COMPROMISO", st["titulo"]))
    elems.append(sp)

    # Datos generales
    datos_gen = (
        f"<b>Fecha:</b> {fecha_txt}<br/>"
        f"<b>Lugar:</b> {lugar_realizacion or '—'}<br/>"
        f"<b>Hora de inicio:</b> {hora_inicio or '—'} &nbsp;&nbsp; "
        f"<b>Hora de cierre:</b> {hora_cierre or '—'}<br/>"
        f"<b>Asociación / Agrupación:</b> {asociacion_agrupacion or '—'}<br/>"
        f"<b>Tema tratado:</b> {tematica or '—'}<br/>"
        f"<b>N.° de participantes:</b> {num_asistentes}<br/>"
        f"<b>Responsable(s):</b> {', '.join(responsables) if responsables else '—'}<br/>"
        f"<b>Institución(es) participante(s):</b> {instituciones_invitadas or '—'}"
    )
    elems.append(Paragraph(datos_gen, st["dato"]))
    elems.append(sp)

    # Antecedentes
    if antecedentes:
        elems.append(Paragraph("Antecedentes:", st["sec"]))
        elems.append(Paragraph(antecedentes.replace("\n", "<br/>"), st["cuerpo"]))
        elems.append(sp)

    # Objetivo
    if objetivo:
        elems.append(Paragraph("Objetivo de la Asamblea:", st["sec"]))
        elems.append(Paragraph(objetivo.replace("\n", "<br/>"), st["cuerpo"]))
        elems.append(sp)

    # Temas abordados
    if temas_abordados:
        elems.append(Paragraph("Temas abordados:", st["sec"]))
        elems.append(Paragraph(temas_abordados.replace("\n", "<br/>"), st["cuerpo"]))
        elems.append(sp)

    # Compromisos generados
    if compromisos:
        elems.append(Paragraph("Compromisos Generados:", st["sec"]))
        elems.append(Spacer(1, 4))
        elems.append(_construir_tabla_compromisos(compromisos, st))
        elems.append(sp)

    # Observaciones
    elems.append(Paragraph("Observaciones Relevantes:", st["sec"]))
    elems.append(Paragraph(observaciones or "Ninguna.", st["cuerpo"]))
    elems.append(sp)

    # Cierre y seguimiento
    elems.append(Paragraph("Cierre y Seguimiento:", st["sec"]))
    elems.append(Paragraph(
        (cierre_seguimiento or "").replace("\n", "<br/>") or "—", st["cuerpo"]))
    elems.append(sp)

    # Responsable(s) del seguimiento
    if responsable_seguimiento:
        elems.append(Paragraph(
            f"<b>Responsable(s) del seguimiento:</b> {', '.join(responsable_seguimiento)}",
            st["dato"],
        ))

    doc.build(elems)
    return buf.getvalue()
