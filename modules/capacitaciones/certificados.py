"""
certificados.py — Generación y descarga de certificados PDF usando plantilla Word.

Flujo:
1. Lee el lote cargado en session state desde Capacitaciones — Carga.
2. Muestra vista previa con los códigos DRAC asignados.
3. Genera un PDF por participante y ofrece descarga en ZIP.
4. Registra el lote en lotes_certificados (Supabase).
5. Exporta resumen en Excel.
"""

from __future__ import annotations

import io
import re
import zipfile

import pandas as pd
import streamlit as st

from database.db import get_connection, insertar_lote_certificado
from utils.docx_generator import generar_certificado_pdf


_KEY_BATCH = "cap_batch_listo"
_KEY_ZIP   = "cert_zip_descarga"


def mostrar_certificados() -> None:
    """Renderiza el módulo completo de generación de certificados."""
    st.title("🎓 Generación de Certificados")
    st.divider()

    # Si hay un ZIP listo (generado en render anterior), mostrar solo descarga
    if _KEY_ZIP in st.session_state:
        zip_bytes = st.session_state[_KEY_ZIP]
        st.success("Certificados generados. Descarga el archivo ZIP:")
        col_dl, _ = st.columns([1, 2])
        with col_dl:
            st.download_button(
                "📥 Descargar ZIP de certificados",
                data=zip_bytes,
                file_name="certificados.zip",
                mime="application/zip",
                use_container_width=True,
            )
        if st.button("↩ Listo, iniciar nueva carga"):
            del st.session_state[_KEY_ZIP]
            st.rerun()
        return

    # Leer lote desde session state
    batch = st.session_state.get(_KEY_BATCH)
    if batch is None:
        st.info(
            "No hay un lote cargado. Ve a **Capacitaciones — Carga**, "
            "sube el archivo y confirma la inserción para generar certificados."
        )
        return

    records = batch.get("records", [])
    if not records:
        st.warning("El lote cargado no contiene registros.")
        return

    # Encabezado del lote
    col1, col2, col3 = st.columns(3)
    col1.metric("Evento", batch.get("nombre_evento", "—"))
    col2.metric("Fecha", batch.get("fecha_evento", "—"))
    col3.metric("Participantes", len(records))

    st.divider()
    df = pd.DataFrame(records)

    # Vista previa
    st.subheader(f"Participantes — {len(df)} registros")
    columnas_preview = ["nombre", "cedula", "codigo_certificado", "fecha_capacitacion", "nombre_curso"]
    cols_ex = [c for c in columnas_preview if c in df.columns]
    st.dataframe(
        df[cols_ex].rename(columns={
            "nombre": "Nombre", "cedula": "Cédula",
            "codigo_certificado": "Código DRAC",
            "fecha_capacitacion": "Fecha evento",
            "nombre_curso": "Curso",
        }),
        use_container_width=True, hide_index=True,
    )

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
                codigos = df["codigo_certificado"].dropna()
                with get_connection() as con:
                    insertar_lote_certificado(con, {
                        "oficina":                  batch.get("oficina", ""),
                        "nombre_evento":            batch.get("nombre_evento", ""),
                        "fecha_evento":             batch.get("fecha_evento", ""),
                        "num_participantes":        len(df),
                        "codigo_inicio":            codigos.iloc[0] if not codigos.empty else None,
                        "codigo_fin":               codigos.iloc[-1] if not codigos.empty else None,
                        "generado_por":             batch.get("oficina_nombre", ""),
                        "numero_reporte_vinculado": None,
                    })

                st.session_state[_KEY_ZIP] = zip_bytes
                del st.session_state[_KEY_BATCH]
                st.rerun()

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
    """Genera un ZIP en memoria con un .pdf por participante."""
    zip_buffer = io.BytesIO()
    errores: list[str] = []
    generados = 0
    total = len(df)

    barra = st.progress(0, text="Generando certificados...")

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (_, fila) in enumerate(df.iterrows()):
            try:
                pdf_bytes = generar_certificado_pdf(
                    nombre=str(fila.get("nombre", "")),
                    cedula=str(fila.get("cedula", "")),
                    nombre_curso=str(fila.get("nombre_curso", "")),
                    fecha_capacitacion=str(fila.get("fecha_capacitacion", "")),
                    codigo_certificado=str(fila.get("codigo_certificado", "")),
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
        "nombre", "cedula", "email", "fecha_capacitacion", "fecha_evento",
        "nombre_curso", "provincia", "institucion", "oficina", "codigo_certificado",
        "p1_conocimiento", "p2_inquietudes", "p3_contenido",
        "p4_presencialidad", "p5_puntualidad", "p6_logistica", "p7_duracion",
    ]
    cols_ex = [c for c in columnas if c in df.columns]
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df[cols_ex].to_excel(writer, index=False, sheet_name="Certificados")
    return buffer.getvalue()
