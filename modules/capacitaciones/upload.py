"""
upload.py — Módulo de carga de capacitaciones desde Google Forms.

Flujo:
1. Usuario sube el Excel/CSV exportado de Google Forms.
2. Opcionalmente vincula un reporte de capacitación, que precarga nombre
   del curso, ciudad, duración y fecha(s) del evento.
3. Completa/ajusta nombre del curso, generado por, ciudad y duración.
4. Selecciona la(s) fecha(s) del evento (reemplaza fecha del CSV).
5. forms_parser mapea y valida cada registro.
6. Se muestra resumen de válidos vs. errores.
7. Se detectan duplicados antes de insertar (advertencia, no bloqueo).
8. Botón confirmar → insertar registros válidos en la BD; batch guardado
   en session state (incluye ciudad/duración) para transferir a Certificados.
"""

import io
from datetime import date

import streamlit as st
import pandas as pd

from database.db import (
    get_connection,
    insertar_capacitacion,
    verificar_duplicados,
    consultar_reportes_capacitacion,
)
from utils.forms_parser import parsear_forms, registros_a_dataframe, RegistroProcesado
from utils.reporte_helpers import calcular_horas, parsear_fecha_reporte


_KEY_RESULTADO     = "cap_upload_resultado"
_KEY_CURSO         = "cap_upload_curso"
_KEY_GENERADO_POR  = "cap_upload_generado_por"
_KEY_CIUDAD        = "cap_upload_ciudad"
_KEY_TIPO_DUR      = "cap_upload_tipo_dur"
_KEY_VALOR_DUR     = "cap_upload_valor_dur"
_KEY_REPORTE_IDX   = "cap_upload_reporte_idx"
_KEY_BATCH         = "cap_batch_listo"
_KEY_FORZAR_TODOS  = "cap_upload_forzar_todos"

_MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def mostrar_carga() -> None:
    """Renderiza el módulo completo de carga de capacitaciones."""
    oficina        = st.session_state.get("oficina_id", "")
    oficina_nombre = st.session_state.get("oficina_nombre", oficina)

    st.title("📋 Carga de Capacitaciones — Google Forms")
    st.markdown(f"**Oficina:** {oficina_nombre}")
    st.divider()

    # ------------------------------------------------------------------
    # PASO 1: Subir archivo
    # ------------------------------------------------------------------
    st.subheader("1. Seleccionar archivo exportado de Google Forms")
    archivo = st.file_uploader(
        "Subir Excel (.xlsx) o CSV (.csv)",
        type=["xlsx", "xls", "csv"],
        help="Exporta el archivo desde Google Forms → Respuestas → Descargar CSV o XLSX.",
    )

    # ------------------------------------------------------------------
    # PASO 2: Vincular a reporte de capacitación (opcional)
    # ------------------------------------------------------------------
    st.subheader("2. Vincular a reporte de capacitación (opcional)")

    anio_actual = date.today().year
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(con, oficina=oficina, anio=anio_actual)

    opciones_reporte = ["— Sin vincular a reporte —"] + [
        f"N.° {r['numero_reporte']} ({r.get('year_reporte', anio_actual)}) — {r.get('tema', '')}"
        for r in reportes
    ]

    def _aplicar_reporte() -> None:
        """Al vincular un reporte, precarga curso, ciudad, duración y fecha(s)."""
        idx = st.session_state.get(_KEY_REPORTE_IDX, 0)
        rep = reportes[idx - 1] if idx > 0 else None
        if not rep:
            return
        st.session_state[_KEY_CURSO]  = rep.get("tema", "") or ""
        st.session_state[_KEY_CIUDAD] = rep.get("canton", "") or ""
        inicio, fin = parsear_fecha_reporte(rep.get("fecha_evento", ""))
        if fin and fin != inicio:
            st.session_state["cap_upload_fecha"] = (inicio, fin)
            st.session_state[_KEY_TIPO_DUR]      = "Por días"
            st.session_state[_KEY_VALOR_DUR]     = (fin - inicio).days + 1
        else:
            st.session_state["cap_upload_fecha"] = (inicio,)
            st.session_state[_KEY_TIPO_DUR]      = "Por horas"
            horas = calcular_horas(rep.get("hora_inicio", ""), rep.get("hora_fin", ""))
            if horas:
                st.session_state[_KEY_VALOR_DUR] = horas

    st.selectbox(
        "Reporte de capacitación del año actual",
        options=range(len(opciones_reporte)),
        format_func=lambda i: opciones_reporte[i],
        key=_KEY_REPORTE_IDX,
        on_change=_aplicar_reporte,
    )

    # ------------------------------------------------------------------
    # PASO 3: Datos del lote
    # ------------------------------------------------------------------
    st.subheader("3. Datos del lote")
    nombre_curso = st.text_input(
        "Nombre del curso (aplica a todos los registros del archivo)",
        placeholder="Ej: Gestión de Recursos Hídricos — Noviembre 2024",
        max_chars=200,
        key=_KEY_CURSO,
    )
    generado_por = st.text_input(
        "Generado por (nombre de quien genera los certificados)",
        placeholder="Nombre completo",
        max_chars=200,
        key=_KEY_GENERADO_POR,
    )
    ciudad = st.text_input(
        "Ciudad",
        placeholder="Ej: Guayaquil",
        max_chars=100,
        key=_KEY_CIUDAD,
    )
    col_tipo_dur, col_val_dur = st.columns([1, 1])
    with col_tipo_dur:
        tipo_duracion = st.radio(
            "Tipo de duración", options=["Por horas", "Por días"], key=_KEY_TIPO_DUR,
        )
    with col_val_dur:
        valor_duracion = st.number_input(
            "Cantidad",
            min_value=1,
            max_value=999,
            value=8,
            step=1,
            key=_KEY_VALOR_DUR,
        )
    unidad_dur   = "horas" if tipo_duracion == "Por horas" else "días"
    duracion_str = f"{valor_duracion} {unidad_dur}"

    # ------------------------------------------------------------------
    # PASO 4: Fecha(s) del evento
    # ------------------------------------------------------------------
    st.subheader("4. Fecha(s) del evento")
    fechas_sel = st.date_input(
        "Selecciona el día o rango de días del evento",
        value=(),
        min_value=date(2024, 1, 1),
        max_value=date(2030, 12, 31),
        key="cap_upload_fecha",
    )
    fecha_inicio: date | None = fechas_sel[0] if fechas_sel else None
    fecha_fin:   date | None = fechas_sel[-1] if fechas_sel else None

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
            f"{fecha_inicio.day} de {_MESES_ES[fecha_inicio.month]} de {fecha_inicio.year}"
        )
        fecha_capacitacion_iso = fecha_inicio.isoformat()
    else:
        fecha_evento_str = fecha_capacitacion_iso = None

    # ------------------------------------------------------------------
    # PASO 5: Parsear y validar
    # ------------------------------------------------------------------
    col_parsear, _ = st.columns([1, 3])
    with col_parsear:
        boton_parsear = st.button(
            "Validar archivo",
            disabled=(
                archivo is None
                or not nombre_curso.strip()
                or not generado_por.strip()
                or fecha_inicio is None
            ),
            use_container_width=True,
        )

    if boton_parsear and archivo and nombre_curso.strip() and generado_por.strip() and fecha_inicio:
        with st.spinner("Procesando archivo..."):
            try:
                resultado = parsear_forms(
                    archivo=io.BytesIO(archivo.read()),
                    nombre_curso=nombre_curso.strip(),
                    oficina=oficina,
                    registrado_por=generado_por.strip(),
                )
                st.session_state[_KEY_RESULTADO] = resultado
            except ValueError as e:
                st.error(f"Error al leer el archivo: {e}")
                return

    # ------------------------------------------------------------------
    # PASO 6: Mostrar resultado de validación
    # ------------------------------------------------------------------
    resultado = st.session_state.get(_KEY_RESULTADO)
    if resultado is None:
        return

    # Inyectar fechas del evento seleccionadas en cada registro (cada render)
    if fecha_capacitacion_iso:
        for reg in resultado.validos + resultado.invalidos:
            reg.datos["fecha_capacitacion"] = fecha_capacitacion_iso
            reg.datos["fecha_evento"]       = fecha_evento_str
            reg.datos["fecha_fin"]          = fecha_fin_iso

    st.divider()
    st.subheader("6. Resultado de validación")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de filas", resultado.total_filas)
    col2.metric("Registros válidos", resultado.total_validos)
    col3.metric(
        "Registros con errores",
        resultado.total_invalidos,
        delta=f"-{resultado.total_invalidos}" if resultado.total_invalidos > 0 else None,
        delta_color="inverse",
    )

    if resultado.columnas_faltantes:
        st.warning(
            f"Columnas no encontradas en el archivo: {', '.join(resultado.columnas_faltantes)}. "
            "Verifique que el archivo sea el export correcto de Google Forms."
        )

    forzar_todos = False
    if resultado.invalidos:
        with st.expander(f"Ver {resultado.total_invalidos} registros con errores"):
            filas_error = [
                {
                    "Fila":    reg.fila_original,
                    "Nombre":  reg.datos.get("nombre", ""),
                    "Cédula":  reg.datos.get("cedula", ""),
                    "Errores": " | ".join(reg.errores),
                }
                for reg in resultado.invalidos
            ]
            st.dataframe(pd.DataFrame(filas_error), use_container_width=True, hide_index=True)

        st.warning(
            "⚠️ Hay registros con errores de validación. Si confirmas que los datos son "
            "correctos (por ejemplo, la cédula es válida pero el sistema la marcó por error), "
            "puedes forzar su inclusión."
        )
        forzar_todos = st.checkbox(
            "Rechazar la validación e incluir TODOS los registros (también los que tienen errores) "
            "para generar sus certificados",
            key=_KEY_FORZAR_TODOS,
        )

    registros_base = (
        resultado.validos + resultado.invalidos if forzar_todos else resultado.validos
    )

    if resultado.validos:
        with st.expander(f"Ver {resultado.total_validos} registros válidos"):
            df_preview = registros_a_dataframe(resultado.validos)
            columnas_preview = ["nombre", "cedula", "fecha_capacitacion", "institucion", "provincia", "email"]
            cols_ex = [c for c in columnas_preview if c in df_preview.columns]
            st.dataframe(
                df_preview[cols_ex].rename(columns={
                    "nombre": "Nombre", "cedula": "Cédula",
                    "fecha_capacitacion": "Fecha", "institucion": "Institución",
                    "provincia": "Provincia", "email": "Email",
                }),
                use_container_width=True, hide_index=True,
            )

    # ------------------------------------------------------------------
    # PASO 7: Detectar duplicados
    # ------------------------------------------------------------------
    if registros_base:
        st.divider()
        st.subheader("7. Verificación de duplicados")

        duplicados: list[RegistroProcesado] = []
        nuevos: list[RegistroProcesado] = []

        with get_connection() as con:
            for reg in registros_base:
                if verificar_duplicados(
                    con,
                    cedula=reg.datos["cedula"],
                    fecha_capacitacion=reg.datos["fecha_capacitacion"],
                    oficina=oficina,
                ):
                    duplicados.append(reg)
                else:
                    nuevos.append(reg)

        if duplicados:
            st.warning(
                f"Se detectaron **{len(duplicados)} registros duplicados** "
                "(misma cédula y fecha ya registrados para esta oficina). "
                "Estos no se insertarán."
            )
            with st.expander("Ver duplicados"):
                st.dataframe(
                    pd.DataFrame([{
                        "Fila":   r.fila_original,
                        "Nombre": r.datos.get("nombre", ""),
                        "Cédula": r.datos.get("cedula", ""),
                        "Fecha":  r.datos.get("fecha_capacitacion", ""),
                    } for r in duplicados]),
                    use_container_width=True, hide_index=True,
                )

        st.info(f"**{len(nuevos)} registros nuevos** listos para insertar.")

        # ------------------------------------------------------------------
        # PASO 8: Confirmar inserción
        # ------------------------------------------------------------------
        if nuevos:
            st.divider()
            st.subheader("8. Confirmar carga")

            if st.button(
                f"✅ Insertar {len(nuevos)} registros en la base de datos",
                type="primary",
            ):
                insertados, insertados_dicts, errores_insercion = _insertar_lote(nuevos)

                if errores_insercion:
                    st.warning(f"Se insertaron {insertados} registros. {len(errores_insercion)} fallaron.")
                    with st.expander("Ver errores de inserción"):
                        for err in errores_insercion:
                            st.text(err)
                else:
                    st.success(
                        f"✅ {insertados} registros insertados correctamente en la oficina **{oficina_nombre}**."
                    )

                if insertados > 0:
                    st.session_state[_KEY_BATCH] = {
                        "records":        insertados_dicts,
                        "nombre_evento":  nombre_curso.strip(),
                        "fecha_evento":   fecha_evento_str or "",
                        "fecha_inicio":   fecha_capacitacion_iso or "",
                        "oficina":        oficina,
                        "oficina_nombre": oficina_nombre,
                        "generado_por":   generado_por.strip(),
                        "ciudad":         ciudad.strip(),
                        "duracion":       duracion_str,
                    }

                del st.session_state[_KEY_RESULTADO]
                st.balloons()
        else:
            st.info("No hay registros nuevos para insertar (todos son duplicados).")


def _insertar_lote(registros: list[RegistroProcesado]) -> tuple[int, list[dict], list[str]]:
    """
    Inserta un lote de registros válidos. Continúa si uno falla.

    Returns:
        Tupla (cantidad_insertados, registros_con_codigo_asignado, lista_de_errores).
    """
    insertados_count = 0
    insertados_dicts: list[dict] = []
    errores: list[str] = []

    with get_connection() as con:
        for reg in registros:
            try:
                insertar_capacitacion(con, reg.datos)
                insertados_count += 1
                insertados_dicts.append(reg.datos.copy())
            except Exception as e:
                nombre = reg.datos.get("nombre", "?")
                cedula = reg.datos.get("cedula", "?")
                errores.append(f"Fila {reg.fila_original} ({nombre} / {cedula}): {e}")

    return insertados_count, insertados_dicts, errores
