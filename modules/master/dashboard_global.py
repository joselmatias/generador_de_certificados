"""
dashboard_global.py — Dashboard consolidado (solo rol master).

Muestra todos los indicadores de capacitaciones agregados
entre las 4 oficinas regionales, con comparativos entre ellas.
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from auth.login import obtener_sesion
from database.db import get_connection, consultar_capacitaciones
from utils.charts import (
    grafico_participantes_provincia,
    grafico_evolucion_mensual,
    grafico_top_instituciones,
    grafico_radar_satisfaccion,
    grafico_histograma_satisfaccion,
    grafico_comparativo_oficinas,
    grafico_radar_comparativo_oficinas,
    ETIQUETAS_SATISFACCION,
)


def mostrar_dashboard_global() -> None:
    """Renderiza el dashboard global (acceso exclusivo para rol master)."""
    sesion = obtener_sesion()

    if sesion["rol"] != "master":
        st.error("Acceso restringido. Solo disponible para el rol master.")
        return

    st.title("🌐 Dashboard Global — Todas las Oficinas")
    st.divider()

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------
    st.subheader("Filtros")
    col1, col2, col3 = st.columns(3)

    with col1:
        fecha_desde = st.date_input("Desde", value=None, key="global_desde")
    with col2:
        fecha_hasta = st.date_input("Hasta", value=None, key="global_hasta")
    with col3:
        sel_oficina = st.selectbox(
            "Filtrar por oficina",
            options=["Todas", "Guayaquil", "Manabí", "Loja", "Cuenca"],
            key="global_oficina",
        )

    oficina_filtro = None if sel_oficina == "Todas" else sel_oficina

    # ------------------------------------------------------------------
    # Consulta sin filtro de oficina (master ve todo)
    # ------------------------------------------------------------------
    with get_connection() as con:
        filas = consultar_capacitaciones(
            con,
            oficina=oficina_filtro,
            fecha_desde=str(fecha_desde) if fecha_desde else None,
            fecha_hasta=str(fecha_hasta) if fecha_hasta else None,
        )

    if not filas:
        st.info("No hay registros con los filtros seleccionados.")
        return

    df = pd.DataFrame([dict(f) for f in filas])

    for col in ETIQUETAS_SATISFACCION.keys():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ------------------------------------------------------------------
    # Métricas globales
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Métricas globales consolidadas")

    promedio = _promedio_satisfaccion_global(df)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total participantes", f"{len(df):,}")
    col2.metric("Cursos distintos", df["nombre_curso"].nunique() if "nombre_curso" in df.columns else 0)
    col3.metric("Oficinas activas", df["oficina"].nunique() if "oficina" in df.columns else 0)
    col4.metric(
        "Satisfacción promedio",
        f"{promedio:.2f} / 5.00" if promedio else "Sin datos",
    )

    # Participantes por oficina
    st.markdown("**Participantes por oficina:**")
    conteo_oficinas = df["oficina"].value_counts().reset_index()
    conteo_oficinas.columns = ["Oficina", "Participantes"]
    cols_met = st.columns(len(conteo_oficinas))
    for col, (_, row) in zip(cols_met, conteo_oficinas.iterrows()):
        col.metric(row["Oficina"], f"{row['Participantes']:,}")

    # ------------------------------------------------------------------
    # Comparativo entre oficinas
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Comparativo entre oficinas")

    col_bar, col_radar = st.columns(2)
    with col_bar:
        st.plotly_chart(grafico_comparativo_oficinas(df), use_container_width=True)
    with col_radar:
        st.plotly_chart(grafico_radar_comparativo_oficinas(df), use_container_width=True)

    # ------------------------------------------------------------------
    # Gráficos consolidados
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Análisis consolidado")

    col_prov, col_inst = st.columns(2)
    with col_prov:
        st.plotly_chart(grafico_participantes_provincia(df), use_container_width=True)
    with col_inst:
        st.plotly_chart(grafico_top_instituciones(df), use_container_width=True)

    st.plotly_chart(grafico_evolucion_mensual(df), use_container_width=True)

    col_radar_sat, col_hist = st.columns(2)
    with col_radar_sat:
        st.plotly_chart(grafico_radar_satisfaccion(df), use_container_width=True)
    with col_hist:
        st.plotly_chart(grafico_histograma_satisfaccion(df), use_container_width=True)

    # ------------------------------------------------------------------
    # Tabla global
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Tabla global de registros")

    columnas_tabla = ["oficina", "nombre", "cedula", "fecha_capacitacion",
                      "nombre_curso", "provincia", "institucion", "codigo_certificado"]
    cols_ex = [c for c in columnas_tabla if c in df.columns]
    st.dataframe(
        df[cols_ex].rename(columns={
            "oficina": "Oficina", "nombre": "Nombre", "cedula": "Cédula",
            "fecha_capacitacion": "Fecha", "nombre_curso": "Curso",
            "provincia": "Provincia", "institucion": "Institución",
            "codigo_certificado": "Certificado",
        }),
        use_container_width=True, hide_index=True,
    )

    if st.button("Descargar tabla global en Excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Global")
        st.download_button(
            label="📥 Descargar Excel global",
            data=buffer.getvalue(),
            file_name="capacitaciones_global.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _promedio_satisfaccion_global(df: pd.DataFrame) -> float | None:
    cols = [c for c in ETIQUETAS_SATISFACCION.keys() if c in df.columns]
    if not cols:
        return None
    valores = [v for v in df[cols].values.flatten() if pd.notna(v)]
    return sum(valores) / len(valores) if valores else None
