"""
charts.py — Gráficos Plotly reutilizables para los dashboards.

Cada función recibe un DataFrame ya filtrado y retorna una figura Plotly.
No accede directamente a la base de datos.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLOR_PRIMARIO   = "#1A3A5C"
COLOR_SECUNDARIO = "#C8A951"
COLORES_OFICINAS = {
    "Guayaquil": "#1A3A5C",
    "Manabí":    "#2E86AB",
    "Loja":      "#A23B72",
    "Cuenca":    "#C8A951",
}

ETIQUETAS_SATISFACCION = {
    "p1_conocimiento":   "Conocimiento",
    "p2_inquietudes":    "Inquietudes",
    "p3_contenido":      "Contenido",
    "p4_presencialidad": "Presencialidad",
    "p5_puntualidad":    "Puntualidad",
    "p6_logistica":      "Logística",
    "p7_duracion":       "Duración",
}


def grafico_participantes_provincia(df: pd.DataFrame) -> go.Figure:
    """Barras horizontales: participantes por provincia, ordenadas descendente."""
    conteo = (
        df["provincia"]
        .dropna()
        .value_counts()
        .reset_index()
        .rename(columns={"provincia": "Provincia", "count": "Participantes"})
        .sort_values("Participantes", ascending=True)
    )
    fig = px.bar(
        conteo, x="Participantes", y="Provincia", orientation="h",
        title="Participantes por provincia",
        color_discrete_sequence=[COLOR_PRIMARIO],
        text="Participantes",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Cantidad", yaxis_title="",
                      margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white")
    return fig


def grafico_evolucion_mensual(df: pd.DataFrame) -> go.Figure:
    """Línea de tiempo: participantes por mes."""
    df_copia = df.copy()
    df_copia["mes"] = pd.to_datetime(
        df_copia["fecha_capacitacion"], errors="coerce"
    ).dt.to_period("M").astype(str)

    mensual = (
        df_copia.groupby("mes").size()
        .reset_index(name="Participantes")
        .sort_values("mes")
    )
    fig = px.line(
        mensual, x="mes", y="Participantes",
        title="Evolución mensual de participantes",
        markers=True, color_discrete_sequence=[COLOR_PRIMARIO],
    )
    fig.update_layout(xaxis_title="Mes", yaxis_title="Cantidad",
                      margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white")
    return fig


def grafico_top_instituciones(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Barras horizontales: top N instituciones de origen."""
    conteo = (
        df["institucion"]
        .dropna()
        .value_counts()
        .head(top_n)
        .reset_index()
        .rename(columns={"institucion": "Institución", "count": "Participantes"})
        .sort_values("Participantes", ascending=True)
    )
    fig = px.bar(
        conteo, x="Participantes", y="Institución", orientation="h",
        title=f"Top {top_n} instituciones de origen",
        color_discrete_sequence=[COLOR_SECUNDARIO],
        text="Participantes",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Cantidad", yaxis_title="",
                      margin=dict(l=10, r=10, t=40, b=30), plot_bgcolor="white")
    return fig


def grafico_radar_satisfaccion(df: pd.DataFrame) -> go.Figure:
    """Radar de satisfacción promedio por dimensión (p1 a p7)."""
    columnas  = list(ETIQUETAS_SATISFACCION.keys())
    etiquetas = list(ETIQUETAS_SATISFACCION.values())

    promedios = [df[col].dropna().astype(float).mean() for col in columnas]
    valores_cerrados   = promedios + [promedios[0]]
    etiquetas_cerradas = etiquetas + [etiquetas[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=valores_cerrados, theta=etiquetas_cerradas,
        fill="toself", name="Satisfacción promedio",
        line_color=COLOR_PRIMARIO,
        fillcolor="rgba(26, 58, 92, 0.25)",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5])),
        showlegend=False,
        title="Satisfacción promedio por dimensión",
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig


def grafico_histograma_satisfaccion(df: pd.DataFrame) -> go.Figure:
    """Histograma de distribución del puntaje promedio de satisfacción por participante."""
    columnas = list(ETIQUETAS_SATISFACCION.keys())
    cols_existentes = [c for c in columnas if c in df.columns]

    if not cols_existentes:
        return go.Figure().update_layout(title="Sin datos de satisfacción")

    df_num = df[cols_existentes].copy().apply(pd.to_numeric, errors="coerce")
    promedio_por_participante = df_num.mean(axis=1).dropna()

    fig = px.histogram(
        promedio_por_participante, nbins=20,
        title="Distribución de puntaje promedio de satisfacción",
        labels={"value": "Puntaje promedio", "count": "Participantes"},
        color_discrete_sequence=[COLOR_PRIMARIO],
    )
    fig.update_layout(
        xaxis_title="Puntaje promedio (1-5)", yaxis_title="Cantidad de participantes",
        showlegend=False, margin=dict(l=10, r=10, t=40, b=10),
        plot_bgcolor="white", bargap=0.05,
    )
    return fig


def grafico_comparativo_oficinas(df: pd.DataFrame) -> go.Figure:
    """Barras agrupadas: participantes por oficina y mes (solo master)."""
    df_copia = df.copy()
    df_copia["mes"] = pd.to_datetime(
        df_copia["fecha_capacitacion"], errors="coerce"
    ).dt.to_period("M").astype(str)

    agrupado = (
        df_copia.groupby(["mes", "oficina"]).size()
        .reset_index(name="Participantes")
        .sort_values("mes")
    )
    fig = px.bar(
        agrupado, x="mes", y="Participantes", color="oficina",
        barmode="group", title="Participantes por oficina y mes",
        color_discrete_map=COLORES_OFICINAS,
    )
    fig.update_layout(xaxis_title="Mes", yaxis_title="Cantidad",
                      legend_title="Oficina",
                      margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white")
    return fig


def grafico_radar_comparativo_oficinas(df: pd.DataFrame) -> go.Figure:
    """Radar de satisfacción promedio por oficina — una traza por oficina."""
    columnas  = list(ETIQUETAS_SATISFACCION.keys())
    etiquetas = list(ETIQUETAS_SATISFACCION.values())

    fig = go.Figure()
    for oficina, grupo in df.groupby("oficina"):
        promedios = [
            grupo[col].dropna().astype(float).mean()
            for col in columnas if col in grupo.columns
        ]
        if not promedios:
            continue
        valores_cerrados   = promedios + [promedios[0]]
        etiquetas_cerradas = etiquetas + [etiquetas[0]]
        color = COLORES_OFICINAS.get(str(oficina), "#888888")
        fig.add_trace(go.Scatterpolar(
            r=valores_cerrados, theta=etiquetas_cerradas,
            fill="toself", name=str(oficina), line_color=color,
        ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5])),
        showlegend=True,
        title="Satisfacción promedio por oficina",
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig
