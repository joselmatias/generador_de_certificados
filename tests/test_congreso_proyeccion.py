from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Las pruebas de lógica no abren PostgreSQL. Estos módulos mínimos permiten
# importarlas también en entornos de desarrollo sin psycopg2 instalado.
try:
    import psycopg2  # noqa: F401
except ModuleNotFoundError:
    psycopg2_falso = types.ModuleType("psycopg2")
    psycopg2_falso.Error = Exception
    psycopg2_falso.connect = lambda *args, **kwargs: None
    extras_falso = types.ModuleType("psycopg2.extras")
    extras_falso.RealDictCursor = object
    sys.modules["psycopg2"] = psycopg2_falso
    sys.modules["psycopg2.extras"] = extras_falso

from database.db import actualizar_confirmacion_proyeccion
from modules.congresos.seguimiento import (
    PROYECCION_ESTUDIANTES_INICIAL,
    _entero_no_negativo,
    _normalizar,
    _ultima_actualizacion_proyeccion,
)


class _CursorFalso:
    def __init__(self, fila=None):
        self.fila = fila

    def fetchone(self):
        return self.fila


class _ConexionFalsa:
    def __init__(self, registro):
        self.registro = registro

    def execute(self, sql, params=None):
        if "FROM congreso_responsables" in sql:
            return _CursorFalso({"nombres": "Ing. Milka Nazareno"})
        if "FROM congreso_proyeccion_estudiantes" in sql:
            return _CursorFalso(self.registro)
        raise AssertionError(f"Consulta inesperada: {sql}")


class ProyeccionEstudiantesTests(unittest.TestCase):
    def test_precarga_conserva_totales_aprobados(self):
        self.assertEqual(len(PROYECCION_ESTUDIANTES_INICIAL), 13)
        self.assertEqual(sum(fila[1] for fila in PROYECCION_ESTUDIANTES_INICIAL), 555)
        self.assertEqual(sum(fila[2] for fila in PROYECCION_ESTUDIANTES_INICIAL), 90)

    def test_normalizacion_bloquea_variantes_equivalentes(self):
        self.assertEqual(_normalizar("  Universidad ÁGORA "), "universidad agora")

    def test_entero_no_negativo_rechaza_decimales_y_negativos(self):
        self.assertEqual(_entero_no_negativo(12.0, "Confirmados"), 12)
        for valor in (-1, 2.5, "texto", None):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                _entero_no_negativo(valor, "Confirmados")

    def test_cambiar_confirmados_exige_contacto_completo(self):
        registro = {
            "id": 1,
            "institucion": "ESPOL",
            "activo": True,
            "confirmados": 60,
            "contacto_nombre": None,
            "contacto_celular": None,
            "observaciones": None,
        }
        with self.assertRaisesRegex(ValueError, "Completa el nombre y celular"):
            actualizar_confirmacion_proyeccion(
                _ConexionFalsa(registro),
                1,
                {
                    "confirmados": 61,
                    "contacto_nombre": "",
                    "contacto_celular": "",
                },
                1,
            )

    def test_ultima_actualizacion_muestra_actor_y_hora_ecuador(self):
        texto = _ultima_actualizacion_proyeccion(
            {
                "ultimo_actor_nombre": "Ab. Carlos García",
                "fecha_actualizacion": datetime(2026, 9, 11, 15, 0, tzinfo=timezone.utc),
            }
        )
        self.assertEqual(
            texto,
            "Ab. Carlos García · 11/09/2026 10:00",
        )


if __name__ == "__main__":
    unittest.main()
