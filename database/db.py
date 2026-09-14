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
import re
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


# ---------------------------------------------------------------------------
# Seguimiento del Congreso Internacional — octubre de 2026
# ---------------------------------------------------------------------------

_CAMPOS_EDITABLES_CONGRESO = {
    "oficina",
    "responsable_id",
    "nombre_asistente_delegado",
    "cargos_asistentes_delegados",
    "confirmado",
    "asistencia_21",
    "asistencia_22",
    "observaciones_seguimiento",
    "numero_oficio",
    "observaciones_cruce",
}

_CAMPOS_CONFIRMACION_PROYECCION = {
    "confirmados",
    "contacto_nombre",
    "contacto_celular",
    "observaciones",
}

_ACTORES_ADICIONALES_PROYECCION_GUAYAQUIL = {"José Matías"}


def _validar_actor_proyeccion_guayaquil(
    con: _Conn,
    actor_responsable_id: int | None,
    actor_nombre_declarado: str,
) -> str:
    if actor_responsable_id is None:
        if actor_nombre_declarado in _ACTORES_ADICIONALES_PROYECCION_GUAYAQUIL:
            return actor_nombre_declarado
        raise ValueError("Selecciona el funcionario de Guayaquil que realiza el cambio.")
    actor = con.execute(
        """
        SELECT nombres
        FROM congreso_responsables
        WHERE id = %s AND oficina = 'guayaquil' AND activo = TRUE
        """,
        (actor_responsable_id,),
    ).fetchone()
    if actor is None:
        raise PermissionError(
            "Solo un funcionario activo de Guayaquil puede modificar la proyección."
        )
    return str(actor["nombres"])


def precargar_proyeccion_estudiantes(
    con: _Conn, filas: list[dict[str, Any]]
) -> int:
    """Inserta únicamente las filas iniciales que todavía no existen."""
    insertadas = 0
    for item in filas:
        row = con.execute(
            """
            INSERT INTO congreso_proyeccion_estudiantes (
                clave_precarga, orden, institucion, institucion_normalizada, proyeccion,
                confirmados, nota_original, observaciones
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                item["clave_precarga"],
                item["orden"],
                item["institucion"],
                item["institucion_normalizada"],
                item["proyeccion"],
                item.get("confirmados", 0),
                item.get("nota_original"),
                item.get("nota_original"),
            ),
        ).fetchone()
        if row is not None:
            insertadas += 1
    return insertadas


def listar_proyeccion_estudiantes(
    con: _Conn, solo_activos: bool | None = True
) -> list[Any]:
    if solo_activos is None:
        where = ""
        params: tuple[Any, ...] = ()
    else:
        where = "WHERE activo = %s"
        params = (solo_activos,)
    return con.execute(
        f"""
        SELECT *
        FROM congreso_proyeccion_estudiantes
        {where}
        ORDER BY orden, institucion
        """,
        params,
    ).fetchall()


def crear_institucion_proyeccion(
    con: _Conn,
    institucion: str,
    institucion_normalizada: str,
    proyeccion: int,
    actor_responsable_id: int | None,
    actor_nombre_declarado: str,
) -> int:
    actor_nombre = _validar_actor_proyeccion_guayaquil(
        con, actor_responsable_id, actor_nombre_declarado
    )
    institucion = institucion.strip()
    if not institucion or not institucion_normalizada:
        raise ValueError("Ingresa el nombre de la institución.")
    if isinstance(proyeccion, bool) or not isinstance(proyeccion, int) or proyeccion < 0:
        raise ValueError("La proyección debe ser un número entero igual o mayor que cero.")
    existente = con.execute(
        "SELECT id FROM congreso_proyeccion_estudiantes WHERE institucion_normalizada = %s",
        (institucion_normalizada,),
    ).fetchone()
    if existente is not None:
        raise ValueError("Ya existe una universidad o institución con ese nombre.")
    con.execute("LOCK TABLE congreso_proyeccion_estudiantes IN SHARE ROW EXCLUSIVE MODE")
    row = con.execute(
        """
        INSERT INTO congreso_proyeccion_estudiantes (
            orden, institucion, institucion_normalizada, proyeccion,
            confirmados, ultimo_actor_responsable_id, ultimo_actor_nombre
        )
        VALUES (
            (SELECT COALESCE(MAX(orden), 0) + 1 FROM congreso_proyeccion_estudiantes),
            %s, %s, %s, 0, %s, %s
        )
        RETURNING id
        """,
        (
            institucion,
            institucion_normalizada,
            proyeccion,
            actor_responsable_id,
            actor_nombre,
        ),
    ).fetchone()
    registro_id = int(row["id"])
    _registrar_historial_congreso(
        con,
        entidad_tipo="proyeccion_estudiantes",
        entidad_id=registro_id,
        invitado_id=None,
        oficina="guayaquil",
        accion="Creación",
        campo="institucion",
        valor_anterior=None,
        valor_nuevo=institucion,
        actor_responsable_id=actor_responsable_id,
        actor_nombre=actor_nombre,
        actor_oficina="guayaquil",
    )
    return registro_id


def actualizar_confirmacion_proyeccion(
    con: _Conn,
    registro_id: int,
    cambios: dict[str, Any],
    actor_responsable_id: int | None,
    actor_nombre_declarado: str,
) -> int:
    campos_invalidos = set(cambios) - _CAMPOS_CONFIRMACION_PROYECCION
    if campos_invalidos:
        raise ValueError(f"Campos no editables: {', '.join(sorted(campos_invalidos))}")
    actor_nombre = _validar_actor_proyeccion_guayaquil(
        con, actor_responsable_id, actor_nombre_declarado
    )
    actual = con.execute(
        "SELECT * FROM congreso_proyeccion_estudiantes WHERE id = %s FOR UPDATE",
        (registro_id,),
    ).fetchone()
    if actual is None or not actual["activo"]:
        raise ValueError("La institución seleccionada ya no está activa.")

    nuevos = {
        "confirmados": cambios.get("confirmados", actual["confirmados"]),
        "contacto_nombre": cambios.get("contacto_nombre", actual["contacto_nombre"]),
        "contacto_celular": cambios.get("contacto_celular", actual["contacto_celular"]),
        "observaciones": cambios.get("observaciones", actual["observaciones"]),
    }
    for campo in ("contacto_nombre", "contacto_celular", "observaciones"):
        valor = nuevos[campo]
        nuevos[campo] = str(valor).strip() if valor is not None else None
        if nuevos[campo] == "":
            nuevos[campo] = None
    confirmados = nuevos["confirmados"]
    if isinstance(confirmados, bool) or not isinstance(confirmados, int) or confirmados < 0:
        raise ValueError("Confirmados debe ser un número entero igual o mayor que cero.")
    if nuevos["contacto_celular"] and len(re.sub(r"\D", "", nuevos["contacto_celular"])) < 7:
        raise ValueError("El celular de contacto debe contener al menos siete dígitos.")
    cambia_confirmados = actual["confirmados"] != confirmados
    if cambia_confirmados and (
        not nuevos["contacto_nombre"] or not nuevos["contacto_celular"]
    ):
        raise ValueError(
            f"Completa el nombre y celular de contacto de {actual['institucion']} "
            "antes de cambiar sus confirmados."
        )
    cambios_reales = {
        campo: valor for campo, valor in nuevos.items() if actual[campo] != valor
    }
    if not cambios_reales:
        return 0
    asignaciones = ", ".join(f"{campo} = %s" for campo in cambios_reales)
    con.execute(
        f"""
        UPDATE congreso_proyeccion_estudiantes
        SET {asignaciones}, ultimo_actor_responsable_id = %s,
            ultimo_actor_nombre = %s, fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        [*cambios_reales.values(), actor_responsable_id, actor_nombre, registro_id],
    )
    for campo, valor_nuevo in cambios_reales.items():
        _registrar_historial_congreso(
            con,
            entidad_tipo="proyeccion_estudiantes",
            entidad_id=registro_id,
            invitado_id=None,
            oficina="guayaquil",
            accion="Actualización",
            campo=campo,
            valor_anterior=actual[campo],
            valor_nuevo=valor_nuevo,
            actor_responsable_id=actor_responsable_id,
            actor_nombre=actor_nombre,
            actor_oficina="guayaquil",
        )
    return len(cambios_reales)


def actualizar_institucion_proyeccion(
    con: _Conn,
    registro_id: int,
    institucion: str,
    institucion_normalizada: str,
    proyeccion: int,
    activo: bool,
    actor_responsable_id: int | None,
    actor_nombre_declarado: str,
) -> int:
    actor_nombre = _validar_actor_proyeccion_guayaquil(
        con, actor_responsable_id, actor_nombre_declarado
    )
    actual = con.execute(
        "SELECT * FROM congreso_proyeccion_estudiantes WHERE id = %s FOR UPDATE",
        (registro_id,),
    ).fetchone()
    if actual is None:
        raise ValueError("La institución seleccionada ya no existe.")
    institucion = institucion.strip()
    if not institucion or not institucion_normalizada:
        raise ValueError("Ingresa el nombre de la institución.")
    if isinstance(proyeccion, bool) or not isinstance(proyeccion, int) or proyeccion < 0:
        raise ValueError("La proyección debe ser un número entero igual o mayor que cero.")
    duplicado = con.execute(
        """
        SELECT id FROM congreso_proyeccion_estudiantes
        WHERE institucion_normalizada = %s AND id <> %s
        """,
        (institucion_normalizada, registro_id),
    ).fetchone()
    if duplicado is not None:
        raise ValueError("Ya existe una universidad o institución con ese nombre.")
    nuevos = {
        "institucion": institucion,
        "institucion_normalizada": institucion_normalizada,
        "proyeccion": proyeccion,
        "activo": bool(activo),
    }
    cambios_reales = {
        campo: valor for campo, valor in nuevos.items() if actual[campo] != valor
    }
    if not cambios_reales:
        return 0
    asignaciones = ", ".join(f"{campo} = %s" for campo in cambios_reales)
    con.execute(
        f"""
        UPDATE congreso_proyeccion_estudiantes
        SET {asignaciones}, ultimo_actor_responsable_id = %s,
            ultimo_actor_nombre = %s, fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        [*cambios_reales.values(), actor_responsable_id, actor_nombre, registro_id],
    )
    for campo, valor_nuevo in cambios_reales.items():
        if campo == "institucion_normalizada":
            continue
        accion = "Actualización"
        if campo == "activo":
            accion = "Reactivación" if valor_nuevo else "Desactivación"
        _registrar_historial_congreso(
            con,
            entidad_tipo="proyeccion_estudiantes",
            entidad_id=registro_id,
            invitado_id=None,
            oficina="guayaquil",
            accion=accion,
            campo=campo,
            valor_anterior=actual[campo],
            valor_nuevo=valor_nuevo,
            actor_responsable_id=actor_responsable_id,
            actor_nombre=actor_nombre,
            actor_oficina="guayaquil",
        )
    return len([campo for campo in cambios_reales if campo != "institucion_normalizada"])


def contar_invitados_congreso(con: _Conn) -> int:
    row = con.execute("SELECT COUNT(*) AS total FROM congreso_invitados").fetchone()
    return int(row["total"]) if row else 0


def listar_responsables_congreso(
    con: _Conn,
    oficina: str | None = None,
    solo_activos: bool = False,
) -> list[Any]:
    condiciones: list[str] = []
    params: list[Any] = []
    if oficina is not None:
        condiciones.append("oficina = %s")
        params.append(oficina)
    if solo_activos:
        condiciones.append("activo = TRUE")
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    return con.execute(
        f"""
        SELECT r.*,
               (SELECT COUNT(*) FROM congreso_invitados i
                WHERE i.responsable_id = r.id) AS invitados_asignados
        FROM congreso_responsables r
        {where}
        ORDER BY r.oficina, r.activo DESC, r.nombres
        """,
        params,
    ).fetchall()


def crear_responsable_congreso(
    con: _Conn,
    oficina: str,
    nombres: str,
    celular: str,
    correo: str,
    actor_responsable_id: int | None,
    actor_nombre: str,
    actor_oficina: str,
) -> int:
    row = con.execute(
        """
        INSERT INTO congreso_responsables (oficina, nombres, celular, correo)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (oficina, nombres.strip(), celular.strip(), correo.strip().lower()),
    ).fetchone()
    responsable_id = int(row["id"])
    _registrar_historial_congreso(
        con,
        entidad_tipo="responsable",
        entidad_id=responsable_id,
        invitado_id=None,
        oficina=oficina,
        accion="Creación",
        campo="Responsable",
        valor_anterior=None,
        valor_nuevo=nombres.strip(),
        actor_responsable_id=actor_responsable_id,
        actor_nombre=actor_nombre,
        actor_oficina=actor_oficina,
    )
    return responsable_id


def actualizar_responsable_congreso(
    con: _Conn,
    responsable_id: int,
    nombres: str,
    celular: str,
    correo: str,
    activo: bool,
    actor_responsable_id: int | None,
    actor_nombre: str,
    actor_oficina: str,
    oficina_permitida: str | None = None,
) -> None:
    actual = con.execute(
        "SELECT * FROM congreso_responsables WHERE id = %s", (responsable_id,)
    ).fetchone()
    if actual is None:
        raise ValueError("El responsable seleccionado ya no existe.")
    if oficina_permitida is not None and actual["oficina"] != oficina_permitida:
        raise PermissionError("No puedes modificar responsables de otra oficina.")
    if not activo:
        asignados = con.execute(
            "SELECT COUNT(*) AS total FROM congreso_invitados WHERE responsable_id = %s",
            (responsable_id,),
        ).fetchone()["total"]
        if asignados:
            raise ValueError(
                "Reasigna primero los invitados de este responsable antes de desactivarlo."
            )

    nuevos = {
        "nombres": nombres.strip(),
        "celular": celular.strip(),
        "correo": correo.strip().lower(),
        "activo": bool(activo),
    }
    cambios = {
        campo: valor
        for campo, valor in nuevos.items()
        if actual[campo] != valor
    }
    if not cambios:
        return

    con.execute(
        """
        UPDATE congreso_responsables
        SET nombres = %s, celular = %s, correo = %s, activo = %s,
            fecha_actualizacion = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (nuevos["nombres"], nuevos["celular"], nuevos["correo"], nuevos["activo"], responsable_id),
    )
    for campo, valor_nuevo in cambios.items():
        _registrar_historial_congreso(
            con,
            entidad_tipo="responsable",
            entidad_id=responsable_id,
            invitado_id=None,
            oficina=actual["oficina"],
            accion="Actualización",
            campo=campo,
            valor_anterior=actual[campo],
            valor_nuevo=valor_nuevo,
            actor_responsable_id=actor_responsable_id,
            actor_nombre=actor_nombre,
            actor_oficina=actor_oficina,
        )


def listar_invitados_congreso(
    con: _Conn,
    oficina: str | None = None,
) -> list[Any]:
    where = "WHERE i.oficina = %s" if oficina is not None else ""
    params = (oficina,) if oficina is not None else ()
    return con.execute(
        f"""
        SELECT i.*, r.nombres AS responsable_nombres,
               r.celular AS responsable_celular,
               r.correo AS responsable_correo,
               r.activo AS responsable_activo
        FROM congreso_invitados i
        LEFT JOIN congreso_responsables r ON r.id = i.responsable_id
        {where}
        ORDER BY i.oficina NULLS FIRST, i.institucion, i.destinatario_oficio
        """,
        params,
    ).fetchall()


def obtener_invitado_congreso(con: _Conn, invitado_id: int) -> Any | None:
    return con.execute(
        """
        SELECT i.*, r.nombres AS responsable_nombres,
               r.celular AS responsable_celular,
               r.correo AS responsable_correo
        FROM congreso_invitados i
        LEFT JOIN congreso_responsables r ON r.id = i.responsable_id
        WHERE i.id = %s
        """,
        (invitado_id,),
    ).fetchone()


def actualizar_invitado_congreso(
    con: _Conn,
    invitado_id: int,
    cambios: dict[str, Any],
    actor_responsable_id: int | None,
    actor_nombre: str,
    actor_oficina: str,
    oficina_permitida: str | None = None,
) -> int:
    campos_invalidos = set(cambios) - _CAMPOS_EDITABLES_CONGRESO
    if campos_invalidos:
        raise ValueError(f"Campos no editables: {', '.join(sorted(campos_invalidos))}")

    # Respaldo idempotente para despliegues donde Streamlit conserve la caché
    # de inicialización mientras ya sirve la interfaz actualizada.
    con.execute(
        "ALTER TABLE congreso_invitados "
        "ADD COLUMN IF NOT EXISTS cargos_asistentes_delegados TEXT"
    )
    actual = con.execute(
        "SELECT * FROM congreso_invitados WHERE id = %s", (invitado_id,)
    ).fetchone()
    if actual is None:
        raise ValueError("El invitado seleccionado ya no existe.")
    if oficina_permitida is not None and actual["oficina"] != oficina_permitida:
        raise PermissionError("No puedes modificar invitados de otra oficina.")

    oficina_nueva = cambios.get("oficina", actual["oficina"])
    responsable_nuevo = cambios.get("responsable_id", actual["responsable_id"])
    if responsable_nuevo is not None:
        responsable = con.execute(
            "SELECT id, oficina, activo FROM congreso_responsables WHERE id = %s",
            (responsable_nuevo,),
        ).fetchone()
        if responsable is None or not responsable["activo"]:
            raise ValueError("Selecciona un responsable activo.")
        if responsable["oficina"] != oficina_nueva:
            raise ValueError("El responsable debe pertenecer a la oficina asignada.")
    if oficina_nueva is None and responsable_nuevo is not None:
        raise ValueError("Un invitado sin oficina no puede tener responsable.")

    confirmado = cambios.get("confirmado", actual["confirmado"])
    asistente = cambios.get(
        "nombre_asistente_delegado", actual["nombre_asistente_delegado"]
    )
    dia_21 = cambios.get("asistencia_21", actual["asistencia_21"])
    dia_22 = cambios.get("asistencia_22", actual["asistencia_22"])
    if confirmado == "Sí" and (
        not str(asistente or "").strip() or (dia_21 != "Sí" and dia_22 != "Sí")
    ):
        raise ValueError(
            "Un invitado confirmado requiere el nombre del asistente o delegado "
            "y al menos un día de asistencia marcado Sí."
        )

    cambios_reales: dict[str, Any] = {}
    for campo, valor in cambios.items():
        if isinstance(valor, str):
            valor = valor.strip() or None
        if campo in {"confirmado", "asistencia_21", "asistencia_22"} and valor is None:
            valor = "Pendiente"
        if actual[campo] != valor:
            cambios_reales[campo] = valor
    if not cambios_reales:
        return 0

    asignaciones = ", ".join(f"{campo} = %s" for campo in cambios_reales)
    valores = list(cambios_reales.values()) + [invitado_id]
    con.execute(
        f"UPDATE congreso_invitados SET {asignaciones}, "
        "fecha_actualizacion = CURRENT_TIMESTAMP WHERE id = %s",
        valores,
    )

    def etiqueta_responsable(valor: Any) -> Any:
        if valor is None:
            return None
        row = con.execute(
            "SELECT nombres FROM congreso_responsables WHERE id = %s", (valor,)
        ).fetchone()
        return row["nombres"] if row else str(valor)

    for campo, valor_nuevo in cambios_reales.items():
        anterior = actual[campo]
        if campo == "responsable_id":
            anterior = etiqueta_responsable(anterior)
            valor_nuevo = etiqueta_responsable(valor_nuevo)
        _registrar_historial_congreso(
            con,
            entidad_tipo="invitado",
            entidad_id=invitado_id,
            invitado_id=invitado_id,
            oficina=oficina_nueva,
            accion="Actualización",
            campo=campo,
            valor_anterior=anterior,
            valor_nuevo=valor_nuevo,
            actor_responsable_id=actor_responsable_id,
            actor_nombre=actor_nombre,
            actor_oficina=actor_oficina,
        )
    return len(cambios_reales)


def listar_historial_congreso(
    con: _Conn,
    oficina: str | None = None,
    limite: int = 2000,
) -> list[Any]:
    where = "WHERE h.oficina = %s" if oficina is not None else ""
    params: list[Any] = [oficina] if oficina is not None else []
    params.append(limite)
    return con.execute(
        f"""
        SELECT h.*,
               COALESCE(i.institucion, p.institucion) AS institucion,
               i.destinatario_oficio
        FROM congreso_historial h
        LEFT JOIN congreso_invitados i ON i.id = h.invitado_id
        LEFT JOIN congreso_proyeccion_estudiantes p
               ON h.entidad_tipo = 'proyeccion_estudiantes'
              AND p.id = h.entidad_id
        {where}
        ORDER BY h.fecha_cambio DESC, h.id DESC
        LIMIT %s
        """,
        params,
    ).fetchall()


def importar_datos_congreso(
    con: _Conn,
    invitados: list[dict[str, Any]],
    responsables: list[dict[str, Any]],
    nombre_archivo: str,
    hash_archivo: str,
    actor_nombre: str,
) -> int:
    con.execute("LOCK TABLE congreso_invitados IN EXCLUSIVE MODE")
    if contar_invitados_congreso(con) > 0:
        raise ValueError("La carga inicial ya fue realizada; no se permiten cargas adicionales.")
    repetida = con.execute(
        "SELECT 1 FROM congreso_importaciones WHERE hash_archivo = %s", (hash_archivo,)
    ).fetchone()
    if repetida:
        raise ValueError("Este archivo ya fue importado.")

    responsables_ids: dict[tuple[str, str], int] = {}
    for item in responsables:
        row = con.execute(
            """
            INSERT INTO congreso_responsables (oficina, nombres, celular, correo)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (item["oficina"], item["nombres"], item["celular"], item["correo"]),
        ).fetchone()
        responsables_ids[(item["oficina"], item["nombres"].casefold())] = int(row["id"])

    columnas = [
        "fila_origen", "numero_lista", "institucion", "tipo_institucion",
        "destinatario_oficio", "firma", "calidad", "cargo", "direccion",
        "correo_institucional", "telefonos_institucionales", "sitio_web",
        "tipo_invitacion", "oficina", "responsable_id",
        "nombre_asistente_delegado", "cargos_asistentes_delegados",
        "confirmado", "asistencia_21",
        "asistencia_22", "observaciones_seguimiento", "numero_oficio",
        "observaciones_cruce",
    ]
    insertados = 0
    for item in invitados:
        datos_item = dict(item)
        responsable_id = None
        responsable_nombre = datos_item.pop("_responsable_nombre", None)
        if datos_item.get("oficina") and responsable_nombre:
            responsable_id = responsables_ids.get(
                (datos_item["oficina"], responsable_nombre.casefold())
            )
        datos_item["responsable_id"] = responsable_id
        valores = [datos_item.get(columna) for columna in columnas]
        placeholders = ", ".join(["%s"] * len(columnas))
        row = con.execute(
            f"INSERT INTO congreso_invitados ({', '.join(columnas)}) "
            f"VALUES ({placeholders}) RETURNING id",
            valores,
        ).fetchone()
        invitado_id = int(row["id"])
        _registrar_historial_congreso(
            con,
            entidad_tipo="invitado",
            entidad_id=invitado_id,
            invitado_id=invitado_id,
            oficina=datos_item.get("oficina"),
            accion="Importación inicial",
            campo=None,
            valor_anterior=None,
            valor_nuevo=datos_item["institucion"],
            actor_responsable_id=None,
            actor_nombre=actor_nombre,
            actor_oficina="guayaquil",
        )
        insertados += 1

    con.execute(
        """
        INSERT INTO congreso_importaciones
            (nombre_archivo, hash_archivo, cantidad_registros, resultado, actor_nombre)
        VALUES (%s, %s, %s, 'Completada', %s)
        """,
        (nombre_archivo, hash_archivo, insertados, actor_nombre),
    )
    return insertados


def sincronizar_documentos_congreso(
    con: _Conn,
    actualizaciones: list[dict[str, Any]],
    nuevos_invitados: list[dict[str, Any]],
    actor_nombre: str = "Sincronización documental",
) -> int:
    """Completa metadatos documentales e incorpora oficios firmados una sola vez.

    Las filas del Excel se identifican por ``fila_origen``. Los campos ya
    completados manualmente se conservan, salvo el número abreviado del oficio,
    que se expande al código documental completo cuando representa los mismos
    números.
    """
    con.execute(
        "ALTER TABLE congreso_invitados "
        "ADD COLUMN IF NOT EXISTS telefonos_institucionales TEXT"
    )
    con.execute(
        "ALTER TABLE congreso_invitados "
        "ADD COLUMN IF NOT EXISTS tipo_invitacion TEXT"
    )
    con.execute("LOCK TABLE congreso_invitados IN EXCLUSIVE MODE")

    def numeros(valor: Any) -> list[str]:
        return re.findall(r"(?<!\d)(?:SCE-(?:IGT-IR-)?2026-)?(\d{3})(?!\d)", str(valor or ""))

    cambios_totales = 0

    def aplicar_cambios(actual: Any, cambios: dict[str, Any], accion: str) -> None:
        nonlocal cambios_totales
        if not cambios:
            return
        asignaciones = ", ".join(f"{campo} = %s" for campo in cambios)
        con.execute(
            f"UPDATE congreso_invitados SET {asignaciones}, "
            "fecha_actualizacion = CURRENT_TIMESTAMP WHERE id = %s",
            [*cambios.values(), actual["id"]],
        )
        for campo, valor_nuevo in cambios.items():
            _registrar_historial_congreso(
                con,
                entidad_tipo="invitado",
                entidad_id=actual["id"],
                invitado_id=actual["id"],
                oficina=cambios.get("oficina", actual.get("oficina")),
                accion=accion,
                campo=campo,
                valor_anterior=actual.get(campo),
                valor_nuevo=valor_nuevo,
                actor_responsable_id=None,
                actor_nombre=actor_nombre,
                actor_oficina="guayaquil",
            )
        cambios_totales += len(cambios)

    por_fila: dict[int, list[dict[str, Any]]] = {}
    for item in actualizaciones:
        por_fila.setdefault(item["fila_origen"], []).append(item)

    columnas_clon = [
        "fila_origen", "numero_lista", "institucion", "tipo_institucion",
        "destinatario_oficio", "firma", "calidad", "cargo", "direccion",
        "correo_institucional", "telefonos_institucionales", "sitio_web",
        "tipo_invitacion", "oficina", "responsable_id",
        "nombre_asistente_delegado", "cargos_asistentes_delegados",
        "confirmado", "asistencia_21", "asistencia_22",
        "observaciones_seguimiento", "numero_oficio", "observaciones_cruce",
    ]

    # Divide filas que en el Excel contenían varios oficios. La primera conserva
    # el registro y su historial; las demás copian su estado actual para que a
    # partir de este punto cada invitación tenga seguimiento independiente.
    for fila_origen, items_fila in por_fila.items():
        items_unicos = list({item.get("numero_oficio"): item for item in items_fila}.values())
        if len(items_unicos) < 2:
            continue
        filas_db = con.execute(
            "SELECT * FROM congreso_invitados WHERE fila_origen = %s ORDER BY id",
            (fila_origen,),
        ).fetchall()
        if not filas_db:
            continue
        codigos_esperados = [item["numero_oficio"] for item in items_unicos]
        numeros_esperados = [numero for codigo in codigos_esperados for numero in numeros(codigo)]
        por_codigo = {fila.get("numero_oficio"): fila for fila in filas_db}
        fuente = next(
            (
                fila for fila in filas_db
                if numeros(fila.get("numero_oficio")) == numeros_esperados
            ),
            por_codigo.get(codigos_esperados[0]),
        )
        if fuente is None:
            # Se preserva una eventual corrección manual que ya no corresponda
            # a los códigos documentales originales.
            continue

        primer_item = items_unicos[0]
        if fuente.get("numero_oficio") != primer_item["numero_oficio"]:
            aplicar_cambios(
                fuente,
                {
                    "numero_oficio": primer_item["numero_oficio"],
                    "tipo_invitacion": primer_item.get("tipo_invitacion"),
                },
                "División por oficio",
            )
            fuente = dict(fuente)
            fuente.update(
                numero_oficio=primer_item["numero_oficio"],
                tipo_invitacion=primer_item.get("tipo_invitacion"),
            )
            por_codigo[primer_item["numero_oficio"]] = fuente

        for item in items_unicos[1:]:
            codigo = item["numero_oficio"]
            if codigo in por_codigo:
                continue
            datos_clon = dict(fuente)
            datos_clon["numero_oficio"] = codigo
            datos_clon["tipo_invitacion"] = item.get("tipo_invitacion")
            valores = [datos_clon.get(columna) for columna in columnas_clon]
            row = con.execute(
                f"INSERT INTO congreso_invitados ({', '.join(columnas_clon)}) "
                f"VALUES ({', '.join(['%s'] * len(columnas_clon))}) RETURNING id",
                valores,
            ).fetchone()
            invitado_id = int(row["id"])
            _registrar_historial_congreso(
                con,
                entidad_tipo="invitado",
                entidad_id=invitado_id,
                invitado_id=invitado_id,
                oficina=datos_clon.get("oficina"),
                accion="División por oficio",
                campo="numero_oficio",
                valor_anterior=None,
                valor_nuevo=codigo,
                actor_responsable_id=None,
                actor_nombre=actor_nombre,
                actor_oficina="guayaquil",
            )
            cambios_totales += 1

    for item in actualizaciones:
        actual = con.execute(
            """
            SELECT * FROM congreso_invitados
            WHERE fila_origen = %s AND numero_oficio IS NOT DISTINCT FROM %s
            ORDER BY id LIMIT 1
            """,
            (item["fila_origen"], item.get("numero_oficio")),
        ).fetchone()
        if actual is None and len(por_fila[item["fila_origen"]]) == 1:
            actual = con.execute(
                "SELECT * FROM congreso_invitados WHERE fila_origen = %s ORDER BY id LIMIT 1",
                (item["fila_origen"],),
            ).fetchone()
        if actual is None:
            continue
        cambios: dict[str, Any] = {}
        telefono = item.get("telefonos_institucionales")
        if telefono and not actual.get("telefonos_institucionales"):
            cambios["telefonos_institucionales"] = telefono
        tipo = item.get("tipo_invitacion")
        if tipo and not actual.get("tipo_invitacion"):
            cambios["tipo_invitacion"] = tipo
        oficina = item.get("oficina")
        if oficina and not actual.get("oficina"):
            cambios["oficina"] = oficina
        responsable_nombre = item.get("responsable_nombre")
        if responsable_nombre and actual.get("responsable_id") is None:
            responsable = con.execute(
                """
                SELECT id FROM congreso_responsables
                WHERE oficina = %s AND LOWER(nombres) = LOWER(%s) AND activo = TRUE
                """,
                (oficina or actual.get("oficina"), responsable_nombre),
            ).fetchone()
            if responsable is not None:
                cambios["responsable_id"] = int(responsable["id"])
        oficio = item.get("numero_oficio")
        oficio_actual = actual.get("numero_oficio")
        if oficio and oficio_actual != oficio:
            # Solo amplía valores vacíos o abreviados equivalentes; no pisa
            # correcciones manuales con una numeración documental diferente.
            if not oficio_actual or numeros(oficio_actual) == numeros(oficio):
                cambios["numero_oficio"] = oficio
        aplicar_cambios(actual, cambios, "Sincronización documental")

    for item in nuevos_invitados:
        existente = con.execute(
            "SELECT id FROM congreso_invitados WHERE numero_oficio = %s",
            (item["numero_oficio"],),
        ).fetchone()
        if existente:
            continue
        row = con.execute(
            """
            INSERT INTO congreso_invitados (
                numero_lista, institucion, tipo_institucion, destinatario_oficio,
                firma, calidad, cargo, direccion, correo_institucional,
                telefonos_institucionales, sitio_web, tipo_invitacion, oficina,
                confirmado, asistencia_21, asistencia_22, numero_oficio
            ) VALUES (
                %(numero_lista)s, %(institucion)s, %(tipo_institucion)s,
                %(destinatario_oficio)s, %(firma)s, %(calidad)s, %(cargo)s,
                %(direccion)s, %(correo_institucional)s,
                %(telefonos_institucionales)s, %(sitio_web)s,
                %(tipo_invitacion)s, %(oficina)s, 'Pendiente', 'Pendiente',
                'Pendiente', %(numero_oficio)s
            ) RETURNING id
            """,
            item,
        ).fetchone()
        invitado_id = int(row["id"])
        _registrar_historial_congreso(
            con,
            entidad_tipo="invitado",
            entidad_id=invitado_id,
            invitado_id=invitado_id,
            oficina=item.get("oficina"),
            accion="Incorporación desde oficio firmado",
            campo=None,
            valor_anterior=None,
            valor_nuevo=f"{item['numero_oficio']} — {item['institucion']}",
            actor_responsable_id=None,
            actor_nombre=actor_nombre,
            actor_oficina="guayaquil",
        )
        cambios_totales += 1
    return cambios_totales


def _registrar_historial_congreso(
    con: _Conn,
    *,
    entidad_tipo: str,
    entidad_id: int | None,
    invitado_id: int | None,
    oficina: str | None,
    accion: str,
    campo: str | None,
    valor_anterior: Any,
    valor_nuevo: Any,
    actor_responsable_id: int | None,
    actor_nombre: str,
    actor_oficina: str | None,
) -> None:
    con.execute(
        """
        INSERT INTO congreso_historial (
            entidad_tipo, entidad_id, invitado_id, oficina, accion, campo,
            valor_anterior, valor_nuevo, actor_responsable_id,
            actor_nombre, actor_oficina
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            entidad_tipo,
            entidad_id,
            invitado_id,
            oficina,
            accion,
            campo,
            None if valor_anterior is None else str(valor_anterior),
            None if valor_nuevo is None else str(valor_nuevo),
            actor_responsable_id,
            actor_nombre,
            actor_oficina,
        ),
    )


# ---------------------------------------------------------------------------
# Checklist y proyección de estudiantes del Congreso
# ---------------------------------------------------------------------------

_CHECKLIST_INICIAL = (
    ("Alimentación", "Coffee break — día 1", None),
    ("Alimentación", "Coffee break — día 2", None),
    ("Alimentación", "Almuerzos — día 1", None),
    ("Alimentación", "Almuerzos — día 2", None),
    ("Protocolo", "Autoridades", None),
    ("Protocolo", "Vocativos", None),
    ("Protocolo", "Maestro de ceremonia", None),
    ("Impresos y acreditación", "Impresión de tickets para coffee break", 550),
    ("Feria de emprendedores", "Asistentes de la feria de emprendedores", None),
    ("Logística", "Montaje de salón, mobiliario y señalética", None),
    ("Logística", "Audio, video, iluminación e internet", None),
    ("Registro", "Acreditación y control de asistencia", None),
    ("Seguridad", "Primeros auxilios, seguridad y plan de contingencia", None),
    ("Comunicación", "Fotografía, prensa y difusión", None),
)


def asegurar_checklist_congreso(con: _Conn) -> None:
    """Crea los rubros base y asigna los tres funcionarios de Guayaquil."""
    for rubro, actividad, cantidad in _CHECKLIST_INICIAL:
        con.execute(
            """
            INSERT INTO congreso_checklist
                (rubro, actividad, cantidad_meta, responsables_adicionales)
            VALUES (%s, %s, %s, 'José Matías')
            ON CONFLICT (rubro, actividad) DO NOTHING
            """,
            (rubro, actividad, cantidad),
        )

    responsables = con.execute(
        """
        SELECT id FROM congreso_responsables
        WHERE oficina = 'guayaquil' AND activo = TRUE
          AND LOWER(nombres) IN ('ing. milka nazareno', 'ab. carlos garcía')
        ORDER BY nombres
        """
    ).fetchall()
    if not responsables:
        return
    items = con.execute("SELECT id FROM congreso_checklist").fetchall()
    for item in items:
        tiene_asignados = con.execute(
            "SELECT 1 FROM congreso_checklist_responsables WHERE checklist_id = %s LIMIT 1",
            (item["id"],),
        ).fetchone()
        if tiene_asignados:
            continue
        for responsable in responsables:
            con.execute(
                """
                INSERT INTO congreso_checklist_responsables (checklist_id, responsable_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
                """,
                (item["id"], responsable["id"]),
            )


def listar_checklist_congreso(con: _Conn) -> list[Any]:
    return con.execute(
        """
        SELECT c.*,
               concat_ws(
                   ', ',
                   NULLIF(string_agg(r.nombres, ', ' ORDER BY r.nombres), ''),
                   NULLIF(c.responsables_adicionales, '')
               ) AS responsables,
               COALESCE(array_agg(r.id ORDER BY r.nombres)
                        FILTER (WHERE r.id IS NOT NULL), ARRAY[]::integer[]) AS responsables_ids
        FROM congreso_checklist c
        LEFT JOIN congreso_checklist_responsables cr ON cr.checklist_id = c.id
        LEFT JOIN congreso_responsables r ON r.id = cr.responsable_id
        GROUP BY c.id
        ORDER BY c.rubro, c.id
        """
    ).fetchall()


def crear_item_checklist_congreso(
    con: _Conn,
    rubro: str,
    actividad: str,
    cantidad_meta: int | None,
    fecha_limite: Any,
    observaciones: str,
    responsables_ids: list[int],
    responsables_adicionales: str,
    actor_responsable_id: int | None,
    actor_nombre: str,
) -> int:
    row = con.execute(
        """
        INSERT INTO congreso_checklist
            (rubro, actividad, cantidad_meta, fecha_limite, observaciones,
             responsables_adicionales, actualizado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            rubro.strip(), actividad.strip(), cantidad_meta, fecha_limite,
            observaciones.strip() or None, responsables_adicionales.strip() or None,
            actor_nombre,
        ),
    ).fetchone()
    item_id = int(row["id"])
    for responsable_id in responsables_ids:
        con.execute(
            "INSERT INTO congreso_checklist_responsables VALUES (%s, %s)",
            (item_id, responsable_id),
        )
    _registrar_historial_checklist(
        con, item_id, rubro.strip(), actividad.strip(), "Creación", None,
        actividad.strip(), actor_responsable_id, actor_nombre,
    )
    return item_id


def actualizar_item_checklist_congreso(
    con: _Conn,
    item_id: int,
    cambios: dict[str, Any],
    responsables_ids: list[int],
    actor_responsable_id: int | None,
    actor_nombre: str,
) -> int:
    actual = con.execute("SELECT * FROM congreso_checklist WHERE id = %s", (item_id,)).fetchone()
    if actual is None:
        raise ValueError("El ítem seleccionado ya no existe.")
    permitidos = {
        "rubro", "actividad", "listo", "cantidad_meta", "fecha_limite",
        "observaciones", "responsables_adicionales",
    }
    if set(cambios) - permitidos:
        raise ValueError("Se intentó modificar un campo no permitido.")

    normalizados: dict[str, Any] = {}
    for campo, valor in cambios.items():
        if isinstance(valor, str):
            valor = valor.strip() or None
        if actual[campo] != valor:
            normalizados[campo] = valor
    if normalizados:
        asignaciones = ", ".join(f"{campo} = %s" for campo in normalizados)
        con.execute(
            f"UPDATE congreso_checklist SET {asignaciones}, actualizado_por = %s, "
            "fecha_actualizacion = CURRENT_TIMESTAMP WHERE id = %s",
            [*normalizados.values(), actor_nombre, item_id],
        )
        for campo, nuevo in normalizados.items():
            _registrar_historial_checklist(
                con, item_id, cambios.get("rubro", actual["rubro"]),
                cambios.get("actividad", actual["actividad"]), campo,
                actual[campo], nuevo, actor_responsable_id, actor_nombre,
            )

    actuales = {
        row["responsable_id"] for row in con.execute(
            "SELECT responsable_id FROM congreso_checklist_responsables WHERE checklist_id = %s",
            (item_id,),
        ).fetchall()
    }
    nuevos = set(responsables_ids)
    if actuales != nuevos:
        nombres_antes = con.execute(
            "SELECT nombres FROM congreso_responsables WHERE id = ANY(%s) ORDER BY nombres",
            (list(actuales),),
        ).fetchall() if actuales else []
        nombres_despues = con.execute(
            "SELECT nombres FROM congreso_responsables WHERE id = ANY(%s) ORDER BY nombres",
            (list(nuevos),),
        ).fetchall() if nuevos else []
        con.execute("DELETE FROM congreso_checklist_responsables WHERE checklist_id = %s", (item_id,))
        for responsable_id in nuevos:
            con.execute(
                "INSERT INTO congreso_checklist_responsables VALUES (%s, %s)",
                (item_id, responsable_id),
            )
        _registrar_historial_checklist(
            con, item_id, cambios.get("rubro", actual["rubro"]),
            cambios.get("actividad", actual["actividad"]), "responsables",
            ", ".join(row["nombres"] for row in nombres_antes),
            ", ".join(row["nombres"] for row in nombres_despues),
            actor_responsable_id, actor_nombre,
        )
        normalizados["responsables"] = responsables_ids
    return len(normalizados)


def _registrar_historial_checklist(
    con: _Conn,
    item_id: int,
    rubro: str,
    actividad: str,
    campo: str,
    anterior: Any,
    nuevo: Any,
    actor_responsable_id: int | None,
    actor_nombre: str,
) -> None:
    con.execute(
        """
        INSERT INTO congreso_checklist_historial
            (checklist_id, rubro, actividad, campo, valor_anterior, valor_nuevo,
             actor_responsable_id, actor_nombre)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            item_id, rubro, actividad, campo,
            None if anterior is None else str(anterior),
            None if nuevo is None else str(nuevo),
            actor_responsable_id, actor_nombre,
        ),
    )


def listar_historial_checklist_congreso(con: _Conn, limite: int = 1000) -> list[Any]:
    return con.execute(
        """
        SELECT * FROM congreso_checklist_historial
        ORDER BY fecha_cambio DESC, id DESC LIMIT %s
        """,
        (limite,),
    ).fetchall()
