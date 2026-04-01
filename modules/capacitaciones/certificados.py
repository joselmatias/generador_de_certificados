"""
certificados.py — Generación y descarga de certificados PDF.

Flujo:
1. Filtros por rango de fechas, curso y oficina (master ve todas).
2. Vista previa de registros a certificar.
3. Generación de PDF por participante con ReportLab.
4. Descarga de ZIP con todos los PDFs.
5. Descarga de resumen Excel con los mismos registros.
"""

from __future__ import annotations

import io
import re
import zipfile

import pandas as pd
import streamlit as st

from auth.login import obtener_sesion
from database.db import get_connection, consultar_capacitaciones, listar_cursos
from utils.pdf_generator import generar_certificado

NOMBRE_INSTITUCION = "Institución Pública del Ecuador"


def mostrar_certificados() -> None:
    """Renderiza el módulo completo de generación de certificados."""
    sesion    = obtener_sesion()
    oficina   = sesion["oficina"]
    es_master = sesion["rol"] == "master"

    st.title("🎓 Generación de Certificados")
    st.markdown(f"**Oficina:** {oficina}")
    st.divider()

    # ------------------------------------------------------------------
    # Filtros
    # ------------------------------------------------------------------
    st.subheader("Filtros de búsqueda")

    col1, col2 = st.columns(2)
    with col1:
        fecha_desde = st.date_input("Fecha desde", value=None, key="cert_desde")
    with col2:
        fecha_hasta = st.date_input("Fecha hasta", value=None, key="cert_hasta")

    oficina_filtro: str | None = oficina
    if es_master:
        sel_oficina = st.selectbox(
            "Oficina",
            options=["Todas", "Guayaquil", "Manabí", "Loja", "Cuenca"],
            key="cert_oficina",
        )
        oficina_filtro = None if sel_oficina == "Todas" else sel_oficina

    with get_connection() as con:
        cursos = listar_cursos(con, oficina=oficina_filtro)

    curso_sel = st.selectbox("Curso", options=["Todos"] + cursos, key="cert_curso")

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------
    with get_connection() as con:
        filas = consultar_capacitaciones(
            con,
            oficina=oficina_filtro,
            fecha_desde=str(fecha_desde) if fecha_desde else None,
            fecha_hasta=str(fecha_hasta) if fecha_hasta else None,
            nombre_curso=None if curso_sel == "Todos" else curso_sel,
        )

    if not filas:
        st.info("No se encontraron registros con los filtros seleccionados.")
        return

    df = pd.DataFrame([dict(f) for f in filas])

    # ------------------------------------------------------------------
    # Vista previa
    # ------------------------------------------------------------------
    st.divider()
    st.subheader(f"Registros encontrados: {len(df)}")

    columnas_preview = ["nombre", "cedula", "fecha_capacitacion", "nombre_curso", "oficina", "codigo_certificado"]
    cols_ex = [c for c in columnas_preview if c in df.columns]
    st.dataframe(
        df[cols_ex].rename(columns={
            "nombre": "Nombre", "cedula": "Cédula",
            "fecha_capacitacion": "Fecha", "nombre_curso": "Curso",
            "oficina": "Oficina", "codigo_certificado": "Código",
        }),
        use_container_width=True, hide_index=True,
    )

    # ------------------------------------------------------------------
    # Descarga ZIP y Excel
    # ------------------------------------------------------------------
    st.divider()
    col_pdf, col_excel = st.columns(2)

    with col_pdf:
        if st.button(f"📄 Generar {len(df)} certificados PDF", type="primary", use_container_width=True):
            zip_bytes, errores = _generar_zip_certificados(df)

            if errores:
                st.warning(f"Se generaron certificados con {len(errores)} errores:")
                for e in errores:
                    st.text(e)

            if zip_bytes:
                st.download_button(
                    label="📥 Descargar ZIP de certificados",
                    data=zip_bytes,
                    file_name="certificados.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

    with col_excel:
        if st.button("📊 Exportar a Excel", use_container_width=True):
            excel_bytes = _dataframe_a_excel(df)
            st.download_button(
                label="📥 Descargar Excel",
                data=excel_bytes,
                file_name="resumen_certificados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )


def _generar_zip_certificados(df: pd.DataFrame) -> tuple[bytes | None, list[str]]:
    """Genera un ZIP en memoria con un PDF por participante."""
    zip_buffer = io.BytesIO()
    errores: list[str] = []
    generados = 0
    total = len(df)

    barra = st.progress(0, text="Generando certificados...")

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (_, fila) in enumerate(df.iterrows()):
            try:
                pdf_bytes = generar_certificado(
                    nombre=str(fila.get("nombre", "")),
                    cedula=str(fila.get("cedula", "")),
                    nombre_curso=str(fila.get("nombre_curso", "")),
                    fecha_capacitacion=str(fila.get("fecha_capacitacion", "")),
                    codigo_certificado=str(fila.get("codigo_certificado", "")),
                    nombre_institucion=NOMBRE_INSTITUCION,
                )
                nombre_archivo = _nombre_archivo_pdf(
                    str(fila.get("nombre", "participante")),
                    str(fila.get("cedula", str(i))),
                )
                zf.writestr(nombre_archivo, pdf_bytes)
                generados += 1
            except Exception as e:
                errores.append(f"{fila.get('nombre', '?')} ({fila.get('cedula', '?')}): {e}")

            barra.progress((i + 1) / total, text=f"Generando {i + 1}/{total}...")

    barra.empty()
    return (zip_buffer.getvalue() if generados > 0 else None), errores


def _nombre_archivo_pdf(nombre: str, cedula: str) -> str:
    """Construye nombre de archivo PDF seguro para el ZIP."""
    nombre_limpio = re.sub(r"[^\w\s]", "", nombre).replace(" ", "_")[:50]
    return f"{cedula}_{nombre_limpio}.pdf"


def _dataframe_a_excel(df: pd.DataFrame) -> bytes:
    """Serializa el DataFrame a bytes de Excel."""
    buffer = io.BytesIO()
    columnas = [
        "nombre", "cedula", "email", "fecha_capacitacion", "nombre_curso",
        "provincia", "institucion", "oficina", "codigo_certificado",
        "p1_conocimiento", "p2_inquietudes", "p3_contenido",
        "p4_presencialidad", "p5_puntualidad", "p6_logistica", "p7_duracion",
    ]
    cols_ex = [c for c in columnas if c in df.columns]
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df[cols_ex].to_excel(writer, index=False, sheet_name="Certificados")
    return buffer.getvalue()
