"""Generación de certificados PDF y registro resumido de códigos consumidos."""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date

import pandas as pd
import streamlit as st

from database.db import (
    consultar_lotes_certificados,
    get_connection,
    insertar_lote_certificado,
    obtener_ultimo_codigo_certificado,
    reservar_rango_codigos_certificado,
)
from utils.docx_generator import generar_certificado_pdf


_KEY_BATCH = "cap_batch_listo"
_KEY_ZIP = "cert_zip_descarga"
_KEY_EXCEL = "cert_excel_descarga"


def mostrar_certificados() -> None:
    """Renderiza el módulo de generación y el historial de rangos consumidos."""
    st.title("🎓 Generación de Certificados")
    _mostrar_placa_ultimo_certificado()
    st.divider()

    if _KEY_ZIP in st.session_state:
        st.success("Certificados generados. Descarga los archivos:")
        col_zip, col_excel = st.columns(2)
        with col_zip:
            st.download_button(
                "📥 Descargar ZIP de certificados",
                data=st.session_state[_KEY_ZIP],
                file_name="certificados.zip",
                mime="application/zip",
                use_container_width=True,
            )
        with col_excel:
            if _KEY_EXCEL in st.session_state:
                st.download_button(
                    "📊 Descargar resumen Excel",
                    data=st.session_state[_KEY_EXCEL],
                    file_name="resumen_certificados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        if st.button("↩ Listo, iniciar nueva carga"):
            st.session_state.pop(_KEY_ZIP, None)
            st.session_state.pop(_KEY_EXCEL, None)
            st.rerun()
        _mostrar_registro_emitidos()
        return

    batch = st.session_state.get(_KEY_BATCH)
    if batch is None:
        st.info(
            "No hay un lote preparado. Ve a **Capacitaciones — Carga**, "
            "sube el archivo y prepara el lote."
        )
        _mostrar_registro_emitidos()
        return

    records = batch.get("records", [])
    if not records:
        st.warning("El lote preparado no contiene registros.")
        _mostrar_registro_emitidos()
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Evento", batch.get("nombre_evento", "—"))
    col2.metric("Fecha", batch.get("fecha_evento", "—"))
    col3.metric("Participantes", len(records))
    numero_reporte = batch.get("numero_reporte_vinculado")
    if numero_reporte is not None:
        st.caption(f"Reporte de capacitación vinculado: **N.° {int(numero_reporte):03d}**")

    st.divider()
    df = pd.DataFrame(records)
    if "codigo_certificado" not in df or df["codigo_certificado"].isna().all():
        df["codigo_certificado"] = "Se asignará al generar"

    st.subheader(f"Participantes — {len(df)} registros")
    columnas_preview = [
        "nombre", "cedula", "codigo_certificado", "fecha_capacitacion", "nombre_curso",
    ]
    cols_ex = [c for c in columnas_preview if c in df.columns]
    st.dataframe(
        df[cols_ex].rename(columns={
            "nombre": "Nombre",
            "cedula": "Cédula",
            "codigo_certificado": "Código DRAC",
            "fecha_capacitacion": "Fecha evento",
            "nombre_curso": "Curso",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    if st.button(
        f"📄 Generar {len(df)} certificados PDF",
        type="primary",
        use_container_width=True,
    ):
        try:
            batch = _reservar_y_registrar_lote(batch)
        except Exception as exc:
            st.error(f"No se pudieron reservar los códigos en Supabase: {exc}")
            _mostrar_registro_emitidos()
            return

        df_generacion = pd.DataFrame(batch["records"])
        zip_bytes, errores = _generar_zip_certificados(
            df_generacion,
            ciudad=batch.get("ciudad", ""),
            duracion=batch.get("duracion", ""),
        )

        if errores:
            st.warning(
                f"No se completó el lote: {len(errores)} certificado(s) fallaron. "
                "Los códigos ya están registrados como consumidos; corrige el problema y "
                "vuelve a pulsar Generar para reutilizar el mismo rango."
            )
            for error in errores:
                st.text(error)
        elif zip_bytes:
            st.session_state[_KEY_ZIP] = zip_bytes
            st.session_state[_KEY_EXCEL] = _dataframe_a_excel(df_generacion)
            st.session_state.pop(_KEY_BATCH, None)
            st.rerun()

    _mostrar_registro_emitidos()


def _reservar_y_registrar_lote(batch: dict) -> dict:
    """Reserva códigos y registra el lote una sola vez por sesión."""
    records = batch.get("records", [])
    codigos_actuales = [r.get("codigo_certificado") for r in records]
    if batch.get("lote_id") and all(codigos_actuales):
        return batch

    anio_actual = date.today().year
    with get_connection() as con:
        codigos = reservar_rango_codigos_certificado(con, anio_actual, len(records))
        lote_id = insertar_lote_certificado(con, {
            "oficina": batch.get("oficina", ""),
            "nombre_evento": batch.get("nombre_evento", ""),
            "fecha_evento": batch.get("fecha_evento", ""),
            "num_participantes": len(records),
            "codigo_inicio": codigos[0],
            "codigo_fin": codigos[-1],
            "generado_por": batch.get("generado_por", ""),
            "numero_reporte_vinculado": batch.get("numero_reporte_vinculado"),
        })

    records_con_codigo = []
    for registro, codigo in zip(records, codigos):
        registro_actualizado = registro.copy()
        registro_actualizado["codigo_certificado"] = codigo
        records_con_codigo.append(registro_actualizado)

    batch_actualizado = batch.copy()
    batch_actualizado["records"] = records_con_codigo
    batch_actualizado["lote_id"] = lote_id
    batch_actualizado["codigo_inicio"] = codigos[0]
    batch_actualizado["codigo_fin"] = codigos[-1]
    st.session_state[_KEY_BATCH] = batch_actualizado
    return batch_actualizado


def _mostrar_placa_ultimo_certificado() -> None:
    anio_actual = date.today().year
    with get_connection() as con:
        ultimo = obtener_ultimo_codigo_certificado(con, anio_actual)
    if ultimo:
        st.info(f"📌 **Último certificado consumido ({anio_actual}):** `{ultimo}`")
    else:
        st.info(f"📌 Aún no se ha consumido ningún código de certificado en {anio_actual}.")


def _formatear_numero_reporte(valor) -> str:
    if valor is None or pd.isna(valor):
        return "—"
    return f"N.° {int(valor):03d}"


def _mostrar_registro_emitidos() -> None:
    """Muestra una fila resumida por rango de códigos consumidos."""
    oficina_id = st.session_state.get("oficina_id", "")
    es_master = st.session_state.get("oficina_rol") == "master"

    st.divider()
    st.subheader("📜 Registro de certificados emitidos")
    st.caption(
        "Este registro representa rangos de códigos consumidos. Un rango permanece "
        "registrado aunque la generación de sus archivos deba reintentarse."
    )

    with get_connection() as con:
        lotes = consultar_lotes_certificados(
            con, oficina=None if es_master else oficina_id,
        )

    if not lotes:
        st.info("Aún no se han consumido códigos de certificados.")
        return

    df_lotes = pd.DataFrame(lotes)
    if "numero_reporte_vinculado" not in df_lotes:
        df_lotes["numero_reporte_vinculado"] = None
    df_lotes["numero_reporte_vinculado"] = df_lotes[
        "numero_reporte_vinculado"
    ].apply(_formatear_numero_reporte)

    columnas = [
        "fecha_generacion",
        "nombre_evento",
        "fecha_evento",
        "numero_reporte_vinculado",
        "num_participantes",
        "codigo_inicio",
        "codigo_fin",
        "generado_por",
    ]
    if es_master:
        columnas.insert(1, "oficina")
    cols_ex = [c for c in columnas if c in df_lotes.columns]
    st.dataframe(
        df_lotes[cols_ex].rename(columns={
            "fecha_generacion": "Fecha de emisión",
            "oficina": "Oficina",
            "nombre_evento": "Evento",
            "fecha_evento": "Fecha evento",
            "numero_reporte_vinculado": "Reporte de capacitación",
            "num_participantes": "Participantes",
            "codigo_inicio": "Código inicio",
            "codigo_fin": "Código fin",
            "generado_por": "Generado por",
        }),
        use_container_width=True,
        hide_index=True,
    )


def _generar_zip_certificados(
    df: pd.DataFrame,
    ciudad: str = "",
    duracion: str = "",
) -> tuple[bytes | None, list[str]]:
    """Genera un ZIP en memoria con un PDF por participante."""
    zip_buffer = io.BytesIO()
    errores: list[str] = []
    generados = 0
    total = len(df)
    barra = st.progress(0, text="Generando certificados...")

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (_, fila) in enumerate(df.iterrows()):
            try:
                fecha_fin_val = fila.get("fecha_fin")
                pdf_bytes = generar_certificado_pdf(
                    nombre=str(fila.get("nombre", "")),
                    cedula=str(fila.get("cedula", "")),
                    nombre_curso=str(fila.get("nombre_curso", "")),
                    fecha_capacitacion=str(fila.get("fecha_capacitacion", "")),
                    codigo_certificado=str(fila.get("codigo_certificado", "")),
                    ciudad=ciudad,
                    duracion=duracion,
                    fecha_fin=str(fecha_fin_val) if pd.notna(fecha_fin_val) else "",
                )
                zf.writestr(
                    _nombre_archivo_pdf(
                        str(fila.get("nombre", "participante")),
                        str(fila.get("cedula", i)),
                    ),
                    pdf_bytes,
                )
                generados += 1
            except Exception as exc:
                errores.append(
                    f"{fila.get('nombre', '?')} ({fila.get('cedula', '?')}): {exc}"
                )
            barra.progress((i + 1) / total, text=f"Generando {i + 1}/{total}...")

    barra.empty()
    return (zip_buffer.getvalue() if generados else None), errores


def _nombre_archivo_pdf(nombre: str, cedula: str) -> str:
    nombre_limpio = re.sub(r"[^\w\s]", "", nombre).replace(" ", "_")[:50]
    return f"{cedula}_{nombre_limpio}.pdf"


def _dataframe_a_excel(df: pd.DataFrame) -> bytes:
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
