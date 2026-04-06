"""
app.py — Punto de entrada principal del Sistema de Gestión de Actividades.

Flujo:
1. Pantalla principal con perfiles de oficinas técnicas.
2. Al seleccionar una oficina, se accede a sus módulos.
"""

import streamlit as st

from database.init_db import init_db


st.set_page_config(
    page_title="Sistema de Gestión — OTRs",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def _inicializar_db() -> None:
    init_db()


_inicializar_db()


# ---------------------------------------------------------------------------
# Oficinas disponibles
# ---------------------------------------------------------------------------
OFICINAS = [
    {
        "id":      "guayaquil",
        "nombre":  "Guayaquil",
        "rol":     "master",
        "icono":   "🏛️",
        "region":  "Costa — Zona 8",
        "detalle": "Oficina principal. Acceso a todos los módulos y dashboard global.",
    },
    {
        "id":      "manabi",
        "nombre":  "Manabí",
        "rol":     "regional",
        "icono":   "🌊",
        "region":  "Costa — Zona 4",
        "detalle": "Oficina técnica regional de Manabí.",
    },
    {
        "id":      "loja",
        "nombre":  "Loja",
        "rol":     "regional",
        "icono":   "🌿",
        "region":  "Sur — Zona 7",
        "detalle": "Oficina técnica regional de Loja.",
    },
    {
        "id":      "cuenca",
        "nombre":  "Cuenca",
        "rol":     "regional",
        "icono":   "⛰️",
        "region":  "Austro — Zona 6",
        "detalle": "Oficina técnica regional de Cuenca.",
    },
]


# ---------------------------------------------------------------------------
# Pantalla principal — selección de oficina
# ---------------------------------------------------------------------------
def mostrar_inicio() -> None:
    st.markdown("## 🏛️ Sistema de Gestión de Actividades")
    st.markdown("#### Oficinas Técnicas Regionales — SCE")
    st.divider()
    st.markdown("**Selecciona tu oficina para continuar:**")
    st.markdown("")

    cols = st.columns(len(OFICINAS), gap="large")

    for col, oficina in zip(cols, OFICINAS):
        with col:
            st.markdown(f"### {oficina['icono']} {oficina['nombre']}")
            st.markdown(f"**{oficina['region']}**")
            st.markdown(oficina["detalle"])
            st.markdown("")
            if st.button(
                f"Ingresar → {oficina['nombre']}",
                key=f"btn_{oficina['id']}",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["oficina_id"]     = oficina["id"]
                st.session_state["oficina_nombre"] = oficina["nombre"]
                st.session_state["oficina_rol"]    = oficina["rol"]
                st.rerun()


# ---------------------------------------------------------------------------
# Si no hay oficina seleccionada, mostrar pantalla principal
# ---------------------------------------------------------------------------
if "oficina_id" not in st.session_state:
    mostrar_inicio()
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar — info de oficina y navegación
# ---------------------------------------------------------------------------
oficina_nombre = st.session_state["oficina_nombre"]
oficina_rol    = st.session_state["oficina_rol"]
es_master      = oficina_rol == "master"

with st.sidebar:
    st.markdown(f"**Oficina:** {oficina_nombre}")
    st.markdown(f"**Rol:** {'Master (todas las oficinas)' if es_master else 'Regional'}")
    st.divider()

    MODULOS_REGIONAL = {
        "📋 Capacitaciones — Carga":         "cap_carga",
        "🎓 Capacitaciones — Certificados":  "cap_certificados",
        "📊 Capacitaciones — Dashboard":     "cap_dashboard",
    }

    MODULOS_MASTER = {
        **MODULOS_REGIONAL,
        "🌐 Dashboard Global": "dashboard_global",
        "📊 Dashboard DRAC":   "dashboard_drac",
    }

    modulos_disponibles = MODULOS_MASTER if es_master else MODULOS_REGIONAL

    st.markdown("### Módulos")
    seleccion = st.radio(
        "Navegar a:",
        options=list(modulos_disponibles.keys()),
        label_visibility="collapsed",
    )

    st.divider()
    if st.button("← Volver al inicio", use_container_width=True, type="secondary"):
        for key in ["oficina_id", "oficina_nombre", "oficina_rol"]:
            st.session_state.pop(key, None)
        st.rerun()


modulo_id = modulos_disponibles[seleccion]


# ---------------------------------------------------------------------------
# Renderizado del módulo seleccionado
# ---------------------------------------------------------------------------
if modulo_id == "cap_carga":
    from modules.capacitaciones.upload import mostrar_carga
    mostrar_carga()

elif modulo_id == "cap_certificados":
    from modules.capacitaciones.certificados import mostrar_certificados
    mostrar_certificados()

elif modulo_id == "cap_dashboard":
    from modules.capacitaciones.dashboard import mostrar_dashboard
    mostrar_dashboard()

elif modulo_id == "dashboard_global" and es_master:
    from modules.master.dashboard_global import mostrar_dashboard_global
    mostrar_dashboard_global()

elif modulo_id == "dashboard_drac" and es_master:
    from modules.master.dashboard_drac import mostrar_dashboard_drac
    mostrar_dashboard_drac()

else:
    st.error("Módulo no disponible.")
