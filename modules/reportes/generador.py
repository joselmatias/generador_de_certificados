"""
generador.py — Generador de Reportes de Capacitaciones y Asambleas Productivas.

Dos subsecciones:
1. Reporte de Capacitaciones — genera PDF con formato DRAC
2. Actas de Asambleas Productivas — registra asistentes

Estadísticas mensuales al pie de la página.
"""

from __future__ import annotations

import json
from datetime import date

import streamlit as st

from database.init_db import init_db
from database.db import (
    get_connection,
    obtener_siguiente_numero_reporte,
    insertar_reporte_capacitacion,
    consultar_reportes_capacitacion,
    insertar_asamblea_productiva,
    consultar_asambleas_productivas,
    estadisticas_mensuales,
)
from utils.reporte_drac_pdf import generar_reporte_drac, TIPOS_EVENTO

# Garantiza que las tablas existan aunque el caché haya bloqueado init_db() en app.py
init_db()

_MESES_ESP = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Configuración específica por oficina
_OFICINA_CFG: dict[str, dict] = {
    "guayaquil": {
        "revisado_por":       "José Matías",
        "area_elaborado":     "DRAC",
        "nombre_institucion": "Dirección Regional de Abogacía de la Competencia",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Dirección Regional de",
            "Abogacía de la Competencia",
        ],
    },
    "cuenca": {
        "revisado_por":       "Roberto Carlos Santos Suarez",
        "area_elaborado":     "OTAC",
        "nombre_institucion": "Oficina Técnica de Apoyo de Cuenca",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Oficina Técnica de Apoyo",
            "Cuenca",
        ],
    },
    "manabi": {
        "revisado_por":       "Roberto Carlos Santos Suarez",
        "area_elaborado":     "OTAP",
        "nombre_institucion": "Oficina Técnica de Apoyo de Portoviejo",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Oficina Técnica de Apoyo",
            "Portoviejo",
        ],
    },
    "loja": {
        "revisado_por":       "Roberto Carlos Santos Suarez",
        "area_elaborado":     "OTAL",
        "nombre_institucion": "Oficina Técnica de Apoyo de Loja",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Oficina Técnica de Apoyo",
            "Loja",
        ],
    },
}

_CFG_DEFAULT = {
    "revisado_por":       "Roberto Carlos Santos Suarez",
    "area_elaborado":     "OTA",
    "nombre_institucion": "la Oficina Técnica de Apoyo",
    "lineas_institucion": [
        "Intendencia Regional /",
        "Oficina Técnica de Apoyo",
        "",
    ],
}


def _cfg_oficina(oficina_id: str) -> dict:
    return _OFICINA_CFG.get(oficina_id.lower(), _CFG_DEFAULT)


def mostrar_generador_reportes() -> None:
    oficina_id     = st.session_state.get("oficina_id", "")
    oficina_nombre = st.session_state.get("oficina_nombre", oficina_id)

    st.title("📝 Generador de Reportes de Capacitaciones y Asambleas Productivas")
    st.markdown(f"**Oficina:** {oficina_nombre}")
    st.divider()

    tab_cap, tab_asm, tab_stats = st.tabs([
        "📋 Reporte de Capacitaciones",
        "🤝 Actas de Asambleas Productivas",
        "📊 Estadísticas del Mes",
    ])

    with tab_cap:
        _tab_reporte_capacitacion(oficina_id, oficina_nombre)

    with tab_asm:
        _tab_asamblea_productiva(oficina_id, oficina_nombre)

    with tab_stats:
        _tab_estadisticas(oficina_id, oficina_nombre)


# ---------------------------------------------------------------------------
# TAB 1 — Reporte de Capacitaciones
# ---------------------------------------------------------------------------

def _tab_reporte_capacitacion(oficina_id: str, oficina_nombre: str) -> None:
    st.subheader("Reporte de Capacitaciones")
    st.markdown("Completa los campos y haz clic en **Generar Reporte** para descargar el PDF.")
    st.divider()

    cfg = _cfg_oficina(oficina_id)
    revisado_por       = cfg["revisado_por"]
    area_elaborado     = cfg["area_elaborado"]
    lineas_institucion = cfg["lineas_institucion"]
    nombre_institucion = cfg["nombre_institucion"]

    col_num, col_fecha = st.columns([1, 2])
    with col_num:
        anio_actual = date.today().year
        st.markdown("**Número de Reporte**")
        with get_connection() as _con:
            ultimo = _con.execute(
                "SELECT ultimo_numero FROM contador_reporte WHERE id = 1"
            ).fetchone()
            proximo = (ultimo["ultimo_numero"] if ultimo else 48) + 1
        st.info(f"Se generará: **DRAC-{proximo:03d}-{anio_actual}**")

    with col_fecha:
        fecha_reporte = st.date_input(
            "Fecha del Reporte",
            value=date.today(),
            key="rep_fecha",
        )

    # Tipo de Evento
    st.markdown("**Tipo de Evento**")
    tipo_evento = st.selectbox(
        "Selecciona el tipo de evento",
        options=TIPOS_EVENTO,
        key="rep_tipo_evento",
        label_visibility="collapsed",
    )

    st.divider()

    # Institución Invitada — Fecha — Modalidad — Tema
    st.markdown("#### Institución Invitada - Fecha - Modalidad - Tema:")
    c1, c2 = st.columns(2)
    with c1:
        institucion_invitada = st.text_input("Institución Invitada", key="rep_institucion")
        modalidad = st.selectbox(
            "Modalidad",
            options=["Presencial", "Virtual", "Híbrida"],
            key="rep_modalidad",
        )
    with c2:
        fecha_evento = st.date_input(
            "Fecha del Evento",
            value=date.today(),
            key="rep_fecha_evento",
            max_value=fecha_reporte,   # no puede ser posterior a la fecha del reporte
        )
        tema = st.text_input("Tema", key="rep_tema")

    if fecha_evento > fecha_reporte:
        st.warning("⚠️ La fecha del evento no puede ser posterior a la fecha del reporte.")

    st.divider()

    # Nombre de los Capacitadores
    st.markdown("#### Nombre de los Capacitadores:")
    num_capacitadores = st.number_input(
        "¿Cuántos capacitadores participaron?",
        min_value=1, max_value=10, value=1, step=1, key="rep_num_cap",
    )
    capacitadores_lista: list[str] = []
    cols_cap = st.columns(min(int(num_capacitadores), 3))
    for i in range(int(num_capacitadores)):
        col_idx = i % 3
        with cols_cap[col_idx]:
            nombre_cap = st.text_input(
                f"Capacitador {i + 1}",
                key=f"rep_cap_{i}",
                placeholder="Nombre completo",
            )
            capacitadores_lista.append(nombre_cap)

    capacitadores_lista = [c for c in capacitadores_lista if c.strip()]
    capacitadores_str = "\n".join(f"• {c}" for c in capacitadores_lista) if capacitadores_lista else ""

    st.divider()

    # Elaborado por — dropdown con los capacitadores
    st.markdown("#### Elaborado por:")
    opciones_elaborado = capacitadores_lista if capacitadores_lista else ["(Ingresa los capacitadores primero)"]
    elaborado_por = st.selectbox(
        "Selecciona quién elaboró el reporte",
        options=opciones_elaborado,
        key="rep_elaborado",
        label_visibility="collapsed",
    )

    st.info(f"**Revisado y aprobado por:** {revisado_por}")

    st.divider()

    # Público Objetivo
    st.markdown("#### Público Objetivo:")
    publico_objetivo = st.text_area(
        "Describe el público objetivo",
        key="rep_publico",
        height=80,
        label_visibility="collapsed",
        placeholder="Ej: Productores agrícolas del cantón Portoviejo...",
    )

    st.divider()

    # Descripción de la Capacitación
    st.markdown("#### Descripción de la Capacitación:")
    descripcion = st.text_area(
        "Describe la capacitación",
        key="rep_descripcion",
        height=120,
        label_visibility="collapsed",
        placeholder="Detalla el contenido, metodología y resultados obtenidos...",
    )

    st.divider()

    # Observaciones — valor fijo
    st.markdown("#### Observaciones:")
    st.info("Ninguna")
    observaciones = "Ninguna"

    # Adjuntos — texto dinámico según oficina
    adjuntos = (
        f"La {nombre_institucion}, cuenta con archivos digitales "
        "de la capacitación efectuada, cuya documentación se detalla a continuación:\n\n"
        "a)\tRegistro de asistencia.\nb)\tFotografías."
    )
    st.markdown("#### Adjuntos (medios de verificación):")
    st.info(adjuntos)

    st.divider()

    # Número de personas capacitadas
    st.markdown("#### Número de Personas Capacitadas:")
    num_personas = st.number_input(
        "Ingresa el número total de personas capacitadas",
        min_value=0, value=0, step=1,
        key="rep_num_personas",
        label_visibility="collapsed",
    )

    st.divider()

    # Botón Generar Reporte
    if st.button("📄 Generar Reporte de Capacitaciones", type="primary", use_container_width=True):
        errores = _validar_campos_reporte(
            institucion_invitada, tema, capacitadores_lista, publico_objetivo, descripcion
        )
        if fecha_evento > fecha_reporte:
            errores.append("La fecha del evento no puede ser posterior a la fecha del reporte.")
        if errores:
            for e in errores:
                st.error(e)
        else:
            with get_connection() as con:
                numero = obtener_siguiente_numero_reporte(con)
                datos_db = {
                    "numero_reporte":           numero,
                    "year_reporte":             anio_actual,
                    "oficina":                  oficina_id,
                    "fecha_reporte":            str(fecha_reporte),
                    "tipo_evento":              tipo_evento,
                    "institucion_invitada":     institucion_invitada,
                    "fecha_evento":             str(fecha_evento),
                    "modalidad":                modalidad,
                    "tema":                     tema,
                    "capacitadores":            json.dumps(capacitadores_lista, ensure_ascii=False),
                    "publico_objetivo":         publico_objetivo,
                    "descripcion":              descripcion,
                    "observaciones":            observaciones,
                    "adjuntos":                 adjuntos,
                    "elaborado_por":            elaborado_por,
                    "revisado_por":             revisado_por,
                    "num_personas_capacitadas": int(num_personas),
                }
                insertar_reporte_capacitacion(con, datos_db)

            pdf_bytes = generar_reporte_drac(
                numero_reporte=numero,
                year_reporte=anio_actual,
                fecha_reporte=str(fecha_reporte),
                tipo_evento=tipo_evento,
                institucion_invitada=institucion_invitada,
                fecha_evento=str(fecha_evento),
                modalidad=modalidad,
                tema=tema,
                capacitadores=capacitadores_str,
                publico_objetivo=publico_objetivo,
                descripcion=descripcion,
                observaciones=observaciones,
                adjuntos=adjuntos,
                elaborado_por=elaborado_por,
                revisado_por=revisado_por,
                fecha_elaboracion=str(fecha_reporte),
                lineas_institucion=lineas_institucion,
                area_elaborado=area_elaborado,
                num_personas_capacitadas=int(num_personas),
            )

            st.success(f"✅ Reporte **DRAC-{numero:03d}-{anio_actual}** generado correctamente.")
            st.download_button(
                label=f"📥 Descargar DRAC-{numero:03d}-{anio_actual}.pdf",
                data=pdf_bytes,
                file_name=f"DRAC-{numero:03d}-{anio_actual}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    # Historial de reportes de la oficina
    st.divider()
    st.subheader("Reportes generados en esta oficina")
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(con, oficina=oficina_id)

    if reportes:
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in reportes])
        cols_mostrar = ["numero_reporte", "year_reporte", "fecha_reporte",
                        "tipo_evento", "tema", "num_personas_capacitadas"]
        cols_ex = [c for c in cols_mostrar if c in df.columns]
        st.dataframe(
            df[cols_ex].rename(columns={
                "numero_reporte": "N.° Reporte",
                "year_reporte": "Año",
                "fecha_reporte": "Fecha",
                "tipo_evento": "Tipo Evento",
                "tema": "Tema",
                "num_personas_capacitadas": "Personas",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Aún no hay reportes registrados para esta oficina.")


# ---------------------------------------------------------------------------
# TAB 2 — Actas de Asambleas Productivas
# ---------------------------------------------------------------------------

def _tab_asamblea_productiva(oficina_id: str, oficina_nombre: str) -> None:
    st.subheader("Actas de Asambleas Productivas")
    st.markdown("Registra el número de personas que asistieron a cada asamblea productiva.")
    st.divider()

    col_fecha, col_personas = st.columns(2)
    with col_fecha:
        fecha_asamblea = st.date_input(
            "Fecha de la Asamblea",
            value=date.today(),
            key="asm_fecha",
        )
    with col_personas:
        num_asistentes = st.number_input(
            "Número de personas que asistieron",
            min_value=0, value=0, step=1,
            key="asm_num_asistentes",
        )

    if st.button("✅ Registrar Asamblea Productiva", type="primary", use_container_width=True):
        if num_asistentes <= 0:
            st.error("Ingresa un número de asistentes mayor a 0.")
        else:
            with get_connection() as con:
                insertar_asamblea_productiva(con, {
                    "oficina":        oficina_id,
                    "fecha":          str(fecha_asamblea),
                    "num_asistentes": int(num_asistentes),
                })
            st.success(f"✅ Asamblea registrada: **{int(num_asistentes)} personas** el {fecha_asamblea}.")
            st.rerun()

    st.divider()
    st.subheader("Asambleas registradas en esta oficina")
    with get_connection() as con:
        asambleas = consultar_asambleas_productivas(con, oficina=oficina_id)

    if asambleas:
        import pandas as pd
        df = pd.DataFrame([dict(a) for a in asambleas])
        cols_ex = [c for c in ["fecha", "num_asistentes", "fecha_registro"] if c in df.columns]
        st.dataframe(
            df[cols_ex].rename(columns={
                "fecha": "Fecha",
                "num_asistentes": "Personas Asistentes",
                "fecha_registro": "Registrado",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Aún no hay asambleas registradas para esta oficina.")


# ---------------------------------------------------------------------------
# TAB 3 — Estadísticas del Mes
# ---------------------------------------------------------------------------

def _tab_estadisticas(oficina_id: str, oficina_nombre: str) -> None:
    st.subheader("Estadísticas Mensuales")
    st.markdown("Resumen de actividades del mes seleccionado.")
    st.divider()

    es_master = st.session_state.get("oficina_rol", "") == "master"

    hoy = date.today()

    # Guayaquil (master) puede elegir ver todas las oficinas o una específica
    if es_master:
        _OPCIONES_OFICINA = {
            "todas":      "Todas las oficinas",
            "guayaquil":  "Guayaquil",
            "manabi":     "Manabí",
            "loja":       "Loja",
            "cuenca":     "Cuenca",
        }
        col_of, col_anio, col_mes = st.columns(3)
        with col_of:
            sel_of = st.selectbox(
                "Oficina",
                options=list(_OPCIONES_OFICINA.keys()),
                format_func=lambda k: _OPCIONES_OFICINA[k],
                key="stats_oficina",
            )
        oficina_filtro = None if sel_of == "todas" else sel_of
        label_oficina  = _OPCIONES_OFICINA[sel_of]
    else:
        col_anio, col_mes = st.columns(2)
        oficina_filtro = oficina_id
        label_oficina  = oficina_nombre

    with col_anio:
        anio_sel = st.selectbox(
            "Año",
            options=list(range(hoy.year, hoy.year - 5, -1)),
            index=0,
            key="stats_anio",
        )
    with col_mes:
        mes_sel = st.selectbox(
            "Mes",
            options=list(_MESES_ESP.keys()),
            format_func=lambda m: _MESES_ESP[m],
            index=hoy.month - 1,
            key="stats_mes",
        )

    with get_connection() as con:
        stats = estadisticas_mensuales(
            con,
            oficina=oficina_filtro,
            anio=int(anio_sel),
            mes=int(mes_sel),
        )

    mes_label = f"{_MESES_ESP[int(mes_sel)]} {int(anio_sel)}"
    st.markdown(f"### Resultados — {label_oficina} · {mes_label}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Capacitaciones realizadas",     stats["num_capacitaciones"])
    c2.metric("Personas capacitadas",          stats["personas_capacitadas"])
    c3.metric("Asambleas productivas",         stats["num_asambleas"])
    c4.metric("Personas en asambleas",         stats["personas_asambleas"])

    st.divider()
    st.markdown("**Detalle de Capacitaciones del mes:**")
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(
            con, oficina=oficina_filtro, anio=int(anio_sel), mes=int(mes_sel)
        )

    if reportes:
        import pandas as pd
        df_r = pd.DataFrame([dict(r) for r in reportes])
        # Cuando se muestran todas las oficinas, incluir columna "oficina"
        cols_base = ["numero_reporte", "fecha_reporte", "tipo_evento",
                     "tema", "elaborado_por", "num_personas_capacitadas"]
        if es_master and oficina_filtro is None:
            cols_base = ["oficina"] + cols_base
        cols = [c for c in cols_base if c in df_r.columns]
        st.dataframe(
            df_r[cols].rename(columns={
                "oficina":                  "Oficina",
                "numero_reporte":           "N.° Reporte",
                "fecha_reporte":            "Fecha",
                "tipo_evento":              "Tipo",
                "tema":                     "Tema",
                "elaborado_por":            "Elaborado por",
                "num_personas_capacitadas": "Personas",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No hay capacitaciones en el período seleccionado.")

    st.markdown("**Detalle de Asambleas del mes:**")
    with get_connection() as con:
        asambleas = consultar_asambleas_productivas(
            con, oficina=oficina_filtro, anio=int(anio_sel), mes=int(mes_sel)
        )

    if asambleas:
        import pandas as pd
        df_a = pd.DataFrame([dict(a) for a in asambleas])
        cols_a_base = ["fecha", "num_asistentes"]
        if es_master and oficina_filtro is None:
            cols_a_base = ["oficina"] + cols_a_base
        cols_a = [c for c in cols_a_base if c in df_a.columns]
        st.dataframe(
            df_a[cols_a].rename(columns={
                "oficina":       "Oficina",
                "fecha":         "Fecha",
                "num_asistentes": "Personas Asistentes",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No hay asambleas registradas en el período seleccionado.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validar_campos_reporte(
    institucion: str,
    tema: str,
    capacitadores: list[str],
    publico: str,
    descripcion: str,
) -> list[str]:
    errores = []
    if not institucion.strip():
        errores.append("El campo 'Institución Invitada' es obligatorio.")
    if not tema.strip():
        errores.append("El campo 'Tema' es obligatorio.")
    if not capacitadores:
        errores.append("Ingresa al menos un capacitador.")
    if not publico.strip():
        errores.append("El campo 'Público Objetivo' es obligatorio.")
    if not descripcion.strip():
        errores.append("El campo 'Descripción de la Capacitación' es obligatorio.")
    return errores
