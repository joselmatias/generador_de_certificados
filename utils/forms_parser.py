"""
forms_parser.py — Parser de archivos exportados de Google Forms.

Mapea exactamente las columnas del export de Google Forms
al esquema interno de la tabla 'capacitaciones', valida cada registro
y devuelve lotes separados de registros válidos e inválidos.

Columnas esperadas del export (nombres exactos con tildes):
    Marca temporal
    Nombres y apellidos del participante
    Correo electrónico
    Fecha de la capacitación
    Institución a la que pertenece
    Número de cédula
    Provincia desde la que recibió la capacitación
    1. Conocimiento del tema
    2. Respuestas a inquietudes planteadas...
    3. Contenido de la capacitación
    4. ¿Qué tan satisfecho estás con que este ...
    5. ¿Qué tan satisfecho estás con la puntua...
    6. ¿Qué tan satisfecho estás con la logísti...
    7. ¿Qué tan satisfecho estás con el tiempo ...
    8. ¿Qué temas adicionales...
    9. Sugerencias y comentarios...
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from utils.validator import (
    validar_cedula,
    validar_email,
    validar_fecha,
    validar_nombre,
    validar_satisfaccion,
)


# ---------------------------------------------------------------------------
# Mapeo: columna original del Forms → nombre interno
# ---------------------------------------------------------------------------

_MAPEO_COLUMNAS: dict[str, str] = {
    "Marca temporal": "timestamp_forms",
    "Nombres y apellidos": "nombre",
    "Correo electrónico": "email",
    "Fecha de la capacitación": "fecha_capacitacion",
    "Institución a la que pertenece": "institucion",
    "Número de cédula": "cedula",
    "Provincia desde la que recibió": "provincia",
    "1. Conocimiento del tema": "p1_conocimiento",
    "2. Respuestas a inquietudes": "p2_inquietudes",
    "3. Contenido de la capacitación": "p3_contenido",
    "4. ¿Qué tan satisfecho estás con que este": "p4_presencialidad",
    "5. ¿Qué tan satisfecho estás con la puntua": "p5_puntualidad",
    "6. ¿Qué tan satisfecho estás con la logísti": "p6_logistica",
    "7. ¿Qué tan satisfecho estás con el tiempo": "p7_duracion",
    "8. ¿Qué temas adicionales": "temas_adicionales",
    "9. Sugerencias y comentarios": "sugerencias",
}

_CAMPOS_SATISFACCION = {
    "p1_conocimiento", "p2_inquietudes", "p3_contenido",
    "p4_presencialidad", "p5_puntualidad", "p6_logistica", "p7_duracion",
}


# ---------------------------------------------------------------------------
# Estructuras de resultado
# ---------------------------------------------------------------------------

@dataclass
class RegistroProcesado:
    """Representa un registro del Forms después de validación."""
    fila_original: int
    datos: dict[str, Any]
    errores: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return len(self.errores) == 0


@dataclass
class ResultadoParseo:
    """Resultado completo del proceso de parseo y validación."""
    validos: list[RegistroProcesado] = field(default_factory=list)
    invalidos: list[RegistroProcesado] = field(default_factory=list)
    columnas_no_mapeadas: list[str] = field(default_factory=list)
    columnas_faltantes: list[str] = field(default_factory=list)
    total_filas: int = 0

    @property
    def total_validos(self) -> int:
        return len(self.validos)

    @property
    def total_invalidos(self) -> int:
        return len(self.invalidos)

    def resumen_texto(self) -> str:
        lineas = [
            f"Total filas procesadas: {self.total_filas}",
            f"Registros válidos: {self.total_validos}",
            f"Registros con errores: {self.total_invalidos}",
        ]
        if self.columnas_faltantes:
            lineas.append(f"Columnas no encontradas: {', '.join(self.columnas_faltantes)}")
        if self.columnas_no_mapeadas:
            lineas.append(f"Columnas extra ignoradas: {', '.join(self.columnas_no_mapeadas)}")
        return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def parsear_forms(
    archivo: io.BytesIO | str,
    nombre_curso: str,
    oficina: str,
    registrado_por: str,
) -> ResultadoParseo:
    """
    Parsea el archivo Excel o CSV exportado de Google Forms, mapea las columnas
    al esquema interno y valida cada registro.

    Args:
        archivo: Objeto BytesIO del archivo subido o ruta al archivo.
        nombre_curso: Nombre del curso ingresado por el usuario (aplica a todo el lote).
        oficina: Oficina del usuario autenticado (asignada automáticamente).
        registrado_por: Username del usuario que realiza la carga.

    Returns:
        ResultadoParseo con listas de registros válidos e inválidos.

    Raises:
        ValueError: Si el archivo no puede ser leído o no tiene columnas reconocibles.
    """
    df = _leer_archivo(archivo)
    resultado = ResultadoParseo(total_filas=len(df))

    df_mapeado, columnas_faltantes, columnas_no_mapeadas = _mapear_columnas(df)
    resultado.columnas_faltantes = columnas_faltantes
    resultado.columnas_no_mapeadas = columnas_no_mapeadas

    for idx, fila in df_mapeado.iterrows():
        fila_num = int(idx) + 2  # +2: header=fila 1, pandas base 0
        registro = _validar_fila(fila, fila_num, nombre_curso, oficina, registrado_por)
        if registro.es_valido:
            resultado.validos.append(registro)
        else:
            resultado.invalidos.append(registro)

    return resultado


# ---------------------------------------------------------------------------
# Funciones auxiliares privadas
# ---------------------------------------------------------------------------

def _leer_archivo(archivo: io.BytesIO | str) -> pd.DataFrame:
    """
    Lee un archivo Excel (.xlsx, .xls) o CSV y retorna un DataFrame.

    Raises:
        ValueError: Si no se puede leer el archivo.
    """
    nombre = getattr(archivo, "name", str(archivo))
    extension = nombre.lower().split(".")[-1] if "." in nombre else ""

    try:
        if extension in ("xlsx", "xls"):
            return pd.read_excel(archivo, dtype=str, keep_default_na=False)
        elif extension == "csv":
            return pd.read_csv(archivo, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        else:
            try:
                return pd.read_excel(archivo, dtype=str, keep_default_na=False)
            except Exception:
                if hasattr(archivo, "seek"):
                    archivo.seek(0)
                return pd.read_csv(archivo, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo: {e}") from e


def _mapear_columnas(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    Renombra las columnas usando coincidencia por prefijo (startswith)
    para tolerar columnas truncadas por Google Forms.
    """
    columnas_originales = list(df.columns)
    renombrado: dict[str, str] = {}
    encontradas: set[str] = set()

    for col_original in columnas_originales:
        col_limpia = col_original.strip()
        for patron, nombre_interno in _MAPEO_COLUMNAS.items():
            if col_limpia.startswith(patron) or col_limpia == patron:
                renombrado[col_original] = nombre_interno
                encontradas.add(patron)
                break

    columnas_faltantes = [
        patron for patron in _MAPEO_COLUMNAS
        if patron not in encontradas
    ]
    columnas_no_mapeadas = [
        col for col in columnas_originales
        if col not in renombrado
    ]

    df_renombrado = df.rename(columns=renombrado)
    columnas_a_mantener = [c for c in df_renombrado.columns if c in _MAPEO_COLUMNAS.values()]
    return df_renombrado[columnas_a_mantener], columnas_faltantes, columnas_no_mapeadas


def _validar_fila(
    fila: pd.Series,
    fila_num: int,
    nombre_curso: str,
    oficina: str,
    registrado_por: str,
) -> RegistroProcesado:
    """Valida un registro individual y construye el dict normalizado."""
    errores: list[str] = []
    datos: dict[str, Any] = {
        "nombre_curso":        nombre_curso.strip(),
        "oficina":             oficina,
        "registrado_por":      registrado_por,
        "codigo_certificado":  None,
    }

    datos["timestamp_forms"] = _get(fila, "timestamp_forms")

    # Nombre
    nombre_raw = _get(fila, "nombre")
    ok, msg = validar_nombre(nombre_raw)
    if not ok:
        errores.append(f"Nombre: {msg}")
    datos["nombre"] = nombre_raw.strip().upper() if nombre_raw else ""

    # Email
    email_raw = _get(fila, "email")
    ok, msg = validar_email(email_raw)
    if not ok:
        errores.append(msg)
    datos["email"] = email_raw.strip().lower() if email_raw else None

    # Cédula
    cedula_raw = _get(fila, "cedula")
    cedula_limpia = cedula_raw.strip().split(".")[0].zfill(10) if cedula_raw else ""
    ok, msg = validar_cedula(cedula_limpia)
    if not ok:
        errores.append(f"Cédula '{cedula_raw}': {msg}")
    datos["cedula"] = cedula_limpia

    # Fecha de capacitación
    fecha_raw = _get(fila, "fecha_capacitacion")
    ok, msg, fecha_iso = validar_fecha(fecha_raw)
    if not ok:
        errores.append(f"Fecha de capacitación: {msg}")
    datos["fecha_capacitacion"] = fecha_iso or ""

    # Institución y provincia
    datos["institucion"] = _get(fila, "institucion") or None
    datos["provincia"]   = _get(fila, "provincia") or None

    # Preguntas de satisfacción p1-p7
    etiquetas_campos = {
        "p1_conocimiento":   "P1 Conocimiento",
        "p2_inquietudes":    "P2 Inquietudes",
        "p3_contenido":      "P3 Contenido",
        "p4_presencialidad": "P4 Presencialidad",
        "p5_puntualidad":    "P5 Puntualidad",
        "p6_logistica":      "P6 Logística",
        "p7_duracion":       "P7 Duración",
    }
    for campo, etiqueta in etiquetas_campos.items():
        valor_raw = _get(fila, campo)
        ok, msg, valor_int = validar_satisfaccion(valor_raw, etiqueta)
        if not ok:
            errores.append(msg)
        datos[campo] = valor_int

    # Texto libre
    datos["temas_adicionales"] = _get(fila, "temas_adicionales") or None
    datos["sugerencias"]       = _get(fila, "sugerencias") or None

    return RegistroProcesado(fila_original=fila_num, datos=datos, errores=errores)


def _get(fila: pd.Series, campo: str) -> str:
    """Extrae valor de una columna de forma segura, devuelve '' si no existe."""
    valor = fila.get(campo, "")
    if valor is None:
        return ""
    s = str(valor).strip()
    return "" if s in ("nan", "None", "NaT", "<NA>") else s


def registros_a_dataframe(registros: list[RegistroProcesado]) -> pd.DataFrame:
    """Convierte lista de RegistroProcesado en DataFrame para exportación."""
    return pd.DataFrame([r.datos for r in registros])
