"""
dashboard_drac.py — Dashboard DRAC (Dirección Regional de Acción Coordinada).

Secciones:
  1. Estadísticas de Encuestas de Satisfacción
  2. Estadísticas de Convenios Institucionales (con mapa interactivo del Ecuador)
"""

from __future__ import annotations

import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.db import get_connection, consultar_capacitaciones
from utils.charts import (
    grafico_radar_satisfaccion,
    grafico_histograma_satisfaccion,
    grafico_participantes_provincia,
    grafico_top_instituciones,
    grafico_evolucion_mensual,
    ETIQUETAS_SATISFACCION,
)

# ---------------------------------------------------------------------------
# Datos estáticos de convenios
# ---------------------------------------------------------------------------
CONVENIOS_DATA = [
    {"N": 1,  "numero": "SCE-UTM-CM-NAC-2024-09",       "contraparte": "UNIVERSIDAD TÉCNICA DE MANABÍ",                        "tipo": "CONVENIO MARCO",              "fecha": "10/12/2024", "canton": "Portoviejo",          "provincia": "Manabí",       "lat": -1.0543, "lon": -80.4543},
    {"N": 2,  "numero": "SCE-CCP-CM-NAC-2024-08",       "contraparte": "CÁMARA DE LA CONSTRUCCIÓN DE PORTOVIEJO",              "tipo": "CONVENIO MARCO",              "fecha": "20/12/2024", "canton": "Portoviejo",          "provincia": "Manabí",       "lat": -1.0543, "lon": -80.4543},
    {"N": 3,  "numero": "SCE-CEG-CM-NAC-2024-10",       "contraparte": "COLEGIO DE ECONOMISTAS DEL GUAYAS",                    "tipo": "CONVENIO MARCO",              "fecha": "23/12/2024", "canton": "Guayaquil",           "provincia": "Guayas",       "lat": -2.1894, "lon": -79.8891},
    {"N": 4,  "numero": "SCE-GADMG-CM-NAC-2025-001",    "contraparte": "GAD MUNICIPAL DE GUALACEO",                            "tipo": "CONVENIO MARCO",              "fecha": "22/01/2025", "canton": "Gualaceo",            "provincia": "Azuay",        "lat": -2.8897, "lon": -78.7833},
    {"N": 5,  "numero": "SCE-UC-CCI-NAC-2025-001",      "contraparte": "UNIVERSIDAD CATÓLICA DE CUENCA",                       "tipo": "COOPERACIÓN INTERINSTITUCIONAL", "fecha": "23/01/2025", "canton": "Cuenca",           "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 6,  "numero": "SCE-UPSE-CM-NAC-2025-002",     "contraparte": "UNIVERSIDAD PENÍNSULA DE SANTA ELENA",                 "tipo": "CONVENIO MARCO",              "fecha": "24/01/2025", "canton": "La Libertad",         "provincia": "Santa Elena",  "lat": -2.2333, "lon": -80.9167},
    {"N": 7,  "numero": "SCE-UG-CM-NAC-2025-003",       "contraparte": "UNIVERSIDAD DE GUAYAQUIL",                             "tipo": "CONVENIO MARCO",              "fecha": "27/01/2025", "canton": "Guayaquil",           "provincia": "Guayas",       "lat": -2.1894, "lon": -79.8891},
    {"N": 8,  "numero": "SCE-UTEG-CM-NAC-2025-004",     "contraparte": "UNIVERSIDAD TECNOLÓGICA EMPRESARIAL DE GUAYAQUIL",     "tipo": "CONVENIO MARCO",              "fecha": "27/01/2025", "canton": "Guayaquil",           "provincia": "Guayas",       "lat": -2.1894, "lon": -79.8891},
    {"N": 9,  "numero": "SCE-UPSC-CM-NAC-2025-005",     "contraparte": "UNIVERSIDAD POLITÉCNICA SALESIANA SEDE CUENCA",        "tipo": "CONVENIO MARCO",              "fecha": "14/02/2025", "canton": "Cuenca",              "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 10, "numero": "SCE-CCCUENCA-CM-NAC-2025-008", "contraparte": "CÁMARA DE COMERCIO DE CUENCA",                         "tipo": "CONVENIO MARCO",              "fecha": "26/03/2025", "canton": "Cuenca",              "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 11, "numero": "SCE-CAPIA-CM-NAC-2025-009",    "contraparte": "CÁMARA DE LA PEQUEÑA INDUSTRIA DEL AZUAY",             "tipo": "CONVENIO MARCO",              "fecha": "27/03/2025", "canton": "Cuenca",              "provincia": "Azuay",        "lat": -2.9001, "lon": -79.0059},
    {"N": 12, "numero": "SCE-FAPM-CM-NAC-2025-15",      "contraparte": "FEDERACIÓN ARTESANOS PROFESIONALES DEL CANTÓN MANTA",  "tipo": "CONVENIO MARCO",              "fecha": "18/08/2025", "canton": "Manta",               "provincia": "Manabí",       "lat": -0.9677, "lon": -80.7089},
    {"N": 13, "numero": "SCE-UETHOG-CM-NAC-2025-16",    "contraparte": "U. E. PARTICULAR TENIENTE HUGO ORTIZ",                 "tipo": "CONVENIO MARCO",              "fecha": "18/08/2025", "canton": "Portoviejo",          "provincia": "Manabí",       "lat": -1.0543, "lon": -80.4543},
    {"N": 14, "numero": "SCE-UNESUM-CM-NAC-2025-17",    "contraparte": "UNIVERSIDAD ESTATAL DEL SUR DE MANABÍ",                "tipo": "CONVENIO MARCO",              "fecha": "12/09/2025", "canton": "Jipijapa",            "provincia": "Manabí",       "lat": -1.3464, "lon": -80.5785},
    {"N": 15, "numero": "SCE-UTPL-CM-NAC-2025-19",      "contraparte": "UNIVERSIDAD TÉCNICA PARTICULAR DE LOJA",               "tipo": "CONVENIO MARCO",              "fecha": "25/09/2025", "canton": "Loja",                "provincia": "Loja",         "lat": -3.9931, "lon": -79.2042},
    {"N": 16, "numero": "SCE-ELECGALAPAGOS-CM-NAC-2025-20", "contraparte": "EMPRESA ELÉCTRICA GALÁPAGOS",                      "tipo": "CONVENIO MARCO",              "fecha": "02/10/2025", "canton": "San Cristóbal",       "provincia": "Galápagos",    "lat": -0.9167, "lon": -89.6167},
    {"N": 17, "numero": "UPSE-P-081-12-2025-C",          "contraparte": "UNIVERSIDAD PENÍNSULA DE SANTA ELENA",                "tipo": "CONVENIO ESPECÍFICO",         "fecha": "11/11/2025", "canton": "La Libertad",         "provincia": "Santa Elena",  "lat": -2.2333, "lon": -80.9167},
    {"N": 18, "numero": "SCE-ESPAM-CM-NAC-2025-23",      "contraparte": "E. S. POLITÉCNICA AGROPECUARIA DE MANABÍ",            "tipo": "CONVENIO MARCO",              "fecha": "12/11/2025", "canton": "Bolívar (Calceta)",   "provincia": "Manabí",       "lat": -0.8268, "lon": -80.1780},
    {"N": 19, "numero": "SCE-ULEAM-CM-NAC-2025-22",      "contraparte": "UNIVERSIDAD LAICA ELOY ALFARO DE MANABÍ",             "tipo": "CONVENIO MARCO",              "fecha": "13/11/2025", "canton": "Manta",               "provincia": "Manabí",       "lat": -0.9677, "lon": -80.7089},
    {"N": 20, "numero": "SCE-UNEMI-CMNAC-2026-01",       "contraparte": "UNIVERSIDAD ESTATAL DE MILAGRO",                      "tipo": "CONVENIO MARCO",              "fecha": "20/02/2026", "canton": "Milagro",             "provincia": "Guayas",       "lat": -2.1340, "lon": -79.5872},
]

COLOR_PRIMARIO   = "#1A3A5C"
COLOR_SECUNDARIO = "#C8A951"

COLORES_TIPO = {
    "CONVENIO MARCO":              "#1A3A5C",
    "COOPERACIÓN INTERINSTITUCIONAL": "#2E86AB",
    "CONVENIO ESPECÍFICO":         "#C8A951",
}


# ---------------------------------------------------------------------------
# GeoJSON provincias Ecuador
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _cargar_geojson_provincias() -> dict | None:
    """Descarga (con caché) el GeoJSON de provincias del Ecuador."""
    url = (
        "https://raw.githubusercontent.com/angelnmara/geojson/master/"
        "EcuadorProvincias.geojson"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _trazas_provincias(geojson: dict) -> tuple[list, list]:
    """Devuelve (lons, lats) con None como separador entre polígonos."""
    all_lons: list = []
    all_lats: list = []
    for feature in geojson.get("features", []):
        geom = feature.get("geometry", {})
        gtype = geom.get("type", "")
        if gtype == "Polygon":
            anillos = [geom["coordinates"][0]]
        elif gtype == "MultiPolygon":
            anillos = [poly[0] for poly in geom["coordinates"]]
        else:
            continue
        for anillo in anillos:
            all_lons.extend([c[0] for c in anillo] + [None])
            all_lats.extend([c[1] for c in anillo] + [None])
    return all_lons, all_lats


# ---------------------------------------------------------------------------
# Helpers — convenios
# ---------------------------------------------------------------------------

def _df_convenios() -> pd.DataFrame:
    df = pd.DataFrame(CONVENIOS_DATA)
    df["fecha_dt"] = pd.to_datetime(df["fecha"], format="%d/%m/%Y", errors="coerce")
    return df


def _mapa_convenios(df: pd.DataFrame) -> go.Figure:
    """Mapa interactivo con base OpenStreetMap, límites provinciales y puntos por convenio.

    - Usa Scattermapbox (sin token) con estilo open-street-map.
    - Dibuja los polígonos del GeoJSON de provincias como líneas sobre el mapa.
    - Zoom inicial muestra tanto el Ecuador continental como las Galápagos.
    """
    # ---- jitter para separar puntos solapados en la misma ciudad ----------
    df_map = df.copy()
    conteo_loc = df_map.groupby(["lat", "lon"]).cumcount()
    df_map["lat_j"] = df_map["lat"] + conteo_loc * 0.04
    df_map["lon_j"] = df_map["lon"] + conteo_loc * 0.04

    df_map["texto_hover"] = (
        "<b>" + df_map["contraparte"] + "</b><br>"
        + "N°: " + df_map["N"].astype(str) + "<br>"
        + "Convenio: " + df_map["numero"] + "<br>"
        + "Tipo: " + df_map["tipo"] + "<br>"
        + "Cantón: " + df_map["canton"] + "<br>"
        + "Provincia: " + df_map["provincia"] + "<br>"
        + "Fecha: " + df_map["fecha"]
    )

    fig = go.Figure()

    # ---- límites de provincias desde GeoJSON ------------------------------
    geojson = _cargar_geojson_provincias()
    if geojson:
        all_lons, all_lats = _trazas_provincias(geojson)
        fig.add_trace(go.Scattermapbox(
            lon=all_lons,
            lat=all_lats,
            mode="lines",
            line=dict(width=1.2, color="#333333"),
            showlegend=False,
            hoverinfo="skip",
            name="",
        ))

    # ---- puntos por convenio (una traza por tipo) -------------------------
    for tipo, color in COLORES_TIPO.items():
        mask = df_map["tipo"] == tipo
        sub = df_map[mask]
        if sub.empty:
            continue
        fig.add_trace(go.Scattermapbox(
            lon=sub["lon_j"],
            lat=sub["lat_j"],
            mode="markers+text",
            name=tipo,
            marker=go.scattermapbox.Marker(
                size=20,
                color=color,
                opacity=0.90,
            ),
            text=sub["N"].astype(str),
            textfont=dict(size=9, color="white"),
            hovertext=sub["texto_hover"],
            hoverinfo="text",
        ))

    # zoom ~4.5 con centro entre continental y Galápagos para ver ambos
    fig.update_layout(
        title=dict(text="Mapa de Convenios Institucionales — Ecuador", x=0.5),
        mapbox=dict(
            style="open-street-map",
            zoom=4.6,
            center={"lat": -1.8, "lon": -81.5},
        ),
        legend=dict(
            title="Tipo de convenio",
            orientation="v",
            x=0.01, y=0.99,
            bgcolor="rgba(255,255,255,0.90)",
            bordercolor="#CCCCCC",
            borderwidth=1,
        ),
        margin=dict(l=0, r=0, t=45, b=0),
        height=600,
        paper_bgcolor="white",
    )
    return fig


def _grafico_convenios_provincia(df: pd.DataFrame) -> go.Figure:
    conteo = (
        df["provincia"].value_counts()
        .reset_index()
        .rename(columns={"provincia": "Provincia", "count": "Convenios"})
        .sort_values("Convenios", ascending=True)
    )
    fig = px.bar(
        conteo, x="Convenios", y="Provincia", orientation="h",
        title="Convenios por provincia",
        color_discrete_sequence=[COLOR_PRIMARIO],
        text="Convenios",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Cantidad", yaxis_title="",
                      margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white")
    return fig


def _grafico_convenios_tipo(df: pd.DataFrame) -> go.Figure:
    conteo = df["tipo"].value_counts().reset_index()
    conteo.columns = ["Tipo", "Cantidad"]
    fig = px.pie(
        conteo, names="Tipo", values="Cantidad",
        title="Distribución por tipo de convenio",
        color="Tipo",
        color_discrete_map=COLORES_TIPO,
        hole=0.4,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10), showlegend=False)
    return fig


def _grafico_convenios_evolucion(df: pd.DataFrame) -> go.Figure:
    df_e = df.copy()
    df_e["mes"] = df_e["fecha_dt"].dt.to_period("M").astype(str)
    mensual = (
        df_e.groupby("mes").size()
        .reset_index(name="Convenios")
        .sort_values("mes")
    )
    mensual["Acumulado"] = mensual["Convenios"].cumsum()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=mensual["mes"], y=mensual["Convenios"],
        name="Por mes", marker_color=COLOR_PRIMARIO, opacity=0.7,
    ))
    fig.add_trace(go.Scatter(
        x=mensual["mes"], y=mensual["Acumulado"],
        name="Acumulado", mode="lines+markers",
        line=dict(color=COLOR_SECUNDARIO, width=2),
        yaxis="y2",
    ))
    fig.update_layout(
        title="Evolución mensual de convenios",
        xaxis_title="Mes",
        yaxis=dict(title="Nuevos convenios"),
        yaxis2=dict(title="Acumulado", overlaying="y", side="right"),
        legend=dict(orientation="h", x=0, y=1.12),
        margin=dict(l=10, r=10, t=60, b=10),
        plot_bgcolor="white",
        barmode="overlay",
    )
    return fig


# ---------------------------------------------------------------------------
# Datos estáticos — Intendencia Regional Abogacía de la Competencia 2025
# ---------------------------------------------------------------------------

CAPACITACIONES_2025 = [
    {"oficina": "Portoviejo", "numero": 51,  "asistentes": 2050, "encuestados": 1143},
    {"oficina": "Loja",       "numero": 19,  "asistentes": 1005, "encuestados": 341},
    {"oficina": "Cuenca",     "numero": 21,  "asistentes": 1024, "encuestados": 706},
    {"oficina": "Guayaquil",  "numero": 63,  "asistentes": 3037, "encuestados": 513},
]

ASAMBLEAS_2025 = [
    {"oficina": "Portoviejo", "numero": 9,  "asistentes": 287},
    {"oficina": "Loja",       "numero": 9,  "asistentes": 165},
    {"oficina": "Cuenca",     "numero": 11, "asistentes": 120},
    {"oficina": "Guayaquil",  "numero": 9,  "asistentes": 564},
]

CONGRESOS_2025 = [
    {
        "oficina": "Cuenca",
        "tema": "Mercados Justos: Tendencia y Desafíos de la Competencia Económica en la Región",
        "asistentes": 400,
        "fecha": "26 de marzo de 2025",
    },
]

COLORES_OFICINAS_DRAC = {
    "Portoviejo": "#2E86AB",
    "Loja":       "#A23B72",
    "Cuenca":     "#C8A951",
    "Guayaquil":  "#1A3A5C",
}


def _grafico_num_capacitaciones(df: pd.DataFrame) -> go.Figure:
    """Barras simples: número de capacitaciones por oficina."""
    fig = go.Figure(go.Bar(
        x=df["oficina"],
        y=df["numero"],
        marker_color=[COLORES_OFICINAS_DRAC.get(o, COLOR_PRIMARIO) for o in df["oficina"]],
        text=df["numero"],
        textposition="outside",
    ))
    fig.update_layout(
        title="N° de capacitaciones ejecutadas por oficina",
        xaxis_title="Oficina",
        yaxis_title="N° Capacitaciones",
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig


def _grafico_asistentes_encuestados_barras(df: pd.DataFrame) -> go.Figure:
    """Barras agrupadas: asistentes y encuestados por oficina."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Asistentes",
        x=df["oficina"],
        y=df["asistentes"],
        marker_color=COLOR_PRIMARIO,
        text=df["asistentes"],
        textposition="outside",
    ))
    fig.add_trace(go.Bar(
        name="Encuestados",
        x=df["oficina"],
        y=df["encuestados"],
        marker_color=COLOR_SECUNDARIO,
        text=df["encuestados"],
        textposition="outside",
    ))
    fig.update_layout(
        title="Asistentes y encuestados por oficina",
        xaxis_title="Oficina",
        yaxis_title="Personas",
        barmode="group",
        legend=dict(orientation="h", x=0, y=1.1),
        margin=dict(l=10, r=10, t=55, b=10),
        plot_bgcolor="white",
    )
    return fig


def _grafico_distribucion_pie(
    df: pd.DataFrame, columna: str, titulo: str
) -> go.Figure:
    """Donut con porcentaje Y número absoluto visibles."""
    total = df[columna].sum()
    etiquetas = df["oficina"].tolist()
    valores   = df[columna].tolist()
    colores   = [COLORES_OFICINAS_DRAC.get(o, COLOR_PRIMARIO) for o in etiquetas]

    textos_personalizados = [
        f"{v:,}<br>({v/total*100:.1f}%)" for v in valores
    ]

    fig = go.Figure(go.Pie(
        labels=etiquetas,
        values=valores,
        hole=0.45,
        marker_colors=colores,
        text=textos_personalizados,
        textinfo="text+label",
        textposition="inside",
        hovertemplate="<b>%{label}</b><br>%{value:,} personas<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        title=titulo,
        showlegend=False,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def _grafico_num_asambleas(df: pd.DataFrame) -> go.Figure:
    """Barras simples: número de asambleas por oficina."""
    fig = go.Figure(go.Bar(
        x=df["oficina"],
        y=df["numero"],
        marker_color=[COLORES_OFICINAS_DRAC.get(o, COLOR_PRIMARIO) for o in df["oficina"]],
        text=df["numero"],
        textposition="outside",
    ))
    fig.update_layout(
        title="N° de Asambleas Productivas por oficina",
        xaxis_title="Oficina",
        yaxis_title="N° Asambleas",
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig


def _grafico_asistentes_asambleas(df: pd.DataFrame) -> go.Figure:
    """Barras simples: asistentes a asambleas por oficina."""
    fig = go.Figure(go.Bar(
        x=df["oficina"],
        y=df["asistentes"],
        marker_color=[COLORES_OFICINAS_DRAC.get(o, COLOR_SECUNDARIO) for o in df["oficina"]],
        text=df["asistentes"],
        textposition="outside",
    ))
    fig.update_layout(
        title="Asistentes a Asambleas Productivas por oficina",
        xaxis_title="Oficina",
        yaxis_title="Asistentes",
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white",
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def mostrar_dashboard_drac() -> None:
    st.title("📊 Dashboard DRAC")
    st.markdown("**Dirección Regional — Acciones y estadísticas consolidadas**")
    st.divider()

    # ======================================================================
    # SECCIÓN 1 — Encuestas de satisfacción
    # ======================================================================
    st.header("1. Estadísticas de Encuestas de Satisfacción")

    with get_connection() as con:
        from database.db import consultar_capacitaciones
        filas = consultar_capacitaciones(con, oficina=None)

    if filas:
        df_cap = pd.DataFrame([dict(f) for f in filas])
        for col in ETIQUETAS_SATISFACCION.keys():
            if col in df_cap.columns:
                df_cap[col] = pd.to_numeric(df_cap[col], errors="coerce")

        # --- Análisis por provincia e institución (al inicio)
        st.subheader("Análisis por provincia e institución")
        col_prov, col_inst = st.columns(2)
        with col_prov:
            st.plotly_chart(grafico_participantes_provincia(df_cap), use_container_width=True)
        with col_inst:
            st.plotly_chart(grafico_top_instituciones(df_cap), use_container_width=True)

        st.plotly_chart(grafico_evolucion_mensual(df_cap), use_container_width=True)
        st.divider()

    if filas:
        # Métricas rápidas
        cols_sat = [c for c in ETIQUETAS_SATISFACCION.keys() if c in df_cap.columns]
        total_respuestas = df_cap[cols_sat].dropna(how="all").shape[0] if cols_sat else 0
        promedio_global  = (
            df_cap[cols_sat].values.flatten()
        )
        promedio_global = [v for v in promedio_global if pd.notna(v)]
        prom_val = round(sum(promedio_global) / len(promedio_global), 2) if promedio_global else None

        m1, m2, m3 = st.columns(3)
        m1.metric("Total participantes evaluados", f"{total_respuestas:,}")
        m2.metric("Satisfacción promedio global", f"{prom_val:.2f} / 5.00" if prom_val else "Sin datos")
        m3.metric("Dimensiones evaluadas", len(cols_sat))

        col_radar, col_hist = st.columns(2)
        with col_radar:
            st.plotly_chart(grafico_radar_satisfaccion(df_cap), use_container_width=True)
        with col_hist:
            st.plotly_chart(grafico_histograma_satisfaccion(df_cap), use_container_width=True)

        # Tabla resumen por dimensión
        if cols_sat:
            st.markdown("**Resumen por dimensión:**")
            resumen = pd.DataFrame({
                "Dimensión": [ETIQUETAS_SATISFACCION[c] for c in cols_sat],
                "Promedio":  [round(df_cap[c].dropna().astype(float).mean(), 2) for c in cols_sat],
                "Respuestas": [int(df_cap[c].dropna().count()) for c in cols_sat],
            })
            st.dataframe(resumen, use_container_width=True, hide_index=True)
    else:
        st.info("No hay registros de capacitaciones con encuestas de satisfacción cargados.")

    # ======================================================================
    # SECCIÓN 2 — Estadísticas de Convenios
    # ======================================================================
    st.divider()
    st.header("2. Estadísticas de Convenios Institucionales")

    df_conv = _df_convenios()

    # --- Métricas
    total_conv    = len(df_conv)
    n_provincias  = df_conv["provincia"].nunique()
    n_cantones    = df_conv["canton"].nunique()
    n_tipos       = df_conv["tipo"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total convenios",  total_conv)
    c2.metric("Provincias",       n_provincias)
    c3.metric("Cantones",         n_cantones)
    c4.metric("Tipos de convenio", n_tipos)

    # --- Gráficos resumen
    col_prov, col_tipo = st.columns(2)
    with col_prov:
        st.plotly_chart(_grafico_convenios_provincia(df_conv), use_container_width=True)
    with col_tipo:
        st.plotly_chart(_grafico_convenios_tipo(df_conv), use_container_width=True)

    st.plotly_chart(_grafico_convenios_evolucion(df_conv), use_container_width=True)

    # --- Mapa interactivo
    st.subheader("Mapa interactivo — Distribución geográfica de convenios")
    st.caption(
        "Cada punto representa un convenio. Pasa el cursor sobre el punto para ver el detalle. "
        "Los límites de provincias se cargan automáticamente desde el repositorio GeoJSON del Ecuador. "
        "Las Islas Galápagos (~89°W) son visibles en el extremo izquierdo del mapa."
    )

    # Filtros rápidos para el mapa
    fi1, fi2 = st.columns(2)
    with fi1:
        provincias_disponibles = ["Todas"] + sorted(df_conv["provincia"].unique().tolist())
        filtro_prov = st.selectbox("Filtrar por provincia", provincias_disponibles, key="drac_prov")
    with fi2:
        tipos_disponibles = ["Todos"] + sorted(df_conv["tipo"].unique().tolist())
        filtro_tipo = st.selectbox("Filtrar por tipo", tipos_disponibles, key="drac_tipo")

    df_filtrado = df_conv.copy()
    if filtro_prov != "Todas":
        df_filtrado = df_filtrado[df_filtrado["provincia"] == filtro_prov]
    if filtro_tipo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["tipo"] == filtro_tipo]

    st.plotly_chart(_mapa_convenios(df_filtrado), use_container_width=True)

    # --- Tabla de convenios
    st.subheader("Tabla de convenios")
    columnas_tabla = ["N", "numero", "contraparte", "tipo", "fecha", "canton", "provincia"]
    st.dataframe(
        df_filtrado[columnas_tabla].rename(columns={
            "N": "N°",
            "numero": "Número de Convenio",
            "contraparte": "Contraparte",
            "tipo": "Tipo",
            "fecha": "Fecha de suscripción",
            "canton": "Cantón",
            "provincia": "Provincia",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # ======================================================================
    # SECCIÓN 3 — Intendencia Regional Abogacía de la Competencia
    # ======================================================================
    st.divider()
    st.header("3. Estadísticas Intendencia Regional — Abogacía de la Competencia")
    st.caption("Datos consolidados 2025 de las cuatro oficinas regionales.")

    df_cap25 = pd.DataFrame(CAPACITACIONES_2025)
    df_asm25 = pd.DataFrame(ASAMBLEAS_2025)
    df_cong25 = pd.DataFrame(CONGRESOS_2025)

    # --- KPIs globales
    total_cap  = df_cap25["numero"].sum()
    total_asi  = df_cap25["asistentes"].sum()
    total_enc  = df_cap25["encuestados"].sum()
    total_asm  = df_asm25["numero"].sum()
    total_asi_asm = df_asm25["asistentes"].sum()
    total_cong = len(df_cong25)
    total_asi_cong = df_cong25["asistentes"].sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Capacitaciones ejecutadas", f"{total_cap:,}", help="Total nacional 2025")
    k2.metric("Asistentes a capacitaciones", f"{total_asi:,}")
    k3.metric("Encuestados", f"{total_enc:,}")
    k4.metric("Tasa de encuestados", f"{total_enc/total_asi*100:.1f}%")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("Asambleas Productivas", f"{total_asm:,}")
    k6.metric("Asistentes a asambleas", f"{total_asi_asm:,}")
    k7.metric("Congresos Internacionales", f"{total_cong:,}")
    k8.metric("Asistentes a congresos", f"{total_asi_cong:,}")

    # --- Capacitaciones ejecutadas
    st.subheader("Capacitaciones Ejecutadas 2025")

    # Fila 1: N° capacitaciones | asistentes + encuestados agrupados
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.plotly_chart(_grafico_num_capacitaciones(df_cap25), use_container_width=True)
    with col_c2:
        st.plotly_chart(_grafico_asistentes_encuestados_barras(df_cap25), use_container_width=True)

    # Fila 2: donut encuestados | donut asistentes
    col_c3, col_c4 = st.columns(2)
    with col_c3:
        st.plotly_chart(
            _grafico_distribucion_pie(df_cap25, "encuestados", "Distribución de encuestados por oficina"),
            use_container_width=True,
        )
    with col_c4:
        st.plotly_chart(
            _grafico_distribucion_pie(df_cap25, "asistentes", "Distribución de asistentes por oficina"),
            use_container_width=True,
        )

    # Tabla capacitaciones
    df_cap_tabla = df_cap25.copy()
    df_cap_tabla.loc[len(df_cap_tabla)] = {
        "oficina": "TOTAL", "numero": total_cap,
        "asistentes": total_asi, "encuestados": total_enc,
    }
    st.dataframe(
        df_cap_tabla.rename(columns={
            "oficina": "Oficina", "numero": "N° Capacitaciones",
            "asistentes": "Asistentes", "encuestados": "Encuestados",
        }),
        use_container_width=True, hide_index=True,
    )

    # --- Asambleas Productivas
    st.subheader("Asambleas Productivas 2025")

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.plotly_chart(_grafico_num_asambleas(df_asm25), use_container_width=True)
    with col_a2:
        st.plotly_chart(_grafico_asistentes_asambleas(df_asm25), use_container_width=True)

    col_a3, col_a4 = st.columns(2)
    with col_a3:
        st.plotly_chart(
            _grafico_distribucion_pie(df_asm25, "numero", "Distribución de asambleas por oficina"),
            use_container_width=True,
        )
    with col_a4:
        st.plotly_chart(
            _grafico_distribucion_pie(df_asm25, "asistentes", "Distribución de asistentes — Asambleas"),
            use_container_width=True,
        )

    # Tabla asambleas
    df_asm_tabla = df_asm25.copy()
    df_asm_tabla.loc[len(df_asm_tabla)] = {
        "oficina": "TOTAL", "numero": total_asm, "asistentes": total_asi_asm,
    }
    st.dataframe(
        df_asm_tabla.rename(columns={
            "oficina": "Oficina", "numero": "N° Asambleas", "asistentes": "Asistentes",
        }),
        use_container_width=True, hide_index=True,
    )

    # --- Congresos Internacionales
    st.subheader("Congresos Internacionales 2025")
    st.dataframe(
        df_cong25.rename(columns={
            "oficina": "Oficina", "tema": "Tema",
            "asistentes": "Asistentes", "fecha": "Fecha",
        }),
        use_container_width=True, hide_index=True,
    )
