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


_FECHA_EVENTO_INICIAL_SQL = (
    "CASE "
    "WHEN fecha_evento ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' "
    "THEN substring(fecha_evento FROM 1 FOR 10)::date "
    "END"
)


# ---------------------------------------------------------------------------
# Capacitaciones
# ---------------------------------------------------------------------------

def reservar_rango_codigos_certificado(
    con: _Conn,
    year: int,
    cantidad: int,
) -> list[str]:
    """Reserva atómicamente ``cantidad`` códigos consecutivos para un año.

    La primera numeración de un año comienza en 1676. La operación usa una
    única sentencia UPSERT, de modo que dos oficinas no pueden recibir rangos
    superpuestos aunque generen certificados al mismo tiempo.
    """
    if cantidad < 1:
        raise ValueError("La cantidad de códigos a reservar debe ser mayor que cero.")

    row = con.execute(
        """
        INSERT INTO contador_certificado (year, ultimo_numero)
        VALUES (%(year)s, 1675 + %(cantidad)s)
        ON CONFLICT (year) DO UPDATE
        SET ultimo_numero = contador_certificado.ultimo_numero + %(cantidad)s
        RETURNING ultimo_numero
        """,
        {"year": year, "cantidad": cantidad},
    ).fetchone()
    numero_fin = row["ultimo_numero"]
    numero_inicio = numero_fin - cantidad + 1
    return [f"DRAC-{year}-{numero}" for numero in range(numero_inicio, numero_fin + 1)]


def obtener_siguiente_codigo_certificado(con: _Conn, year: int) -> str:
    """
    Genera el siguiente código de certificado con formato DRAC-YYYY-NNNN.

    Usa un contador persistente por año en `contador_certificado` (igual que
    `contador_reporte`/`contador_asamblea`), no un conteo de filas — así que
    borrar filas de prueba en `capacitaciones` nunca afecta la numeración
    futura ni genera colisiones. La numeración parte de 1676 (histórico).
    """
    return reservar_rango_codigos_certificado(con, year, 1)[0]


def obtener_ultimo_codigo_certificado(con: _Conn, year: int) -> str | None:
    """
    Devuelve el último código de certificado generado este año (sin generar
    uno nuevo), o None si aún no se ha generado ninguno.
    """
    row = con.execute(
        "SELECT ultimo_numero FROM contador_certificado WHERE year = %s",
        (year,),
    ).fetchone()
    if row is None:
        return None
    return f"DRAC-{year}-{row['ultimo_numero']}"


def insertar_capacitacion(con: _Conn, registro: dict[str, Any]) -> int:
    """
    Inserta un registro de capacitación. El código de certificado
    se genera automáticamente si no viene en el registro.

    Returns:
        ID del registro insertado.
    """
    from datetime import date
    year = date.today().year

    registro.setdefault("fecha_evento", None)

    if not registro.get("codigo_certificado"):
        registro["codigo_certificado"] = obtener_siguiente_codigo_certificado(con, year)

    row = con.execute(
        """
        INSERT INTO capacitaciones (
            oficina, timestamp_forms, nombre, email, cedula,
            fecha_capacitacion, fecha_evento, institucion, provincia, nombre_curso,
            codigo_certificado, p1_conocimiento, p2_inquietudes,
            p3_contenido, p4_presencialidad, p5_puntualidad,
            p6_logistica, p7_duracion, temas_adicionales, sugerencias,
            registrado_por
        ) VALUES (
            %(oficina)s, %(timestamp_forms)s, %(nombre)s, %(email)s, %(cedula)s,
            %(fecha_capacitacion)s, %(fecha_evento)s, %(institucion)s, %(provincia)s, %(nombre_curso)s,
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


def insertar_lote_certificado(con: _Conn, datos: dict[str, Any]) -> int:
    """Registra un lote de generación de certificados. Devuelve el id insertado."""
    row = con.execute(
        """
        INSERT INTO lotes_certificados
            (oficina, nombre_evento, fecha_evento, num_participantes,
             codigo_inicio, codigo_fin, generado_por, numero_reporte_vinculado)
        VALUES (%(oficina)s, %(nombre_evento)s, %(fecha_evento)s,
                %(num_participantes)s, %(codigo_inicio)s, %(codigo_fin)s,
                %(generado_por)s, %(numero_reporte_vinculado)s)
        RETURNING id
        """,
        datos,
    ).fetchone()
    return row["id"] if row else -1


def consultar_lotes_certificados(con: _Conn, oficina: str | None = None) -> list[Any]:
    """Devuelve el historial de lotes de certificados emitidos, más recientes primero."""
    where = "WHERE oficina = %s" if oficina else ""
    params = (oficina,) if oficina else ()
    return con.execute(
        f"SELECT * FROM lotes_certificados {where} ORDER BY fecha_generacion DESC",
        params,
    ).fetchall()


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
        condiciones.append(f"to_char({_FECHA_EVENTO_INICIAL_SQL}, 'YYYY') = %s")
        params.append(str(anio))
    if mes:
        condiciones.append(f"to_char({_FECHA_EVENTO_INICIAL_SQL}, 'MM') = %s")
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
        "hora_inicio":             None,
        "hora_cierre":             None,
        "antecedentes":            None,
        "objetivo":                None,
        "temas_abordados":         None,
        "cierre_seguimiento":      None,
        "contacto_nombre":         None,
        "contacto_celular":        None,
        "contacto_institucion":    None,
        "provincia":               None,
        "canton":                  None,
        "parroquia_recinto":       None,
        **datos,
    }
    row = con.execute(
        """
        INSERT INTO asamblea_productiva (
            numero_reporte, oficina, fecha, num_asistentes, responsables, tematica,
            asociacion_agrupacion, lugar_realizacion, instituciones_invitadas,
            acuerdos_compromisos, responsable_seguimiento, estado_compromisos, observaciones,
            hora_inicio, hora_cierre, antecedentes, objetivo, temas_abordados, cierre_seguimiento,
            contacto_nombre, contacto_celular, contacto_institucion,
            provincia, canton, parroquia_recinto
        ) VALUES (
            %(numero_reporte)s, %(oficina)s, %(fecha)s, %(num_asistentes)s, %(responsables)s, %(tematica)s,
            %(asociacion_agrupacion)s, %(lugar_realizacion)s, %(instituciones_invitadas)s,
            %(acuerdos_compromisos)s, %(responsable_seguimiento)s, %(estado_compromisos)s, %(observaciones)s,
            %(hora_inicio)s, %(hora_cierre)s, %(antecedentes)s, %(objetivo)s, %(temas_abordados)s, %(cierre_seguimiento)s,
            %(contacto_nombre)s, %(contacto_celular)s, %(contacto_institucion)s,
            %(provincia)s, %(canton)s, %(parroquia_recinto)s
        )
        RETURNING id
        """,
        datos,
    ).fetchone()
    return row["id"]


def actualizar_compromisos(
    con: _Conn, asamblea_id: int, acuerdos_json: str | None, estado_overall: str
) -> None:
    """Actualiza la lista de compromisos (JSON) y el estado global de una asamblea."""
    con.execute(
        "UPDATE asamblea_productiva "
        "SET acuerdos_compromisos = %s, estado_compromisos = %s WHERE id = %s",
        (acuerdos_json, estado_overall, asamblea_id),
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
        condiciones_rep.append(f"to_char({_FECHA_EVENTO_INICIAL_SQL}, 'YYYY') = %s")
        condiciones_asm.append("to_char(fecha::date, 'YYYY') = %s")
        params_rep.append(str(anio))
        params_asm.append(str(anio))
    if mes:
        condiciones_rep.append(f"to_char({_FECHA_EVENTO_INICIAL_SQL}, 'MM') = %s")
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

    num_capacitaciones = r["cnt"] if r else 0
    personas_capacitadas = r["personas"] if r else 0
    num_asambleas = a["cnt"] if a else 0
    personas_asambleas = a["personas"] if a else 0

    return {
        "num_capacitaciones":                 num_capacitaciones,
        "personas_capacitadas":               personas_capacitadas,
        "num_asambleas":                      num_asambleas,
        "personas_asambleas":                 personas_asambleas,
        "total_capacitados_incluye_asamblea": personas_capacitadas + personas_asambleas,
        "num_capacitaciones_incluye_asamblea": num_capacitaciones + num_asambleas,
    }
