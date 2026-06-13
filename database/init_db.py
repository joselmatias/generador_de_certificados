"""
init_db.py — Inicialización de la base de datos PostgreSQL (Supabase).

Crea las tablas del sistema si no existen. Diseñado para ejecutarse
una sola vez al arrancar la aplicación (idempotente).

La cadena de conexión se lee de la variable de entorno DATABASE_URL o,
si no existe, de st.secrets["DATABASE_URL"] (Streamlit Cloud).
"""

import os

import psycopg2


def _dsn() -> str:
    """
    Devuelve la cadena de conexión a Postgres.

    Prioridad:
    1. Variable de entorno DATABASE_URL (para scripts fuera de Streamlit).
    2. st.secrets["DATABASE_URL"] (en la app de Streamlit).
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
        except Exception:
            url = None
    if not url:
        raise RuntimeError(
            "DATABASE_URL no está configurada. Defínela como variable de entorno "
            "o en .streamlit/secrets.toml / Streamlit Cloud → Settings → Secrets."
        )
    return url


# DDL de cada tabla (PostgreSQL)
_DDL_CAPACITACIONES = """
CREATE TABLE IF NOT EXISTS capacitaciones (
    id                  SERIAL PRIMARY KEY,
    oficina             TEXT NOT NULL,
    timestamp_forms     TEXT,
    nombre              TEXT NOT NULL,
    email               TEXT,
    cedula              TEXT NOT NULL,
    fecha_capacitacion  TEXT NOT NULL,
    institucion         TEXT,
    provincia           TEXT,
    nombre_curso        TEXT NOT NULL,
    codigo_certificado  TEXT UNIQUE,
    p1_conocimiento     INTEGER,
    p2_inquietudes      INTEGER,
    p3_contenido        INTEGER,
    p4_presencialidad   INTEGER,
    p5_puntualidad      INTEGER,
    p6_logistica        INTEGER,
    p7_duracion         INTEGER,
    temas_adicionales   TEXT,
    sugerencias         TEXT,
    fecha_registro      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    registrado_por      TEXT
);
"""

_DDL_ASAMBLEAS = """
CREATE TABLE IF NOT EXISTS asambleas (
    id                  SERIAL PRIMARY KEY,
    oficina             TEXT NOT NULL,
    nombre_asamblea     TEXT NOT NULL,
    fecha               DATE NOT NULL,
    provincia           TEXT,
    canton              TEXT,
    num_participantes   INTEGER,
    tematica            TEXT,
    observaciones       TEXT,
    fecha_registro      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    registrado_por      TEXT
);
"""

_DDL_CONVENIOS = """
CREATE TABLE IF NOT EXISTS convenios (
    id                  SERIAL PRIMARY KEY,
    oficina             TEXT NOT NULL,
    nombre_convenio     TEXT NOT NULL,
    institucion_contraparte TEXT NOT NULL,
    fecha_suscripcion   DATE,
    fecha_vigencia_hasta DATE,
    tipo_convenio       TEXT,
    estado              TEXT DEFAULT 'Activo',
    objeto              TEXT,
    fecha_registro      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    registrado_por      TEXT
);
"""

_DDL_REPORTES_CAPACITACION = """
CREATE TABLE IF NOT EXISTS reportes_capacitacion (
    id                      SERIAL PRIMARY KEY,
    numero_reporte          INTEGER NOT NULL,
    year_reporte            INTEGER NOT NULL,
    oficina                 TEXT NOT NULL,
    fecha_reporte           TEXT NOT NULL,
    tipo_evento             TEXT NOT NULL,
    institucion_invitada    TEXT,
    tipo_institucion        TEXT,
    provincia               TEXT,
    canton                  TEXT,
    contacto_nombre         TEXT,
    contacto_celular        TEXT,
    tipo_actividad_productiva TEXT,
    publico_objetivo_capacitado TEXT,
    corresponde_convenio    TEXT,
    numero_convenio         TEXT,
    convenio_contraparte    TEXT,
    fecha_evento            TEXT,
    hora_inicio             TEXT,
    hora_fin                TEXT,
    modalidad               TEXT,
    tema                    TEXT,
    capacitadores           TEXT,
    publico_objetivo        TEXT,
    descripcion             TEXT,
    observaciones           TEXT,
    adjuntos                TEXT,
    elaborado_por           TEXT,
    revisado_por            TEXT,
    num_personas_capacitadas INTEGER DEFAULT 0,
    encuestas_realizadas    INTEGER DEFAULT 0,
    fecha_registro          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_DDL_ASAMBLEA_PRODUCTIVA = """
CREATE TABLE IF NOT EXISTS asamblea_productiva (
    id                      SERIAL PRIMARY KEY,
    numero_reporte          INTEGER,
    oficina                 TEXT NOT NULL,
    fecha                   TEXT NOT NULL,
    num_asistentes          INTEGER NOT NULL DEFAULT 0,
    responsables            TEXT,
    tematica                TEXT,
    asociacion_agrupacion   TEXT,
    lugar_realizacion       TEXT,
    instituciones_invitadas TEXT,
    acuerdos_compromisos    TEXT,
    responsable_seguimiento TEXT,
    estado_compromisos      TEXT DEFAULT 'Pendiente',
    observaciones           TEXT,
    fecha_registro          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_DDL_CONTADOR_REPORTE = """
CREATE TABLE IF NOT EXISTS contador_reporte (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    ultimo_numero   INTEGER NOT NULL DEFAULT 83
);
"""

_DDL_CONTADOR_ASAMBLEA = """
CREATE TABLE IF NOT EXISTS contador_asamblea (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    ultimo_numero   INTEGER NOT NULL DEFAULT 17
);
"""

# Índices para mejorar rendimiento de consultas frecuentes
_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cap_oficina ON capacitaciones(oficina);",
    "CREATE INDEX IF NOT EXISTS idx_cap_cedula ON capacitaciones(cedula);",
    "CREATE INDEX IF NOT EXISTS idx_cap_fecha ON capacitaciones(fecha_capacitacion);",
    "CREATE INDEX IF NOT EXISTS idx_cap_curso ON capacitaciones(nombre_curso);",
    "CREATE INDEX IF NOT EXISTS idx_asm_oficina ON asambleas(oficina);",
    "CREATE INDEX IF NOT EXISTS idx_conv_oficina ON convenios(oficina);",
    "CREATE INDEX IF NOT EXISTS idx_rep_oficina ON reportes_capacitacion(oficina);",
    "CREATE INDEX IF NOT EXISTS idx_rep_fecha ON reportes_capacitacion(fecha_reporte);",
    "CREATE INDEX IF NOT EXISTS idx_asm_prod_oficina ON asamblea_productiva(oficina);",
]


def init_db() -> None:
    """
    Inicializa la base de datos: crea las tablas e índices si no existen.
    Operación idempotente.

    Raises:
        RuntimeError: si no se puede conectar o inicializar la base de datos.
    """
    try:
        con = psycopg2.connect(_dsn())
        try:
            with con, con.cursor() as cur:
                cur.execute(_DDL_CAPACITACIONES)
                cur.execute(_DDL_ASAMBLEAS)
                cur.execute(_DDL_CONVENIOS)
                cur.execute(_DDL_REPORTES_CAPACITACION)
                cur.execute(_DDL_ASAMBLEA_PRODUCTIVA)
                cur.execute(_DDL_CONTADOR_REPORTE)
                cur.execute(_DDL_CONTADOR_ASAMBLEA)
                cur.execute(
                    "INSERT INTO contador_reporte (id, ultimo_numero) VALUES (1, 83) "
                    "ON CONFLICT (id) DO NOTHING"
                )
                cur.execute(
                    "INSERT INTO contador_asamblea (id, ultimo_numero) VALUES (1, 17) "
                    "ON CONFLICT (id) DO NOTHING"
                )
                # La numeración de asambleas comienza en 018 (17 actas históricas previas)
                cur.execute(
                    "UPDATE contador_asamblea SET ultimo_numero = 17 "
                    "WHERE id = 1 AND ultimo_numero < 17"
                )
                # Migración: los reportes 1-83 son históricos; el sistema comienza desde el 84
                cur.execute(
                    "UPDATE contador_reporte SET ultimo_numero = 83 "
                    "WHERE id = 1 AND ultimo_numero < 83"
                )
                # Migración idempotente: columnas nuevas en reportes_capacitacion
                for col in (
                    "hora_inicio", "hora_fin",
                    "tipo_institucion", "provincia", "canton",
                    "contacto_nombre", "contacto_celular",
                    "tipo_actividad_productiva", "publico_objetivo_capacitado",
                    "corresponde_convenio", "numero_convenio", "convenio_contraparte",
                ):
                    cur.execute(
                        f"ALTER TABLE reportes_capacitacion ADD COLUMN IF NOT EXISTS {col} TEXT"
                    )
                cur.execute(
                    "ALTER TABLE reportes_capacitacion "
                    "ADD COLUMN IF NOT EXISTS encuestas_realizadas INTEGER DEFAULT 0"
                )
                # Migración idempotente: columnas del acta completa en asambleas productivas
                for col in (
                    "responsables", "tematica",
                    "asociacion_agrupacion", "lugar_realizacion", "instituciones_invitadas",
                    "acuerdos_compromisos", "responsable_seguimiento", "observaciones",
                ):
                    cur.execute(
                        f"ALTER TABLE asamblea_productiva ADD COLUMN IF NOT EXISTS {col} TEXT"
                    )
                cur.execute(
                    "ALTER TABLE asamblea_productiva "
                    "ADD COLUMN IF NOT EXISTS numero_reporte INTEGER"
                )
                cur.execute(
                    "ALTER TABLE asamblea_productiva "
                    "ADD COLUMN IF NOT EXISTS estado_compromisos TEXT DEFAULT 'Pendiente'"
                )
                for idx in _INDICES:
                    cur.execute(idx)
        finally:
            con.close()
    except psycopg2.Error as e:
        raise RuntimeError(f"Error al inicializar la base de datos: {e}") from e


if __name__ == "__main__":
    init_db()
    print("Base de datos PostgreSQL inicializada correctamente.")
