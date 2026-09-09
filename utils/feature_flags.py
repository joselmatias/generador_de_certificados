"""Interruptores temporales para funciones dependientes de servicios externos."""

from __future__ import annotations


# Contingencia iniciada el 2026-09-08.
# Streamlit Community Cloud no puede instalar paquetes APT porque uno de sus
# repositorios Debian publica un índice vencido. La generación de certificados
# usa LibreOffice y debe permanecer deshabilitada hasta restaurar packages.txt.
CERTIFICATE_GENERATION_ENABLED = False

CERTIFICATE_GENERATION_NOTICE = (
    "La generación y descarga de certificados está temporalmente inhabilitada "
    "por una incidencia del servicio de instalación de Streamlit Cloud. "
    "Las demás funciones continúan disponibles y esta contingencia no modifica "
    "los datos existentes."
)
