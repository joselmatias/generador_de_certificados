"""
docx_generator.py — Generación de certificados PDF usando la plantilla Word.

Flujo:
1. Rellena los placeholders del .docx en el XML interno.
2. Convierte el .docx a PDF usando LibreOffice (disponible en Streamlit Cloud).
"""

from __future__ import annotations

import io
import math
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

# Autoajuste del tamaño de fuente del párrafo del cuerpo (el que va tras la
# cédula). El bloque de firma "Eco. Roberto Santos, Mgs." es un cuadro flotante
# anclado en una posición fija: si el cuerpo es largo, invade su espacio. Por eso
# se reduce la fuente ~1/sqrt(longitud) para que el cuerpo ocupe siempre una banda
# vertical similar y la firma conserve su lugar. Tamaños en media-puntos (docx).
_BODY_BASE_SZ    = 32    # 16 pt — tamaño normal de la plantilla
_BODY_MIN_SZ     = 16    # 8 pt (50%) — piso para textos extremadamente largos
_BODY_BASE_CHARS = 210   # longitud del cuerpo por defecto que se ve bien (~4 líneas)


def _tamano_fuente_cuerpo(texto: str) -> int:
    """Devuelve el tamaño de fuente (media-puntos) del párrafo del cuerpo.

    Escala ~1/sqrt(longitud): el espacio vertical usado ≈ (líneas)×(altura de
    línea); como una fuente menor mete más caracteres por línea y reduce la
    altura, mantener el espacio vertical constante implica tamaño ∝ 1/√(longitud).
    """
    n = len(texto)
    if n <= _BODY_BASE_CHARS:
        return _BODY_BASE_SZ
    sz = round(_BODY_BASE_SZ * math.sqrt(_BODY_BASE_CHARS / n))
    return max(_BODY_MIN_SZ, sz)


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


def _formatear_dia_mes(fecha_iso: str, fecha_fin_iso: str = "") -> tuple[str, str]:
    """
    Devuelve (dia_mes, año) para reemplazar los dos fragmentos de fecha.
    Ejemplo: '2024-11-19' → ('19 de noviembre', '2024')

    Si fecha_fin_iso se especifica y difiere de fecha_iso, dia_mes se arma
    como rango: 'D1 al D2 de mes' (asume mismo mes/año que fecha_iso).
    """
    try:
        dt = datetime.strptime(fecha_iso, "%Y-%m-%d")
    except (ValueError, IndexError):
        return fecha_iso, ""

    if fecha_fin_iso:
        try:
            dt_fin = datetime.strptime(fecha_fin_iso, "%Y-%m-%d")
        except (ValueError, IndexError):
            dt_fin = dt
        if dt_fin.date() != dt.date():
            return f"{dt.day} al {dt_fin.day} de {_MESES[dt.month]}", str(dt.year)

    return f"{dt.day} de {_MESES[dt.month]}", str(dt.year)


def generar_certificado_docx(
    nombre: str,
    cedula: str,
    nombre_curso: str,
    fecha_capacitacion: str,
    codigo_certificado: str,
    ciudad: str = "",
    duracion: str = "",
    texto_participacion: str = "",
    fecha_fin: str = "",
) -> bytes:
    """
    Genera un certificado .docx rellenando la plantilla Word con los datos
    del participante.

    Args:
        nombre: Nombre completo (se muestra en mayúsculas).
        cedula: Número de cédula.
        nombre_curso: Nombre del curso o capacitación.
        fecha_capacitacion: Fecha de inicio en formato YYYY-MM-DD.
        codigo_certificado: Código único del certificado.
        fecha_fin: Fecha de fin en formato YYYY-MM-DD (opcional). Si se
            especifica y difiere de fecha_capacitacion, el certificado
            muestra el rango "D1 al D2 de mes de año".

    Returns:
        Bytes del archivo .docx generado.
    """
    dia_mes, anio = _formatear_dia_mes(fecha_capacitacion, fecha_fin)

    try:
        _dt = datetime.strptime(fecha_capacitacion, "%Y-%m-%d")
        mes_anio = f"{_MESES[_dt.month].capitalize()} de {_dt.year}"
    except (ValueError, IndexError):
        mes_anio = ""

    # Valores por defecto cuando el llamador no los envía (p.ej. flujo por lote).
    ciudad              = ciudad or _CIUDAD_DEFAULT
    duracion            = duracion or _DURACION_DEFAULT
    texto_participacion = texto_participacion or _TEXTO_PARTICIPACION_DEFAULT

    # Tamaño de fuente autoajustado del cuerpo según la longitud real de la frase
    # (reproduce la del template solo para medirla), reservando espacio a la firma.
    cuerpo_texto = (
        f"Con C.I. {cedula} {texto_participacion} {nombre_curso}, "
        f"realizada en la ciudad de {ciudad} - Ecuador, el {dia_mes} de {anio} "
        f"({duracion} de duración)."
    )
    sz_cuerpo = _tamano_fuente_cuerpo(cuerpo_texto)

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
                    # El tamaño 32 se usa solo en el párrafo del cuerpo: escalarlo
                    # ahí reduce la fuente cuando el texto es largo y evita invadir
                    # el bloque de firma. Solo en document.xml (los headers no usan 32).
                    if item == "word/document.xml" and sz_cuerpo != _BODY_BASE_SZ:
                        xml = xml.replace('<w:sz w:val="32"/>',   f'<w:sz w:val="{sz_cuerpo}"/>')
                        xml = xml.replace('<w:szCs w:val="32"/>', f'<w:szCs w:val="{sz_cuerpo}"/>')
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
    fecha_fin: str = "",
) -> bytes:
    """
    Genera un certificado PDF convirtiendo la plantilla Word rellenada.

    Usa LibreOffice headless para la conversión .docx → PDF.

    Args:
        fecha_fin: Fecha de fin en formato YYYY-MM-DD (opcional), para
            eventos de varios días. Ver generar_certificado_docx.

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
        fecha_fin=fecha_fin,
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
