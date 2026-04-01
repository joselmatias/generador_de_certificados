"""
upload.py — Módulo de carga de capacitaciones desde Google Forms.

Flujo:
1. Usuario sube el Excel/CSV exportado de Google Forms.
2. forms_parser mapea y valida cada registro.
3. Se muestra resumen de válidos vs. errores.
4. Usuario ingresa el nombre del curso (aplica a todo el lote).
5. Se detectan duplicados antes de insertar (advertencia, no bloqueo).
6. Botón confirmar → insertar registros válidos en SQLite.
"""

import io
import streamlit as st
import pandas as pd

from auth.login import obtener_sesion
from database.db import get_connection, insertar_capacitacion, verificar_duplicados
from utils.forms_parser import parsear_forms, registros_a_dataframe, RegistroProcesado


_KEY_RESULTADO = "cap_upload_resultado"
_KEY_CURSO     = "cap_upload_curso"


def mostrar_carga() -> None:
    """Renderiza el módulo completo de carga de capacitaciones."""
    sesion  = obtener_sesion()
    oficina = sesion["oficina"]
    usuario = sesion["usuario"]

    st.title("📋 Carga de Capacitaciones — Google Forms")
    st.markdown(f"**Oficina:** {oficina}")
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
    # PASO 2: Nombre del curso
    # ------------------------------------------------------------------
    st.subheader("2. Nombre del curso")
    nombre_curso = st.text_input(
        "Nombre del curso (aplica a todos los registros del archivo)",
        placeholder="Ej: Gestión de Recursos Hídricos — Noviembre 2024",
        max_chars=200,
        key=_KEY_CURSO,
    )

    # ------------------------------------------------------------------
    # PASO 3: Parsear y validar
    # ------------------------------------------------------------------
    col_parsear, _ = st.columns([1, 3])
    with col_parsear:
        boton_parsear = st.button(
            "Validar archivo",
            disabled=(archivo is None or not nombre_curso.strip()),
            use_container_width=True,
        )

    if boton_parsear and archivo and nombre_curso.strip():
        with st.spinner("Procesando archivo..."):
            try:
                resultado = parsear_forms(
                    archivo=io.BytesIO(archivo.read()),
                    nombre_curso=nombre_curso.strip(),
                    oficina=oficina,
                    registrado_por=usuario,
                )
                st.session_state[_KEY_RESULTADO] = resultado
            except ValueError as e:
                st.error(f"Error al leer el archivo: {e}")
                return

    # ------------------------------------------------------------------
    # PASO 4: Mostrar resultado de validación
    # ------------------------------------------------------------------
    resultado = st.session_state.get(_KEY_RESULTADO)
    if resultado is None:
        return

    st.divider()
    st.subheader("3. Resultado de validación")

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
    # PASO 5: Detectar duplicados
    # ------------------------------------------------------------------
    if resultado.validos:
        st.divider()
        st.subheader("4. Verificación de duplicados")

        duplicados: list[RegistroProcesado] = []
        nuevos: list[RegistroProcesado] = []

        with get_connection() as con:
            for reg in resultado.validos:
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
        # PASO 6: Confirmar inserción
        # ------------------------------------------------------------------
        if nuevos:
            st.divider()
            st.subheader("5. Confirmar carga")

            if st.button(
                f"✅ Insertar {len(nuevos)} registros en la base de datos",
                type="primary",
            ):
                insertados, errores_insercion = _insertar_lote(nuevos)

                if errores_insercion:
                    st.warning(f"Se insertaron {insertados} registros. {len(errores_insercion)} fallaron.")
                    with st.expander("Ver errores de inserción"):
                        for err in errores_insercion:
                            st.text(err)
                else:
                    st.success(
                        f"✅ {insertados} registros insertados correctamente en la oficina **{oficina}**."
                    )

                del st.session_state[_KEY_RESULTADO]
                st.balloons()
        else:
            st.info("No hay registros nuevos para insertar (todos son duplicados).")


def _insertar_lote(registros: list[RegistroProcesado]) -> tuple[int, list[str]]:
    """
    Inserta un lote de registros válidos. Continúa si uno falla.

    Returns:
        Tupla (cantidad_insertados, lista_de_errores).
    """
    insertados = 0
    errores: list[str] = []

    with get_connection() as con:
        for reg in registros:
            try:
                insertar_capacitacion(con, reg.datos.copy())
                insertados += 1
            except Exception as e:
                nombre = reg.datos.get("nombre", "?")
                cedula = reg.datos.get("cedula", "?")
                errores.append(f"Fila {reg.fila_original} ({nombre} / {cedula}): {e}")

    return insertados, errores
