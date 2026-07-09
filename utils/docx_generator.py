"""
docx_generator.py — Generación de certificados PDF usando la plantilla Word.

Flujo:
1. Rellena los placeholders del .docx en el XML interno.
2. Convierte el .docx a PDF usando LibreOffice (disponible en Streamlit Cloud).
"""

from __future__ import annotations

import io
import os
import re
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

# Valores por defecto para los campos opcionales (flujo por lote no los envía);
# reproducen el texto que la plantilla tenía fijo antes de convertirse en placeholder.
_TEXTO_PARTICIPACION_DEFAULT = (
    "Por su participación en la capacitación en materia de competencia sobre la"
)
_CIUDAD_DEFAULT   = "Guayaquil"
_DURACION_DEFAULT = "1 Hora"


def _strip_merge_fields(xml: str) -> str:
    """Removes Word MERGEFIELD markers so LibreOffice renders the result text as-is.

    Without this, LibreOffice re-evaluates «MERGEFIELD X» at PDF-conversion time
    and replaces the substituted value with an empty string (no data source).
    """
    xml = re.sub(r"<w:fldChar[^>]*/?>", "", xml)
    xml = re.sub(r"<w:instrText[^>]*>.*?</w:instrText>", "", xml, flags=re.DOTALL)
    return xml


def _repair_placeholder_runs(xml: str) -> str:
    """Recompone placeholders «...» que Word haya partido en varios runs XML.

    Al escribir «duracion» o «texto_participacion» a mano, Word suele separar los
    guillemets del texto en runs distintos (por el corrector ortográfico), dejando
    p.ej. «<run>duracion<run>» — lo que rompe el reemplazo por texto plano. Esta
    función elimina las etiquetas XML entre « y » cuando el contenido es un único
    token de placeholder, dejándolo contiguo. Es defensiva: si la plantilla ya está
    limpia, no cambia nada.
    """
    def _clean(m: "re.Match") -> str:
        inner = re.sub(r"<[^>]+>", "", m.group(1))
        if re.fullmatch(r"[A-Za-zÀ-ÿ_]+", inner):
            return "«" + inner + "»"
        return m.group(0)

    return re.sub(r"«(.{0,600}?)»", _clean, xml, flags=re.DOTALL)


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
    ciudad: str = "",
    duracion: str = "",
    texto_participacion: str = "",
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

    try:
        _dt = datetime.strptime(fecha_capacitacion, "%Y-%m-%d")
        mes_anio = f"{_MESES[_dt.month].capitalize()} de {_dt.year}"
    except (ValueError, IndexError):
        mes_anio = ""

    # Valores por defecto cuando el llamador no los envía (p.ej. flujo por lote).
    ciudad              = ciudad or _CIUDAD_DEFAULT
    duracion            = duracion or _DURACION_DEFAULT
    texto_participacion = texto_participacion or _TEXTO_PARTICIPACION_DEFAULT

    reemplazos = {
        "«apellidos_y_nombres_de_la_persona»": xml_escape(nombre.upper()),
        "«Número_de_cédula»":                  xml_escape(cedula),
        "«CODIGO»":                             xml_escape(codigo_certificado),
        "xxxxxx":                               xml_escape(dia_mes),
        "de 2025":                              xml_escape(f"de {anio}"),
        _CURSO_PLANTILLA:                       xml_escape(nombre_curso),
        "«nombre_curso»":                       xml_escape(nombre_curso),
        "«ciudad»":                             xml_escape(ciudad),
        "«duracion»":                           xml_escape(duracion),
        "«texto_participacion»":                xml_escape(texto_participacion),
        "«mes_anio»":                           xml_escape(mes_anio),
    }

    with open(_TEMPLATE, "rb") as f:
        template_bytes = f.read()

    output_buffer = io.BytesIO()

    # Los placeholders pueden vivir en el cuerpo o en encabezados/pies de página
    # (p.ej. «mes_anio» suele escribirse en el header de Word, no en el body).
    _partes_con_texto = re.compile(r"^word/(document|header\d+|footer\d+)\.xml$")

    with zipfile.ZipFile(io.BytesIO(template_bytes), "r") as zin:
        with zipfile.ZipFile(output_buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if _partes_con_texto.match(item):
                    xml = data.decode("utf-8")
                    xml = _strip_merge_fields(xml)
                    xml = _repair_placeholder_runs(xml)
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
    ciudad: str = "",
    duracion: str = "",
    texto_participacion: str = "",
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
        ciudad=ciudad,
        duracion=duracion,
        texto_participacion=texto_participacion,
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
