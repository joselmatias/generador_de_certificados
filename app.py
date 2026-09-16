"""
app.py — Punto de entrada principal del Sistema de Gestión de Actividades.

Flujo:
1. Pantalla principal con perfiles de oficinas técnicas.
2. Al seleccionar una oficina, se accede a sus módulos.
"""

import importlib

import streamlit as st

from utils.feature_flags import CERTIFICATE_GENERATION_ENABLED

DB_SCHEMA_VERSION = 15
CONGRESO_SYNC_VERSION = 7


st.set_page_config(
    page_title="Sistema de Gestión — OTRs",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner=False)
def _inicializar_db(schema_version: int) -> int:
    del schema_version  # Su valor invalida la caché cuando cambia el esquema.
    # Streamlit puede conservar módulos importados en memoria durante un
    # despliegue. Recargarlos en orden evita combinar seguimiento.py nuevo
    # con una capa de datos o una migración de la versión anterior.
    importlib.invalidate_caches()
    modulo_init_db = importlib.reload(importlib.import_module("database.init_db"))
    importlib.reload(importlib.import_module("database.db"))
    seguimiento = importlib.reload(
        importlib.import_module("modules.congresos.seguimiento")
    )

    modulo_init_db.init_db()

    version_modulo = getattr(seguimiento, "CONGRESO_SYNC_VERSION", 0)
    if version_modulo != CONGRESO_SYNC_VERSION:
        raise RuntimeError(
            "El módulo de Seguimiento Congreso todavía se está actualizando "
            f"(versión {version_modulo}; esperada {CONGRESO_SYNC_VERSION}). "
            "Recarga la aplicación en unos segundos."
        )

    seguimiento.precargar_congreso_desde_repositorio()
    seguimiento.precargar_proyeccion_estudiantes_desde_repositorio()
    sincronizar = seguimiento.sincronizar_congreso_desde_documentos
    # Solo se almacena en caché una inicialización ejecutada con el contrato
    # completo; las excepciones permiten que Streamlit vuelva a intentarlo.
    return sincronizar()


try:
    _inicializar_db(DB_SCHEMA_VERSION)
except Exception as exc:
    st.error(
        "No se pudo inicializar la información del congreso. "
        f"Recarga la aplicación en unos segundos. Detalle: {exc}"
    )
    st.stop()


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
        "nombre":  "Portoviejo",
        "rol":     "regional",
        "icono":   "🌊",
        "region":  "Costa — Zona 4",
        "detalle": "Oficina técnica regional de Portoviejo.",
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
es_guayaquil   = st.session_state["oficina_id"] == "guayaquil"

with st.sidebar:
    st.markdown(f"**Oficina:** {oficina_nombre}")
    st.markdown(f"**Rol:** {'Master (todas las oficinas)' if es_master else 'Regional'}")
    if not CERTIFICATE_GENERATION_ENABLED:
        st.warning("Emisión de certificados temporalmente inhabilitada.")
    st.divider()

    MODULOS_REGIONAL = {
        "🤝 Proyectos de vinculación":                    "proyectos_vinculacion",
        "📌 Seguimiento Congreso":                         "seguimiento_congreso",
        "📋 Capacitaciones — Carga":                    "cap_carga",
        "🎓 Capacitaciones — Certificados":             "cap_certificados",
        "📜 Certificado Individual":                    "cert_individual",
        "🖥️ Capacitación Virtual":                      "cap_virtual",
        "📝 Generador de Reportes":                     "generador_reportes",
    }

    MODULOS_MASTER = {
        **MODULOS_REGIONAL,
        **({"✅ Checklist Congreso": "checklist_congreso"} if es_guayaquil else {}),
        "📊 Dashboard DRAC": "dashboard_drac",
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

elif modulo_id == "proyectos_vinculacion":
    from modules.vinculacion.dashboard import mostrar_proyectos_vinculacion
    mostrar_proyectos_vinculacion()

elif modulo_id == "seguimiento_congreso":
    from modules.congresos.seguimiento import mostrar_seguimiento_congreso
    mostrar_seguimiento_congreso()

elif modulo_id == "checklist_congreso" and es_master and es_guayaquil:
    from modules.congresos.checklist import mostrar_checklist_congreso
    mostrar_checklist_congreso()

elif modulo_id == "cap_certificados":
    from modules.capacitaciones.certificados import mostrar_certificados
    mostrar_certificados()

elif modulo_id == "cert_individual":
    from modules.capacitaciones.certificado_individual import mostrar_certificado_individual
    mostrar_certificado_individual()

elif modulo_id == "cap_virtual":
    from modules.capacitaciones.capacitacion_virtual import mostrar_capacitacion_virtual
    mostrar_capacitacion_virtual()

elif modulo_id == "generador_reportes":
    from modules.reportes.generador import mostrar_generador_reportes
    mostrar_generador_reportes()

elif modulo_id == "dashboard_drac" and es_master:
    from modules.master.dashboard_drac import mostrar_dashboard_drac
    mostrar_dashboard_drac()

else:
    st.error("Módulo no disponible.")
