"""Interruptores temporales para funciones dependientes de servicios externos."""

from __future__ import annotations


# Contingencia iniciada el 2026-09-08 y revertida el 2026-09-21: Streamlit
# confirmó el fix del índice Debian vencido el 2026-09-09. Se reactiva la
# generación de certificados; verificar el primer despliegue en Streamlit Cloud.
CERTIFICATE_GENERATION_ENABLED = True

CERTIFICATE_GENERATION_NOTICE = (
    "La generación y descarga de certificados está temporalmente inhabilitada "
    "por una incidencia del servicio de instalación de Streamlit Cloud. "
    "Las demás funciones continúan disponibles y esta contingencia no modifica "
    "los datos existentes."
)
