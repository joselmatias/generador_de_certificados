"""
pdf_generator.py — Generación de certificados PDF con ReportLab.

Genera certificados A4 horizontal (landscape) con:
- Nombre completo en mayúsculas
- Cédula de identidad
- Nombre del curso
- Fecha de capacitación formateada en español
- Código del certificado
"""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER


# ---------------------------------------------------------------------------
# Constantes de diseño
# ---------------------------------------------------------------------------
PAGE_SIZE = landscape(A4)

MARGIN_TOP    = 2.0 * cm
MARGIN_BOTTOM = 2.0 * cm
MARGIN_LEFT   = 2.5 * cm
MARGIN_RIGHT  = 2.5 * cm

COLOR_PRIMARIO   = colors.HexColor("#1A3A5C")
COLOR_SECUNDARIO = colors.HexColor("#C8A951")
COLOR_TEXTO      = colors.HexColor("#2C2C2C")

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def formatear_fecha_esp(fecha_iso: str) -> str:
    """
    Convierte una fecha ISO (YYYY-MM-DD) a formato largo en español.
    Ejemplo: '2024-11-19' → '19 de noviembre de 2024'
    """
    try:
        dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
        return f"{dt.day} de {_MESES[dt.month]} de {dt.year}"
    except (ValueError, IndexError):
        return fecha_iso


def generar_certificado(
    nombre: str,
    cedula: str,
    nombre_curso: str,
    fecha_capacitacion: str,
    codigo_certificado: str,
    nombre_institucion: str = "Institución Pública del Ecuador",
) -> bytes:
    """
    Genera un certificado en PDF (A4 horizontal) y lo devuelve como bytes.

    Args:
        nombre: Nombre completo del participante (se muestra en mayúsculas).
        cedula: Número de cédula de identidad.
        nombre_curso: Nombre del curso o capacitación.
        fecha_capacitacion: Fecha en formato YYYY-MM-DD.
        codigo_certificado: Código único del certificado.
        nombre_institucion: Nombre de la institución emisora.

    Returns:
        Bytes del PDF generado.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
    )

    estilos = _construir_estilos()
    elementos = _construir_contenido(
        estilos=estilos,
        nombre=nombre.upper(),
        cedula=cedula,
        nombre_curso=nombre_curso,
        fecha_formateada=formatear_fecha_esp(fecha_capacitacion),
        codigo_certificado=codigo_certificado,
        nombre_institucion=nombre_institucion,
    )

    doc.build(elementos, onFirstPage=_dibujar_borde, onLaterPages=_dibujar_borde)
    return buffer.getvalue()


def _construir_estilos() -> dict:
    """Construye y retorna los estilos de párrafo del certificado."""
    return {
        "titulo_institucion": ParagraphStyle(
            "TituloInstitucion",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=COLOR_PRIMARIO,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "titulo_certificado": ParagraphStyle(
            "TituloCertificado",
            fontName="Helvetica-Bold",
            fontSize=28,
            textColor=COLOR_SECUNDARIO,
            alignment=TA_CENTER,
            spaceBefore=8,
            spaceAfter=4,
            leading=34,
        ),
        "subtitulo": ParagraphStyle(
            "Subtitulo",
            fontName="Helvetica",
            fontSize=12,
            textColor=COLOR_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "nombre_participante": ParagraphStyle(
            "NombreParticipante",
            fontName="Helvetica-Bold",
            fontSize=22,
            textColor=COLOR_PRIMARIO,
            alignment=TA_CENTER,
            spaceBefore=6,
            spaceAfter=4,
            leading=28,
        ),
        "cedula": ParagraphStyle(
            "Cedula",
            fontName="Helvetica",
            fontSize=11,
            textColor=COLOR_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "cuerpo": ParagraphStyle(
            "Cuerpo",
            fontName="Helvetica",
            fontSize=12,
            textColor=COLOR_TEXTO,
            alignment=TA_CENTER,
            spaceAfter=6,
            leading=16,
        ),
        "nombre_curso": ParagraphStyle(
            "NombreCurso",
            fontName="Helvetica-Bold",
            fontSize=14,
            textColor=COLOR_PRIMARIO,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=4,
            leading=18,
        ),
        "codigo": ParagraphStyle(
            "Codigo",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceBefore=12,
        ),
    }


def _construir_contenido(
    estilos: dict,
    nombre: str,
    cedula: str,
    nombre_curso: str,
    fecha_formateada: str,
    codigo_certificado: str,
    nombre_institucion: str,
) -> list:
    """Construye la lista de elementos ReportLab para el certificado."""
    elementos = []

    elementos.append(Paragraph(nombre_institucion.upper(), estilos["titulo_institucion"]))
    elementos.append(Spacer(1, 0.3 * cm))

    # Línea decorativa dorada
    tabla_linea = Table([[""]], colWidths=[22 * cm], rowHeights=[0.15 * cm])
    tabla_linea.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLOR_SECUNDARIO),
    ]))
    elementos.append(tabla_linea)
    elementos.append(Spacer(1, 0.4 * cm))

    elementos.append(Paragraph("CERTIFICADO", estilos["titulo_certificado"]))
    elementos.append(Paragraph("DE PARTICIPACIÓN", estilos["subtitulo"]))
    elementos.append(Spacer(1, 0.3 * cm))

    elementos.append(Paragraph("La institución certifica que:", estilos["cuerpo"]))
    elementos.append(Spacer(1, 0.2 * cm))

    elementos.append(Paragraph(nombre, estilos["nombre_participante"]))
    elementos.append(Paragraph(f"Cédula de identidad: {cedula}", estilos["cedula"]))

    elementos.append(Paragraph(
        "participó satisfactoriamente en la capacitación:",
        estilos["cuerpo"],
    ))
    elementos.append(Spacer(1, 0.1 * cm))
    elementos.append(Paragraph(f'"{nombre_curso}"', estilos["nombre_curso"]))
    elementos.append(Spacer(1, 0.2 * cm))
    elementos.append(Paragraph(
        f"realizada el <b>{fecha_formateada}</b>.",
        estilos["cuerpo"],
    ))

    # Espacio para firma
    elementos.append(Spacer(1, 1.2 * cm))
    tabla_firma = Table(
        [["_________________________", "_________________________"],
         ["Firma responsable", "Sello institucional"]],
        colWidths=[8 * cm, 8 * cm],
    )
    tabla_firma.setStyle(TableStyle([
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",  (0, 0), (-1, -1), COLOR_TEXTO),
        ("TOPPADDING", (0, 1), (-1, 1),  2),
    ]))
    elementos.append(tabla_firma)

    elementos.append(Paragraph(f"Código: {codigo_certificado}", estilos["codigo"]))

    return elementos


def _dibujar_borde(canvas, doc) -> None:
    """Dibuja el borde decorativo del certificado en cada página."""
    canvas.saveState()
    ancho, alto = PAGE_SIZE

    canvas.setStrokeColor(COLOR_PRIMARIO)
    canvas.setLineWidth(3)
    canvas.rect(1.0 * cm, 1.0 * cm, ancho - 2.0 * cm, alto - 2.0 * cm)

    canvas.setStrokeColor(COLOR_SECUNDARIO)
    canvas.setLineWidth(1)
    canvas.rect(1.3 * cm, 1.3 * cm, ancho - 2.6 * cm, alto - 2.6 * cm)

    canvas.restoreState()
