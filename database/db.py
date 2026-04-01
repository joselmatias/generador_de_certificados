"""
db.py — Capa de acceso a datos.

Provee conexión centralizada y queries parametrizadas para todas
las operaciones CRUD del sistema. Nunca construye SQL con f-strings
para evitar inyección SQL.
"""

import sqlite3
import contextlib
from typing import Any, Generator

from database.init_db import DB_PATH


@contextlib.contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager que provee una conexión SQLite configurada.
    Hace commit automático al salir sin excepción; rollback en caso de error.

    Yields:
        sqlite3.Connection con row_factory = sqlite3.Row
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Capacitaciones
# ---------------------------------------------------------------------------

def obtener_siguiente_codigo_certificado(con: sqlite3.Connection, year: int) -> str:
    """
    Genera el siguiente código de certificado con formato AGM-CAP-YYYY-NNNN.
    La secuencia es global (no por oficina) y atómica dentro de la transacción.

    Args:
        con: Conexión activa (debe estar dentro de una transacción).
        year: Año del certificado (ej: 2024).

    Returns:
        Código único, ej: 'AGM-CAP-2024-0042'
    """
    prefix = f"AGM-CAP-{year}-"
    row = con.execute(
        """
        SELECT COUNT(*) AS total
        FROM capacitaciones
        WHERE codigo_certificado LIKE ?
        """,
        (f"{prefix}%",)
    ).fetchone()
    siguiente = (row["total"] if row else 0) + 1
    return f"{prefix}{siguiente:04d}"


def insertar_capacitacion(con: sqlite3.Connection, registro: dict[str, Any]) -> int:
    """
    Inserta un registro de capacitación. El código de certificado
    se genera automáticamente si no viene en el registro.

    Args:
        con: Conexión activa.
        registro: Diccionario con los campos del esquema interno.

    Returns:
        ID del registro insertado.
    """
    from datetime import date
    year = date.today().year

    if not registro.get("codigo_certificado"):
        registro["codigo_certificado"] = obtener_siguiente_codigo_certificado(con, year)

    con.execute(
        """
        INSERT INTO capacitaciones (
            oficina, timestamp_forms, nombre, email, cedula,
            fecha_capacitacion, institucion, provincia, nombre_curso,
            codigo_certificado, p1_conocimiento, p2_inquietudes,
            p3_contenido, p4_presencialidad, p5_puntualidad,
            p6_logistica, p7_duracion, temas_adicionales, sugerencias,
            registrado_por
        ) VALUES (
            :oficina, :timestamp_forms, :nombre, :email, :cedula,
            :fecha_capacitacion, :institucion, :provincia, :nombre_curso,
            :codigo_certificado, :p1_conocimiento, :p2_inquietudes,
            :p3_contenido, :p4_presencialidad, :p5_puntualidad,
            :p6_logistica, :p7_duracion, :temas_adicionales, :sugerencias,
            :registrado_por
        )
        """,
        registro,
    )
    return con.lastrowid  # type: ignore[return-value]


def verificar_duplicados(
    con: sqlite3.Connection,
    cedula: str,
    fecha_capacitacion: str,
    oficina: str,
) -> bool:
    """
    Verifica si ya existe un registro con la misma cédula y fecha
    dentro de la misma oficina.

    Returns:
        True si existe duplicado, False en caso contrario.
    """
    row = con.execute(
        """
        SELECT 1 FROM capacitaciones
        WHERE cedula = ? AND fecha_capacitacion = ? AND oficina = ?
        LIMIT 1
        """,
        (cedula, fecha_capacitacion, oficina),
    ).fetchone()
    return row is not None


def consultar_capacitaciones(
    con: sqlite3.Connection,
    oficina: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    nombre_curso: str | None = None,
) -> list[sqlite3.Row]:
    """
    Consulta capacitaciones con filtros opcionales.
    Si 'oficina' es None se devuelven todas (solo para rol master).

    Args:
        con: Conexión activa.
        oficina: Filtro por oficina. None = todas (master).
        fecha_desde: Fecha mínima de capacitación (YYYY-MM-DD).
        fecha_hasta: Fecha máxima de capacitación (YYYY-MM-DD).
        nombre_curso: Filtro exacto por nombre de curso.

    Returns:
        Lista de filas como sqlite3.Row.
    """
    condiciones: list[str] = []
    params: list[Any] = []

    if oficina is not None:
        condiciones.append("oficina = ?")
        params.append(oficina)
    if fecha_desde:
        condiciones.append("fecha_capacitacion >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        condiciones.append("fecha_capacitacion <= ?")
        params.append(fecha_hasta)
    if nombre_curso:
        condiciones.append("nombre_curso = ?")
        params.append(nombre_curso)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    filas = con.execute(
        f"SELECT * FROM capacitaciones {where} ORDER BY fecha_capacitacion DESC",
        params,
    ).fetchall()
    return filas


def listar_cursos(con: sqlite3.Connection, oficina: str | None = None) -> list[str]:
    """
    Devuelve la lista de nombres de cursos distintos registrados.
    Respeta el filtro de oficina para usuarios regionales.
    """
    if oficina:
        filas = con.execute(
            "SELECT DISTINCT nombre_curso FROM capacitaciones WHERE oficina = ? ORDER BY nombre_curso",
            (oficina,),
        ).fetchall()
    else:
        filas = con.execute(
            "SELECT DISTINCT nombre_curso FROM capacitaciones ORDER BY nombre_curso"
        ).fetchall()
    return [f["nombre_curso"] for f in filas]
