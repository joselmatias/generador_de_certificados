"""
app.py — Punto de entrada principal del Sistema de Gestión de Actividades.

Flujo de la aplicación:
1. Inicializar la base de datos (idempotente).
2. Verificar si hay sesión activa; si no, mostrar pantalla de login.
3. Mostrar sidebar con info de usuario y navegación por módulos.
4. Renderizar el módulo seleccionado según permisos.
"""

import streamlit as st

from database.init_db import init_db
from auth.login import esta_autenticado, mostrar_login, mostrar_sidebar_sesion, obtener_sesion


# ---------------------------------------------------------------------------
# Configuración de página (debe ser la primera llamada a Streamlit)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Gestión — OTRs",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Inicialización de la base de datos
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _inicializar_db() -> None:
    """Inicializa la DB una sola vez por proceso."""
    init_db()


_inicializar_db()


# ---------------------------------------------------------------------------
# Flujo de autenticación
# ---------------------------------------------------------------------------
if not esta_autenticado():
    mostrar_login()
    st.stop()

# Sidebar con info del usuario (solo si está autenticado)
mostrar_sidebar_sesion()

sesion = obtener_sesion()
es_master = sesion["rol"] == "master"


# ---------------------------------------------------------------------------
# Navegación por módulos
# ---------------------------------------------------------------------------
MODULOS_REGIONAL = {
    "📋 Capacitaciones — Carga": "cap_carga",
    "🎓 Capacitaciones — Certificados": "cap_certificados",
    "📊 Capacitaciones — Dashboard": "cap_dashboard",
}

MODULOS_MASTER = {
    **MODULOS_REGIONAL,
    "🌐 Dashboard Global": "dashboard_global",
}

modulos_disponibles = MODULOS_MASTER if es_master else MODULOS_REGIONAL

with st.sidebar:
    st.markdown("### Módulos")
    seleccion = st.radio(
        "Navegar a:",
        options=list(modulos_disponibles.keys()),
        label_visibility="collapsed",
    )

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

else:
    st.error("Módulo no disponible o sin permisos suficientes.")
