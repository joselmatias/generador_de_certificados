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

CAPACITACIONES_EXPOSITORES_RAW = [
    # ENERO
    {"mes": "Enero",      "fecha": "14/01/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "XAVIER GALARZA"]},
    {"mes": "Enero",      "fecha": "20/01/2025", "oficina": "Cuenca",     "expositores": ["MARIA MOROCHO", "ANGEL PEREZ"]},
    {"mes": "Enero",      "fecha": "21/01/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA"]},
    {"mes": "Enero",      "fecha": "21/01/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    {"mes": "Enero",      "fecha": "27/01/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    {"mes": "Enero",      "fecha": "30/01/2025", "oficina": "Cuenca",     "expositores": ["MARIA MOROCHO", "ANGEL PEREZ"]},
    {"mes": "Enero",      "fecha": "30/01/2025", "oficina": "Portoviejo", "expositores": ["GEOCONDA VERA", "CRISTIAN ROMERO"]},
    # FEBRERO
    {"mes": "Febrero",    "fecha": "01/02/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    {"mes": "Febrero",    "fecha": "18/02/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    {"mes": "Febrero",    "fecha": "19/02/2025", "oficina": "Portoviejo", "expositores": ["XAVIER GALARZA"]},
    {"mes": "Febrero",    "fecha": "21/02/2025", "oficina": "Guayaquil",  "expositores": ["ALEJANDRA MURILLO", "CARLOS GARCIA"]},
    {"mes": "Febrero",    "fecha": "24/02/2025", "oficina": "Loja",       "expositores": ["KARLA MONCADA"]},
    {"mes": "Febrero",    "fecha": "27/02/2025", "oficina": "Loja",       "expositores": ["KARLA MONCADA"]},
    # MARZO
    {"mes": "Marzo",      "fecha": "01/03/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "XAVIER GALARZA"]},
    {"mes": "Marzo",      "fecha": "11/03/2025", "oficina": "Cuenca",     "expositores": ["MARIA MOROCHO", "ANGEL PEREZ"]},
    {"mes": "Marzo",      "fecha": "17/03/2025", "oficina": "Portoviejo", "expositores": ["XAVIER GALARZA"]},
    {"mes": "Marzo",      "fecha": "24/03/2025", "oficina": "Portoviejo", "expositores": ["XAVIER GALARZA"]},
    {"mes": "Marzo",      "fecha": "26/03/2025", "oficina": "Cuenca",     "expositores": ["VARIOS PONENTES"]},
    {"mes": "Marzo",      "fecha": "27/03/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    {"mes": "Marzo",      "fecha": "28/03/2025", "oficina": "Guayaquil",  "expositores": ["ALEJANDRA MURILLO", "CARLOS GARCIA"]},
    {"mes": "Marzo",      "fecha": "31/03/2025", "oficina": "Guayaquil",  "expositores": ["ALEJANDRA MURILLO", "CARLOS GARCIA"]},
    # ABRIL
    {"mes": "Abril",      "fecha": "02/04/2025", "oficina": "Guayaquil",  "expositores": ["ALEJANDRA MURILLO", "CARLOS GARCIA"]},
    {"mes": "Abril",      "fecha": "11/04/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    {"mes": "Abril",      "fecha": "22/04/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    {"mes": "Abril",      "fecha": "23/04/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    {"mes": "Abril",      "fecha": "23/04/2025", "oficina": "Cuenca",     "expositores": ["ANGEL PEREZ", "MARIA MOROCHO"]},
    {"mes": "Abril",      "fecha": "23/04/2025", "oficina": "Cuenca",     "expositores": ["ANGEL PEREZ", "MARIA MOROCHO"]},
    {"mes": "Abril",      "fecha": "25/04/2025", "oficina": "Cuenca",     "expositores": ["ANGEL PEREZ", "MARIA MOROCHO"]},
    {"mes": "Abril",      "fecha": "30/04/2025", "oficina": "Guayaquil",  "expositores": ["ALEJANDRA MURILLO", "CARLOS GARCIA"]},
    {"mes": "Abril",      "fecha": "30/04/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    # MAYO
    {"mes": "Mayo",       "fecha": "15/05/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA", "CARLOS GARCIA"]},
    {"mes": "Mayo",       "fecha": "19/05/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "XAVIER GALARZA"]},
    {"mes": "Mayo",       "fecha": "21/05/2025", "oficina": "Cuenca",     "expositores": ["ANGEL PEREZ", "MARIA MOROCHO"]},
    {"mes": "Mayo",       "fecha": "21/05/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO", "XAVIER GALARZA"]},
    {"mes": "Mayo",       "fecha": "22/05/2025", "oficina": "Cuenca",     "expositores": ["ANGEL PEREZ", "MARIA MOROCHO"]},
    {"mes": "Mayo",       "fecha": "22/05/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "RICHARD ALVARADO", "XAVIER GALARZA"]},
    {"mes": "Mayo",       "fecha": "22/05/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "RICHARD ALVARADO", "XAVIER GALARZA"]},
    {"mes": "Mayo",       "fecha": "28/05/2025", "oficina": "Loja",       "expositores": ["SALOME ROSALES"]},
    # JUNIO
    {"mes": "Junio",      "fecha": "03/06/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Junio",      "fecha": "10/06/2025", "oficina": "Portoviejo", "expositores": ["RICHARD ALVARADO", "ALEJANDRA MURILLO", "XAVIER GALARZA"]},
    {"mes": "Junio",      "fecha": "18/06/2025", "oficina": "Portoviejo", "expositores": ["RICHARD ALVARADO", "ALEJANDRA MURILLO"]},
    {"mes": "Junio",      "fecha": "25/06/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA", "CARLOS GARCIA"]},
    {"mes": "Junio",      "fecha": "25/06/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA", "CARLOS GARCIA"]},
    {"mes": "Junio",      "fecha": "26/06/2025", "oficina": "Cuenca",     "expositores": ["ROSA MORALES"]},
    {"mes": "Junio",      "fecha": "27/06/2025", "oficina": "Loja",       "expositores": ["SALOME ROSALES"]},
    {"mes": "Junio",      "fecha": "30/06/2025", "oficina": "Cuenca",     "expositores": ["ROSA MORALES"]},
    # JULIO
    {"mes": "Julio",      "fecha": "01/07/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA"]},
    {"mes": "Julio",      "fecha": "04/07/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Julio",      "fecha": "10/07/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Julio",      "fecha": "11/07/2025", "oficina": "Cuenca",     "expositores": ["ROSA MORALES", "ANGEL PEREZ"]},
    {"mes": "Julio",      "fecha": "14/07/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    {"mes": "Julio",      "fecha": "14/07/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA", "MARICELA LOAYZA", "ROBERTO SANTOS"]},
    {"mes": "Julio",      "fecha": "14/07/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA"]},
    {"mes": "Julio",      "fecha": "15/07/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA", "CRISTIAN ROMERO"]},
    {"mes": "Julio",      "fecha": "16/07/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA", "CRISTIAN ROMERO"]},
    {"mes": "Julio",      "fecha": "16/07/2025", "oficina": "Cuenca",     "expositores": ["ROSA MORALES", "ANGEL PEREZ"]},
    {"mes": "Julio",      "fecha": "18/07/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "ALEXANDRA SILVA"]},
    {"mes": "Julio",      "fecha": "22/07/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ"]},
    {"mes": "Julio",      "fecha": "30/07/2025", "oficina": "Loja",       "expositores": ["SALOME ROSALES"]},
    # AGOSTO
    {"mes": "Agosto",     "fecha": "01/08/2025", "oficina": "Guayaquil",  "expositores": ["ROBERTO SANTOS", "CARLOS GARCIA", "ALEXANDRA SILVA"]},
    {"mes": "Agosto",     "fecha": "02/08/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Agosto",     "fecha": "05/08/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Agosto",     "fecha": "05/08/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO", "XAVIER GALARZA"]},
    {"mes": "Agosto",     "fecha": "06/08/2025", "oficina": "Loja",       "expositores": ["CARLOS GARCIA"]},
    {"mes": "Agosto",     "fecha": "12/08/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "ALEXANDRA SILVA"]},
    {"mes": "Agosto",     "fecha": "14/08/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Agosto",     "fecha": "15/08/2025", "oficina": "Cuenca",     "expositores": ["MARIA MOROCHO", "ANGEL PEREZ"]},
    {"mes": "Agosto",     "fecha": "16/08/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA", "CRISTIAN ROMERO"]},
    {"mes": "Agosto",     "fecha": "16/08/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA", "CRISTIAN ROMERO"]},
    {"mes": "Agosto",     "fecha": "17/08/2025", "oficina": "Portoviejo", "expositores": ["MARIO NARANJO", "ALEJANDRA MURILLO"]},
    {"mes": "Agosto",     "fecha": "18/08/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA", "CRISTIAN ROMERO"]},
    {"mes": "Agosto",     "fecha": "18/08/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA"]},
    {"mes": "Agosto",     "fecha": "19/08/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "MILKA NAZARENO"]},
    {"mes": "Agosto",     "fecha": "19/08/2025", "oficina": "Loja",       "expositores": ["SALOME ROSALES", "KARLA MONCADA"]},
    {"mes": "Agosto",     "fecha": "20/08/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Agosto",     "fecha": "21/08/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Agosto",     "fecha": "22/08/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "ALEXANDRA SILVA"]},
    {"mes": "Agosto",     "fecha": "25/08/2025", "oficina": "Cuenca",     "expositores": ["MARIA MOROCHO"]},
    {"mes": "Agosto",     "fecha": "25/08/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Agosto",     "fecha": "26/08/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Agosto",     "fecha": "26/08/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"mes": "Agosto",     "fecha": "26/08/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"mes": "Agosto",     "fecha": "27/08/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "ALEXANDRA SILVA"]},
    # SEPTIEMBRE
    {"mes": "Septiembre", "fecha": "10/09/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Septiembre", "fecha": "10/09/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA"]},
    {"mes": "Septiembre", "fecha": "11/09/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"mes": "Septiembre", "fecha": "12/09/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"mes": "Septiembre", "fecha": "12/09/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Septiembre", "fecha": "13/09/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"mes": "Septiembre", "fecha": "15/09/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "ALEXANDRA SILVA"]},
    {"mes": "Septiembre", "fecha": "16/09/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA"]},
    {"mes": "Septiembre", "fecha": "17/09/2025", "oficina": "Guayaquil",  "expositores": ["ROBERTO SANTOS", "DAVID SEGOVIA"]},
    {"mes": "Septiembre", "fecha": "18/09/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "MILKA NAZARENO"]},
    {"mes": "Septiembre", "fecha": "18/09/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "MILKA NAZARENO"]},
    {"mes": "Septiembre", "fecha": "19/09/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "XAVIER GALARZA"]},
    {"mes": "Septiembre", "fecha": "22/09/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    {"mes": "Septiembre", "fecha": "26/09/2025", "oficina": "Cuenca",     "expositores": ["ROSA MORALES", "MARIA MOROCHO"]},
    {"mes": "Septiembre", "fecha": "26/09/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Septiembre", "fecha": "29/09/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Septiembre", "fecha": "30/09/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    # OCTUBRE
    {"mes": "Octubre",    "fecha": "02/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "03/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "06/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "07/10/2025", "oficina": "Cuenca",     "expositores": ["ROSA MORALES", "MARIA MOROCHO"]},
    {"mes": "Octubre",    "fecha": "07/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "08/10/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"mes": "Octubre",    "fecha": "13/10/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"mes": "Octubre",    "fecha": "13/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Octubre",    "fecha": "14/10/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "15/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "16/10/2025", "oficina": "Loja",       "expositores": ["DAVID SEGOVIA", "ROBERTO SANTOS", "MARICELA LOAYZA"]},
    {"mes": "Octubre",    "fecha": "20/10/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Octubre",    "fecha": "20/10/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "21/10/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "MILKA NAZARENO"]},
    {"mes": "Octubre",    "fecha": "21/10/2025", "oficina": "Cuenca",     "expositores": ["ROBERTO SANTOS", "ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "23/10/2025", "oficina": "Cuenca",     "expositores": ["MARIA MOROCHO", "ANGEL PEREZ"]},
    {"mes": "Octubre",    "fecha": "23/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Octubre",    "fecha": "24/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Octubre",    "fecha": "24/10/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    {"mes": "Octubre",    "fecha": "27/10/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "28/10/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA"]},
    {"mes": "Octubre",    "fecha": "29/10/2025", "oficina": "Cuenca",     "expositores": ["ROBERTO SANTOS", "CARLOS GARCIA"]},
    {"mes": "Octubre",    "fecha": "30/10/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    # NOVIEMBRE
    {"mes": "Noviembre",  "fecha": "05/11/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO"]},
    {"mes": "Noviembre",  "fecha": "10/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Noviembre",  "fecha": "10/11/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA", "ROBERTO SANTOS", "MARICELA LOAYZA"]},
    {"mes": "Noviembre",  "fecha": "13/11/2025", "oficina": "Portoviejo", "expositores": ["DAVID SEGOVIA"]},
    {"mes": "Noviembre",  "fecha": "14/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA"]},
    {"mes": "Noviembre",  "fecha": "19/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Noviembre",  "fecha": "20/11/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    {"mes": "Noviembre",  "fecha": "20/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Noviembre",  "fecha": "21/11/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA", "MILKA NAZARENO"]},
    {"mes": "Noviembre",  "fecha": "21/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Noviembre",  "fecha": "21/11/2025", "oficina": "Portoviejo", "expositores": ["NAZRE MURGUEITO"]},
    {"mes": "Noviembre",  "fecha": "24/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Noviembre",  "fecha": "26/11/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Noviembre",  "fecha": "27/11/2025", "oficina": "Cuenca",     "expositores": ["ROBERTO SANTOS", "MARIA SILVA"]},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Loja",       "expositores": ["KARLA MONCADA", "ANAHI LOPEZ"]},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    # DICIEMBRE
    {"mes": "Diciembre",  "fecha": "06/12/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Diciembre",  "fecha": "08/12/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Diciembre",  "fecha": "11/12/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "SALOME ROSALES"]},
    {"mes": "Diciembre",  "fecha": "11/12/2025", "oficina": "Loja",       "expositores": ["ANAHI LOPEZ", "SALOME ROSALES"]},
    {"mes": "Diciembre",  "fecha": "11/12/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA"]},
    {"mes": "Diciembre",  "fecha": "12/12/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA"]},
    {"mes": "Diciembre",  "fecha": "12/12/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Diciembre",  "fecha": "15/12/2025", "oficina": "Guayaquil",  "expositores": ["CARLOS GARCIA"]},
    {"mes": "Diciembre",  "fecha": "17/12/2025", "oficina": "Portoviejo", "expositores": ["ALEJANDRA MURILLO"]},
    {"mes": "Diciembre",  "fecha": "18/12/2025", "oficina": "Portoviejo", "expositores": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"mes": "Diciembre",  "fecha": "18/12/2025", "oficina": "Guayaquil",  "expositores": ["ALEXANDRA SILVA", "ROBERTO SANTOS", "MARICELA LOAYZA", "CARLOS VEINTEMILLA"]},
    {"mes": "Diciembre",  "fecha": "18/12/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO"]},
    {"mes": "Diciembre",  "fecha": "19/12/2025", "oficina": "Guayaquil",  "expositores": ["MILKA NAZARENO", "ALEXANDRA SILVA", "CARLOS GARCIA"]},
    {"mes": "Diciembre",  "fecha": "20/12/2025", "oficina": "Cuenca",     "expositores": ["ROSA MORALES", "ANGEL PEREZ"]},
]

ASAMBLEAS_RESPONSABLES_RAW = [
    {"numero": "001", "oficina": "Portoviejo", "responsables": ["CRISTIAN ROMERO"]},
    {"numero": "002", "oficina": "Loja",       "responsables": ["KARLA MONCADA", "ANAHI LOPEZ"]},
    {"numero": "003", "oficina": "Guayaquil",  "responsables": ["ALEJANDRA MURILLO", "CARLOS GARCÍA"]},
    {"numero": "004", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "005", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "006", "oficina": "Loja",       "responsables": ["SALOME ROSALES"]},
    {"numero": "007", "oficina": "Guayaquil",  "responsables": ["ALEXANDRA SILVA", "CARLOS GARCÍA"]},
    {"numero": "008", "oficina": "Portoviejo", "responsables": ["CRISTIAN ROMERO", "XAVIER GALARZA"]},
    {"numero": "009", "oficina": "Loja",       "responsables": ["KARLA MONCADA"]},
    {"numero": "010", "oficina": "Portoviejo", "responsables": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"numero": "011", "oficina": "Guayaquil",  "responsables": ["ALEXANDRA SILVA", "CARLOS GARCÍA"]},
    {"numero": "012", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "013", "oficina": "Portoviejo", "responsables": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"numero": "014", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "015", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "016", "oficina": "Guayaquil",  "responsables": ["MILKA NAZARENO"]},
    {"numero": "017", "oficina": "Loja",       "responsables": ["KARLA MONCADA", "SALOME ROSALES"]},
    {"numero": "018", "oficina": "Guayaquil",  "responsables": ["MILKA NAZARENO"]},
    {"numero": "019", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "020", "oficina": "Loja",       "responsables": ["KARLA MONCADA", "SALOME ROSALES"]},
    {"numero": "021", "oficina": "Portoviejo", "responsables": ["CRISTIAN ROMERO", "ALEJANDRA MURILLO"]},
    {"numero": "022", "oficina": "Guayaquil",  "responsables": ["MILKA NAZARENO"]},
    {"numero": "023", "oficina": "Portoviejo", "responsables": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"numero": "024", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "025", "oficina": "Loja",       "responsables": ["KARLA MONCADA"]},
    {"numero": "026", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO", "ANGEL PEREZ"]},
    {"numero": "027", "oficina": "Loja",       "responsables": ["ANAHI LOPEZ", "KARLA MONCADA"]},
    {"numero": "028", "oficina": "Guayaquil",  "responsables": ["MILKA NAZARENO"]},
    {"numero": "029", "oficina": "Portoviejo", "responsables": ["ALEJANDRA MURILLO"]},
    {"numero": "030", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "031", "oficina": "Guayaquil",  "responsables": ["MILKA NAZARENO"]},
    {"numero": "032", "oficina": "Portoviejo", "responsables": ["ALEJANDRA MURILLO", "CRISTIAN ROMERO"]},
    {"numero": "033", "oficina": "Loja",       "responsables": ["KARLA MONCADA"]},
    {"numero": "034", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "035", "oficina": "Guayaquil",  "responsables": ["MILKA NAZARENO"]},
    {"numero": "036", "oficina": "Portoviejo", "responsables": ["ALEJANDRA MURILLO"]},
    {"numero": "037", "oficina": "Cuenca",     "responsables": ["MARIA MOROCHO"]},
    {"numero": "038", "oficina": "Loja",       "responsables": ["KARLA MONCADA"]},
]

COLORES_OFICINAS_DRAC = {
    "Portoviejo": "#2E86AB",
    "Loja":       "#A23B72",
    "Cuenca":     "#C8A951",
    "Guayaquil":  "#1A3A5C",
}

# ---------------------------------------------------------------------------
# Datos estáticos — Incidencia geográfica de capacitaciones 2025 (por provincia)
# ---------------------------------------------------------------------------

CAPACITACIONES_PROVINCIAS_RAW = [
    # ENERO
    {"mes": "Enero",      "fecha": "14/01/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Enero",      "fecha": "20/01/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Enero",      "fecha": "21/01/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Enero",      "fecha": "21/01/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Enero",      "fecha": "27/01/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Enero",      "fecha": "30/01/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Enero",      "fecha": "30/01/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    # FEBRERO
    {"mes": "Febrero",    "fecha": "01/02/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Febrero",    "fecha": "18/02/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Febrero",    "fecha": "19/02/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Febrero",    "fecha": "21/02/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Febrero",    "fecha": "24/02/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Febrero",    "fecha": "27/02/2025", "oficina": "Loja",       "provincia": "Loja"},
    # MARZO
    {"mes": "Marzo",      "fecha": "01/03/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Marzo",      "fecha": "11/03/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Marzo",      "fecha": "17/03/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Marzo",      "fecha": "24/03/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Marzo",      "fecha": "26/03/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Marzo",      "fecha": "27/03/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Marzo",      "fecha": "28/03/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Marzo",      "fecha": "31/03/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    # ABRIL
    {"mes": "Abril",      "fecha": "02/04/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Abril",      "fecha": "11/04/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Abril",      "fecha": "22/04/2025", "oficina": "Loja",       "provincia": "Zamora Chinchipe"},
    {"mes": "Abril",      "fecha": "23/04/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Abril",      "fecha": "23/04/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Abril",      "fecha": "23/04/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Abril",      "fecha": "25/04/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Abril",      "fecha": "30/04/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Abril",      "fecha": "30/04/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    # MAYO
    {"mes": "Mayo",       "fecha": "15/05/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Mayo",       "fecha": "19/05/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Mayo",       "fecha": "21/05/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Mayo",       "fecha": "21/05/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Mayo",       "fecha": "22/05/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Mayo",       "fecha": "22/05/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Mayo",       "fecha": "22/05/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Mayo",       "fecha": "28/05/2025", "oficina": "Loja",       "provincia": "Loja"},
    # JUNIO
    {"mes": "Junio",      "fecha": "03/06/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Junio",      "fecha": "10/06/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Junio",      "fecha": "18/06/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Junio",      "fecha": "25/06/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Junio",      "fecha": "25/06/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Junio",      "fecha": "26/06/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Junio",      "fecha": "27/06/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Junio",      "fecha": "30/06/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    # JULIO
    {"mes": "Julio",      "fecha": "01/07/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Julio",      "fecha": "04/07/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Julio",      "fecha": "10/07/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Julio",      "fecha": "11/07/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Julio",      "fecha": "14/07/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Julio",      "fecha": "14/07/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Julio",      "fecha": "14/07/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Julio",      "fecha": "15/07/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Julio",      "fecha": "16/07/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Julio",      "fecha": "16/07/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Julio",      "fecha": "18/07/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Julio",      "fecha": "22/07/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Julio",      "fecha": "30/07/2025", "oficina": "Loja",       "provincia": "Loja"},
    # AGOSTO
    {"mes": "Agosto",     "fecha": "01/08/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Agosto",     "fecha": "02/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "05/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "05/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "06/08/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Agosto",     "fecha": "12/08/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Agosto",     "fecha": "14/08/2025", "oficina": "Guayaquil",  "provincia": "Los Ríos"},
    {"mes": "Agosto",     "fecha": "15/08/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Agosto",     "fecha": "16/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "16/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "17/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "18/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "18/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "19/08/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Agosto",     "fecha": "19/08/2025", "oficina": "Loja",       "provincia": "El Oro"},
    {"mes": "Agosto",     "fecha": "20/08/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Agosto",     "fecha": "21/08/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Agosto",     "fecha": "22/08/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Agosto",     "fecha": "25/08/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Agosto",     "fecha": "25/08/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Agosto",     "fecha": "26/08/2025", "oficina": "Guayaquil",  "provincia": "Bolívar"},
    {"mes": "Agosto",     "fecha": "26/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "26/08/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Agosto",     "fecha": "27/08/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    # SEPTIEMBRE
    {"mes": "Septiembre", "fecha": "10/09/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Septiembre", "fecha": "10/09/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Septiembre", "fecha": "11/09/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Septiembre", "fecha": "12/09/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Septiembre", "fecha": "13/09/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Septiembre", "fecha": "12/09/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Septiembre", "fecha": "15/09/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Septiembre", "fecha": "16/09/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Septiembre", "fecha": "17/09/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Septiembre", "fecha": "18/09/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Septiembre", "fecha": "18/09/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Septiembre", "fecha": "19/09/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Septiembre", "fecha": "22/09/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Septiembre", "fecha": "26/09/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Septiembre", "fecha": "26/09/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Septiembre", "fecha": "29/09/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Septiembre", "fecha": "30/09/2025", "oficina": "Loja",       "provincia": "Loja"},
    # OCTUBRE
    {"mes": "Octubre",    "fecha": "02/10/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Octubre",    "fecha": "03/10/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Octubre",    "fecha": "06/10/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Octubre",    "fecha": "07/10/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Octubre",    "fecha": "07/10/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Octubre",    "fecha": "08/10/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Octubre",    "fecha": "13/10/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Octubre",    "fecha": "13/10/2025", "oficina": "Guayaquil",  "provincia": "Bolívar"},
    {"mes": "Octubre",    "fecha": "14/10/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Octubre",    "fecha": "15/10/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Octubre",    "fecha": "16/10/2025", "oficina": "Loja",       "provincia": "El Oro"},
    {"mes": "Octubre",    "fecha": "20/10/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Octubre",    "fecha": "20/10/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Octubre",    "fecha": "21/10/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Octubre",    "fecha": "21/10/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Octubre",    "fecha": "23/10/2025", "oficina": "Cuenca",     "provincia": "Cañar"},
    {"mes": "Octubre",    "fecha": "23/10/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Octubre",    "fecha": "24/10/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Octubre",    "fecha": "24/10/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Octubre",    "fecha": "27/10/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Octubre",    "fecha": "28/10/2025", "oficina": "Guayaquil",  "provincia": "Santa Elena"},
    {"mes": "Octubre",    "fecha": "29/10/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Octubre",    "fecha": "30/10/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    # NOVIEMBRE
    {"mes": "Noviembre",  "fecha": "05/11/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Noviembre",  "fecha": "10/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "10/11/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Noviembre",  "fecha": "13/11/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Noviembre",  "fecha": "14/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "19/11/2025", "oficina": "Guayaquil",  "provincia": "Bolívar"},
    {"mes": "Noviembre",  "fecha": "20/11/2025", "oficina": "Loja",       "provincia": "Zamora Chinchipe"},
    {"mes": "Noviembre",  "fecha": "20/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "21/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "21/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "21/11/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Noviembre",  "fecha": "24/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "26/11/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Noviembre",  "fecha": "27/11/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Noviembre",  "fecha": "28/11/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    # DICIEMBRE
    {"mes": "Diciembre",  "fecha": "06/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "08/12/2025", "oficina": "Guayaquil",  "provincia": "Los Ríos"},
    {"mes": "Diciembre",  "fecha": "11/12/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Diciembre",  "fecha": "11/12/2025", "oficina": "Loja",       "provincia": "Loja"},
    {"mes": "Diciembre",  "fecha": "11/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "12/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "12/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "15/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "17/12/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Diciembre",  "fecha": "18/12/2025", "oficina": "Portoviejo", "provincia": "Manabí"},
    {"mes": "Diciembre",  "fecha": "18/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "18/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "19/12/2025", "oficina": "Guayaquil",  "provincia": "Guayas"},
    {"mes": "Diciembre",  "fecha": "20/12/2025", "oficina": "Cuenca",     "provincia": "Azuay"},
]

# Normalización de nombres de provincia (cubre variantes con/sin tilde y ciudad→provincia)
_PROV_NORM: dict[str, str] = {
    "manabi":             "Manabí",
    "manabí":             "Manabí",
    "azuay":              "Azuay",
    "guayas":             "Guayas",
    "santa elena":        "Santa Elena",
    "loja":               "Loja",
    "zamora":             "Zamora Chinchipe",
    "zamora chinchipe":   "Zamora Chinchipe",
    "los ríos":           "Los Ríos",
    "los rios":           "Los Ríos",
    "el oro":             "El Oro",
    "bolívar":            "Bolívar",
    "bolivar":            "Bolívar",
    "cañar":              "Cañar",
    "canar":              "Cañar",
    "cuenca":             "Azuay",   # ciudad → provincia
}

# Coordenadas aproximadas del centroide de cada provincia (lat, lon)
_COORDS_PROVINCIAS_CAP: dict[str, tuple[float, float]] = {
    "Manabí":           (-1.05,  -80.45),
    "Azuay":            (-2.90,  -79.00),
    "Guayas":           (-2.19,  -79.89),
    "Santa Elena":      (-2.23,  -80.92),
    "Loja":             (-3.99,  -79.20),
    "Zamora Chinchipe": (-4.07,  -78.95),
    "Los Ríos":         (-1.80,  -79.50),
    "El Oro":           (-3.26,  -79.96),
    "Bolívar":          (-1.60,  -79.00),
    "Cañar":            (-2.56,  -78.94),
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


def _df_responsables_detalle() -> pd.DataFrame:
    """DataFrame expandido: una fila por (asamblea, responsable, oficina)."""
    filas = []
    for r in ASAMBLEAS_RESPONSABLES_RAW:
        for resp in r["responsables"]:
            filas.append({
                "numero":      r["numero"],
                "oficina":     r["oficina"].strip().title(),
                "responsable": resp.strip().upper(),
            })
    return pd.DataFrame(filas)


def _conteo_responsables() -> pd.DataFrame:
    """Total de asambleas por responsable (participaciones individuales)."""
    df = _df_responsables_detalle()
    return (
        df.groupby("responsable").size()
        .reset_index(name="Asambleas")
        .sort_values("Asambleas", ascending=True)
        .rename(columns={"responsable": "Responsable"})
    )


def _grafico_responsables_asambleas() -> go.Figure:
    """Barras horizontales: total de asambleas por responsable."""
    df = _conteo_responsables()
    fig = go.Figure(go.Bar(
        y=df["Responsable"],
        x=df["Asambleas"],
        orientation="h",
        marker_color=COLOR_PRIMARIO,
        text=df["Asambleas"],
        textposition="outside",
    ))
    fig.update_layout(
        title="Participaciones por responsable (total nacional)",
        xaxis_title="N° Asambleas",
        yaxis_title="",
        margin=dict(l=10, r=40, t=50, b=10),
        plot_bgcolor="white",
        showlegend=False,
        height=420,
    )
    return fig


def _grafico_responsables_por_oficina() -> go.Figure:
    """Barras agrupadas: responsables por oficina."""
    df = _df_responsables_detalle()
    pivot = (
        df.groupby(["oficina", "responsable"]).size()
        .reset_index(name="Asambleas")
    )
    oficinas_orden = ["Portoviejo", "Loja", "Cuenca", "Guayaquil"]
    fig = px.bar(
        pivot,
        x="responsable", y="Asambleas",
        color="oficina",
        barmode="group",
        title="Responsables por oficina",
        color_discrete_map={
            "Portoviejo": COLORES_OFICINAS_DRAC["Portoviejo"],
            "Loja":       COLORES_OFICINAS_DRAC["Loja"],
            "Cuenca":     COLORES_OFICINAS_DRAC["Cuenca"],
            "Guayaquil":  COLORES_OFICINAS_DRAC["Guayaquil"],
        },
        category_orders={"oficina": oficinas_orden},
        text="Asambleas",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_title="Responsable",
        yaxis_title="N° Asambleas",
        xaxis_tickangle=-35,
        legend_title="Oficina",
        margin=dict(l=10, r=10, t=55, b=120),
        plot_bgcolor="white",
        height=480,
    )
    return fig


def _grafico_responsables_pie() -> go.Figure:
    """Donut: distribución con número y porcentaje por responsable."""
    df = _conteo_responsables().sort_values("Asambleas", ascending=False)
    total = df["Asambleas"].sum()
    textos = [f"{v}<br>({v/total*100:.1f}%)" for v in df["Asambleas"]]
    fig = go.Figure(go.Pie(
        labels=df["Responsable"],
        values=df["Asambleas"],
        hole=0.42,
        text=textos,
        textinfo="text+label",
        textposition="inside",
        hovertemplate="<b>%{label}</b><br>%{value} asambleas (%{percent})<extra></extra>",
    ))
    fig.update_layout(
        title="Distribución de asambleas por responsable",
        showlegend=False,
        margin=dict(l=10, r=10, t=50, b=10),
        height=420,
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
# Helpers — expositores capacitaciones
# ---------------------------------------------------------------------------

_MESES_ORDEN = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _df_expositores_detalle() -> pd.DataFrame:
    """Una fila por (fecha, oficina, expositor)."""
    filas = []
    for r in CAPACITACIONES_EXPOSITORES_RAW:
        for exp in r["expositores"]:
            filas.append({
                "mes":       r["mes"],
                "fecha":     r["fecha"],
                "oficina":   r["oficina"].strip().title(),
                "expositor": exp.strip().upper(),
            })
    return pd.DataFrame(filas)


def _grafico_expositores_total() -> go.Figure:
    """Barras horizontales: participaciones totales por expositor."""
    df = (
        _df_expositores_detalle()
        .groupby("expositor").size()
        .reset_index(name="Capacitaciones")
        .sort_values("Capacitaciones", ascending=True)
    )
    fig = go.Figure(go.Bar(
        y=df["expositor"], x=df["Capacitaciones"],
        orientation="h",
        marker_color=COLOR_PRIMARIO,
        text=df["Capacitaciones"], textposition="outside",
    ))
    fig.update_layout(
        title="Participaciones por expositor (total nacional)",
        xaxis_title="N° Capacitaciones", yaxis_title="",
        margin=dict(l=10, r=40, t=50, b=10),
        plot_bgcolor="white", showlegend=False, height=500,
    )
    return fig


def _grafico_expositores_por_oficina() -> go.Figure:
    """Barras agrupadas: expositores por oficina (top expositores internos)."""
    df = _df_expositores_detalle()
    # Solo expositores con > 1 participación para no saturar el gráfico
    conteo_total = df.groupby("expositor").size()
    top_exp = conteo_total[conteo_total > 1].index
    df_top = df[df["expositor"].isin(top_exp)]

    pivot = (
        df_top.groupby(["oficina", "expositor"]).size()
        .reset_index(name="Capacitaciones")
    )
    fig = px.bar(
        pivot, x="expositor", y="Capacitaciones", color="oficina",
        barmode="group", title="Expositores por oficina",
        color_discrete_map={
            "Portoviejo": COLORES_OFICINAS_DRAC["Portoviejo"],
            "Loja":       COLORES_OFICINAS_DRAC["Loja"],
            "Cuenca":     COLORES_OFICINAS_DRAC["Cuenca"],
            "Guayaquil":  COLORES_OFICINAS_DRAC["Guayaquil"],
        },
        text="Capacitaciones",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_title="Expositor", yaxis_title="N° Capacitaciones",
        xaxis_tickangle=-40, legend_title="Oficina",
        margin=dict(l=10, r=10, t=55, b=140),
        plot_bgcolor="white", height=520,
    )
    return fig


def _df_cap_provincias(meses: list[str] | None = None) -> pd.DataFrame:
    """Conteo de capacitaciones por provincia (con normalización de nombres).

    Args:
        meses: Lista de nombres de mes para filtrar. None = todos.

    Returns:
        DataFrame con columnas ['provincia', 'Capacitaciones'] ordenado descendente.
    """
    provincias = []
    for r in CAPACITACIONES_PROVINCIAS_RAW:
        if meses and r["mes"] not in meses:
            continue
        prov_key = r["provincia"].strip().lower()
        prov = _PROV_NORM.get(prov_key, r["provincia"].strip().title())
        provincias.append(prov)

    if not provincias:
        return pd.DataFrame(columns=["provincia", "Capacitaciones"])

    return (
        pd.Series(provincias, name="provincia")
        .value_counts()
        .reset_index()
        .rename(columns={"count": "Capacitaciones"})
        .sort_values("Capacitaciones", ascending=False)
        .reset_index(drop=True)
    )


def _mapa_calor_capacitaciones(df: pd.DataFrame) -> go.Figure:
    """Mapa de calor coroplético: incidencia de capacitaciones por provincia.

    Usa Choroplethmapbox para colorear las provincias según el conteo,
    con etiquetas numéricas sobre cada provincia.
    Similar a _mapa_convenios pero con escala de color continua.
    """
    geojson = _cargar_geojson_provincias()
    fig = go.Figure()

    # ---- Capa coroplética -------------------------------------------------
    if geojson and not df.empty:
        # Detectar la clave de nombre de provincia en el GeoJSON
        clave_geojson = None
        for candidata in ["DPA_DESPRO", "NAME_1", "NOM_DEPAR", "NOMBRE_PRO", "name", "NAME"]:
            if (geojson.get("features")
                    and candidata in geojson["features"][0].get("properties", {})):
                clave_geojson = candidata
                break

        if clave_geojson:
            # DPA_DESPRO usa mayúsculas con tildes: "MANABÍ", "AZUAY", etc.
            df_map = df.copy()
            df_map["prov_key"] = df_map["provincia"].str.upper()

            fig.add_trace(go.Choroplethmapbox(
                geojson=geojson,
                locations=df_map["prov_key"],
                z=df_map["Capacitaciones"],
                featureidkey=f"properties.{clave_geojson}",
                colorscale=[
                    [0.00, "#EBF5FB"],
                    [0.15, "#AED6F1"],
                    [0.35, "#5DADE2"],
                    [0.60, "#2471A3"],
                    [0.80, "#1A5276"],
                    [1.00, "#0B1F3A"],
                ],
                colorbar=dict(
                    title=dict(text="Capacitaciones", side="right"),
                    thickness=14,
                    len=0.55,
                    x=1.0,
                ),
                marker_opacity=0.80,
                marker_line_width=1.2,
                marker_line_color="#333333",
                hovertemplate=(
                    "<b>%{location}</b><br>"
                    "Capacitaciones: <b>%{z}</b><extra></extra>"
                ),
                name="Incidencia",
                showscale=True,
            ))
        else:
            # Sin clave coincidente: dibujar bordes provinciales manualmente
            all_lons, all_lats = _trazas_provincias(geojson)
            fig.add_trace(go.Scattermapbox(
                lon=all_lons, lat=all_lats,
                mode="lines",
                line=dict(width=1.2, color="#555555"),
                showlegend=False, hoverinfo="skip", name="",
            ))

    # ---- Etiquetas con el conteo sobre cada provincia ---------------------
    if not df.empty:
        s_lats, s_lons, s_text, s_hover = [], [], [], []
        for _, row in df.iterrows():
            coords = _COORDS_PROVINCIAS_CAP.get(row["provincia"])
            if coords:
                s_lats.append(coords[0])
                s_lons.append(coords[1])
                s_text.append(str(int(row["Capacitaciones"])))
                s_hover.append(
                    f"<b>{row['provincia']}</b><br>"
                    f"Capacitaciones: {int(row['Capacitaciones'])}"
                )

        if s_lats:
            fig.add_trace(go.Scattermapbox(
                lat=s_lats,
                lon=s_lons,
                mode="markers+text",
                marker=go.scattermapbox.Marker(
                    size=28,
                    color=COLOR_SECUNDARIO,
                    opacity=0.85,
                ),
                text=s_text,
                textfont=dict(size=11, color="white"),
                hovertext=s_hover,
                hoverinfo="text",
                showlegend=False,
                name="",
            ))

    fig.update_layout(
        title=dict(
            text="Mapa de Calor — Incidencia de Capacitaciones por Provincia (2025)",
            x=0.5,
        ),
        mapbox=dict(
            style="open-street-map",
            zoom=4.8,
            center={"lat": -2.0, "lon": -79.5},
        ),
        margin=dict(l=0, r=0, t=45, b=0),
        height=600,
        paper_bgcolor="white",
    )
    return fig


def _grafico_expositores_mensual() -> go.Figure:
    """Barras apiladas: capacitaciones por mes y oficina."""
    df = pd.DataFrame(CAPACITACIONES_EXPOSITORES_RAW)
    df["oficina"] = df["oficina"].str.strip().str.title()
    mensual = (
        df.groupby(["mes", "oficina"]).size()
        .reset_index(name="Capacitaciones")
    )
    # Ordenar meses cronológicamente
    cat_mes = pd.CategoricalDtype(categories=_MESES_ORDEN, ordered=True)
    mensual["mes"] = mensual["mes"].astype(cat_mes)
    mensual = mensual.sort_values("mes")

    fig = px.bar(
        mensual, x="mes", y="Capacitaciones", color="oficina",
        barmode="stack", title="Capacitaciones por mes y oficina",
        color_discrete_map={
            "Portoviejo": COLORES_OFICINAS_DRAC["Portoviejo"],
            "Loja":       COLORES_OFICINAS_DRAC["Loja"],
            "Cuenca":     COLORES_OFICINAS_DRAC["Cuenca"],
            "Guayaquil":  COLORES_OFICINAS_DRAC["Guayaquil"],
        },
        text="Capacitaciones",
    )
    fig.update_traces(textposition="inside")
    fig.update_layout(
        xaxis_title="Mes", yaxis_title="N° Capacitaciones",
        legend_title="Oficina",
        margin=dict(l=10, r=10, t=55, b=10),
        plot_bgcolor="white",
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

    # --- Estadísticas por expositor
    st.subheader("Estadísticas por Expositor — Capacitaciones 2025")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.plotly_chart(_grafico_expositores_total(), use_container_width=True)
    with col_e2:
        st.plotly_chart(_grafico_expositores_por_oficina(), use_container_width=True)

    st.plotly_chart(_grafico_expositores_mensual(), use_container_width=True)

    st.markdown("**Detalle — expositor por capacitación:**")
    df_exp_tabla = pd.DataFrame([
        {
            "Mes":        r["mes"],
            "Fecha":      r["fecha"],
            "Oficina":    r["oficina"].strip().title(),
            "Expositor(es)": " / ".join(r["expositores"]),
        }
        for r in CAPACITACIONES_EXPOSITORES_RAW
    ])
    st.dataframe(df_exp_tabla, use_container_width=True, hide_index=True)

    # --- Mapa de calor — distribución geográfica
    st.subheader("Mapa interactivo — Distribución geográfica de capacitaciones")
    st.caption(
        "El mapa muestra la incidencia de capacitaciones por provincia durante 2025. "
        "Las provincias con mayor actividad aparecen en tonos más oscuros. "
        "Los números sobre cada provincia indican el total de capacitaciones realizadas."
    )

    # Filtro por mes
    fi_mes1, fi_mes2 = st.columns([2, 3])
    with fi_mes1:
        meses_filter = st.multiselect(
            "Filtrar por mes",
            options=_MESES_ORDEN,
            default=[],
            placeholder="Todos los meses",
            key="drac_cap_meses",
        )

    meses_sel = meses_filter if meses_filter else None
    df_prov = _df_cap_provincias(meses=meses_sel)

    if not df_prov.empty:
        # KPIs rápidos del mapa
        prov_top = df_prov.iloc[0]
        total_eventos = int(df_prov["Capacitaciones"].sum())
        n_provincias_activas = len(df_prov)

        km1, km2, km3 = st.columns(3)
        km1.metric("Total capacitaciones (período)", total_eventos)
        km2.metric("Provincias con actividad", n_provincias_activas)
        km3.metric(
            "Provincia con mayor incidencia",
            prov_top["provincia"],
            delta=f"{int(prov_top['Capacitaciones'])} capacitaciones",
        )

        st.plotly_chart(_mapa_calor_capacitaciones(df_prov), use_container_width=True)

        # Ranking de provincias
        col_rank, _ = st.columns([1, 1])
        with col_rank:
            fig_rank = go.Figure(go.Bar(
                y=df_prov["provincia"][::-1],
                x=df_prov["Capacitaciones"][::-1],
                orientation="h",
                marker_color=[
                    COLOR_PRIMARIO if i > 0 else COLOR_SECUNDARIO
                    for i in range(len(df_prov) - 1, -1, -1)
                ],
                text=df_prov["Capacitaciones"][::-1],
                textposition="outside",
            ))
            fig_rank.update_layout(
                title="Ranking por provincia",
                xaxis_title="N° Capacitaciones",
                yaxis_title="",
                margin=dict(l=10, r=40, t=45, b=10),
                plot_bgcolor="white",
                showlegend=False,
                height=max(280, len(df_prov) * 40),
            )
            st.plotly_chart(fig_rank, use_container_width=True)
    else:
        st.info("No hay datos para los meses seleccionados.")

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

    # --- Estadísticas por responsable
    st.subheader("Estadísticas por responsable")

    # Fila 1: total nacional | donut
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.plotly_chart(_grafico_responsables_asambleas(), use_container_width=True)
    with col_r2:
        st.plotly_chart(_grafico_responsables_pie(), use_container_width=True)

    # Fila 2: responsables por oficina (ancho completo)
    st.plotly_chart(_grafico_responsables_por_oficina(), use_container_width=True)

    # Tabla detalle con oficina
    st.markdown("**Detalle — responsable y oficina por asamblea:**")
    filas_resp = [
        {
            "N° Reporte":    f"Asamblea Productiva {r['numero']}",
            "Oficina":       r["oficina"].strip().title(),
            "Responsable(s)": " / ".join(r["responsables"]),
        }
        for r in ASAMBLEAS_RESPONSABLES_RAW
    ]
    st.dataframe(pd.DataFrame(filas_resp), use_container_width=True, hide_index=True)

    # --- Congresos Internacionales
    st.subheader("Congresos Internacionales 2025")
    st.dataframe(
        df_cong25.rename(columns={
            "oficina": "Oficina", "tema": "Tema",
            "asistentes": "Asistentes", "fecha": "Fecha",
        }),
        use_container_width=True, hide_index=True,
    )
