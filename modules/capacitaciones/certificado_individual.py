"""
certificado_individual.py — Generación de un certificado individual con formulario manual.

Flujo:
1. Selecciona (opcionalmente) un reporte de capacitación existente para precargar fecha y nombre.
2. Completa los datos del participante: nombre, CI, evento, fecha, duración, ciudad, texto.
3. Genera PDF → descarga directa + registra en Supabase (capacitaciones + lotes_certificados).
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from auth.login import obtener_sesion
from database.db import (
    get_connection,
    consultar_reportes_capacitacion,
    insertar_capacitacion,
    insertar_lote_certificado,
)
from utils.docx_generator import generar_certificado_pdf
from utils.validator import validar_cedula


_MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

_TEXTO_PARTICIPACION_DEFAULT = (
    "Por su participación en la capacitación en materia de competencia sobre la"
)


def _fmt_fecha(d: date) -> str:
    return f"{d.day} de {_MESES_ES[d.month]} de {d.year}"


def mostrar_certificado_individual() -> None:
    """Renderiza el módulo de generación de certificado individual."""
    sesion  = obtener_sesion()
    oficina = sesion["oficina"]
    usuario = sesion["usuario"]

    st.title("📜 Certificado Individual")
    st.markdown(f"**Oficina:** {oficina}")
    st.info(
        "⚠️ **Requisito:** La plantilla Word debe contener los marcadores "
        "`«ciudad»`, `«duracion»` y `«texto_participacion»` para que estos campos "
        "aparezcan en el PDF generado."
    )
    st.divider()

    # ------------------------------------------------------------------
    # Cargar reportes del año actual para preselección
    # ------------------------------------------------------------------
    anio_actual = date.today().year
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(con, oficina=oficina, anio=anio_actual)

    opciones = ["— Sin vincular a reporte —"] + [
        f"N.° {r['numero_reporte']} ({r.get('year_reporte', anio_actual)}) — {r.get('tema', '')}"
        for r in reportes
    ]

    sel_idx = st.selectbox(
        "Vincular a reporte de capacitación del año actual (opcional)",
        options=range(len(opciones)),
        format_func=lambda i: opciones[i],
        key="ci_reporte_idx",
    )

    reporte_sel = reportes[sel_idx - 1] if sel_idx > 0 else None

    # Valores precargados desde el reporte seleccionado
    precarga_nombre_evento = reporte_sel.get("tema", "") if reporte_sel else ""
    precarga_fecha_str     = reporte_sel.get("fecha_evento", "") if reporte_sel else ""

    try:
        precarga_fecha = date.fromisoformat(precarga_fecha_str) if precarga_fecha_str else date.today()
    except ValueError:
        precarga_fecha = date.today()

    st.divider()
    st.subheader("Datos del participante")

    col_nom, col_ci = st.columns(2)
    with col_nom:
        nombre = st.text_input("Nombres y apellidos", key="ci_nombre", max_chars=200)
    with col_ci:
        cedula = st.text_input("Número de cédula", key="ci_cedula", max_chars=10)

    st.subheader("Datos del evento")

    nombre_evento = st.text_input(
        "Nombre del evento",
        value=precarga_nombre_evento,
        key="ci_nombre_evento",
        max_chars=300,
    )

    fecha_evento_d = st.date_input(
        "Fecha del evento",
        value=precarga_fecha,
        min_value=date(2024, 1, 1),
        max_value=date(2030, 12, 31),
        key="ci_fecha_evento",
    )

    col_tipo_dur, col_val_dur = st.columns([1, 1])
    with col_tipo_dur:
        tipo_duracion = st.radio("Tipo de duración", options=["Por horas", "Por días"], key="ci_tipo_dur")
    with col_val_dur:
        valor_duracion = st.number_input(
            "Cantidad",
            min_value=1,
            max_value=999,
            value=8,
            step=1,
            key="ci_valor_dur",
        )

    unidad       = "horas" if tipo_duracion == "Por horas" else "días"
    duracion_str = f"{valor_duracion} {unidad}"

    texto_participacion = st.text_area(
        "Texto de participación (editable)",
        value=_TEXTO_PARTICIPACION_DEFAULT,
        height=80,
        key="ci_texto_participacion",
    )

    ciudad = st.text_input("Ciudad", key="ci_ciudad", max_chars=100)

    st.divider()

    if st.button("🖨️ Generar certificado", type="primary"):
        cedula_ok, msg_cedula = validar_cedula(cedula.strip())
        if not nombre.strip():
            st.error("El nombre no puede estar vacío.")
            return
        if not cedula_ok:
            st.error(f"Cédula inválida: {msg_cedula}")
            return
        if not nombre_evento.strip():
            st.error("El nombre del evento no puede estar vacío.")
            return

        fecha_iso        = str(fecha_evento_d)
        fecha_evento_txt = _fmt_fecha(fecha_evento_d)

        with get_connection() as con:
            datos_cap = {
                "oficina":            oficina,
                "timestamp_forms":    None,
                "nombre":             nombre.strip(),
                "email":              None,
                "cedula":             cedula.strip(),
                "fecha_capacitacion": fecha_iso,
                "fecha_evento":       fecha_evento_txt,
                "institucion":        None,
                "provincia":          None,
                "nombre_curso":       nombre_evento.strip(),
                "codigo_certificado": None,
                "p1_conocimiento":    None,
                "p2_inquietudes":     None,
                "p3_contenido":       None,
                "p4_presencialidad":  None,
                "p5_puntualidad":     None,
                "p6_logistica":       None,
                "p7_duracion":        None,
                "temas_adicionales":  None,
                "sugerencias":        None,
                "registrado_por":     usuario,
            }
            insertar_capacitacion(con, datos_cap)
            codigo = datos_cap["codigo_certificado"]

            numero_reporte_vinculado = (
                reporte_sel["numero_reporte"] if reporte_sel else None
            )
            insertar_lote_certificado(con, {
                "oficina":                  oficina,
                "nombre_evento":            nombre_evento.strip(),
                "fecha_evento":             fecha_evento_txt,
                "num_participantes":        1,
                "codigo_inicio":            codigo,
                "codigo_fin":               codigo,
                "generado_por":             usuario,
                "numero_reporte_vinculado": numero_reporte_vinculado,
            })

        try:
            pdf_bytes = generar_certificado_pdf(
                nombre=nombre.strip(),
                cedula=cedula.strip(),
                nombre_curso=nombre_evento.strip(),
                fecha_capacitacion=fecha_iso,
                codigo_certificado=codigo,
                ciudad=ciudad.strip(),
                duracion=duracion_str,
                texto_participacion=texto_participacion.strip(),
            )
            nombre_archivo = f"{cedula.strip()}_{nombre.strip()[:30].replace(' ', '_')}.pdf"
            st.success(f"✅ Certificado generado. Código asignado: **{codigo}**")
            st.download_button(
                "📥 Descargar certificado PDF",
                data=pdf_bytes,
                file_name=nombre_archivo,
                mime="application/pdf",
            )
        except Exception as e:
            st.error(f"Error al generar el PDF: {e}")
