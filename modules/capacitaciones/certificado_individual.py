"""
certificado_individual.py — Generación de un certificado individual con formulario manual.

Flujo:
1. Selecciona (opcionalmente) un reporte de capacitación existente para precargar fecha y nombre.
2. Completa los datos del participante: nombre, CI, evento, fecha, duración, ciudad, texto.
3. Reserva un código, registra el lote resumido en Supabase y genera el PDF.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from database.db import (
    get_connection,
    consultar_reportes_capacitacion,
    insertar_lote_certificado,
    obtener_ultimo_codigo_certificado,
    reservar_rango_codigos_certificado,
)
from utils.docx_generator import generar_certificado_pdf
from utils.reporte_helpers import calcular_horas, parsear_fecha_reporte
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
    oficina        = st.session_state.get("oficina_id", "")
    oficina_nombre = st.session_state.get("oficina_nombre", oficina)

    st.title("📜 Certificado Individual")
    st.markdown(f"**Oficina:** {oficina_nombre}")
    st.info(
        "⚠️ **Requisito:** La plantilla Word debe contener los marcadores "
        "`«ciudad»`, `«duracion»` y `«texto_participacion»` para que estos campos "
        "aparezcan en el PDF generado."
    )

    # ------------------------------------------------------------------
    # Cargar reportes del año actual para preselección
    # ------------------------------------------------------------------
    anio_actual = date.today().year
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(con, oficina=oficina, anio=anio_actual)
        ultimo_codigo = obtener_ultimo_codigo_certificado(con, anio_actual)

    if ultimo_codigo:
        st.info(f"📌 **Último certificado generado ({anio_actual}):** `{ultimo_codigo}`")
    else:
        st.info(f"📌 Aún no se ha generado ningún certificado en {anio_actual}.")

    st.divider()

    # Defaults iniciales de los campos que se precargan desde un reporte. Se
    # siembran en session_state ANTES de crear los widgets; los widgets NO usan
    # value= (para evitar el conflicto value/session_state de Streamlit) y el
    # callback del selectbox los actualiza al vincular un reporte.
    _defaults = {
        "ci_nombre_evento":      "",
        "ci_ciudad":             "",
        "ci_valor_dur":          8,
        "ci_tipo_dur":           "Por horas",
        "ci_fecha_evento_rango": (date.today(), date.today()),
    }
    for _k, _v in _defaults.items():
        st.session_state.setdefault(_k, _v)

    opciones = ["— Sin vincular a reporte —"] + [
        f"N.° {r['numero_reporte']} ({r.get('year_reporte', anio_actual)}) — {r.get('tema', '')}"
        for r in reportes
    ]

    def _aplicar_reporte() -> None:
        """Al cambiar el reporte vinculado, precarga los campos del evento."""
        idx = st.session_state.get("ci_reporte_idx", 0)
        rep = reportes[idx - 1] if idx > 0 else None
        if not rep:
            return
        st.session_state["ci_nombre_evento"] = rep.get("tema", "") or ""
        st.session_state["ci_ciudad"]        = rep.get("canton", "") or ""
        inicio, fin = parsear_fecha_reporte(rep.get("fecha_evento", ""))
        if fin and fin != inicio:
            # Evento de varios días → duración en días
            st.session_state["ci_tipo_dur"]           = "Por días"
            st.session_state["ci_fecha_evento_rango"] = (inicio, fin)
            st.session_state["ci_valor_dur"]          = (fin - inicio).days + 1
        else:
            st.session_state["ci_tipo_dur"]           = "Por horas"
            st.session_state["ci_fecha_evento_rango"] = (inicio, inicio)
            horas = calcular_horas(rep.get("hora_inicio", ""), rep.get("hora_fin", ""))
            if horas:
                st.session_state["ci_valor_dur"] = horas

    st.selectbox(
        "Vincular a reporte de capacitación del año actual (opcional)",
        options=range(len(opciones)),
        format_func=lambda i: opciones[i],
        key="ci_reporte_idx",
        on_change=_aplicar_reporte,
    )

    reporte_sel = (
        reportes[st.session_state["ci_reporte_idx"] - 1]
        if st.session_state.get("ci_reporte_idx", 0) > 0 else None
    )

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
        key="ci_nombre_evento",
        max_chars=300,
    )

    col_tipo_dur, col_val_dur = st.columns([1, 1])
    with col_tipo_dur:
        tipo_duracion = st.radio("Tipo de duración", options=["Por horas", "Por días"], key="ci_tipo_dur")
    with col_val_dur:
        valor_duracion = st.number_input(
            "Cantidad",
            min_value=1,
            max_value=999,
            step=1,
            key="ci_valor_dur",
        )

    unidad       = "horas" if tipo_duracion == "Por horas" else "días"
    duracion_str = f"{valor_duracion} {unidad}"

    # La fecha del evento admite seleccionar uno o más días independientemente
    # del "Tipo de duración" (p.ej. un evento de 2 días puede seguir midiéndose
    # en horas totales, no solo en días).
    fechas_sel = st.date_input(
        "Fecha del evento (selecciona uno o más días)",
        min_value=date(2024, 1, 1),
        max_value=date(2030, 12, 31),
        key="ci_fecha_evento_rango",
    )
    fecha_inicio = fechas_sel[0] if fechas_sel else date.today()
    fecha_fin    = fechas_sel[-1] if fechas_sel else fecha_inicio
    fecha_evento_d = fecha_inicio
    if fecha_fin != fecha_inicio:
        fecha_evento_txt_rango = (
            f"{fecha_inicio.day} al {fecha_fin.day} de "
            f"{_MESES_ES[fecha_fin.month]} de {fecha_fin.year}"
        )
        fecha_evento_fin = fecha_fin
    else:
        fecha_evento_txt_rango = None
        fecha_evento_fin = None

    texto_participacion = st.text_area(
        "Texto de participación (editable)",
        value=_TEXTO_PARTICIPACION_DEFAULT,
        height=80,
        key="ci_texto_participacion",
    )

    ciudad = st.text_input(
        "Ciudad",
        key="ci_ciudad",
        max_chars=100,
    )

    generado_por = st.text_input(
        "Generado por (nombre de quien genera el certificado)",
        key="ci_generado_por",
        max_chars=200,
    )

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
        if not generado_por.strip():
            st.error("Ingresa el nombre de quien genera el certificado.")
            return

        fecha_iso        = str(fecha_evento_d)
        fecha_evento_txt = fecha_evento_txt_rango or _fmt_fecha(fecha_evento_d)

        numero_reporte_vinculado = (
            reporte_sel["numero_reporte"] if reporte_sel else None
        )
        clave_emision = (
            oficina,
            nombre.strip(),
            cedula.strip(),
            nombre_evento.strip(),
            fecha_evento_txt,
            generado_por.strip(),
            numero_reporte_vinculado,
        )
        reserva = st.session_state.get("ci_emision_reservada")

        # Si LibreOffice falla, un nuevo clic con los mismos datos reutiliza el
        # código ya consumido y no crea otra fila en lotes_certificados.
        if not reserva or reserva.get("clave") != clave_emision:
            try:
                with get_connection() as con:
                    codigo = reservar_rango_codigos_certificado(
                        con, date.today().year, 1,
                    )[0]
                    lote_id = insertar_lote_certificado(con, {
                        "oficina":                  oficina,
                        "nombre_evento":            nombre_evento.strip(),
                        "fecha_evento":             fecha_evento_txt,
                        "num_participantes":        1,
                        "codigo_inicio":            codigo,
                        "codigo_fin":               codigo,
                        "generado_por":             generado_por.strip(),
                        "numero_reporte_vinculado": numero_reporte_vinculado,
                    })
            except Exception as e:
                st.error(f"No se pudo reservar el código en Supabase: {e}")
                return

            reserva = {"clave": clave_emision, "codigo": codigo, "lote_id": lote_id}
            st.session_state["ci_emision_reservada"] = reserva
        else:
            codigo = reserva["codigo"]

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
                fecha_fin=str(fecha_evento_fin) if fecha_evento_fin else "",
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
