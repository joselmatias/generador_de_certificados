"""Registro y seguimiento de proyectos de vinculación por oficina técnica."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from database.db import (
    actualizar_actividad_vinculacion,
    actualizar_proyecto_vinculacion,
    actualizar_proyecto_vinculacion_por_aperturar,
    crear_actividad_vinculacion,
    crear_proyecto_vinculacion,
    crear_proyecto_vinculacion_por_aperturar,
    desactivar_actividad_vinculacion,
    eliminar_proyecto_vinculacion,
    desactivar_proyecto_vinculacion_por_aperturar,
    get_connection,
    listar_actividades_vinculacion,
    listar_opciones_proyecto_vinculacion,
    listar_proyectos_vinculacion,
    listar_proyectos_vinculacion_por_aperturar,
)
from utils.convenios import CONVENIOS_DATA, CONTRAPARTES
from utils.ubicaciones_ec import PROVINCIAS_CANTONES


OFICINAS = {
    "guayaquil": "Guayaquil",
    "manabi": "Portoviejo",
    "loja": "Loja",
    "cuenca": "Cuenca",
}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def estado_proyecto(estado: str | None) -> str:
    return estado if estado in {"En proceso", "Finalizado"} else "En proceso"


def _filas_editor(valores: list[str] | None = None) -> pd.DataFrame:
    return pd.DataFrame({"Nombre": list(valores or [""])})


def _leer_editor(tabla: Any) -> list[str]:
    if isinstance(tabla, pd.DataFrame) and "Nombre" in tabla:
        valores = tabla["Nombre"].tolist()
    else:
        valores = []
    resultado: list[str] = []
    vistos: set[str] = set()
    for valor in valores:
        texto = str(valor or "").strip()
        clave = texto.casefold()
        if texto and clave not in vistos:
            resultado.append(texto)
            vistos.add(clave)
    return resultado


def _convenios_de(institucion: str) -> list[dict[str, Any]]:
    return [c for c in CONVENIOS_DATA if c["contraparte"] == institucion]


def _convenio_por_numero(numero: str) -> dict[str, Any]:
    return next(c for c in CONVENIOS_DATA if c["numero"] == numero)


def _nombre_oficina(oficina: str) -> str:
    return OFICINAS.get(oficina, oficina.title())


def _cargar_datos(
    es_master: bool, oficina_id: str
) -> tuple[list[dict], list[dict], list[dict]]:
    oficina_consulta = None if es_master else oficina_id
    with get_connection() as con:
        proyectos = [dict(row) for row in listar_proyectos_vinculacion(con, oficina_consulta)]
        actividades = [dict(row) for row in listar_actividades_vinculacion(con, oficina_consulta)]
        por_aperturar = [
            dict(row)
            for row in listar_proyectos_vinculacion_por_aperturar(con, oficina_consulta)
        ]
    return proyectos, actividades, por_aperturar


def _cabecera() -> None:
    st.markdown(
        """
        <style>
        .vinculacion-cabecera {border-left: 6px solid #C8A951; padding: .2rem 0 .2rem 1rem; margin-bottom: 1rem;}
        .vinculacion-cabecera h2 {color: #1A3A5C; margin: 0; font-weight: 700;}
        .vinculacion-cabecera p {color: #526170; margin: .3rem 0 0;}
        .vinculacion-seccion {color: #1A3A5C; border-bottom: 2px solid #C8A951; padding-bottom: .3rem; margin-top: .5rem;}
        </style>
        <div class="vinculacion-cabecera">
          <h2>Proyectos de vinculación</h2>
          <p>Seguimiento de convenios, proyectos y actividades territoriales</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _tabla_proyectos(proyectos: list[dict]) -> None:
    filas = [
        {
            "Proyecto": p["nombre"],
            "Institución": p["convenio_institucion"],
            "Responsables": ", ".join(p.get("responsables") or [p["responsable"]]),
            "Oficina": _nombre_oficina(p["oficina"]),
            "Inicio": p["fecha_inicio"],
            "Fin": p["fecha_fin"],
            "Duración": f"{p.get('duracion_anios', 0)} años, {p.get('duracion_meses', 0)} meses",
            "Estado": estado_proyecto(p.get("estado")),
            "Cantón": p["canton"],
            "Actividades": int(p["total_actividades"]),
            "Estudiantes": int(p["total_estudiantes"]),
            "Asistentes asociaciones": int(p["total_asistentes"]),
            "Horas": float(p["total_horas"]),
        }
        for p in proyectos
    ]
    if not filas:
        st.info("No hay proyectos que coincidan con los filtros. Crea el primero desde esta pestaña.")
        return
    st.dataframe(
        pd.DataFrame(filas), hide_index=True, use_container_width=True,
        column_config={
            "Inicio": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Fin": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Horas": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def _filtros_proyectos(proyectos: list[dict], es_master: bool) -> list[dict]:
    c1, c2, c3, c4, c5 = st.columns(5)
    oficinas = sorted({p["oficina"] for p in proyectos})
    oficina = c1.selectbox(
        "Oficina", [None, *oficinas], format_func=lambda v: "Todas" if v is None else _nombre_oficina(v),
        disabled=not es_master, key="vinc_filtro_oficina",
    )
    anios = sorted({p["fecha_inicio"].year for p in proyectos}, reverse=True)
    anio = c2.selectbox("Año", [None, *anios], format_func=lambda v: "Todos" if v is None else str(v))
    estado = c3.selectbox("Estado", [None, "En proceso", "Finalizado"], format_func=lambda v: v or "Todos")
    instituciones = sorted({p["convenio_institucion"] for p in proyectos})
    institucion = c4.selectbox("Institución", [None, *instituciones], format_func=lambda v: v or "Todas")
    cantones = sorted({p["canton"] for p in proyectos})
    canton = c5.selectbox("Cantón", [None, *cantones], format_func=lambda v: v or "Todos")
    return [
        p for p in proyectos
        if (oficina is None or p["oficina"] == oficina)
        and (anio is None or p["fecha_inicio"].year == anio)
        and (estado is None or estado_proyecto(p.get("estado")) == estado)
        and (institucion is None or p["convenio_institucion"] == institucion)
        and (canton is None or p["canton"] == canton)
    ]


def _selector_convenio(prefijo: str, actual: dict | None = None) -> tuple[str, dict]:
    institucion_actual = actual["convenio_institucion"] if actual else CONTRAPARTES[0]
    indice = CONTRAPARTES.index(institucion_actual) if institucion_actual in CONTRAPARTES else 0
    institucion = st.selectbox("Institución con convenio", CONTRAPARTES, index=indice, key=f"{prefijo}_institucion")
    convenios = _convenios_de(institucion)
    numeros = [c["numero"] for c in convenios]
    actual_numero = actual["convenio_numero"] if actual and actual["convenio_numero"] in numeros else numeros[0]
    numero = st.selectbox(
        "Convenio", numeros, index=numeros.index(actual_numero),
        format_func=lambda n: f"{n} — {_convenio_por_numero(n)['tipo']}",
        key=f"{prefijo}_convenio_{CONTRAPARTES.index(institucion)}",
    )
    return institucion, _convenio_por_numero(numero)


def _editor_catalogos(prefijo: str, actual: dict | None = None) -> tuple[Any, Any, Any, Any]:
    st.markdown('<h4 class="vinculacion-seccion">Intervinientes</h4>', unsafe_allow_html=True)
    st.caption("Agrega una fila por cada responsable, facultad, sector económico o asociación.")
    c0, c1 = st.columns(2)
    responsables = c0.data_editor(
        _filas_editor(actual.get("responsables") if actual else None), num_rows="dynamic",
        hide_index=True, use_container_width=True, key=f"{prefijo}_responsables",
        column_config={"Nombre": st.column_config.TextColumn("Responsables")},
    )
    facultades = c1.data_editor(
        _filas_editor(actual.get("facultades") if actual else None), num_rows="dynamic",
        hide_index=True, use_container_width=True, key=f"{prefijo}_facultades",
        column_config={"Nombre": st.column_config.TextColumn("Facultades")},
    )
    c2, c3 = st.columns(2)
    sectores = c2.data_editor(
        _filas_editor(actual.get("sectores") if actual else None), num_rows="dynamic",
        hide_index=True, use_container_width=True, key=f"{prefijo}_sectores",
        column_config={"Nombre": st.column_config.TextColumn("Sectores económicos")},
    )
    asociaciones = c3.data_editor(
        _filas_editor(actual.get("asociaciones") if actual else None), num_rows="dynamic",
        hide_index=True, use_container_width=True, key=f"{prefijo}_asociaciones",
        column_config={"Nombre": st.column_config.TextColumn("Asociaciones")},
    )
    return responsables, facultades, sectores, asociaciones


def _campos_proyecto(
    prefijo: str, oficina_id: str, actual: dict | None = None
) -> tuple[dict, list, list, list, list]:
    st.markdown('<h4 class="vinculacion-seccion">Información general</h4>', unsafe_allow_html=True)
    nombre = st.text_input("Nombre del proyecto", value=actual["nombre"] if actual else "", key=f"{prefijo}_nombre")
    c1, c2 = st.columns(2)
    with c1:
        institucion, convenio = _selector_convenio(prefijo, actual)
    inicio_defecto = actual["fecha_inicio"] if actual else date.today()
    with c2:
        fecha_inicio = st.date_input(
            "Fecha de inicio", value=inicio_defecto, format="DD/MM/YYYY", key=f"{prefijo}_inicio"
        )
        estado_actual = estado_proyecto(actual.get("estado")) if actual else "En proceso"
        estado = st.radio(
            "Estado", ["En proceso", "Finalizado"], horizontal=True,
            index=0 if estado_actual == "En proceso" else 1, key=f"{prefijo}_estado",
        )
    d1, d2 = st.columns(2)
    duracion_anios = d1.number_input(
        "Duración — años", min_value=0, step=1,
        value=int(actual.get("duracion_anios", 0)) if actual else 0, key=f"{prefijo}_duracion_anios",
    )
    duracion_meses = d2.number_input(
        "Duración — meses", min_value=0, max_value=11, step=1,
        value=int(actual.get("duracion_meses", 0)) if actual else 1, key=f"{prefijo}_duracion_meses",
    )
    fecha_fin = None
    if estado == "Finalizado":
        fin_defecto = actual.get("fecha_fin") if actual else None
        fecha_fin = st.date_input(
            "Fecha de finalización", value=fin_defecto or fecha_inicio,
            min_value=fecha_inicio, format="DD/MM/YYYY", key=f"{prefijo}_fin",
        )
    resumen = st.text_area(
        "Resumen del proyecto", value=actual["resumen"] if actual else "", height=150,
        help="Campo de texto libre, sin límite funcional de caracteres.", key=f"{prefijo}_resumen",
    )
    responsables, facultades, sectores, asociaciones = _editor_catalogos(prefijo, actual)
    st.markdown('<h4 class="vinculacion-seccion">Territorio principal</h4>', unsafe_allow_html=True)
    provincias = sorted(PROVINCIAS_CANTONES)
    provincia_actual = actual["provincia"] if actual and actual["provincia"] in provincias else provincias[0]
    t1, t2 = st.columns(2)
    provincia = t1.selectbox("Provincia", provincias, index=provincias.index(provincia_actual), key=f"{prefijo}_provincia")
    cantones = sorted(PROVINCIAS_CANTONES[provincia])
    canton_actual = actual["canton"] if actual and actual["canton"] in cantones else cantones[0]
    canton = t2.selectbox(
        "Cantón", cantones, index=cantones.index(canton_actual),
        key=f"{prefijo}_canton_{provincias.index(provincia)}",
    )
    datos = {
        "oficina": oficina_id, "nombre": nombre,
        "convenio_numero": convenio["numero"], "convenio_institucion": institucion,
        "convenio_tipo": convenio["tipo"], "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin, "duracion_anios": int(duracion_anios),
        "duracion_meses": int(duracion_meses), "estado": estado,
        "resumen": resumen, "provincia": provincia,
        "canton": canton, "registrado_por": f"Perfil {_nombre_oficina(oficina_id)}",
    }
    return (
        datos, _leer_editor(responsables), _leer_editor(facultades),
        _leer_editor(sectores), _leer_editor(asociaciones),
    )


def _crear_proyecto(oficina_id: str) -> None:
    with st.expander("Crear nuevo proyecto"):
        datos, responsables, facultades, sectores, asociaciones = _campos_proyecto("vinc_nuevo", oficina_id)
        if st.button("Guardar proyecto", type="primary", key="vinc_guardar_nuevo"):
            try:
                with get_connection() as con:
                    crear_proyecto_vinculacion(
                        con, datos, responsables, facultades, sectores, asociaciones
                    )
                st.success("Proyecto guardado.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"No se pudo guardar el proyecto: {exc}")


def _editar_proyecto(proyectos: list[dict], oficina_id: str) -> None:
    propios = [p for p in proyectos if p["oficina"] == oficina_id]
    if not propios:
        return
    por_id = {p["id"]: p for p in propios}
    st.markdown("#### Editar o eliminar un proyecto")
    proyecto_id = st.selectbox(
        "Proyecto seleccionado", list(por_id),
        format_func=lambda i: (
            f"ID {i} · {por_id[i]['nombre']} · {por_id[i]['convenio_numero']} · "
            f"{por_id[i]['fecha_inicio']:%d/%m/%Y}"
        ),
        key="vinc_proyecto_editar",
    )
    actual = por_id[proyecto_id]
    st.caption(
        f"Seleccionado: **{actual['nombre']}** · "
        f"{actual['convenio_institucion']} · {_nombre_oficina(actual['oficina'])}"
    )
    with st.expander("Editar el proyecto seleccionado", expanded=True):
        datos, responsables, facultades, sectores, asociaciones = _campos_proyecto(
            f"vinc_editar_{proyecto_id}", oficina_id, actual
        )
        if st.button("Guardar cambios", type="primary", key=f"vinc_actualizar_{proyecto_id}"):
            try:
                with get_connection() as con:
                    actualizar_proyecto_vinculacion(
                        con, proyecto_id, oficina_id, datos, responsables,
                        facultades, sectores, asociaciones,
                    )
                st.success("Proyecto actualizado.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"No se pudo actualizar el proyecto: {exc}")

    with st.expander("Eliminar definitivamente el proyecto seleccionado"):
        st.error(
            "Esta acción elimina el proyecto, todas sus actividades, responsables, "
            "facultades, sectores y asociaciones. No se puede deshacer."
        )
        confirmacion = st.text_input(
            f"Escribe exactamente: {actual['nombre']}",
            key=f"vinc_confirmar_eliminar_{proyecto_id}",
        )
        coincide = confirmacion.strip() == actual["nombre"].strip()
        if st.button(
            "Eliminar proyecto definitivamente", disabled=not coincide,
            key=f"vinc_eliminar_proy_{proyecto_id}",
        ):
            try:
                with get_connection() as con:
                    resultado = eliminar_proyecto_vinculacion(
                        con, proyecto_id, oficina_id
                    )
                st.success(
                    "Proyecto eliminado definitivamente. "
                    f"También se eliminaron {resultado['actividades']} actividades."
                )
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"No se pudo eliminar el proyecto: {exc}")


def _vista_proyectos(proyectos: list[dict], oficina_id: str, es_master: bool) -> None:
    filtrados = _filtros_proyectos(proyectos, es_master)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Proyectos", len(filtrados))
    m2.metric("En proceso", sum(estado_proyecto(p.get("estado")) == "En proceso" for p in filtrados))
    m3.metric("Estudiantes", sum(int(p["total_estudiantes"]) for p in filtrados))
    m4.metric("Asistentes de asociaciones", sum(int(p["total_asistentes"]) for p in filtrados))
    _tabla_proyectos(filtrados)
    _crear_proyecto(oficina_id)
    _editar_proyecto(proyectos, oficina_id)


def _opciones_actividad(proyecto_id: int) -> tuple[dict[int, str], dict[int, str]]:
    with get_connection() as con:
        opciones = listar_opciones_proyecto_vinculacion(con, proyecto_id)
    return (
        {int(row["id"]): row["nombre"] for row in opciones["facultades"]},
        {int(row["id"]): row["nombre"] for row in opciones["asociaciones"]},
    )


def _campos_actividad(prefijo: str, proyecto: dict, actual: dict | None = None) -> dict:
    facultades, asociaciones = _opciones_actividad(proyecto["id"])
    nombre = st.text_input("Actividad", value=actual["nombre"] if actual else "", key=f"{prefijo}_nombre")
    c1, c2 = st.columns(2)
    fecha_kwargs: dict[str, Any] = {
        "value": actual["fecha"] if actual else proyecto["fecha_inicio"],
        "min_value": proyecto["fecha_inicio"], "format": "DD/MM/YYYY",
        "key": f"{prefijo}_fecha",
    }
    if proyecto.get("fecha_fin") is not None:
        fecha_kwargs["max_value"] = proyecto["fecha_fin"]
    fecha = c1.date_input("Fecha", **fecha_kwargs)
    duracion = c2.number_input(
        "Duración (horas)", min_value=0.25, step=0.25,
        value=float(actual["duracion_horas"]) if actual else 1.0, key=f"{prefijo}_duracion",
    )
    provincias = sorted(PROVINCIAS_CANTONES)
    provincia_actual = actual["provincia"] if actual else proyecto["provincia"]
    if provincia_actual not in provincias:
        provincia_actual = provincias[0]
    t1, t2 = st.columns(2)
    provincia = t1.selectbox("Provincia", provincias, index=provincias.index(provincia_actual), key=f"{prefijo}_provincia")
    cantones = sorted(PROVINCIAS_CANTONES[provincia])
    canton_actual = actual["canton"] if actual else proyecto["canton"]
    if canton_actual not in cantones:
        canton_actual = cantones[0]
    canton = t2.selectbox(
        "Cantón", cantones, index=cantones.index(canton_actual),
        key=f"{prefijo}_canton_{provincias.index(provincia)}",
    )
    c3, c4 = st.columns(2)
    facultad_ids = list(facultades)
    facultad_actual = actual.get("facultad_id") if actual else facultad_ids[0]
    if facultad_actual not in facultad_ids:
        facultad_actual = facultad_ids[0]
    facultad_id = c3.selectbox("Facultad", facultad_ids, index=facultad_ids.index(facultad_actual), format_func=facultades.get, key=f"{prefijo}_facultad")
    asociacion_ids = [None, *asociaciones]
    asociacion_actual = actual.get("asociacion_id") if actual else None
    asociacion_id = c4.selectbox(
        "Asociación", asociacion_ids,
        index=asociacion_ids.index(asociacion_actual) if asociacion_actual in asociacion_ids else 0,
        format_func=lambda i: "Sin asociación" if i is None else asociaciones[i], key=f"{prefijo}_asociacion",
    )
    c5, c6 = st.columns(2)
    estudiantes = c5.number_input(
        "Estudiantes capacitados", min_value=0, step=1,
        value=int(actual["estudiantes_capacitados"]) if actual else 0, key=f"{prefijo}_estudiantes",
    )
    asistentes = c6.number_input(
        "Asistentes de asociaciones", min_value=0, step=1,
        value=int(actual["asistentes_asociaciones"]) if actual else 0, key=f"{prefijo}_asistentes",
    )
    observaciones = st.text_area(
        "Observaciones o detalle", value=(actual.get("observaciones") or "") if actual else "",
        key=f"{prefijo}_observaciones",
    )
    return {
        "proyecto_id": proyecto["id"], "nombre": nombre, "fecha": fecha,
        "duracion_horas": Decimal(str(duracion)), "provincia": provincia, "canton": canton,
        "facultad_id": facultad_id, "asociacion_id": asociacion_id,
        "estudiantes_capacitados": int(estudiantes), "asistentes_asociaciones": int(asistentes),
        "observaciones": observaciones, "registrado_por": f"Perfil {_nombre_oficina(proyecto['oficina'])}",
    }


def _tabla_actividades(actividades: list[dict]) -> None:
    if not actividades:
        st.info("Este proyecto todavía no tiene actividades registradas.")
        return
    tabla = pd.DataFrame([
        {
            "Mes": f"{MESES[a['fecha'].month]} {a['fecha'].year}", "Fecha": a["fecha"],
            "Actividad": a["nombre"], "Facultad": a.get("facultad") or "—",
            "Asociación": a.get("asociacion") or "—", "Cantón": a["canton"],
            "Horas": float(a["duracion_horas"]), "Estudiantes": a["estudiantes_capacitados"],
            "Asistentes asociaciones": a["asistentes_asociaciones"],
        } for a in actividades
    ])
    st.dataframe(
        tabla, hide_index=True, use_container_width=True,
        column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"), "Horas": st.column_config.NumberColumn(format="%.2f")},
    )


def _vista_actividades(proyectos: list[dict], actividades: list[dict], oficina_id: str) -> None:
    propios = [p for p in proyectos if p["oficina"] == oficina_id]
    if not propios:
        st.info("Crea primero un proyecto de vinculación para registrar actividades.")
        return
    por_id = {p["id"]: p for p in propios}
    proyecto_id = st.selectbox("Proyecto", list(por_id), format_func=lambda i: por_id[i]["nombre"], key="vinc_actividad_proyecto")
    proyecto = por_id[proyecto_id]
    del_proyecto = [a for a in actividades if a["proyecto_id"] == proyecto_id]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Actividades", len(del_proyecto))
    m2.metric("Horas ejecutadas", f"{sum(float(a['duracion_horas']) for a in del_proyecto):.2f}")
    m3.metric("Estudiantes", sum(a["estudiantes_capacitados"] for a in del_proyecto))
    m4.metric("Asistentes de asociaciones", sum(a["asistentes_asociaciones"] for a in del_proyecto))
    _tabla_actividades(del_proyecto)
    with st.expander("Agregar actividad mensual"):
        datos = _campos_actividad(f"vinc_act_nueva_{proyecto_id}", proyecto)
        if st.button("Guardar actividad", type="primary", key=f"vinc_guardar_act_{proyecto_id}"):
            try:
                with get_connection() as con:
                    crear_actividad_vinculacion(con, datos, oficina_id)
                st.success("Actividad guardada; los totales del proyecto fueron actualizados.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"No se pudo guardar la actividad: {exc}")
    if del_proyecto:
        por_actividad = {a["id"]: a for a in del_proyecto}
        with st.expander("Editar o desactivar una actividad"):
            actividad_id = st.selectbox("Actividad registrada", list(por_actividad), format_func=lambda i: f"{por_actividad[i]['fecha']:%d/%m/%Y} — {por_actividad[i]['nombre']}")
            actual = por_actividad[actividad_id]
            datos = _campos_actividad(f"vinc_act_editar_{actividad_id}", proyecto, actual)
            b1, b2 = st.columns([2, 1])
            if b1.button("Guardar cambios", type="primary", key=f"vinc_actualizar_act_{actividad_id}"):
                try:
                    with get_connection() as con:
                        actualizar_actividad_vinculacion(con, actividad_id, datos, oficina_id)
                    st.success("Actividad actualizada.")
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"No se pudo actualizar la actividad: {exc}")
            confirmar = b2.checkbox("Confirmo la desactivación", key=f"vinc_confirma_act_{actividad_id}")
            if b2.button("Desactivar actividad", disabled=not confirmar, key=f"vinc_desactivar_act_{actividad_id}"):
                try:
                    with get_connection() as con:
                        desactivar_actividad_vinculacion(con, actividad_id, oficina_id)
                    st.success("Actividad desactivada; sus datos se conservaron.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def _vista_consolidado(actividades: list[dict], es_master: bool) -> None:
    if not actividades:
        st.info("No existen actividades para consolidar.")
        return
    c1, c2, c3, c4 = st.columns(4)
    oficinas = sorted({a["oficina"] for a in actividades})
    oficina = c1.selectbox("Oficina", [None, *oficinas], format_func=lambda v: "Todas" if v is None else _nombre_oficina(v), disabled=not es_master, key="vinc_consol_oficina")
    anios = sorted({a["fecha"].year for a in actividades}, reverse=True)
    anio = c2.selectbox("Año", [None, *anios], format_func=lambda v: "Todos" if v is None else str(v), key="vinc_consol_anio")
    mes = c3.selectbox("Mes", [None, *MESES], format_func=lambda v: "Todos" if v is None else MESES[v], key="vinc_consol_mes")
    instituciones = sorted({a["convenio_institucion"] for a in actividades})
    institucion = c4.selectbox("Institución", [None, *instituciones], format_func=lambda v: v or "Todas", key="vinc_consol_inst")
    c5, c6, c7, c8 = st.columns(4)
    convenios = sorted({a["convenio_numero"] for a in actividades})
    convenio = c5.selectbox("Convenio", [None, *convenios], format_func=lambda v: v or "Todos")
    sectores = sorted({s.strip() for a in actividades for s in (a.get("sectores") or "").split(",") if s.strip()})
    sector = c6.selectbox("Sector económico", [None, *sectores], format_func=lambda v: v or "Todos")
    territorios = sorted({f"{a['provincia']} / {a['canton']}" for a in actividades})
    territorio = c7.selectbox("Territorio", [None, *territorios], format_func=lambda v: v or "Todos")
    estado = c8.selectbox(
        "Estado del proyecto", [None, "En proceso", "Finalizado"],
        format_func=lambda v: v or "Todos", key="vinc_consol_estado",
    )
    filtradas = [
        a for a in actividades
        if (oficina is None or a["oficina"] == oficina)
        and (anio is None or a["fecha"].year == anio)
        and (mes is None or a["fecha"].month == mes)
        and (institucion is None or a["convenio_institucion"] == institucion)
        and (convenio is None or a["convenio_numero"] == convenio)
        and (sector is None or sector in (a.get("sectores") or "").split(", "))
        and (territorio is None or f"{a['provincia']} / {a['canton']}" == territorio)
        and (
            estado is None
            or estado_proyecto(a.get("proyecto_estado")) == estado
        )
    ]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Actividades", len(filtradas))
    m2.metric("Horas", f"{sum(float(a['duracion_horas']) for a in filtradas):.2f}")
    m3.metric("Estudiantes", sum(a["estudiantes_capacitados"] for a in filtradas))
    m4.metric("Asistentes de asociaciones", sum(a["asistentes_asociaciones"] for a in filtradas))
    if filtradas:
        tabla = pd.DataFrame([
            {
                "Oficina": _nombre_oficina(a["oficina"]), "Fecha": a["fecha"],
                "Proyecto": a["proyecto_nombre"], "Actividad": a["nombre"],
                "Institución": a["convenio_institucion"], "Convenio": a["convenio_numero"],
                "Sectores": a.get("sectores") or "", "Provincia": a["provincia"],
                "Cantón": a["canton"], "Facultad": a.get("facultad") or "—",
                "Asociación": a.get("asociacion") or "—", "Horas": float(a["duracion_horas"]),
                "Estudiantes": a["estudiantes_capacitados"],
                "Asistentes asociaciones": a["asistentes_asociaciones"],
            } for a in filtradas
        ])
        st.dataframe(tabla, hide_index=True, use_container_width=True, column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"), "Horas": st.column_config.NumberColumn(format="%.2f")})
    else:
        st.info("No hay actividades que coincidan con los filtros.")


def _campos_por_aperturar(
    prefijo: str, oficina_id: str, actual: dict | None = None
) -> dict[str, Any]:
    universidad_actual = actual["universidad"] if actual else CONTRAPARTES[0]
    indice = CONTRAPARTES.index(universidad_actual) if universidad_actual in CONTRAPARTES else 0
    c1, c2 = st.columns(2)
    universidad = c1.selectbox(
        "Universidad o institución", CONTRAPARTES, index=indice,
        key=f"{prefijo}_universidad",
    )
    facultad = c2.text_input(
        "Facultad", value=actual["facultad"] if actual else "", key=f"{prefijo}_facultad",
    )
    fecha_tentativa = st.date_input(
        "Fecha tentativa de inicio",
        value=actual["fecha_tentativa"] if actual else date.today(),
        format="DD/MM/YYYY", key=f"{prefijo}_fecha",
    )
    observaciones = st.text_area(
        "Observaciones", value=(actual.get("observaciones") or "") if actual else "",
        height=130, help="Campo de texto libre.", key=f"{prefijo}_observaciones",
    )
    return {
        "oficina": oficina_id, "universidad": universidad, "facultad": facultad,
        "fecha_tentativa": fecha_tentativa, "observaciones": observaciones,
        "registrado_por": f"Perfil {_nombre_oficina(oficina_id)}",
    }


def _vista_por_aperturar(
    registros: list[dict], oficina_id: str, es_master: bool
) -> None:
    st.caption(
        "Registra iniciativas preliminares antes de completar la ficha formal del proyecto."
    )
    f1, f2 = st.columns(2)
    oficinas = sorted({r["oficina"] for r in registros})
    oficina = f1.selectbox(
        "Oficina", [None, *oficinas],
        format_func=lambda v: "Todas" if v is None else _nombre_oficina(v),
        disabled=not es_master, key="vinc_apertura_filtro_oficina",
    )
    universidades = sorted({r["universidad"] for r in registros})
    universidad = f2.selectbox(
        "Universidad o institución", [None, *universidades],
        format_func=lambda v: v or "Todas", key="vinc_apertura_filtro_universidad",
    )
    filtrados = [
        r for r in registros
        if (oficina is None or r["oficina"] == oficina)
        and (universidad is None or r["universidad"] == universidad)
    ]
    hoy = date.today()
    proximos_90 = sum(
        hoy <= r["fecha_tentativa"] <= hoy + timedelta(days=90) for r in filtrados
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Por aperturar", len(filtrados))
    m2.metric("Próximos 90 días", proximos_90)
    m3.metric("Instituciones", len({r["universidad"] for r in filtrados}))
    m4.metric("Facultades", len({r["facultad"].casefold() for r in filtrados}))
    if filtrados:
        st.dataframe(
            pd.DataFrame([
                {
                    "Oficina": _nombre_oficina(r["oficina"]),
                    "Universidad o institución": r["universidad"],
                    "Facultad": r["facultad"],
                    "Fecha tentativa": r["fecha_tentativa"],
                    "Observaciones": r.get("observaciones") or "",
                }
                for r in filtrados
            ]),
            hide_index=True, use_container_width=True,
            column_config={
                "Fecha tentativa": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Observaciones": st.column_config.TextColumn(width="large"),
            },
        )
        resumen = (
            pd.DataFrame(filtrados)
            .groupby("universidad", as_index=False)
            .size()
            .rename(columns={"universidad": "Universidad o institución", "size": "Proyectos"})
            .sort_values("Proyectos", ascending=False)
        )
        st.markdown("#### Resumen por institución")
        st.dataframe(resumen, hide_index=True, use_container_width=True)
    else:
        st.info("No hay proyectos por aperturar que coincidan con los filtros.")

    with st.expander("Agregar proyecto por aperturar"):
        datos = _campos_por_aperturar("vinc_apertura_nuevo", oficina_id)
        if st.button("Guardar proyecto por aperturar", type="primary", key="vinc_apertura_guardar"):
            try:
                with get_connection() as con:
                    crear_proyecto_vinculacion_por_aperturar(con, datos)
                st.success("Proyecto por aperturar guardado.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"No se pudo guardar el registro: {exc}")

    propios = [r for r in registros if r["oficina"] == oficina_id]
    if not propios:
        return
    por_id = {r["id"]: r for r in propios}
    with st.expander("Editar o desactivar un proyecto por aperturar"):
        registro_id = st.selectbox(
            "Registro", list(por_id),
            format_func=lambda i: (
                f"{por_id[i]['universidad']} — {por_id[i]['facultad']} — "
                f"{por_id[i]['fecha_tentativa']:%d/%m/%Y}"
            ),
            key="vinc_apertura_editar",
        )
        actual = por_id[registro_id]
        datos = _campos_por_aperturar(f"vinc_apertura_editar_{registro_id}", oficina_id, actual)
        b1, b2 = st.columns([2, 1])
        if b1.button("Guardar cambios", type="primary", key=f"vinc_apertura_actualizar_{registro_id}"):
            try:
                with get_connection() as con:
                    actualizar_proyecto_vinculacion_por_aperturar(
                        con, registro_id, oficina_id, datos
                    )
                st.success("Proyecto por aperturar actualizado.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"No se pudo actualizar el registro: {exc}")
        confirmar = b2.checkbox(
            "Confirmo la desactivación", key=f"vinc_apertura_confirmar_{registro_id}"
        )
        if b2.button(
            "Desactivar", disabled=not confirmar, key=f"vinc_apertura_desactivar_{registro_id}"
        ):
            try:
                with get_connection() as con:
                    desactivar_proyecto_vinculacion_por_aperturar(
                        con, registro_id, oficina_id
                    )
                st.success("Registro desactivado; sus datos se conservaron.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def mostrar_proyectos_vinculacion() -> None:
    _cabecera()
    oficina_id = st.session_state.get("oficina_id", "")
    es_master = st.session_state.get("oficina_rol") == "master"
    try:
        proyectos, actividades, por_aperturar = _cargar_datos(es_master, oficina_id)
    except Exception as exc:
        st.error(f"No se pudo cargar el módulo de vinculación: {exc}")
        return
    tab_proyectos, tab_actividades, tab_consolidado, tab_por_aperturar = st.tabs(
        [
            "Proyectos", "Actividades mensuales", "Consolidado",
            "Proyectos de vinculación por aperturar",
        ]
    )
    with tab_proyectos:
        _vista_proyectos(proyectos, oficina_id, es_master)
    with tab_actividades:
        _vista_actividades(proyectos, actividades, oficina_id)
    with tab_consolidado:
        _vista_consolidado(actividades, es_master)
    with tab_por_aperturar:
        _vista_por_aperturar(por_aperturar, oficina_id, es_master)
