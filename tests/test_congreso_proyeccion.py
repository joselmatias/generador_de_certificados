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

from database.db import (
    _validar_actor_proyeccion_guayaquil,
    actualizar_confirmacion_proyeccion,
    sincronizar_documentos_congreso,
)
from modules.congresos.seguimiento import (
    ACTUALIZACIONES_OFICIOS_IR,
    PROYECCION_ESTUDIANTES_INICIAL,
    _entero_no_negativo,
    _firmado_por,
    _normalizar,
    _separar_oficios_y_categorias,
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


class _ConexionSincronizacionFalsa:
    def __init__(self):
        self.registro = {
            "id": 65,
            "fila_origen": 65,
            "numero_oficio": None,
            "telefonos_institucionales": None,
            "tipo_invitacion": None,
            "oficina": None,
            "responsable_id": None,
        }
        self.actualizacion = None

    def execute(self, sql, params=None):
        sql_limpio = " ".join(sql.split())
        if sql_limpio.startswith("ALTER TABLE") or sql_limpio.startswith("LOCK TABLE"):
            return _CursorFalso()
        if "FROM congreso_invitados" in sql_limpio:
            return _CursorFalso(self.registro)
        if "FROM congreso_responsables" in sql_limpio:
            return _CursorFalso({"id": 2})
        if sql_limpio.startswith("UPDATE congreso_invitados"):
            self.actualizacion = params
            return _CursorFalso()
        if sql_limpio.startswith("INSERT INTO congreso_historial"):
            return _CursorFalso()
        raise AssertionError(f"Consulta inesperada: {sql_limpio}")


class ProyeccionEstudiantesTests(unittest.TestCase):
    def test_actualizaciones_ir_cubren_162_a_182(self):
        self.assertEqual(len(ACTUALIZACIONES_OFICIOS_IR), 21)
        self.assertEqual(
            [item[1] for item in ACTUALIZACIONES_OFICIOS_IR],
            [f"SCE-IGT-IR-2026-{numero}" for numero in range(162, 183)],
        )

    def test_codigo_ir_se_normaliza_sin_prefijo_oficio(self):
        self.assertEqual(
            _separar_oficios_y_categorias("OFICIO SCE-IGT-IR-2026-177"),
            [("SCE-IGT-IR-2026-177", None)],
        )

    def test_firmado_por_usa_las_dos_etiquetas_solicitadas(self):
        self.assertEqual(_firmado_por("Superintendente"), "Superintendente")
        self.assertEqual(_firmado_por("IR"), "IR")
        self.assertEqual(_firmado_por("Intendente Regional de Guayaquil"), "IR")

    def test_sincronizacion_asigna_oficina_y_responsable_si_estan_vacios(self):
        conexion = _ConexionSincronizacionFalsa()
        cambios = sincronizar_documentos_congreso(
            conexion,
            [
                {
                    "fila_origen": 65,
                    "numero_oficio": "SCE-IGT-IR-2026-177",
                    "tipo_invitacion": "Invitación general",
                    "oficina": "guayaquil",
                    "responsable_nombre": "Ab. Carlos García",
                }
            ],
            [],
        )
        self.assertEqual(cambios, 4)
        self.assertEqual(
            conexion.actualizacion,
            ["Invitación general", "guayaquil", 2, "SCE-IGT-IR-2026-177", 65],
        )

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
                "Ing. Milka Nazareno",
            )

    def test_jose_matias_es_actor_adicional_de_guayaquil(self):
        self.assertEqual(
            _validar_actor_proyeccion_guayaquil(None, None, "José Matías"),
            "José Matías",
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
