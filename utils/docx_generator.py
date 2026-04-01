"""
docx_generator.py — Generación de certificados PDF usando la plantilla Word.

Flujo:
1. Rellena los placeholders del .docx en el XML interno.
2. Convierte el .docx a PDF usando LibreOffice (disponible en Streamlit Cloud).
"""

from __future__ import annotations

import io
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# Ruta de la plantilla Word (en la raíz del proyecto)
_TEMPLATE = Path(__file__).parent.parent / "formato de certificado de asistencia.docx"

# Texto del curso hardcodeado en la plantilla que se reemplazará
_CURSO_PLANTILLA = "Socialización a la Ley Orgánica de Regulación y Control del Poder de Mercado"


def _formatear_dia_mes(fecha_iso: str) -> tuple[str, str]:
    """
    Devuelve (dia_mes, año) para reemplazar los dos fragmentos de fecha.
    Ejemplo: '2024-11-19' → ('19 de noviembre', '2024')
    """
    try:
        dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
        return f"{dt.day} de {_MESES[dt.month]}", str(dt.year)
    except (ValueError, IndexError):
        return fecha_iso, ""


def generar_certificado_docx(
    nombre: str,
    cedula: str,
    nombre_curso: str,
    fecha_capacitacion: str,
    codigo_certificado: str,
) -> bytes:
    """
    Genera un certificado .docx rellenando la plantilla Word con los datos
    del participante.

    Args:
        nombre: Nombre completo (se muestra en mayúsculas).
        cedula: Número de cédula.
        nombre_curso: Nombre del curso o capacitación.
        fecha_capacitacion: Fecha en formato YYYY-MM-DD.
        codigo_certificado: Código único del certificado.

    Returns:
        Bytes del archivo .docx generado.
    """
    dia_mes, anio = _formatear_dia_mes(fecha_capacitacion)

    reemplazos = {
        "«apellidos_y_nombres_de_la_persona»": xml_escape(nombre.upper()),
        "«Número_de_cédula»":                  xml_escape(cedula),
        "«CODIGO»":                             xml_escape(codigo_certificado),
        "xxxxxx":                               xml_escape(dia_mes),
        "de 2025":                              xml_escape(f"de {anio}"),
        _CURSO_PLANTILLA:                       xml_escape(nombre_curso),
    }

    with open(_TEMPLATE, "rb") as f:
        template_bytes = f.read()

    output_buffer = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(template_bytes), "r") as zin:
        with zipfile.ZipFile(output_buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item == "word/document.xml":
                    xml = data.decode("utf-8")
                    for placeholder, valor in reemplazos.items():
                        xml = xml.replace(placeholder, valor)
                    data = xml.encode("utf-8")
                zout.writestr(item, data)

    return output_buffer.getvalue()


def generar_certificado_pdf(
    nombre: str,
    cedula: str,
    nombre_curso: str,
    fecha_capacitacion: str,
    codigo_certificado: str,
) -> bytes:
    """
    Genera un certificado PDF convirtiendo la plantilla Word rellenada.

    Usa LibreOffice headless para la conversión .docx → PDF.

    Returns:
        Bytes del archivo PDF generado.
    """
    docx_bytes = generar_certificado_docx(
        nombre=nombre,
        cedula=cedula,
        nombre_curso=nombre_curso,
        fecha_capacitacion=fecha_capacitacion,
        codigo_certificado=codigo_certificado,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, "certificado.docx")
        pdf_path  = os.path.join(tmpdir, "certificado.pdf")

        with open(docx_path, "wb") as f:
            f.write(docx_bytes)

        subprocess.run(
            [
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", tmpdir, docx_path,
            ],
            check=True,
            capture_output=True,
        )

        with open(pdf_path, "rb") as f:
            return f.read()
