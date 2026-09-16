from __future__ import annotations

import unittest
from datetime import date

from database.db import (
    _lista_textos_unicos,
    _validar_actividad_vinculacion,
    _validar_datos_proyecto,
)
from modules.vinculacion.dashboard import estado_proyecto


class _Cursor:
    def __init__(self, fila=None):
        self.fila = fila

    def fetchone(self):
        return self.fila


class _ConexionActividad:
    def __init__(self, oficina="loja"):
        self.proyecto = {
            "id": 7,
            "oficina": oficina,
            "fecha_inicio": date(2026, 1, 1),
            "fecha_fin": date(2026, 12, 31),
        }

    def execute(self, sql, params=None):
        if "FROM proyectos_vinculacion WHERE" in sql:
            oficina = params[1]
            return _Cursor(self.proyecto if oficina == self.proyecto["oficina"] else None)
        if "FROM proyectos_vinculacion_facultades" in sql:
            return _Cursor({"ok": True} if params == (11, 7) else None)
        if "FROM proyectos_vinculacion_asociaciones" in sql:
            return _Cursor({"ok": True} if params == (21, 7) else None)
        raise AssertionError(f"Consulta inesperada: {sql}")


def _datos_proyecto(**cambios):
    datos = {
        "oficina": "loja",
        "nombre": "Economía comunitaria",
        "responsable": "Analista regional",
        "convenio_numero": "SCE-UTPL-CM-NAC-2025-19",
        "convenio_institucion": "UNIVERSIDAD TÉCNICA PARTICULAR DE LOJA",
        "fecha_inicio": date(2026, 1, 1),
        "fecha_fin": date(2026, 12, 31),
        "resumen": "Proyecto territorial",
        "provincia": "LOJA",
        "canton": "LOJA",
    }
    datos.update(cambios)
    return datos


def _datos_actividad(**cambios):
    datos = {
        "proyecto_id": 7,
        "nombre": "Capacitación",
        "fecha": date(2026, 6, 15),
        "provincia": "LOJA",
        "canton": "LOJA",
        "facultad_id": 11,
        "asociacion_id": 21,
        "estudiantes_capacitados": 20,
        "asistentes_asociaciones": 15,
        "duracion_horas": 2.5,
        "observaciones": "",
    }
    datos.update(cambios)
    return datos


class VinculacionTests(unittest.TestCase):
    def test_estado_automatico_por_fechas(self):
        inicio = date(2026, 5, 1)
        fin = date(2026, 5, 31)
        self.assertEqual(estado_proyecto(inicio, fin, date(2026, 4, 30)), "Planificado")
        self.assertEqual(estado_proyecto(inicio, fin, date(2026, 5, 15)), "En ejecución")
        self.assertEqual(estado_proyecto(inicio, fin, date(2026, 6, 1)), "Finalizado")

    def test_proyecto_rechaza_periodo_invertido(self):
        with self.assertRaisesRegex(ValueError, "finalización"):
            _validar_datos_proyecto(
                _datos_proyecto(fecha_inicio=date(2026, 8, 1), fecha_fin=date(2026, 7, 31))
            )

    def test_listas_eliminan_vacios_y_duplicados(self):
        self.assertEqual(
            _lista_textos_unicos([" Economía ", "", "economía", "Turismo"], "sectores"),
            ["Economía", "Turismo"],
        )

    def test_actividad_valida_pertenencia_y_periodo(self):
        normalizados, proyecto = _validar_actividad_vinculacion(
            _ConexionActividad(), _datos_actividad(), "loja"
        )
        self.assertEqual(proyecto["id"], 7)
        self.assertIsNone(normalizados["observaciones"])

    def test_actividad_rechaza_fecha_fuera_del_proyecto(self):
        with self.assertRaisesRegex(ValueError, "período"):
            _validar_actividad_vinculacion(
                _ConexionActividad(), _datos_actividad(fecha=date(2027, 1, 1)), "loja"
            )

    def test_actividad_rechaza_cantidades_negativas(self):
        with self.assertRaisesRegex(ValueError, "enteros no negativos"):
            _validar_actividad_vinculacion(
                _ConexionActividad(), _datos_actividad(estudiantes_capacitados=-1), "loja"
            )

    def test_otra_oficina_no_puede_modificar_actividad(self):
        with self.assertRaisesRegex(PermissionError, "oficina propietaria"):
            _validar_actividad_vinculacion(
                _ConexionActividad(), _datos_actividad(), "cuenca"
            )


if __name__ == "__main__":
    unittest.main()
