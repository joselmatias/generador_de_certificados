"""
login.py — Módulo de autenticación con bcrypt y st.secrets.

Gestiona:
- Pantalla de login (usuario/contraseña)
- Verificación contra st.secrets
- Sesión en st.session_state
- Sidebar con info del usuario y botón de cierre de sesión
"""

import streamlit as st
import bcrypt


# ---------------------------------------------------------------------------
# Claves de session_state
# ---------------------------------------------------------------------------
_KEY_AUTENTICADO = "autenticado"
_KEY_USUARIO     = "usuario"
_KEY_ROL         = "rol"
_KEY_OFICINA     = "oficina"


def esta_autenticado() -> bool:
    """Devuelve True si existe una sesión activa."""
    return st.session_state.get(_KEY_AUTENTICADO, False)


def obtener_sesion() -> dict:
    """
    Devuelve los datos de la sesión activa.

    Returns:
        dict con keys: usuario, rol, oficina.
        Valores vacíos si no hay sesión.
    """
    return {
        "usuario": st.session_state.get(_KEY_USUARIO, ""),
        "rol":     st.session_state.get(_KEY_ROL, ""),
        "oficina": st.session_state.get(_KEY_OFICINA, ""),
    }


def _verificar_credenciales(usuario: str, password: str) -> dict | None:
    """
    Verifica usuario y contraseña contra st.secrets.
    Usa comparación en tiempo constante (bcrypt) para evitar timing attacks.

    Args:
        usuario: Nombre de usuario ingresado.
        password: Contraseña en texto plano ingresada.

    Returns:
        dict con {rol, oficina} si las credenciales son válidas, None si no.
    """
    try:
        datos_usuario = st.secrets["users"].get(usuario)
    except (KeyError, AttributeError):
        return None

    if datos_usuario is None:
        return None

    hash_almacenado = datos_usuario.get("password", "")

    try:
        es_valido = bcrypt.checkpw(
            password.encode("utf-8"),
            hash_almacenado.encode("utf-8"),
        )
    except Exception:
        return None

    if not es_valido:
        return None

    return {
        "rol":     datos_usuario.get("role", "regional"),
        "oficina": datos_usuario.get("oficina", ""),
    }


def mostrar_login() -> None:
    """
    Renderiza la pantalla de login centrada en la página.
    Al autenticarse correctamente, escribe en st.session_state y
    hace rerun para mostrar la aplicación principal.
    """
    col_izq, col_centro, col_der = st.columns([1, 2, 1])

    with col_centro:
        st.markdown("## Sistema de Gestión de Actividades")
        st.markdown("#### Oficinas Técnicas Regionales")
        st.divider()

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input(
                "Usuario",
                placeholder="Ingrese su usuario",
                autocomplete="username",
            )
            password = st.text_input(
                "Contraseña",
                type="password",
                placeholder="Ingrese su contraseña",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button("Ingresar", use_container_width=True)

        if submitted:
            if not usuario or not password:
                st.error("Ingrese usuario y contraseña.")
                return

            datos = _verificar_credenciales(usuario.strip(), password)

            if datos is None:
                st.error("Credenciales incorrectas. Intente nuevamente.")
                return

            st.session_state[_KEY_AUTENTICADO] = True
            st.session_state[_KEY_USUARIO]     = usuario.strip()
            st.session_state[_KEY_ROL]         = datos["rol"]
            st.session_state[_KEY_OFICINA]     = datos["oficina"]
            st.rerun()


def mostrar_sidebar_sesion() -> None:
    """
    Muestra en el sidebar la información del usuario autenticado
    y el botón de cierre de sesión.
    """
    sesion = obtener_sesion()

    with st.sidebar:
        st.markdown(f"**Usuario:** {sesion['usuario']}")
        st.markdown(f"**Oficina:** {sesion['oficina']}")
        st.markdown(
            f"**Rol:** {'Master (todas las oficinas)' if sesion['rol'] == 'master' else 'Regional'}"
        )
        st.divider()

        if st.button("Cerrar sesión", use_container_width=True, type="secondary"):
            _cerrar_sesion()


def _cerrar_sesion() -> None:
    """Limpia la sesión y recarga la aplicación."""
    for key in [_KEY_AUTENTICADO, _KEY_USUARIO, _KEY_ROL, _KEY_OFICINA]:
        st.session_state.pop(key, None)
    st.rerun()
