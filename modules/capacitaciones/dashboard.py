"""
dashboard.py — Dashboard de Capacitaciones por oficina.

Métricas y gráficos filtrados por la oficina del usuario autenticado.
El rol master usa este dashboard para su propia oficina;
el consolidado global está en master/dashboard_global.py.
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from auth.login import obtener_sesion
from database.db import get_connection, consultar_capacitaciones, listar_cursos
from utils.charts import (
    grafico_participantes_provincia,
    grafico_evolucion_mensual,
    grafico_top_instituciones,
    grafico_radar_satisfaccion,
    grafico_histograma_satisfaccion,
    ETIQUETAS_SATISFACCION,
)


def mostrar_dashboard() -> None:
    """Renderiza el dashboard de capacitaciones para el usuario actual."""
    sesion  = obtener_sesion()
    oficina = sesion["oficina"]

    st.title("📊 Dashboard — Capacitaciones")
    st.markdown(f"**Oficina:** {oficina}")
    st.divider()

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------
    st.subheader("Filtros")
    col1, col2, col3 = st.columns(3)

    with col1:
        fecha_desde = st.date_input("Desde", value=None, key="dash_cap_desde")
    with col2:
        fecha_hasta = st.date_input("Hasta", value=None, key="dash_cap_hasta")

    with get_connection() as con:
        cursos = listar_cursos(con, oficina=oficina)

    with col3:
        curso_sel = st.selectbox("Curso", options=["Todos"] + cursos, key="dash_cap_curso")

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    with get_connection() as con:
        filas = consultar_capacitaciones(
            con,
            oficina=oficina,
            fecha_desde=str(fecha_desde) if fecha_desde else None,
            fecha_hasta=str(fecha_hasta) if fecha_hasta else None,
            nombre_curso=None if curso_sel == "Todos" else curso_sel,
        )

    if not filas:
        st.info("No hay registros con los filtros seleccionados.")
        return

    df = pd.DataFrame([dict(f) for f in filas])

    for col in ETIQUETAS_SATISFACCION.keys():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ------------------------------------------------------------------
    # Métricas
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Métricas generales")

    promedio = _promedio_satisfaccion(df)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total participantes", f"{len(df):,}")
    col2.metric("Cursos distintos", df["nombre_curso"].nunique())
    col3.metric("Provincia líder", _provincia_top(df))
    col4.metric(
        "Satisfacción promedio",
        f"{promedio:.2f} / 5.00" if promedio else "Sin datos",
    )

    # ------------------------------------------------------------------
    # Gráficos
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Análisis por provincia e institución")
    col_izq, col_der = st.columns(2)
    with col_izq:
        st.plotly_chart(grafico_participantes_provincia(df), use_container_width=True)
    with col_der:
        st.plotly_chart(grafico_top_instituciones(df), use_container_width=True)

    st.divider()
    st.subheader("Evolución temporal")
    st.plotly_chart(grafico_evolucion_mensual(df), use_container_width=True)

    st.divider()
    st.subheader("Satisfacción de los participantes")
    col_radar, col_hist = st.columns(2)
    with col_radar:
        st.plotly_chart(grafico_radar_satisfaccion(df), use_container_width=True)
    with col_hist:
        st.plotly_chart(grafico_histograma_satisfaccion(df), use_container_width=True)

    # ------------------------------------------------------------------
    # Tabla detallada
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Detalle de registros")

    columnas_tabla = ["nombre", "cedula", "fecha_capacitacion", "nombre_curso",
                      "provincia", "institucion", "codigo_certificado"]
    cols_ex = [c for c in columnas_tabla if c in df.columns]
    st.dataframe(
        df[cols_ex].rename(columns={
            "nombre": "Nombre", "cedula": "Cédula",
            "fecha_capacitacion": "Fecha", "nombre_curso": "Curso",
            "provincia": "Provincia", "institucion": "Institución",
            "codigo_certificado": "Certificado",
        }),
        use_container_width=True, hide_index=True,
    )

    if st.button("Descargar tabla en Excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df[cols_ex].to_excel(writer, index=False, sheet_name="Capacitaciones")
        st.download_button(
            label="📥 Descargar Excel",
            data=buffer.getvalue(),
            file_name=f"capacitaciones_{oficina.lower()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _provincia_top(df: pd.DataFrame) -> str:
    if "provincia" not in df.columns or df["provincia"].dropna().empty:
        return "N/D"
    return df["provincia"].value_counts().idxmax()


def _promedio_satisfaccion(df: pd.DataFrame) -> float | None:
    cols = [c for c in ETIQUETAS_SATISFACCION.keys() if c in df.columns]
    if not cols:
        return None
    valores = [v for v in df[cols].values.flatten() if pd.notna(v)]
    return sum(valores) / len(valores) if valores else None
