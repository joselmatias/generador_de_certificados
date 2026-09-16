from __future__ import annotations

import unittest
from datetime import date

from database.db import (
    _lista_textos_unicos,
    _reemplazar_lista_proyecto,
    _validar_actividad_vinculacion,
    _validar_datos_proyecto,
    _validar_proyecto_por_aperturar,
    eliminar_proyecto_vinculacion,
)
from modules.vinculacion.dashboard import estado_proyecto


class _Cursor:
    def __init__(self, fila=None, rowcount=0):
        self.fila = fila
        self.rowcount = rowcount

    def fetchone(self):
        return self.fila

    def fetchall(self):
        return self.fila or []


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


class _ConexionListas:
    def __init__(self):
        self.operaciones = []

    def execute(self, sql, params=None):
        sql_limpio = " ".join(sql.split())
        self.operaciones.append((sql_limpio, params))
        if sql_limpio.startswith("SELECT id, nombre"):
            return _Cursor([
                {"id": 1, "nombre": "Economía"},
                {"id": 2, "nombre": "economía"},
            ])
        return _Cursor()


class _ConexionEliminar:
    def __init__(self, autorizado=True):
        self.autorizado = autorizado
        self.consultas = []

    def execute(self, sql, params=None):
        sql_limpio = " ".join(sql.split())
        self.consultas.append((sql_limpio, params))
        if sql_limpio.startswith("SELECT id FROM proyectos_vinculacion"):
            return _Cursor({"id": 7} if self.autorizado else None)
        if sql_limpio.startswith("DELETE FROM actividades_vinculacion"):
            return _Cursor(rowcount=3)
        if sql_limpio.startswith("DELETE FROM proyectos_vinculacion"):
            return _Cursor(rowcount=1)
        raise AssertionError(f"Consulta inesperada: {sql_limpio}")


def _datos_proyecto(**cambios):
    datos = {
        "oficina": "loja",
        "nombre": "Economía comunitaria",
        "responsable": "Analista regional",
        "convenio_numero": "SCE-UTPL-CM-NAC-2025-19",
        "convenio_institucion": "UNIVERSIDAD TÉCNICA PARTICULAR DE LOJA",
        "fecha_inicio": date(2026, 1, 1),
        "fecha_fin": None,
        "duracion_anios": 1,
        "duracion_meses": 0,
        "estado": "En proceso",
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
    def test_estado_es_manual(self):
        self.assertEqual(estado_proyecto("En proceso"), "En proceso")
        self.assertEqual(estado_proyecto("Finalizado"), "Finalizado")
        self.assertEqual(estado_proyecto(None), "En proceso")

    def test_proyecto_rechaza_periodo_invertido(self):
        with self.assertRaisesRegex(ValueError, "finalización"):
            _validar_datos_proyecto(
                _datos_proyecto(
                    estado="Finalizado", fecha_inicio=date(2026, 8, 1),
                    fecha_fin=date(2026, 7, 31),
                )
            )

    def test_finalizado_exige_fecha_y_en_proceso_la_limpia(self):
        with self.assertRaisesRegex(ValueError, "fecha de finalización"):
            _validar_datos_proyecto(_datos_proyecto(estado="Finalizado", fecha_fin=None))
        datos = _validar_datos_proyecto(
            _datos_proyecto(estado="En proceso", fecha_fin=date(2026, 12, 31))
        )
        self.assertIsNone(datos["fecha_fin"])

    def test_duracion_debe_ser_mayor_que_cero(self):
        with self.assertRaisesRegex(ValueError, "mayor que cero"):
            _validar_datos_proyecto(
                _datos_proyecto(duracion_anios=0, duracion_meses=0)
            )

    def test_proyecto_por_aperturar_admite_observacion_libre(self):
        datos = _validar_proyecto_por_aperturar(
            {
                "oficina": "cuenca",
                "universidad": "Universidad de prueba",
                "facultad": "Facultad de Economía",
                "fecha_tentativa": date(2027, 2, 1),
                "observaciones": "Texto libre con varias líneas.\nSegunda línea.",
            }
        )
        self.assertIn("Segunda línea", datos["observaciones"])

    def test_listas_eliminan_vacios_y_duplicados(self):
        self.assertEqual(
            _lista_textos_unicos([" Economía ", "", "economía", "Turismo"], "sectores"),
            ["Economía", "Turismo"],
        )

    def test_edicion_consolida_duplicados_por_mayusculas(self):
        conexion = _ConexionListas()
        _reemplazar_lista_proyecto(
            conexion, "proyectos_vinculacion_sectores", 7, ["ECONOMÍA"]
        )
        operaciones = [op for op, _ in conexion.operaciones]
        self.assertTrue(any(op.startswith("DELETE FROM") for op in operaciones))
        self.assertTrue(any(op.startswith("UPDATE proyectos_vinculacion_sectores") for op in operaciones))
        self.assertFalse(any(op.startswith("INSERT INTO") for op in operaciones))

    def test_eliminar_proyecto_borra_primero_sus_actividades(self):
        conexion = _ConexionEliminar()
        resultado = eliminar_proyecto_vinculacion(conexion, 7, "loja")
        self.assertEqual(resultado, {"proyectos": 1, "actividades": 3})
        borrados = [sql for sql, _ in conexion.consultas if sql.startswith("DELETE")]
        self.assertIn("actividades_vinculacion", borrados[0])
        self.assertIn("proyectos_vinculacion", borrados[1])

    def test_otra_oficina_no_puede_eliminar_proyecto(self):
        with self.assertRaisesRegex(PermissionError, "oficina propietaria"):
            eliminar_proyecto_vinculacion(_ConexionEliminar(False), 7, "cuenca")

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
