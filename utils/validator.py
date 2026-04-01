"""
validator.py — Validaciones de negocio para el sistema.

Incluye:
- Cédula ecuatoriana (algoritmo módulo 10 del Registro Civil)
- Email (RFC básico)
- Nombre (presencia y longitud mínima)
- Fecha (parseable en múltiples formatos)
- Escala de satisfacción (1-5)
"""

import re
from datetime import datetime
from typing import Any
from dateutil import parser as dateutil_parser


# ---------------------------------------------------------------------------
# Cédula ecuatoriana
# ---------------------------------------------------------------------------

# Coeficientes para el algoritmo módulo 10
_COEFICIENTES = [2, 1, 2, 1, 2, 1, 2, 1, 2]

# Dígitos de provincia válidos para cédulas (01-24 y 30)
_PROVINCIAS_VALIDAS = set(range(1, 25)) | {30}


def validar_cedula(cedula: str) -> tuple[bool, str]:
    """
    Valida una cédula ecuatoriana según el algoritmo módulo 10
    del Registro Civil del Ecuador.

    Reglas aplicadas:
    1. Exactamente 10 dígitos numéricos.
    2. Código de provincia (primeros 2 dígitos) entre 01-24 o 30.
    3. Tercer dígito entre 0 y 5 (personas naturales).
    4. Dígito verificador correcto (posición 10).

    Args:
        cedula: Cadena con la cédula a validar.

    Returns:
        Tupla (es_valida: bool, mensaje: str).
        mensaje está vacío cuando es_valida es True.
    """
    cedula = str(cedula).strip()

    # Regla 1: exactamente 10 dígitos
    if not re.fullmatch(r"\d{10}", cedula):
        return False, "La cédula debe tener exactamente 10 dígitos numéricos."

    # Regla 2: código de provincia válido
    provincia = int(cedula[:2])
    if provincia not in _PROVINCIAS_VALIDAS:
        return False, f"Código de provincia inválido: {cedula[:2]} (válido: 01-24, 30)."

    # Regla 3: tercer dígito entre 0 y 5
    tercer_digito = int(cedula[2])
    if tercer_digito > 5:
        return False, f"Tercer dígito inválido: {tercer_digito} (debe ser 0-5)."

    # Regla 4: verificador módulo 10
    digitos = [int(d) for d in cedula]
    suma = 0
    for i, coef in enumerate(_COEFICIENTES):
        producto = digitos[i] * coef
        suma += producto - 9 if producto > 9 else producto

    verificador_calculado = (10 - (suma % 10)) % 10
    if verificador_calculado != digitos[9]:
        return False, "Dígito verificador incorrecto."

    return True, ""


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def validar_email(email: str) -> tuple[bool, str]:
    """
    Valida formato básico de correo electrónico (RFC simplificado).

    Args:
        email: Cadena con el email a validar.

    Returns:
        Tupla (es_valido: bool, mensaje: str).
    """
    email = str(email).strip()
    if not email:
        return True, ""  # Email es opcional en el sistema
    if not _EMAIL_PATTERN.match(email):
        return False, f"Formato de email inválido: '{email}'."
    return True, ""


# ---------------------------------------------------------------------------
# Nombre
# ---------------------------------------------------------------------------

def validar_nombre(nombre: str, min_chars: int = 5) -> tuple[bool, str]:
    """
    Valida que el nombre no esté vacío y tenga al menos min_chars caracteres.

    Args:
        nombre: Cadena con el nombre a validar.
        min_chars: Longitud mínima requerida (por defecto 5).

    Returns:
        Tupla (es_valido: bool, mensaje: str).
    """
    nombre = str(nombre).strip()
    if not nombre:
        return False, "El nombre no puede estar vacío."
    if len(nombre) < min_chars:
        return False, f"El nombre debe tener al menos {min_chars} caracteres."
    return True, ""


# ---------------------------------------------------------------------------
# Fecha
# ---------------------------------------------------------------------------

def validar_fecha(valor: str | None) -> tuple[bool, str, str]:
    """
    Intenta parsear una fecha en múltiples formatos comunes.
    Devuelve la fecha normalizada como cadena YYYY-MM-DD si es válida.

    Args:
        valor: Cadena con la fecha a validar.

    Returns:
        Tupla (es_valida: bool, mensaje: str, fecha_iso: str).
        fecha_iso es '' cuando es_valida es False.
    """
    if not valor or str(valor).strip() in ("", "nan", "None", "NaT"):
        return False, "La fecha no puede estar vacía.", ""
    try:
        dt = dateutil_parser.parse(str(valor).strip(), dayfirst=True)
        return True, "", dt.strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return False, f"Fecha no reconocida: '{valor}'.", ""


# ---------------------------------------------------------------------------
# Escala de satisfacción
# ---------------------------------------------------------------------------

def validar_satisfaccion(valor: Any, campo: str) -> tuple[bool, str, int | None]:
    """
    Valida que el valor sea un entero entre 1 y 5.

    Args:
        valor: Valor a validar (puede venir como str, float o int).
        campo: Nombre del campo para el mensaje de error.

    Returns:
        Tupla (es_valido: bool, mensaje: str, valor_int: int | None).
    """
    if valor is None or str(valor).strip() in ("", "nan", "None"):
        return True, "", None  # Respuesta opcional aceptada como NULL

    try:
        entero = int(float(str(valor).strip()))
    except (ValueError, TypeError):
        return False, f"{campo}: '{valor}' no es un número entero.", None

    if entero < 1 or entero > 5:
        return False, f"{campo}: valor {entero} fuera de rango (1-5).", None

    return True, "", entero
