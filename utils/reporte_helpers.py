"""
reporte_helpers.py — Utilidades compartidas para precargar datos desde un
reporte de capacitación (usado por Certificado Individual y Capacitaciones — Carga).
"""

from __future__ import annotations

from datetime import date, datetime


def calcular_horas(hora_inicio: str, hora_fin: str) -> int | None:
    """Calcula la duración en horas completas a partir de 'HH:MM' - 'HH:MM'."""
    try:
        hi = datetime.strptime(hora_inicio, "%H:%M")
        hf = datetime.strptime(hora_fin, "%H:%M")
        horas = round((hf - hi).total_seconds() / 3600)
        return horas if horas > 0 else None
    except (ValueError, TypeError):
        return None


def parsear_fecha_reporte(texto: str) -> tuple[date, date | None]:
    """Interpreta el fecha_evento del reporte: 'YYYY-MM-DD' o 'YYYY-MM-DD al YYYY-MM-DD'.

    Devuelve (inicio, fin). fin es None si es un solo día.
    """
    partes = (texto or "").split(" al ")
    try:
        inicio = date.fromisoformat(partes[0].strip())
    except (ValueError, TypeError, IndexError):
        return date.today(), None
    fin: date | None = None
    if len(partes) > 1:
        try:
            fin = date.fromisoformat(partes[1].strip())
        except (ValueError, TypeError):
            fin = None
    return inicio, fin
