"""
reporte_drac_pdf.py — Generación de Reporte DRAC en PDF con ReportLab.

Replica la estructura del archivo Word Reporte 049_2026.docx:
- Encabezado con logo, código de reporte y fecha
- Tabla de Tipo de Evento (checkbox)
- Secciones de contenido
- Tabla de Áreas y Personas Responsables
"""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
)

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "image1.png"

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

COLOR_HEADER  = colors.HexColor("#1F3864")
COLOR_SECTION = colors.HexColor("#2E5EA8")
COLOR_TABLA   = colors.HexColor("#D6E4F0")
COLOR_NEGRO   = colors.black
COLOR_BLANCO  = colors.white
COLOR_GRIS    = colors.HexColor("#F2F2F2")

TIPOS_EVENTO = ["Capacitación", "Foros", "Congresos", "Seminarios"]


def _fecha_esp(fecha_iso: str) -> str:
    from datetime import datetime
    try:
        dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
        return f"{dt.day} de {_MESES[dt.month]} de {dt.year}"
    except (ValueError, IndexError):
        return fecha_iso


def _estilo_seccion() -> ParagraphStyle:
    return ParagraphStyle(
        "SeccionHeader",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=COLOR_NEGRO,
        spaceBefore=8,
        spaceAfter=2,
    )


def _estilo_cuerpo() -> ParagraphStyle:
    return ParagraphStyle(
        "Cuerpo",
        fontName="Helvetica",
        fontSize=10,
        textColor=COLOR_NEGRO,
        leading=14,
        spaceAfter=4,
    )


def generar_reporte_drac(
    numero_reporte: int,
    year_reporte: int,
    fecha_reporte: str,
    tipo_evento: str,
    institucion_invitada: str,
    fecha_evento: str,
    modalidad: str,
    tema: str,
    capacitadores: str,
    publico_objetivo: str,
    descripcion: str,
    observaciones: str,
    adjuntos: str,
    elaborado_por: str,
    revisado_por: str,
    fecha_elaboracion: str,
    num_personas_capacitadas: int = 0,
) -> bytes:
    """
    Genera el Reporte DRAC en PDF y lo devuelve como bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
    )

    elementos: list = []
    ancho_util = A4[0] - 4.0 * cm

    estilo_sec = _estilo_seccion()
    estilo_cuerpo = _estilo_cuerpo()

    # ------------------------------------------------------------------
    # 1. Encabezado: logo | código reporte | fecha
    # ------------------------------------------------------------------
    codigo_reporte = f"Reporte DRAC-{numero_reporte:03d}-{year_reporte}"
    fecha_formateada = _fecha_esp(fecha_reporte)

    logo_cell: list = []
    if LOGO_PATH.exists():
        logo_cell = [Image(str(LOGO_PATH), width=1.8 * cm, height=2.3 * cm)]

    header_data = [[
        logo_cell[0] if logo_cell else "",
        Paragraph(
            f"<b>Intendencia Regional /</b><br/>Dirección Regional de<br/>Abogacía de la Competencia",
            ParagraphStyle("hdr", fontName="Helvetica-Bold", fontSize=9,
                           alignment=TA_CENTER, textColor=COLOR_BLANCO, leading=12),
        ),
        Paragraph(
            f"<b>{codigo_reporte}</b>",
            ParagraphStyle("hdr2", fontName="Helvetica-Bold", fontSize=11,
                           alignment=TA_CENTER, textColor=COLOR_BLANCO),
        ),
        Paragraph(
            f"<b>Fecha:</b><br/>{fecha_formateada}",
            ParagraphStyle("hdr3", fontName="Helvetica", fontSize=9,
                           alignment=TA_CENTER, textColor=COLOR_BLANCO, leading=13),
        ),
    ]]

    header_table = Table(
        header_data,
        colWidths=[2.2 * cm, 6.5 * cm, 5.0 * cm, 3.8 * cm],
        rowHeights=[2.6 * cm],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), COLOR_HEADER),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("BOX",          (0, 0), (-1, -1), 1, COLOR_NEGRO),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, colors.HexColor("#4472C4")),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    elementos.append(header_table)
    elementos.append(Spacer(1, 0.4 * cm))

    # ------------------------------------------------------------------
    # 2. Tipo de Evento — tabla de checkbox
    # ------------------------------------------------------------------
    elementos.append(Paragraph("Tipo de Evento:", estilo_sec))
    evento_data = []
    for t in TIPOS_EVENTO:
        marca = "✓" if t == tipo_evento else ""
        evento_data.append([
            Paragraph(t, ParagraphStyle("ev", fontName="Helvetica", fontSize=10)),
            Paragraph(
                f"<b>{marca}</b>",
                ParagraphStyle("mk", fontName="Helvetica-Bold", fontSize=12,
                               alignment=TA_CENTER, textColor=COLOR_SECTION),
            ),
        ])

    evento_table = Table(evento_data, colWidths=[5.5 * cm, 1.2 * cm])
    evento_table.setStyle(TableStyle([
        ("BOX",         (0, 0), (-1, -1), 0.8, COLOR_NEGRO),
        ("INNERGRID",   (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",       (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [COLOR_BLANCO, COLOR_GRIS]),
    ]))
    elementos.append(evento_table)
    elementos.append(Spacer(1, 0.3 * cm))

    # ------------------------------------------------------------------
    # 3. Institución Invitada — Fecha — Modalidad — Tema
    # ------------------------------------------------------------------
    def seccion_tabla(titulo: str, filas_datos: list[tuple[str, str]]) -> list:
        bloque = []
        bloque.append(Paragraph(titulo, estilo_sec))
        tdata = []
        for etiqueta, valor in filas_datos:
            tdata.append([
                Paragraph(f"<b>{etiqueta}</b>",
                          ParagraphStyle("et", fontName="Helvetica-Bold", fontSize=9,
                                         textColor=COLOR_SECTION)),
                Paragraph(valor or "—",
                          ParagraphStyle("vl", fontName="Helvetica", fontSize=10)),
            ])
        t = Table(tdata, colWidths=[4.0 * cm, ancho_util - 4.0 * cm])
        t.setStyle(TableStyle([
            ("BOX",          (0, 0), (-1, -1), 0.8, COLOR_NEGRO),
            ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("BACKGROUND",   (0, 0), (0, -1), COLOR_TABLA),
            ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        bloque.append(t)
        bloque.append(Spacer(1, 0.25 * cm))
        return bloque

    def seccion_parrafo(titulo: str, texto: str) -> list:
        bloque = []
        bloque.append(Paragraph(titulo, estilo_sec))
        tdata = [[Paragraph(texto or "—", estilo_cuerpo)]]
        t = Table(tdata, colWidths=[ancho_util])
        t.setStyle(TableStyle([
            ("BOX",          (0, 0), (-1, -1), 0.8, COLOR_NEGRO),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        bloque.append(t)
        bloque.append(Spacer(1, 0.25 * cm))
        return bloque

    elementos += seccion_tabla(
        "Institución Invitada - Fecha - Modalidad - Tema:",
        [
            ("Institución:", institucion_invitada),
            ("Fecha:",       fecha_evento),
            ("Modalidad:",   modalidad),
            ("Tema:",        tema),
        ],
    )

    elementos += seccion_parrafo("Nombre de los Capacitadores:", capacitadores)
    elementos += seccion_parrafo("Público Objetivo:", publico_objetivo)
    elementos += seccion_parrafo("Descripción de la Capacitación:", descripcion)
    elementos += seccion_parrafo("Observaciones:", observaciones)
    elementos += seccion_parrafo("Adjuntos (medios de verificación):", adjuntos)

    # ------------------------------------------------------------------
    # 4. Número de personas capacitadas
    # ------------------------------------------------------------------
    personas_data = [[
        Paragraph("<b>N.° de personas capacitadas:</b>",
                  ParagraphStyle("pc_lbl", fontName="Helvetica-Bold", fontSize=10,
                                 textColor=COLOR_SECTION)),
        Paragraph(
            str(num_personas_capacitadas),
            ParagraphStyle("pc_val", fontName="Helvetica-Bold", fontSize=12,
                           alignment=TA_CENTER),
        ),
    ]]
    personas_table = Table(personas_data, colWidths=[9.0 * cm, 2.5 * cm])
    personas_table.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.8, COLOR_NEGRO),
        ("BACKGROUND",   (0, 0), (0, 0), COLOR_TABLA),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    elementos.append(personas_table)
    elementos.append(Spacer(1, 0.5 * cm))

    # ------------------------------------------------------------------
    # 5. Áreas y Personas Responsables
    # ------------------------------------------------------------------
    estilo_th = ParagraphStyle(
        "th", fontName="Helvetica-Bold", fontSize=9,
        alignment=TA_CENTER, textColor=COLOR_BLANCO,
    )
    estilo_td = ParagraphStyle(
        "td", fontName="Helvetica", fontSize=9, alignment=TA_CENTER,
    )
    estilo_td_bold = ParagraphStyle(
        "tdb", fontName="Helvetica-Bold", fontSize=9,
    )

    resp_col = [ancho_util * 0.22, ancho_util * 0.28, ancho_util * 0.18,
                ancho_util * 0.16, ancho_util * 0.16]

    resp_data = [
        [
            Paragraph("ÁREAS Y PERSONAS RESPONSABLES", estilo_th),
            "", "", "", "",
        ],
        [
            Paragraph("ACCIÓN",   estilo_th),
            Paragraph("NOMBRE",   estilo_th),
            Paragraph("ÁREA",     estilo_th),
            Paragraph("FECHA",    estilo_th),
            Paragraph("FIRMA",    estilo_th),
        ],
        [
            Paragraph("Elaborado por:", estilo_td_bold),
            Paragraph(elaborado_por,    estilo_td),
            Paragraph("DRAC",           estilo_td),
            Paragraph(fecha_elaboracion, estilo_td),
            "",
        ],
        [
            Paragraph("Revisado y aprobado por:", estilo_td_bold),
            Paragraph(revisado_por,     estilo_td),
            Paragraph("DRAC",           estilo_td),
            Paragraph(fecha_elaboracion, estilo_td),
            "",
        ],
    ]

    resp_table = Table(resp_data, colWidths=resp_col)
    resp_table.setStyle(TableStyle([
        ("SPAN",         (0, 0), (-1, 0)),
        ("BACKGROUND",   (0, 0), (-1, 0), COLOR_HEADER),
        ("BACKGROUND",   (0, 1), (-1, 1), COLOR_SECTION),
        ("BACKGROUND",   (0, 2), (-1, 3), COLOR_BLANCO),
        ("ROWBACKGROUNDS",(0, 2), (-1, 3), [COLOR_BLANCO, COLOR_GRIS]),
        ("BOX",          (0, 0), (-1, -1), 1, COLOR_NEGRO),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
    ]))
    elementos.append(KeepTogether(resp_table))

    doc.build(elementos)
    return buffer.getvalue()
