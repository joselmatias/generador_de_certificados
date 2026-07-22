"""
upload.py — Preparación de lotes de certificados desde un export de Google Forms.

El archivo se considera previamente revisado por el operador. La aplicación
solo comprueba que pueda leerse y que contenga las columnas de nombre y cédula;
no valida contenido, no busca duplicados y no guarda encuestas en Supabase.
"""

import io
from datetime import date

import pandas as pd
import streamlit as st

from database.db import get_connection, consultar_reportes_capacitacion
from utils.forms_parser import parsear_forms_sin_validacion
from utils.reporte_helpers import calcular_horas, parsear_fecha_reporte


_KEY_RESULTADO = "cap_upload_registros"
_KEY_CURSO = "cap_upload_curso"
_KEY_GENERADO_POR = "cap_upload_generado_por"
_KEY_CIUDAD = "cap_upload_ciudad"
_KEY_TIPO_DUR = "cap_upload_tipo_dur"
_KEY_VALOR_DUR = "cap_upload_valor_dur"
_KEY_REPORTE_IDX = "cap_upload_reporte_idx_obligatorio"
_KEY_FECHA = "cap_upload_fecha"
_KEY_BATCH = "cap_batch_listo"

_MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def mostrar_carga() -> None:
    """Renderiza la preparación de un lote sin persistir sus participantes."""
    oficina = st.session_state.get("oficina_id", "")
    oficina_nombre = st.session_state.get("oficina_nombre", oficina)

    st.title("📋 Carga de Capacitaciones — Google Forms")
    st.markdown(f"**Oficina:** {oficina_nombre}")
    st.info(
        "El archivo se procesará tal como fue cargado. Asegúrate de haber "
        "revisado previamente nombres, cédulas, correos y demás respuestas."
    )
    st.divider()

    st.subheader("1. Seleccionar archivo exportado de Google Forms")
    archivo = st.file_uploader(
        "Subir Excel (.xlsx) o CSV (.csv)",
        type=["xlsx", "xls", "csv"],
        help="Exporta el archivo desde Google Forms → Respuestas → Descargar CSV o XLSX.",
    )

    st.subheader("2. Vincular a reporte de capacitación")
    anio_actual = date.today().year
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(
            con, oficina=oficina, anio=anio_actual,
        )

    def _aplicar_reporte() -> None:
        """Precarga los datos del evento desde el reporte seleccionado."""
        idx = st.session_state.get(_KEY_REPORTE_IDX)
        if idx is None or idx >= len(reportes):
            return
        rep = reportes[idx]
        st.session_state[_KEY_CURSO] = rep.get("tema", "") or ""
        st.session_state[_KEY_CIUDAD] = rep.get("canton", "") or ""
        inicio, fin = parsear_fecha_reporte(rep.get("fecha_evento", ""))
        if fin and fin != inicio:
            st.session_state[_KEY_FECHA] = (inicio, fin)
            st.session_state[_KEY_TIPO_DUR] = "Por días"
            st.session_state[_KEY_VALOR_DUR] = (fin - inicio).days + 1
        else:
            st.session_state[_KEY_FECHA] = (inicio,)
            st.session_state[_KEY_TIPO_DUR] = "Por horas"
            horas = calcular_horas(rep.get("hora_inicio", ""), rep.get("hora_fin", ""))
            if horas:
                st.session_state[_KEY_VALOR_DUR] = horas

    if reportes:
        reporte_idx = st.selectbox(
            "Reporte de capacitación del año actual",
            options=range(len(reportes)),
            index=None,
            format_func=lambda i: (
                f"N.° {reportes[i]['numero_reporte']} "
                f"({reportes[i].get('year_reporte', anio_actual)}) — "
                f"{reportes[i].get('tema', '')}"
            ),
            placeholder="Selecciona un reporte",
            key=_KEY_REPORTE_IDX,
            on_change=_aplicar_reporte,
        )
    else:
        reporte_idx = None
        st.session_state.pop(_KEY_REPORTE_IDX, None)
        st.warning(
            f"No existen reportes de capacitación de {anio_actual} para esta oficina. "
            "Crea el reporte antes de preparar certificados."
        )

    reporte_sel = reportes[reporte_idx] if reporte_idx is not None else None

    st.subheader("3. Datos del lote")
    st.session_state.setdefault(_KEY_CURSO, "")
    st.session_state.setdefault(_KEY_GENERADO_POR, "")
    st.session_state.setdefault(_KEY_CIUDAD, "")
    st.session_state.setdefault(_KEY_TIPO_DUR, "Por horas")
    st.session_state.setdefault(_KEY_VALOR_DUR, 8)
    st.session_state.setdefault(_KEY_FECHA, ())

    nombre_curso = st.text_input(
        "Nombre del curso (aplica a todos los registros del archivo)",
        max_chars=200,
        key=_KEY_CURSO,
    )
    generado_por = st.text_input(
        "Generado por (nombre de quien genera los certificados)",
        max_chars=200,
        key=_KEY_GENERADO_POR,
    )
    ciudad = st.text_input("Ciudad", max_chars=100, key=_KEY_CIUDAD)

    col_tipo_dur, col_val_dur = st.columns(2)
    with col_tipo_dur:
        tipo_duracion = st.radio(
            "Tipo de duración", ["Por horas", "Por días"], key=_KEY_TIPO_DUR,
        )
    with col_val_dur:
        valor_duracion = st.number_input(
            "Cantidad", min_value=1, max_value=999, step=1, key=_KEY_VALOR_DUR,
        )
    unidad_dur = "horas" if tipo_duracion == "Por horas" else "días"
    duracion_str = f"{valor_duracion} {unidad_dur}"

    st.subheader("4. Fecha(s) del evento")
    fechas_sel = st.date_input(
        "Selecciona el día o rango de días del evento",
        min_value=date(2024, 1, 1),
        max_value=date(2030, 12, 31),
        key=_KEY_FECHA,
    )
    fecha_inicio: date | None = fechas_sel[0] if fechas_sel else None
    fecha_fin: date | None = fechas_sel[-1] if fechas_sel else None

    fecha_fin_iso: str | None = None
    if fecha_inicio and fecha_fin and fecha_inicio != fecha_fin:
        fecha_evento_str = (
            f"{fecha_inicio.day} al {fecha_fin.day} de "
            f"{_MESES_ES[fecha_fin.month]} de {fecha_fin.year}"
        )
        fecha_capacitacion_iso = fecha_inicio.isoformat()
        fecha_fin_iso = fecha_fin.isoformat()
    elif fecha_inicio:
        fecha_evento_str = (
            f"{fecha_inicio.day} de {_MESES_ES[fecha_inicio.month]} "
            f"de {fecha_inicio.year}"
        )
        fecha_capacitacion_iso = fecha_inicio.isoformat()
    else:
        fecha_evento_str = fecha_capacitacion_iso = None

    st.subheader("5. Procesar archivo")
    puede_procesar = bool(
        archivo is not None
        and reporte_sel is not None
        and nombre_curso.strip()
        and generado_por.strip()
        and fecha_inicio is not None
    )
    if st.button(
        "Procesar archivo",
        disabled=not puede_procesar,
        use_container_width=False,
    ):
        with st.spinner("Leyendo archivo..."):
            try:
                archivo.seek(0)
                registros = parsear_forms_sin_validacion(
                    archivo=io.BytesIO(archivo.read()),
                    nombre_curso=nombre_curso,
                    oficina=oficina,
                    registrado_por=generado_por,
                )
            except ValueError as exc:
                st.error(f"Error al leer el archivo: {exc}")
                return
        st.session_state[_KEY_RESULTADO] = registros

    registros = st.session_state.get(_KEY_RESULTADO)
    if registros is None:
        return
    if not registros:
        st.warning("El archivo no contiene participantes.")
        return

    # Los datos del evento prevalecen sobre cualquier fecha incluida en el export.
    for registro in registros:
        registro["nombre_curso"] = nombre_curso.strip()
        registro["oficina"] = oficina
        registro["registrado_por"] = generado_por.strip()
        registro["fecha_capacitacion"] = fecha_capacitacion_iso
        registro["fecha_evento"] = fecha_evento_str
        registro["fecha_fin"] = fecha_fin_iso
        registro["codigo_certificado"] = None

    st.divider()
    st.subheader("6. Vista previa")
    st.metric("Participantes encontrados", len(registros))
    df_preview = pd.DataFrame(registros)
    columnas_preview = [
        "nombre", "cedula", "fecha_capacitacion", "institucion", "provincia", "email",
    ]
    cols_ex = [c for c in columnas_preview if c in df_preview.columns]
    st.dataframe(
        df_preview[cols_ex].rename(columns={
            "nombre": "Nombre",
            "cedula": "Cédula",
            "fecha_capacitacion": "Fecha",
            "institucion": "Institución",
            "provincia": "Provincia",
            "email": "Email",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("7. Preparar lote")
    if st.button(
        f"✅ Preparar lote de {len(registros)} certificados",
        type="primary",
    ):
        st.session_state[_KEY_BATCH] = {
            "records": [registro.copy() for registro in registros],
            "nombre_evento": nombre_curso.strip(),
            "fecha_evento": fecha_evento_str or "",
            "fecha_inicio": fecha_capacitacion_iso or "",
            "oficina": oficina,
            "oficina_nombre": oficina_nombre,
            "generado_por": generado_por.strip(),
            "ciudad": ciudad.strip(),
            "duracion": duracion_str,
            "numero_reporte_vinculado": reporte_sel["numero_reporte"],
        }
        st.session_state.pop("cert_zip_descarga", None)
        st.session_state.pop("cert_excel_descarga", None)
        st.session_state.pop(_KEY_RESULTADO, None)
        st.success(
            "Lote preparado. Ve a **Capacitaciones — Certificados** para reservar "
            "los códigos y generar los documentos."
        )
        st.balloons()
