"""
db.py — Capa de acceso a datos (PostgreSQL / Supabase).

Provee conexión centralizada y queries parametrizadas para todas
las operaciones CRUD del sistema. Nunca interpola valores en el SQL
(usa placeholders) para evitar inyección SQL.

Para no tocar los módulos consumidores, `get_connection()` entrega un
wrapper con la misma API que se usaba con sqlite3:
    con.execute(sql, params).fetchone() / .fetchall()
Las filas son `RealDictRow` (subclase de dict), por lo que `row["col"]`
y `dict(row)` siguen funcionando igual que antes.
"""

import contextlib
from typing import Any, Generator

import psycopg2
from psycopg2.extras import RealDictCursor

from database.init_db import _dsn


class _Conn:
    """Wrapper sobre una conexión psycopg2 que imita `con.execute(...)` de sqlite3."""

    def __init__(self, raw: "psycopg2.extensions.connection") -> None:
        self._raw = raw

    def execute(self, sql: str, params: Any = None):
        """Ejecuta el SQL en un cursor RealDict y devuelve el cursor (fetchone/fetchall)."""
        cur = self._raw.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        return cur


@contextlib.contextmanager
def get_connection() -> Generator[_Conn, None, None]:
    """
    Context manager que provee una conexión a Postgres.
    Hace commit automático al salir sin excepción; rollback en caso de error.
    """
    raw = psycopg2.connect(_dsn())
    con = _Conn(raw)
    try:
        yield con
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


# ---------------------------------------------------------------------------
# Capacitaciones
# ---------------------------------------------------------------------------

def obtener_siguiente_codigo_certificado(con: _Conn, year: int) -> str:
    """
    Genera el siguiente código de certificado con formato AGM-CAP-YYYY-NNNN.
    La secuencia es global (no por oficina) y atómica dentro de la transacción.
    """
    prefix = f"AGM-CAP-{year}-"
    row = con.execute(
        """
        SELECT COUNT(*) AS total
        FROM capacitaciones
        WHERE codigo_certificado LIKE %s
        """,
        (f"{prefix}%",),
    ).fetchone()
    siguiente = (row["total"] if row else 0) + 1
    return f"{prefix}{siguiente:04d}"


def insertar_capacitacion(con: _Conn, registro: dict[str, Any]) -> int:
    """
    Inserta un registro de capacitación. El código de certificado
    se genera automáticamente si no viene en el registro.

    Returns:
        ID del registro insertado.
    """
    from datetime import date
    year = date.today().year

    if not registro.get("codigo_certificado"):
        registro["codigo_certificado"] = obtener_siguiente_codigo_certificado(con, year)

    row = con.execute(
        """
        INSERT INTO capacitaciones (
            oficina, timestamp_forms, nombre, email, cedula,
            fecha_capacitacion, institucion, provincia, nombre_curso,
            codigo_certificado, p1_conocimiento, p2_inquietudes,
            p3_contenido, p4_presencialidad, p5_puntualidad,
            p6_logistica, p7_duracion, temas_adicionales, sugerencias,
            registrado_por
        ) VALUES (
            %(oficina)s, %(timestamp_forms)s, %(nombre)s, %(email)s, %(cedula)s,
            %(fecha_capacitacion)s, %(institucion)s, %(provincia)s, %(nombre_curso)s,
            %(codigo_certificado)s, %(p1_conocimiento)s, %(p2_inquietudes)s,
            %(p3_contenido)s, %(p4_presencialidad)s, %(p5_puntualidad)s,
            %(p6_logistica)s, %(p7_duracion)s, %(temas_adicionales)s, %(sugerencias)s,
            %(registrado_por)s
        )
        RETURNING id
        """,
        registro,
    ).fetchone()
    return row["id"]


def verificar_duplicados(
    con: _Conn,
    cedula: str,
    fecha_capacitacion: str,
    oficina: str,
) -> bool:
    """
    Verifica si ya existe un registro con la misma cédula y fecha
    dentro de la misma oficina.
    """
    row = con.execute(
        """
        SELECT 1 FROM capacitaciones
        WHERE cedula = %s AND fecha_capacitacion = %s AND oficina = %s
        LIMIT 1
        """,
        (cedula, fecha_capacitacion, oficina),
    ).fetchone()
    return row is not None


def consultar_capacitaciones(
    con: _Conn,
    oficina: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    nombre_curso: str | None = None,
) -> list[Any]:
    """
    Consulta capacitaciones con filtros opcionales.
    Si 'oficina' es None se devuelven todas (solo para rol master).
    """
    condiciones: list[str] = []
    params: list[Any] = []

    if oficina is not None:
        condiciones.append("oficina = %s")
        params.append(oficina)
    if fecha_desde:
        condiciones.append("fecha_capacitacion >= %s")
        params.append(fecha_desde)
    if fecha_hasta:
        condiciones.append("fecha_capacitacion <= %s")
        params.append(fecha_hasta)
    if nombre_curso:
        condiciones.append("nombre_curso = %s")
        params.append(nombre_curso)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    filas = con.execute(
        f"SELECT * FROM capacitaciones {where} ORDER BY fecha_capacitacion DESC",
        params,
    ).fetchall()
    return filas


def listar_cursos(con: _Conn, oficina: str | None = None) -> list[str]:
    """
    Devuelve la lista de nombres de cursos distintos registrados.
    Respeta el filtro de oficina para usuarios regionales.
    """
    if oficina:
        filas = con.execute(
            "SELECT DISTINCT nombre_curso FROM capacitaciones WHERE oficina = %s ORDER BY nombre_curso",
            (oficina,),
        ).fetchall()
    else:
        filas = con.execute(
            "SELECT DISTINCT nombre_curso FROM capacitaciones ORDER BY nombre_curso"
        ).fetchall()
    return [f["nombre_curso"] for f in filas]


# ---------------------------------------------------------------------------
# Reportes de Capacitación
# ---------------------------------------------------------------------------

def obtener_siguiente_numero_reporte(con: _Conn) -> int:
    """
    Incrementa de forma atómica el contador global de reportes y devuelve
    el nuevo número. La secuencia comienza en 084.
    """
    row = con.execute(
        "UPDATE contador_reporte SET ultimo_numero = ultimo_numero + 1 "
        "WHERE id = 1 RETURNING ultimo_numero"
    ).fetchone()
    return row["ultimo_numero"]


def insertar_reporte_capacitacion(con: _Conn, datos: dict[str, Any]) -> int:
    row = con.execute(
        """
        INSERT INTO reportes_capacitacion (
            numero_reporte, year_reporte, oficina, fecha_reporte, tipo_evento,
            institucion_invitada, tipo_institucion, provincia, canton,
            contacto_nombre, contacto_celular, tipo_actividad_productiva,
            publico_objetivo_capacitado,
            corresponde_convenio, numero_convenio, convenio_contraparte,
            fecha_evento, hora_inicio, hora_fin, modalidad, tema,
            capacitadores, publico_objetivo, descripcion,
            observaciones, adjuntos, elaborado_por, revisado_por,
            num_personas_capacitadas, encuestas_realizadas
        ) VALUES (
            %(numero_reporte)s, %(year_reporte)s, %(oficina)s, %(fecha_reporte)s, %(tipo_evento)s,
            %(institucion_invitada)s, %(tipo_institucion)s, %(provincia)s, %(canton)s,
            %(contacto_nombre)s, %(contacto_celular)s, %(tipo_actividad_productiva)s,
            %(publico_objetivo_capacitado)s,
            %(corresponde_convenio)s, %(numero_convenio)s, %(convenio_contraparte)s,
            %(fecha_evento)s, %(hora_inicio)s, %(hora_fin)s, %(modalidad)s, %(tema)s,
            %(capacitadores)s, %(publico_objetivo)s, %(descripcion)s,
            %(observaciones)s, %(adjuntos)s, %(elaborado_por)s, %(revisado_por)s,
            %(num_personas_capacitadas)s, %(encuestas_realizadas)s
        )
        RETURNING id
        """,
        datos,
    ).fetchone()
    return row["id"]


def consultar_reportes_capacitacion(
    con: _Conn,
    oficina: str | None = None,
    anio: int | None = None,
    mes: int | None = None,
) -> list[Any]:
    condiciones: list[str] = []
    params: list[Any] = []

    if oficina:
        condiciones.append("oficina = %s")
        params.append(oficina)
    if anio:
        condiciones.append("year_reporte = %s")
        params.append(anio)
    if mes:
        condiciones.append("to_char(fecha_reporte::date, 'MM') = %s")
        params.append(f"{mes:02d}")

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return con.execute(
        f"SELECT * FROM reportes_capacitacion {where} ORDER BY fecha_reporte DESC",
        params,
    ).fetchall()


# ---------------------------------------------------------------------------
# Asambleas Productivas
# ---------------------------------------------------------------------------

def obtener_siguiente_numero_asamblea(con: _Conn) -> int:
    """
    Incrementa de forma atómica el contador global de asambleas productivas
    y devuelve el nuevo número. La secuencia comienza en 001.
    """
    row = con.execute(
        "UPDATE contador_asamblea SET ultimo_numero = ultimo_numero + 1 "
        "WHERE id = 1 RETURNING ultimo_numero"
    ).fetchone()
    return row["ultimo_numero"]


def insertar_asamblea_productiva(con: _Conn, datos: dict[str, Any]) -> int:
    datos = {
        "numero_reporte":          None,
        "responsables":            None,
        "tematica":                None,
        "asociacion_agrupacion":   None,
        "lugar_realizacion":       None,
        "instituciones_invitadas": None,
        "acuerdos_compromisos":    None,
        "responsable_seguimiento": None,
        "estado_compromisos":      "Pendiente",
        "observaciones":           None,
        **datos,
    }
    row = con.execute(
        """
        INSERT INTO asamblea_productiva (
            numero_reporte, oficina, fecha, num_asistentes, responsables, tematica,
            asociacion_agrupacion, lugar_realizacion, instituciones_invitadas,
            acuerdos_compromisos, responsable_seguimiento, estado_compromisos, observaciones
        ) VALUES (
            %(numero_reporte)s, %(oficina)s, %(fecha)s, %(num_asistentes)s, %(responsables)s, %(tematica)s,
            %(asociacion_agrupacion)s, %(lugar_realizacion)s, %(instituciones_invitadas)s,
            %(acuerdos_compromisos)s, %(responsable_seguimiento)s, %(estado_compromisos)s, %(observaciones)s
        )
        RETURNING id
        """,
        datos,
    ).fetchone()
    return row["id"]


def actualizar_estado_compromiso(con: _Conn, asamblea_id: int, estado: str) -> None:
    """Actualiza el estado de los compromisos de una asamblea (Pendiente/Cumplido)."""
    con.execute(
        "UPDATE asamblea_productiva SET estado_compromisos = %s WHERE id = %s",
        (estado, asamblea_id),
    )


def consultar_asambleas_productivas(
    con: _Conn,
    oficina: str | None = None,
    anio: int | None = None,
    mes: int | None = None,
) -> list[Any]:
    condiciones: list[str] = []
    params: list[Any] = []

    if oficina:
        condiciones.append("oficina = %s")
        params.append(oficina)
    if anio:
        condiciones.append("to_char(fecha::date, 'YYYY') = %s")
        params.append(str(anio))
    if mes:
        condiciones.append("to_char(fecha::date, 'MM') = %s")
        params.append(f"{mes:02d}")

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return con.execute(
        f"SELECT * FROM asamblea_productiva {where} ORDER BY fecha DESC",
        params,
    ).fetchall()


def estadisticas_mensuales(
    con: _Conn,
    oficina: str | None = None,
    anio: int | None = None,
    mes: int | None = None,
) -> dict[str, int]:
    """Devuelve KPIs del mes: capacitaciones, personas capacitadas, asambleas, personas en asambleas."""
    condiciones_rep: list[str] = []
    condiciones_asm: list[str] = []
    params_rep: list[Any] = []
    params_asm: list[Any] = []

    if oficina:
        condiciones_rep.append("oficina = %s")
        condiciones_asm.append("oficina = %s")
        params_rep.append(oficina)
        params_asm.append(oficina)
    if anio:
        condiciones_rep.append("year_reporte = %s")
        condiciones_asm.append("to_char(fecha::date, 'YYYY') = %s")
        params_rep.append(anio)
        params_asm.append(str(anio))
    if mes:
        condiciones_rep.append("to_char(fecha_reporte::date, 'MM') = %s")
        condiciones_asm.append("to_char(fecha::date, 'MM') = %s")
        params_rep.append(f"{mes:02d}")
        params_asm.append(f"{mes:02d}")

    where_rep = ("WHERE " + " AND ".join(condiciones_rep)) if condiciones_rep else ""
    where_asm = ("WHERE " + " AND ".join(condiciones_asm)) if condiciones_asm else ""

    r = con.execute(
        f"SELECT COUNT(*) as cnt, COALESCE(SUM(num_personas_capacitadas),0) as personas "
        f"FROM reportes_capacitacion {where_rep}",
        params_rep,
    ).fetchone()

    a = con.execute(
        f"SELECT COUNT(*) as cnt, COALESCE(SUM(num_asistentes),0) as personas "
        f"FROM asamblea_productiva {where_asm}",
        params_asm,
    ).fetchone()

    return {
        "num_capacitaciones":        r["cnt"] if r else 0,
        "personas_capacitadas":      r["personas"] if r else 0,
        "num_asambleas":             a["cnt"] if a else 0,
        "personas_asambleas":        a["personas"] if a else 0,
    }
