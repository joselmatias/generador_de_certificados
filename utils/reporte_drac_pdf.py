"""
reporte_drac_pdf.py — Generación de Reporte DRAC en PDF con ReportLab.

Encabezado en cada página:
  - Logo superior derecho sin fondo ni sombreado
  - Franja azul debajo con 3 columnas: Institución | Código reporte | Fecha
Cuerpo: secciones del reporte según formato Word Reporte 049_2026.docx
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
    KeepTogether, HRFlowable,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.utils import ImageReader

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "image1.png"

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Colores
AZUL_OSCURO = colors.HexColor("#1F3864")
AZUL_MEDIO  = colors.HexColor("#2E5EA8")
AZUL_CLARO  = colors.HexColor("#D6E4F0")
NEGRO       = colors.black
BLANCO      = colors.white
GRIS_FILA   = colors.HexColor("#F5F5F5")

# Geometría de página
PAGE_W, PAGE_H = A4                 # 21 x 29.7 cm
MARGIN_L = 2.0 * cm
MARGIN_R = 2.0 * cm
MARGIN_T = 0.3 * cm                 # arriba del logo (más arriba)
MARGIN_B = 1.5 * cm

LOGO_W      = 2.4 * cm              # ancho del logo (20 % menor)
LOGO_H      = 3.12 * cm            # alto del logo (20 % menor, ratio 206/271 ≈ 0.76)
GAP_FRANJA  = 0.35 * cm            # separación entre logo y franja azul
FRANJA_H    = 1.6 * cm             # altura de la franja azul
HEADER_H    = LOGO_H + GAP_FRANJA + FRANJA_H   # altura total del encabezado

# Posición fija de la tabla ÁREAS Y PERSONAS RESPONSABLES
AREAS_H = 6.0 * cm   # altura total de la tabla (filas: 0.7+0.7+2.2+2.2 + márgenes)
AREAS_Y = MARGIN_B   # Y fija desde el borde inferior (1.5 cm)

TIPOS_EVENTO = ["Capacitación", "Foros", "Congresos", "Seminarios"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fecha_esp(fecha_iso: str) -> str:
    from datetime import datetime
    try:
        dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
        return f"{dt.day} de {_MESES[dt.month]} de {dt.year}"
    except (ValueError, IndexError):
        return fecha_iso


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


# ---------------------------------------------------------------------------
# Estilos de párrafo
# ---------------------------------------------------------------------------

def _estilos() -> dict:
    base = dict(fontName="Helvetica", fontSize=10, textColor=NEGRO,
                leading=14, spaceAfter=2)
    return {
        "sec":    ParagraphStyle("sec",    fontName="Helvetica-Bold", fontSize=10,
                                 textColor=NEGRO, spaceBefore=8, spaceAfter=0),
        "cuerpo": ParagraphStyle("cuerpo", **base, alignment=TA_LEFT),
        "hdr_w":  ParagraphStyle("hdr_w",  fontName="Helvetica-Bold", fontSize=9,
                                 textColor=BLANCO, leading=12, alignment=TA_CENTER),
        "hdr_ws": ParagraphStyle("hdr_ws", fontName="Helvetica",      fontSize=8,
                                 textColor=BLANCO, leading=11, alignment=TA_CENTER),
        "etiq":   ParagraphStyle("etiq",   fontName="Helvetica-Bold", fontSize=9,
                                 textColor=AZUL_MEDIO),
        "valor":  ParagraphStyle("valor",  fontName="Helvetica",      fontSize=10,
                                 textColor=NEGRO, leading=13),
        "td":     ParagraphStyle("td",     fontName="Helvetica",      fontSize=9,
                                 alignment=TA_CENTER),
        "tdb":    ParagraphStyle("tdb",    fontName="Helvetica-Bold", fontSize=9),
    }


# ---------------------------------------------------------------------------
# Encabezado dibujado en canvas (aparece en cada página)
# ---------------------------------------------------------------------------

def _dibujar_encabezado(
    canvas, doc,
    codigo_reporte: str,
    fecha_txt: str,
    lineas_institucion: list[str],
) -> None:
    canvas.saveState()

    ancho_pag = PAGE_W
    top       = PAGE_H - MARGIN_T          # y de la parte superior del logo

    # --- Logo: esquina superior derecha, sin fondo ---
    logo_x = ancho_pag - MARGIN_R - LOGO_W
    logo_y = top - LOGO_H

    if LOGO_PATH.exists():
        img = ImageReader(str(LOGO_PATH))
        canvas.drawImage(
            img,
            logo_x, logo_y,
            width=LOGO_W, height=LOGO_H,
            mask="auto",          # respeta transparencia PNG
            preserveAspectRatio=True,
        )

    # --- Franja azul: ocupa todo el ancho, con separación respecto al logo ---
    franja_y = logo_y - GAP_FRANJA - FRANJA_H
    franja_w = ancho_pag - MARGIN_L - MARGIN_R

    canvas.setFillColor(AZUL_OSCURO)
    canvas.rect(MARGIN_L, franja_y, franja_w, FRANJA_H, fill=1, stroke=0)

    # Divisores verticales de la franja (2 líneas)
    col1_w = franja_w * 0.42
    col2_w = franja_w * 0.32
    col3_w = franja_w - col1_w - col2_w

    canvas.setStrokeColor(colors.HexColor("#4472C4"))
    canvas.setLineWidth(0.5)
    # línea 1
    x1 = MARGIN_L + col1_w
    canvas.line(x1, franja_y, x1, franja_y + FRANJA_H)
    # línea 2
    x2 = x1 + col2_w
    canvas.line(x2, franja_y, x2, franja_y + FRANJA_H)

    # Borde exterior de la franja
    canvas.setStrokeColor(NEGRO)
    canvas.setLineWidth(0.8)
    canvas.rect(MARGIN_L, franja_y, franja_w, FRANJA_H, fill=0, stroke=1)

    # Texto en la franja — col 1: institución (3 líneas dinámicas)
    canvas.setFillColor(BLANCO)
    canvas.setFont("Helvetica-Bold", 7.5)
    cy = franja_y + FRANJA_H * 0.68
    cx1 = MARGIN_L + col1_w / 2
    for i, linea in enumerate(lineas_institucion[:3]):
        canvas.drawCentredString(cx1, cy - i * 9, linea)

    # col 2: código de reporte
    canvas.setFont("Helvetica-Bold", 9)
    cx2 = x1 + col2_w / 2
    canvas.drawCentredString(cx2, franja_y + FRANJA_H * 0.35, codigo_reporte)

    # col 3: fecha
    canvas.setFont("Helvetica-Bold", 7.5)
    cx3 = x2 + col3_w / 2
    canvas.drawCentredString(cx3, franja_y + FRANJA_H * 0.65, "Fecha:")
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(cx3, franja_y + FRANJA_H * 0.30, fecha_txt)

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Función principal de generación — build de dos pasos
# ---------------------------------------------------------------------------

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
    lineas_institucion: list[str] | None = None,
    area_elaborado: str = "DRAC",
    num_personas_capacitadas: int = 0,
) -> bytes:

    codigo_reporte = f"Reporte DRAC-{numero_reporte:03d}-{year_reporte}"
    fecha_txt      = _fecha_esp(fecha_reporte)

    if lineas_institucion is None:
        lineas_institucion = [
            "Intendencia Regional /",
            "Dirección Regional de",
            "Abogacía de la Competencia",
        ]

    top_margin        = MARGIN_T + HEADER_H + 0.5 * cm
    frame_bottom_last = AREAS_Y + AREAS_H + 0.4 * cm   # solo última página
    ancho_util        = PAGE_W - MARGIN_L - MARGIN_R

    # ------------------------------------------------------------------
    # Funciones que crean flowables SIEMPRE FRESCOS (se llaman dos veces)
    # ------------------------------------------------------------------
    def _nuevo_frame() -> Frame:
        """Frame completo para páginas intermedias (sin reserva de ÁREAS)."""
        return Frame(
            MARGIN_L, MARGIN_B, ancho_util,
            PAGE_H - MARGIN_B - top_margin,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )

    def _nuevo_frame_reducido() -> Frame:
        """Frame reducido: reserva espacio para firmas en última página."""
        return Frame(
            MARGIN_L, frame_bottom_last, ancho_util,
            PAGE_H - frame_bottom_last - top_margin,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )

    def _nueva_resp_table() -> Table:
        est  = _estilos()
        col_w = [ancho_util * p for p in [0.20, 0.30, 0.12, 0.12, 0.26]]
        th   = ParagraphStyle("th2",  fontName="Helvetica-Bold", fontSize=9,
                               alignment=TA_CENTER, textColor=BLANCO)
        tdb  = ParagraphStyle("tdb2", fontName="Helvetica-Bold", fontSize=9)
        tdc  = ParagraphStyle("tdc2", fontName="Helvetica", fontSize=9,
                               alignment=TA_CENTER)
        data = [
            [_p("ÁREAS Y PERSONAS RESPONSABLES", th), "", "", "", ""],
            [_p("ACCIÓN", th), _p("NOMBRE", th), _p("ÁREA", th),
             _p("FECHA",  th), _p("FIRMA",  th)],
            [_p("Elaborado por:", tdb),
             _p(elaborado_por,    tdc),
             _p(area_elaborado,   tdc),
             _p(fecha_elaboracion, tdc), ""],
            [_p("Revisado y\naprobado por:", tdb),
             _p(revisado_por,     tdc),
             _p("IR",             tdc),
             _p(fecha_elaboracion, tdc), ""],
        ]
        t = Table(data, colWidths=col_w,
                  rowHeights=[0.7*cm, 0.7*cm, 2.2*cm, 2.2*cm])
        t.setStyle(TableStyle([
            ("SPAN",          (0,0), (-1,0)),
            ("BACKGROUND",    (0,0), (-1,0), AZUL_OSCURO),
            ("BACKGROUND",    (0,1), (-1,1), AZUL_MEDIO),
            ("ROWBACKGROUNDS",(0,2), (-1,3), [BLANCO, GRIS_FILA]),
            ("BOX",           (0,0), (-1,-1), 1, NEGRO),
            ("INNERGRID",     (0,0), (-1,-1), 0.4, colors.lightgrey),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ]))
        return t

    def _nuevos_elementos() -> list:
        est  = _estilos()
        elems: list = []

        # Tipo de Evento
        elems.append(_p("Tipo de Evento:", est["sec"]))
        ev_data = []
        for te in TIPOS_EVENTO:
            marca = "✓" if te == tipo_evento else ""
            ev_data.append([
                _p(te, est["valor"]),
                _p(f"<b>{marca}</b>",
                   ParagraphStyle("mk2", fontName="Helvetica-Bold", fontSize=12,
                                  alignment=TA_CENTER, textColor=AZUL_MEDIO)),
            ])
        ev_t = Table(ev_data, colWidths=[5.5*cm, 1.0*cm])
        ev_t.setStyle(TableStyle([
            ("BOX",           (0,0),(-1,-1), 0.8, NEGRO),
            ("INNERGRID",     (0,0),(-1,-1), 0.4, colors.lightgrey),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("ALIGN",         (1,0),(1,-1),  "CENTER"),
            ("TOPPADDING",    (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("ROWBACKGROUNDS",(0,0),(-1,-1), [BLANCO, GRIS_FILA]),
        ]))
        elems.append(ev_t)
        elems.append(Spacer(1, 0.4*cm))

        elems += _seccion_tabla(
            "Institución Invitada - Fecha - Modalidad - Tema:",
            [("Institución:", institucion_invitada),
             ("Fecha del evento:", _fecha_esp(fecha_evento) if fecha_evento else ""),
             ("Modalidad:", modalidad),
             ("Tema:", tema)],
            ancho_util, est,
        )
        elems += _seccion_parrafo("Nombre de los Capacitadores:", capacitadores, ancho_util, est)
        elems += _seccion_parrafo("Público Objetivo:",            publico_objetivo, ancho_util, est)
        elems += _seccion_parrafo("Descripción de la Capacitación:", descripcion,  ancho_util, est)
        elems += _seccion_parrafo("Observaciones:",                observaciones,  ancho_util, est)
        elems += _seccion_parrafo("Adjuntos (medios de verificación):", adjuntos,  ancho_util, est)

        # N.° personas
        pd_data = [[
            _p("<b>N.° de personas capacitadas:</b>",
               ParagraphStyle("pclbl2", fontName="Helvetica-Bold", fontSize=10,
                              textColor=AZUL_MEDIO)),
            _p(f"<b>{num_personas_capacitadas}</b>",
               ParagraphStyle("pcval2", fontName="Helvetica-Bold", fontSize=12,
                              alignment=TA_CENTER)),
        ]]
        pt = Table(pd_data, colWidths=[9.0*cm, 2.5*cm])
        pt.setStyle(TableStyle([
            ("BOX",          (0,0),(-1,-1), 0.8, NEGRO),
            ("BACKGROUND",   (0,0),(0,0),   AZUL_CLARO),
            ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ]))
        elems.append(pt)
        return elems

    # ------------------------------------------------------------------
    # Paso 1 — estimación inicial: frame COMPLETO en todas las páginas
    # ------------------------------------------------------------------
    _pg1 = [0]
    def _on_count1(c, d): _pg1[0] += 1

    buf1 = io.BytesIO()
    tmpl1 = PageTemplate(id="c1", frames=[_nuevo_frame()], onPage=_on_count1)
    doc1  = BaseDocTemplate(buf1, pagesize=A4, pageTemplates=[tmpl1])
    doc1.build(_nuevos_elementos())
    total_pages = _pg1[0]

    # ------------------------------------------------------------------
    # Paso 1b — refinamiento iterativo: frame reducido solo en la última
    # página. Se itera hasta que el conteo sea estable (máx 4 veces).
    # Esto es necesario porque reducir la última página puede provocar
    # que el contenido necesite una página más.
    # ------------------------------------------------------------------
    def _contar_con_ultima_reducida(ref_total: int) -> int:
        _pg = [0]
        def _on_pg(c, d):
            _pg[0] += 1
            if _pg[0] == ref_total:
                for fr in d.pageTemplate.frames:
                    fr._y1     = frame_bottom_last
                    fr._height = PAGE_H - frame_bottom_last - top_margin
        buf = io.BytesIO()
        tmpl = PageTemplate(id="ref", frames=[_nuevo_frame_reducido()], onPage=_on_pg)
        doc  = BaseDocTemplate(buf, pagesize=A4, pageTemplates=[tmpl])
        doc.build(_nuevos_elementos())
        return _pg[0]

    for _ in range(4):
        new_total = _contar_con_ultima_reducida(total_pages)
        if new_total == total_pages:
            break
        total_pages = new_total

    # Garantizar mínimo 2 páginas: si todo cabe en 1, crear página 2 para firmas
    if total_pages < 2:
        total_pages = 2

    # ------------------------------------------------------------------
    # Paso 2 — build final: ÁREAS dibujado en onPage de la última página
    # El frame que se usa en cada iteración coincide exactamente con el
    # paso 1b, por lo que no hay desajuste en la distribución.
    # ------------------------------------------------------------------
    _pg2 = [0]

    def _on_page_final(c, d):
        _pg2[0] += 1
        _dibujar_encabezado(c, d, codigo_reporte, fecha_txt, lineas_institucion)
        if _pg2[0] == total_pages:
            # Dibujar tabla de firmas en posición fija al pie de la última página
            fr = Frame(MARGIN_L, AREAS_Y, ancho_util, AREAS_H,
                       leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                       showBoundary=0)
            fr.addFromList([_nueva_resp_table()], c)

    buffer = io.BytesIO()
    tmpl_final = PageTemplate(id="m", frames=[_nuevo_frame()], onPage=_on_page_final)
    doc_final  = BaseDocTemplate(buffer, pagesize=A4, pageTemplates=[tmpl_final])
    doc_final.build(_nuevos_elementos())
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Helpers de construcción de secciones
# ---------------------------------------------------------------------------

def _seccion_tabla(titulo: str, filas: list[tuple[str, str]],
                   ancho: float, estilos: dict) -> list:
    bloque = [_p(titulo, estilos["sec"])]
    tdata = [
        [_p(f"<b>{etq}</b>", estilos["etiq"]),
         _p(val or "—",      estilos["valor"])]
        for etq, val in filas
    ]
    t = Table(tdata, colWidths=[3.8 * cm, ancho - 3.8 * cm])
    t.setStyle(TableStyle([
        ("BOX",          (0, 0), (-1, -1), 0.8, NEGRO),
        ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("BACKGROUND",   (0, 0), (0, -1), AZUL_CLARO),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    bloque.append(t)
    bloque.append(Spacer(1, 0.3 * cm))
    return bloque


def _seccion_parrafo(titulo: str, texto: str,
                     ancho: float, estilos: dict) -> list:
    # Paragraph con borde: puede dividirse entre páginas (no Table de 1 fila).
    # borderPadding=3 evita que el borde se superponga con el título superior.
    # spaceBefore=4 asegura separación visual suficiente del título.
    titulo_p = _p(titulo, estilos["sec"])
    estilo_caja = ParagraphStyle(
        "cuerpo_caja",
        parent=estilos["cuerpo"],
        borderColor=NEGRO,
        borderWidth=0.8,
        borderPadding=4,
        spaceBefore=4,
        spaceAfter=4,
        leftIndent=2,
        rightIndent=2,
    )
    texto_html = (texto or "—").replace("\n", "<br/>")
    contenido_p = _p(texto_html, estilo_caja)
    return [titulo_p, contenido_p, Spacer(1, 0.25 * cm)]
