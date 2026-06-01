"""
init_db.py — Inicialización de la base de datos SQLite.

Crea las tablas del sistema si no existen. Diseñado para ejecutarse
una sola vez al arrancar la aplicación (idempotente).
"""

import sqlite3
from pathlib import Path


# Ruta canónica de la base de datos
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sistema.db"

# DDL de cada tabla
_DDL_CAPACITACIONES = """
CREATE TABLE IF NOT EXISTS capacitaciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
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
    fecha_registro      TEXT DEFAULT CURRENT_TIMESTAMP,
    registrado_por      TEXT
);
"""

_DDL_ASAMBLEAS = """
CREATE TABLE IF NOT EXISTS asambleas (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    oficina             TEXT NOT NULL,
    nombre_asamblea     TEXT NOT NULL,
    fecha               DATE NOT NULL,
    provincia           TEXT,
    canton              TEXT,
    num_participantes   INTEGER,
    tematica            TEXT,
    observaciones       TEXT,
    fecha_registro      TEXT DEFAULT CURRENT_TIMESTAMP,
    registrado_por      TEXT
);
"""

_DDL_CONVENIOS = """
CREATE TABLE IF NOT EXISTS convenios (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    oficina             TEXT NOT NULL,
    nombre_convenio     TEXT NOT NULL,
    institucion_contraparte TEXT NOT NULL,
    fecha_suscripcion   DATE,
    fecha_vigencia_hasta DATE,
    tipo_convenio       TEXT,
    estado              TEXT DEFAULT 'Activo',
    objeto              TEXT,
    fecha_registro      TEXT DEFAULT CURRENT_TIMESTAMP,
    registrado_por      TEXT
);
"""

_DDL_REPORTES_CAPACITACION = """
CREATE TABLE IF NOT EXISTS reportes_capacitacion (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_reporte          INTEGER NOT NULL,
    year_reporte            INTEGER NOT NULL,
    oficina                 TEXT NOT NULL,
    fecha_reporte           TEXT NOT NULL,
    tipo_evento             TEXT NOT NULL,
    institucion_invitada    TEXT,
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
    fecha_registro          TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_DDL_ASAMBLEA_PRODUCTIVA = """
CREATE TABLE IF NOT EXISTS asamblea_productiva (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    oficina             TEXT NOT NULL,
    fecha               TEXT NOT NULL,
    num_asistentes      INTEGER NOT NULL DEFAULT 0,
    fecha_registro      TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_DDL_CONTADOR_REPORTE = """
CREATE TABLE IF NOT EXISTS contador_reporte (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    ultimo_numero   INTEGER NOT NULL DEFAULT 83
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
    Inicializa la base de datos: crea el directorio data/, las tablas
    y los índices si no existen. Operación idempotente.

    Raises:
        RuntimeError: si no se puede crear el directorio o la base de datos.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        con = sqlite3.connect(DB_PATH)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA foreign_keys=ON;")

        with con:
            con.execute(_DDL_CAPACITACIONES)
            con.execute(_DDL_ASAMBLEAS)
            con.execute(_DDL_CONVENIOS)
            con.execute(_DDL_REPORTES_CAPACITACION)
            con.execute(_DDL_ASAMBLEA_PRODUCTIVA)
            con.execute(_DDL_CONTADOR_REPORTE)
            con.execute("INSERT OR IGNORE INTO contador_reporte (id, ultimo_numero) VALUES (1, 83)")
            # Migración: si el contador está por debajo de 83, actualizarlo
            # (los reportes 1-83 son históricos; el sistema comienza desde el 84)
            con.execute("UPDATE contador_reporte SET ultimo_numero = 83 WHERE id = 1 AND ultimo_numero < 83")

            # Migración: agregar columnas nuevas a reportes_capacitacion si faltan
            # (las BDs creadas antes de estos campos no las tienen).
            cols_existentes = {
                row[1] for row in con.execute("PRAGMA table_info(reportes_capacitacion)")
            }
            for col in ("hora_inicio", "hora_fin"):
                if col not in cols_existentes:
                    con.execute(f"ALTER TABLE reportes_capacitacion ADD COLUMN {col} TEXT")

            for idx in _INDICES:
                con.execute(idx)

        con.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"Error al inicializar la base de datos: {e}") from e


if __name__ == "__main__":
    init_db()
    print(f"Base de datos inicializada correctamente en: {DB_PATH}")
