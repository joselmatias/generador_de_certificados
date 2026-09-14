"""Checklist operativo y proyección de estudiantes del Congreso 2026."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from database.db import (
    actualizar_item_checklist_congreso,
    asegurar_checklist_congreso,
    crear_item_checklist_congreso,
    eliminar_item_checklist_congreso,
    get_connection,
    listar_checklist_congreso,
    listar_historial_checklist_congreso,
    listar_responsables_congreso,
)


ETIQUETAS_CAMPOS = {
    "Creación": "Creación",
    "rubro": "Rubro",
    "actividad": "Checklist",
    "listo": "¿Está listo?",
    "cantidad_meta": "Cantidad / meta",
    "fecha_limite": "Fecha límite",
    "observaciones": "Observaciones",
    "responsables": "Responsables",
    "responsables_adicionales": "Responsables adicionales",
}

RESPONSABLE_ADICIONAL_GUAYAQUIL = "José Matías"
RESPONSABLES_BASE_GUAYAQUIL = {"Ing. Milka Nazareno", "Ab. Carlos García"}
ZONA_HORARIA_ECUADOR = ZoneInfo("America/Guayaquil")


def _texto(valor: Any) -> str:
    return "" if valor is None else str(valor).strip()


def _fecha_hora_ecuador(valor: Any) -> datetime | None:
    if valor is None or valor == "":
        return None
    fecha = valor.to_pydatetime() if isinstance(valor, pd.Timestamp) else valor
    if not isinstance(fecha, datetime):
        fecha = pd.to_datetime(fecha).to_pydatetime()
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(ZONA_HORARIA_ECUADOR).replace(tzinfo=None)


def _consultar_datos() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    with get_connection() as con:
        asegurar_checklist_congreso(con)
        items = [dict(row) for row in listar_checklist_congreso(con)]
        historial = [dict(row) for row in listar_historial_checklist_congreso(con)]
        responsables = [
            dict(row)
            for row in listar_responsables_congreso(con, "guayaquil", solo_activos=True)
        ]
    return items, historial, responsables


def _datos() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        return _consultar_datos()
    except Exception as exc:
        # Respaldo para instancias de Streamlit que conserven en caché una
        # inicialización anterior mientras ya sirven este módulo nuevo.
        if getattr(exc, "pgcode", None) != "42P01":
            raise
        modulo_init_db = importlib.reload(importlib.import_module("database.init_db"))
        modulo_init_db.init_db()
        return _consultar_datos()


def _actor(responsables: list[dict[str, Any]]) -> tuple[int | None, str]:
    por_id = {row["id"]: row for row in responsables}
    opciones: list[tuple[str, int | str]] = [
        ("responsable", valor) for valor in por_id
    ]
    opciones.append(("adicional", RESPONSABLE_ADICIONAL_GUAYAQUIL))
    opcion = st.selectbox(
        "¿Quién está actualizando el checklist?",
        opciones,
        format_func=lambda valor: (
            por_id[int(valor[1])]["nombres"]
            if valor[0] == "responsable" else str(valor[1])
        ),
        key="checklist_actor",
    )
    if opcion[0] == "responsable":
        actor_id = int(opcion[1])
        return actor_id, por_id[actor_id]["nombres"]
    return None, str(opcion[1])


def _vista_checklist(
    items: list[dict[str, Any]],
    historial: list[dict[str, Any]],
    responsables: list[dict[str, Any]],
    actor_id: int | None,
    actor_nombre: str,
) -> None:
    ultimo_cambio: dict[int, dict[str, Any]] = {}
    for cambio in historial:
        if cambio.get("checklist_id") is not None:
            ultimo_cambio.setdefault(cambio["checklist_id"], cambio)

    st.metric("Actividades", len(items))

    filas = []
    for item in items:
        cambio = ultimo_cambio.get(item["id"], {})
        historial_breve = "Sin cambios"
        if cambio:
            fecha = _fecha_hora_ecuador(cambio["fecha_cambio"])
            historial_breve = f"{fecha:%d/%m/%Y %H:%M} · {cambio['actor_nombre']}"
        filas.append(
            {
                "Rubro": item["rubro"],
                "Checklist": item["actividad"],
                "¿Está listo?": "Sí" if item["listo"] else "No",
                "Responsables": item.get("responsables") or "Sin asignar",
                "Observaciones": item.get("observaciones") or "",
                "Historial / último cambio": historial_breve,
            }
        )
    st.dataframe(
        pd.DataFrame(filas),
        hide_index=True,
        use_container_width=True,
        height=430,
        column_config={
            "Observaciones": st.column_config.TextColumn(width="large"),
            "Historial / último cambio": st.column_config.TextColumn(width="medium"),
        },
    )

    if not items:
        return
    por_id = {item["id"]: item for item in items}
    item_id = st.selectbox(
        "Actividad que deseas actualizar",
        list(por_id),
        format_func=lambda valor: f"{por_id[valor]['rubro']} — {por_id[valor]['actividad']}",
        key="checklist_item_editar",
    )
    item = por_id[item_id]
    responsables_por_id = {row["id"]: row for row in responsables}
    responsables_actuales = [
        valor for valor in item.get("responsables_ids", []) if valor in responsables_por_id
    ]
    with st.form(f"form_checklist_{item_id}"):
        e1, e2 = st.columns([1, 2])
        rubro = e1.text_input("Rubro", value=item["rubro"])
        actividad = e2.text_input("Checklist", value=item["actividad"])
        listo = st.selectbox(
            "¿Está listo?", [False, True], index=1 if item["listo"] else 0,
            format_func=lambda valor: "Sí" if valor else "No",
        )
        responsables_ids = st.multiselect(
            "Responsables de Guayaquil",
            list(responsables_por_id),
            default=responsables_actuales,
            format_func=lambda valor: responsables_por_id[valor]["nombres"],
        )
        incluir_responsable_adicional = st.checkbox(
            f"Incluir a {RESPONSABLE_ADICIONAL_GUAYAQUIL}",
            value=RESPONSABLE_ADICIONAL_GUAYAQUIL in _texto(
                item.get("responsables_adicionales")
            ),
        )
        observaciones = st.text_area("Observaciones", value=item.get("observaciones") or "")
        guardar = st.form_submit_button(
            "Guardar cambios", type="primary", disabled=not actor_nombre
        )
    if guardar:
        if not rubro.strip() or not actividad.strip():
            st.error("Rubro y checklist son obligatorios.")
        else:
            try:
                with get_connection() as con:
                    cambios = actualizar_item_checklist_congreso(
                        con,
                        item_id,
                        {
                            "rubro": rubro,
                            "actividad": actividad,
                            "listo": listo,
                            "observaciones": observaciones,
                            "responsables_adicionales": (
                                RESPONSABLE_ADICIONAL_GUAYAQUIL
                                if incluir_responsable_adicional else ""
                            ),
                        },
                        responsables_ids,
                        actor_id,
                        actor_nombre,
                    )
                if cambios:
                    st.success("Checklist actualizado y cambio registrado en el historial.")
                    st.rerun()
                st.info("No se detectaron cambios.")
            except Exception as exc:
                st.error(f"No se pudo actualizar el checklist: {exc}")

    with st.expander("Agregar otro campo al checklist"):
        with st.form("form_nuevo_item_checklist", clear_on_submit=True):
            n1, n2 = st.columns([1, 2])
            nuevo_rubro = n1.text_input("Rubro")
            nueva_actividad = n2.text_input("Nuevo campo o actividad")
            nuevos_responsables = st.multiselect(
                "Responsables",
                list(responsables_por_id),
                default=[
                    valor for valor, datos in responsables_por_id.items()
                    if datos["nombres"] in RESPONSABLES_BASE_GUAYAQUIL
                ],
                format_func=lambda valor: responsables_por_id[valor]["nombres"],
            )
            incluir_nuevo_responsable_adicional = st.checkbox(
                f"Incluir a {RESPONSABLE_ADICIONAL_GUAYAQUIL}", value=True
            )
            nuevas_observaciones = st.text_area("Observaciones")
            agregar = st.form_submit_button(
                "Agregar al checklist", type="primary", disabled=not actor_nombre
            )
        if agregar:
            if not nuevo_rubro.strip() or not nueva_actividad.strip():
                st.error("Rubro y actividad son obligatorios.")
            else:
                try:
                    with get_connection() as con:
                        crear_item_checklist_congreso(
                            con, nuevo_rubro, nueva_actividad,
                            None, None,
                            nuevas_observaciones, nuevos_responsables,
                            (
                                RESPONSABLE_ADICIONAL_GUAYAQUIL
                                if incluir_nuevo_responsable_adicional else ""
                            ),
                            actor_id, actor_nombre,
                        )
                    st.success("Actividad agregada al checklist.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"No se pudo agregar la actividad: {exc}")

    with st.expander("Eliminar actividad del checklist"):
        st.caption(
            "La actividad dejará de mostrarse. Su historial permanecerá disponible."
        )
        with st.form("form_eliminar_item_checklist"):
            eliminar_id = st.selectbox(
                "Actividad que deseas eliminar",
                list(por_id),
                format_func=lambda valor: (
                    f"{por_id[valor]['rubro']} — {por_id[valor]['actividad']}"
                ),
            )
            confirmar = st.checkbox(
                "Confirmo que deseo eliminar esta actividad del checklist"
            )
            eliminar = st.form_submit_button(
                "Eliminar actividad",
                disabled=not actor_nombre or not confirmar,
            )
        if eliminar:
            try:
                with get_connection() as con:
                    eliminar_item_checklist_congreso(
                        con, eliminar_id, actor_id, actor_nombre
                    )
                st.success("Actividad eliminada del checklist.")
                st.rerun()
            except Exception as exc:
                st.error(f"No se pudo eliminar la actividad: {exc}")


def _vista_historial(historial: list[dict[str, Any]]) -> None:
    if not historial:
        st.info("Aún no hay cambios registrados en el checklist.")
        return
    tabla = pd.DataFrame(
        [
            {
                "Fecha (Ecuador)": _fecha_hora_ecuador(row["fecha_cambio"]),
                "Rubro": row["rubro"],
                "Checklist": row["actividad"],
                "Campo": ETIQUETAS_CAMPOS.get(row.get("campo"), row.get("campo") or "—"),
                "Valor anterior": row.get("valor_anterior") or "—",
                "Valor nuevo": row.get("valor_nuevo") or "—",
                "Actualizado por": row["actor_nombre"],
            }
            for row in historial
        ]
    )
    st.caption("Fechas y horas mostradas en America/Guayaquil (UTC−5).")
    st.dataframe(tabla, hide_index=True, use_container_width=True, height=520)


def mostrar_checklist_congreso() -> None:
    st.markdown(
        """
        <style>
        .checklist-cabecera {border-left: 5px solid #C8A951; padding: .15rem 0 .15rem 1rem; margin-bottom: 1rem;}
        .checklist-cabecera h2 {color: #1A3A5C; margin: 0;}
        .checklist-cabecera p {margin: .25rem 0 0; color: #526170;}
        </style>
        <div class="checklist-cabecera">
          <h2>Checklist Congreso</h2>
          <p>Coordinación operativa · Guayaquil · Congreso Internacional 2026</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        items, historial, responsables = _datos()
    except Exception as exc:
        st.error(f"No se pudo cargar el checklist: {exc}")
        return
    actor_id, actor_nombre = _actor(responsables)
    tab_checklist, tab_historial = st.tabs(["Checklist", "Historial"])
    with tab_checklist:
        _vista_checklist(items, historial, responsables, actor_id, actor_nombre)
    with tab_historial:
        _vista_historial(historial)
