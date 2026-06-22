"""
generador.py — Generador de Reportes de Capacitaciones y Asambleas Productivas.

Dos subsecciones:
1. Reporte de Capacitaciones — genera PDF con formato DRAC
2. Actas de Asambleas Productivas — registra asistentes

Estadísticas mensuales al pie de la página.
"""

from __future__ import annotations

import json
from datetime import date, time, timedelta

import streamlit as st

from database.init_db import init_db
from database.db import (
    get_connection,
    obtener_siguiente_numero_reporte,
    insertar_reporte_capacitacion,
    consultar_reportes_capacitacion,
    obtener_siguiente_numero_asamblea,
    insertar_asamblea_productiva,
    consultar_asambleas_productivas,
    actualizar_compromisos,
    estadisticas_mensuales,
)
from utils.reporte_drac_pdf import generar_reporte_drac, TIPOS_EVENTO
from utils.ubicaciones_ec import PROVINCIAS_CANTONES
from utils.convenios import CONTRAPARTES, CONTRAPARTE_NUMEROS

# Garantiza que las tablas existan aunque el caché haya bloqueado init_db() en app.py
init_db()

_MESES_ESP = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

# Configuración específica por oficina
_OFICINA_CFG: dict[str, dict] = {
    "guayaquil": {
        "revisado_por":       "José Matías",
        "area_elaborado":     "DRAC",
        "nombre_institucion": "Dirección Regional de Abogacía de la Competencia",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Dirección Regional de",
            "Abogacía de la Competencia",
        ],
    },
    "cuenca": {
        "revisado_por":       "Roberto Carlos Santos Suarez",
        "area_elaborado":     "OTAC",
        "nombre_institucion": "Oficina Técnica de Apoyo de Cuenca",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Oficina Técnica de Apoyo",
            "Cuenca",
        ],
    },
    "manabi": {
        "revisado_por":       "Roberto Carlos Santos Suarez",
        "area_elaborado":     "OTAP",
        "nombre_institucion": "Oficina Técnica de Apoyo de Portoviejo",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Oficina Técnica de Apoyo",
            "Portoviejo",
        ],
    },
    "loja": {
        "revisado_por":       "Roberto Carlos Santos Suarez",
        "area_elaborado":     "OTAL",
        "nombre_institucion": "Oficina Técnica de Apoyo de Loja",
        "lineas_institucion": [
            "Intendencia Regional /",
            "Oficina Técnica de Apoyo",
            "Loja",
        ],
    },
}

_CFG_DEFAULT = {
    "revisado_por":       "Roberto Carlos Santos Suarez",
    "area_elaborado":     "OTA",
    "nombre_institucion": "la Oficina Técnica de Apoyo",
    "lineas_institucion": [
        "Intendencia Regional /",
        "Oficina Técnica de Apoyo",
        "",
    ],
}


def _cfg_oficina(oficina_id: str) -> dict:
    return _OFICINA_CFG.get(oficina_id.lower(), _CFG_DEFAULT)


def _construir_adjuntos(nombre_institucion: str, items: list[str]) -> str:
    """
    Arma el texto de adjuntos con el prefijo institucional y una lista
    enumerada con letras (a, b, c, …). Si no hay ítems, devuelve solo el prefijo.
    """
    prefijo = (
        f"La {nombre_institucion}, cuenta con archivos digitales "
        "de la capacitación efectuada, cuya documentación se detalla a continuación:"
    )
    if not items:
        return prefijo
    letras = "abcdefghijklmnopqrstuvwxyz"
    lista = "\n".join(
        f"{letras[i]})\t{item.rstrip('.').strip()}." for i, item in enumerate(items)
    )
    return f"{prefijo}\n\n{lista}"


def mostrar_generador_reportes() -> None:
    oficina_id     = st.session_state.get("oficina_id", "")
    oficina_nombre = st.session_state.get("oficina_nombre", oficina_id)

    st.title("📝 Generador de Reportes de Capacitaciones y Asambleas Productivas")
    st.markdown(f"**Oficina:** {oficina_nombre}")
    st.divider()

    tab_cap, tab_asm, tab_stats = st.tabs([
        "📋 Reporte de Capacitaciones",
        "🤝 Actas de Asambleas Productivas",
        "📊 Estadísticas del Mes",
    ])

    with tab_cap:
        _tab_reporte_capacitacion(oficina_id, oficina_nombre)

    with tab_asm:
        _tab_asamblea_productiva(oficina_id, oficina_nombre)

    with tab_stats:
        _tab_estadisticas(oficina_id, oficina_nombre)


# ---------------------------------------------------------------------------
# TAB 1 — Reporte de Capacitaciones
# ---------------------------------------------------------------------------

def _tab_reporte_capacitacion(oficina_id: str, oficina_nombre: str) -> None:
    st.subheader("Reporte de Capacitaciones")
    st.markdown("Completa los campos y haz clic en **Generar Reporte** para descargar el PDF.")
    st.divider()

    cfg = _cfg_oficina(oficina_id)
    revisado_por       = cfg["revisado_por"]
    area_elaborado     = cfg["area_elaborado"]
    lineas_institucion = cfg["lineas_institucion"]
    nombre_institucion = cfg["nombre_institucion"]

    col_num, col_fecha = st.columns([1, 2])
    with col_num:
        anio_actual = date.today().year
        st.markdown("**Número de Reporte**")
        with get_connection() as _con:
            ultimo = _con.execute(
                "SELECT ultimo_numero FROM contador_reporte WHERE id = 1"
            ).fetchone()
            proximo = (ultimo["ultimo_numero"] if ultimo else 83) + 1
        st.info(f"Se generará: **DRAC-{proximo:03d}-{anio_actual}**")

    with col_fecha:
        fecha_reporte = st.date_input(
            "Fecha del Reporte",
            value=date.today(),
            key="rep_fecha",
        )

    # Tipo de Evento (con opción "Otros")
    st.markdown("**Tipo de Evento**")
    tipo_evento_sel = st.selectbox(
        "Selecciona el tipo de evento",
        options=TIPOS_EVENTO + ["Otros"],
        key="rep_tipo_evento",
        label_visibility="collapsed",
    )
    if tipo_evento_sel == "Otros":
        tipo_evento_otro = st.text_input(
            "Especifica el tipo de evento",
            key="rep_tipo_evento_otro",
            placeholder="Ej: Taller, Conversatorio...",
        ).strip()
        tipo_evento = tipo_evento_otro or "Otros"
    else:
        tipo_evento_otro = ""
        tipo_evento = tipo_evento_sel
    es_congreso = tipo_evento == "Congresos"

    st.divider()

    # Institución /asociación capacitada — tipo + nombre + condicionales
    st.markdown("#### Institución /asociación capacitada - Fecha - Modalidad - Tema:")

    tipos_institucion_opts = ["Institución pública", "Institución Privada", "Asociación"]
    if es_congreso:
        tipos_inst_sel = st.multiselect(
            "Tipo de institución / asociación capacitada",
            options=tipos_institucion_opts,
            placeholder="Selecciona uno o más tipos",
            key="rep_tipo_institucion_multi",
        )
    else:
        tipo_inst_unico = st.selectbox(
            "Tipo de institución / asociación capacitada",
            options=tipos_institucion_opts,
            index=None,
            placeholder="Selecciona el tipo",
            key="rep_tipo_institucion",
        )
        tipos_inst_sel = [tipo_inst_unico] if tipo_inst_unico else []

    # Valores condicionales (se rellenan según el tipo elegido)
    institucion_invitada = ""
    tipo_institucion = ""
    contacto_nombre = ""
    contacto_celular = ""
    tipo_actividad_productiva = ""
    publico_objetivo_capacitado = ""

    if tipos_inst_sel:
        tipo_institucion = ", ".join(tipos_inst_sel)
        incluye_asociacion = "Asociación" in tipos_inst_sel
        incluye_no_asociacion = any(t != "Asociación" for t in tipos_inst_sel)

        # Nombre de la institución (siempre que haya un tipo elegido)
        institucion_invitada = st.text_input(
            "Nombre de la institución / asociación capacitada",
            key="rep_institucion",
            placeholder="Nombre completo",
        )

        # Datos de contacto — para los 3 tipos
        st.markdown("**Datos de contacto** (obligatorios)")
        ca1, ca2 = st.columns(2)
        with ca1:
            contacto_nombre = st.text_input(
                "Nombres y apellidos del contacto", key="rep_contacto_nombre")
        with ca2:
            contacto_celular = st.text_input("Celular", key="rep_contacto_celular")

        if incluye_asociacion:
            tipo_actividad_productiva = st.text_input(
                "Tipo de actividad productiva", key="rep_actividad_productiva")
        if incluye_no_asociacion:
            publico_objetivo_capacitado = st.text_input(
                "Tipo de personal capacitado",
                key="rep_publico_capacitado",
                placeholder="Ej.: Estudiantes, Funcionarios Públicos, docentes, etc.",
            )

    # Provincia y Cantón — desplegables encadenados con autocompletar
    cpc1, cpc2 = st.columns(2)
    with cpc1:
        provincia = st.selectbox(
            "Provincia",
            options=sorted(PROVINCIAS_CANTONES),
            index=None,
            placeholder="Escribe o selecciona la provincia",
            key="rep_provincia",
        )
    cantones_opts = sorted(PROVINCIAS_CANTONES[provincia]) if provincia else []
    # Si el cantón guardado ya no pertenece a la provincia elegida, se descarta
    if (st.session_state.get("rep_canton") is not None
            and st.session_state.get("rep_canton") not in cantones_opts):
        del st.session_state["rep_canton"]
    with cpc2:
        canton = st.selectbox(
            "Cantón",
            options=cantones_opts,
            index=None,
            placeholder="Escribe o selecciona el cantón",
            key="rep_canton",
        )

    # Para el reporte: cadena vacía si no se seleccionó
    provincia = provincia or ""
    canton    = canton or ""

    c1, c2 = st.columns(2)
    with c1:
        modalidad = st.selectbox(
            "Modalidad",
            options=["Presencial", "Virtual", "Híbrida"],
            key="rep_modalidad",
        )
    with c2:
        if es_congreso:
            fecha_evento_val = st.date_input(
                "Fechas del Evento",
                value=(fecha_reporte - timedelta(days=1), fecha_reporte),
                key="rep_fechas_evento",
                max_value=fecha_reporte,   # no puede ser posterior a la fecha del reporte
            )
            fecha_evento_inicio, fecha_evento_fin = _normalizar_rango_fechas(fecha_evento_val)
        else:
            fecha_evento = st.date_input(
                "Fecha del Evento",
                value=date.today(),
                key="rep_fecha_evento",
                max_value=fecha_reporte,   # no puede ser posterior a la fecha del reporte
            )
            fecha_evento_inicio, fecha_evento_fin = fecha_evento, fecha_evento
        fecha_evento_texto = _formatear_fecha_evento_para_guardar(
            fecha_evento_inicio, fecha_evento_fin
        )
    tema = st.text_input("Tema", key="rep_tema")

    # Horario del evento
    ch1, ch2 = st.columns(2)
    with ch1:
        hora_inicio_val = st.time_input("Hora de inicio", value=time(9, 0), key="rep_hora_inicio")
    with ch2:
        hora_fin_val = st.time_input("Hora de fin", value=time(12, 0), key="rep_hora_fin")
    hora_inicio_str = hora_inicio_val.strftime("%H:%M") if hora_inicio_val else ""
    hora_fin_str    = hora_fin_val.strftime("%H:%M") if hora_fin_val else ""

    if es_congreso and (not fecha_evento_inicio or not fecha_evento_fin):
        st.warning("⚠️ Selecciona la fecha de inicio y fin del congreso.")
    elif es_congreso and fecha_evento_inicio == fecha_evento_fin:
        st.warning("⚠️ Para congresos, selecciona un rango de dos o más días.")
    elif fecha_evento_fin and fecha_evento_fin > fecha_reporte:
        st.warning("⚠️ La fecha del evento no puede ser posterior a la fecha del reporte.")

    st.divider()

    # Convenio (no va al PDF; solo se guarda en BD)
    st.markdown("#### Convenio:")
    corresponde_convenio = st.radio(
        "¿La capacitación corresponde a un convenio?",
        options=["No", "Sí"],
        horizontal=True,
        key="rep_corresponde_convenio",
    )
    numero_convenio = ""
    convenio_contraparte = ""
    if corresponde_convenio == "Sí":
        convenio_contraparte = st.selectbox(
            "Contraparte del convenio",
            options=CONTRAPARTES,
            index=None,
            placeholder="Escribe o selecciona la contraparte",
            key="rep_convenio_contraparte",
        ) or ""
        if convenio_contraparte:
            nums = CONTRAPARTE_NUMEROS[convenio_contraparte]
            if len(nums) == 1:
                numero_convenio = nums[0]
                st.info(f"**N.° de convenio:** {numero_convenio}")
            else:
                numero_convenio = st.selectbox(
                    "N.° de convenio (esta contraparte tiene varios)",
                    options=nums,
                    index=None,
                    placeholder="Selecciona el número",
                    key="rep_numero_convenio",
                ) or ""

    st.divider()

    # Nombre de los Capacitadores
    st.markdown("#### Nombre de los Capacitadores:")
    num_capacitadores = st.number_input(
        "¿Cuántos capacitadores participaron?",
        min_value=1, value=1, step=1, key="rep_num_cap",
    )
    capacitadores_lista: list[str] = []
    cols_cap = st.columns(min(int(num_capacitadores), 3))
    for i in range(int(num_capacitadores)):
        col_idx = i % 3
        with cols_cap[col_idx]:
            nombre_cap = st.text_input(
                f"Capacitador {i + 1}",
                key=f"rep_cap_{i}",
                placeholder="Nombre completo",
            )
            capacitadores_lista.append(nombre_cap)

    capacitadores_lista = [c for c in capacitadores_lista if c.strip()]
    capacitadores_str = "\n".join(f"• {c}" for c in capacitadores_lista) if capacitadores_lista else ""

    st.divider()

    # Elaborado por — dropdown con los capacitadores + opción "Otro"
    st.markdown("#### Elaborado por:")
    opciones_elaborado = (capacitadores_lista if capacitadores_lista
                          else ["(Ingresa los capacitadores primero)"])
    opciones_elaborado = opciones_elaborado + ["Otro"]
    elaborado_sel = st.selectbox(
        "Selecciona quién elaboró el reporte",
        options=opciones_elaborado,
        key="rep_elaborado",
        label_visibility="collapsed",
    )
    if elaborado_sel == "Otro":
        elaborado_por = st.text_input(
            "Nombre de quien elaboró el reporte",
            key="rep_elaborado_otro",
            placeholder="Nombre completo",
        )
    else:
        elaborado_por = elaborado_sel

    st.info(f"**Revisado y aprobado por:** {revisado_por}")

    st.divider()

    # Público Objetivo
    st.markdown("#### Público Objetivo:")
    publico_objetivo = st.text_area(
        "Describe el público objetivo",
        key="rep_publico",
        height=80,
        label_visibility="collapsed",
        placeholder="Ej: Productores agrícolas del cantón Portoviejo...",
    )

    st.divider()

    # Descripción de la Capacitación
    st.markdown("#### Descripción de la Capacitación:")
    descripcion = st.text_area(
        "Describe la capacitación",
        key="rep_descripcion",
        height=120,
        label_visibility="collapsed",
        placeholder="Detalla el contenido, metodología y resultados obtenidos...",
    )

    st.divider()

    # Observaciones — desplegable con opción "Otros"
    st.markdown("#### Observaciones:")
    obs_sel = st.selectbox(
        "Observaciones",
        options=["Ninguna", "Otros"],
        key="rep_obs_sel",
        label_visibility="collapsed",
    )
    if obs_sel == "Otros":
        observaciones = st.text_area(
            "Detalle la observación",
            key="rep_obs_otro",
            height=80,
            placeholder="Escribe la observación...",
        ).strip() or "Ninguna"
    else:
        observaciones = "Ninguna"

    # Adjuntos — desplegable de medios + opción "Otros" con ítems libres
    st.markdown("#### Adjuntos (medios de verificación):")
    adj_sel = st.multiselect(
        "Medios de verificación",
        options=["Registro de asistencia", "Fotografías", "Otros"],
        default=["Registro de asistencia", "Fotografías"],
        key="rep_adj_sel",
        label_visibility="collapsed",
    )
    items_adj = [m for m in adj_sel if m != "Otros"]
    if "Otros" in adj_sel:
        extra_adj = st.text_area(
            "Otros medios (uno por línea)",
            key="rep_adj_otro",
            height=80,
            placeholder="Ej:\nActa de la reunión\nMaterial entregado",
        )
        items_adj += [ln.strip() for ln in extra_adj.splitlines() if ln.strip()]

    adjuntos = _construir_adjuntos(nombre_institucion, items_adj)
    st.info(adjuntos)

    st.divider()

    # Número de personas capacitadas + Encuestas realizadas
    cnp1, cnp2 = st.columns(2)
    with cnp1:
        st.markdown("#### Número de Personas Capacitadas:")
        num_personas = st.number_input(
            "Ingresa el número total de personas capacitadas",
            min_value=0, value=0, step=1,
            key="rep_num_personas",
            label_visibility="collapsed",
        )
    with cnp2:
        st.markdown("#### Encuestas Realizadas:")
        encuestas_realizadas = st.number_input(
            "Ingresa el número de encuestas realizadas",
            min_value=0, value=0, step=1,
            key="rep_encuestas",
            label_visibility="collapsed",
        )

    st.divider()

    # Botón Generar Reporte — se inhabilita tras generar para no duplicar
    ya_generado = st.session_state.get("rep_pdf") is not None

    if st.button("📄 Generar Reporte de Capacitaciones", type="primary",
                 use_container_width=True, disabled=ya_generado):
        errores = _validar_campos_reporte(
            institucion_invitada, tema, capacitadores_lista, publico_objetivo, descripcion
        )
        if not tipos_inst_sel:
            errores.append("Selecciona el tipo de institución / asociación capacitada.")
        if tipo_evento_sel == "Otros" and not tipo_evento_otro:
            errores.append("Especifica el tipo de evento (opción 'Otros').")
        if corresponde_convenio == "Sí":
            if not convenio_contraparte:
                errores.append("Selecciona la contraparte del convenio.")
            elif not numero_convenio:
                errores.append("Selecciona el número de convenio.")
        if not provincia:
            errores.append("Selecciona la provincia.")
        if not canton:
            errores.append("Selecciona el cantón.")
        if tipos_inst_sel:
            # Contacto obligatorio para los 3 tipos
            if not contacto_nombre.strip():
                errores.append("Ingresa los nombres y apellidos del contacto.")
            cel = contacto_celular.strip()
            if not (cel.isdigit() and len(cel) == 10):
                errores.append("El celular debe tener exactamente 10 dígitos numéricos.")
            if "Asociación" in tipos_inst_sel:
                if not tipo_actividad_productiva.strip():
                    errores.append("Ingresa el tipo de actividad productiva.")
            if any(t != "Asociación" for t in tipos_inst_sel) and not publico_objetivo_capacitado.strip():
                errores.append("El campo 'Tipo de personal capacitado' es obligatorio.")
        if es_congreso:
            if not fecha_evento_inicio or not fecha_evento_fin:
                errores.append("Selecciona la fecha de inicio y fin del congreso.")
            elif fecha_evento_inicio == fecha_evento_fin:
                errores.append("Para congresos, selecciona un rango de dos o más días.")
        if fecha_evento_fin and fecha_evento_fin > fecha_reporte:
            errores.append("La fecha del evento no puede ser posterior a la fecha del reporte.")
        if errores:
            for e in errores:
                st.error(e)
        else:
            with get_connection() as con:
                numero = obtener_siguiente_numero_reporte(con)
                datos_db = {
                    "numero_reporte":           numero,
                    "year_reporte":             anio_actual,
                    "oficina":                  oficina_id,
                    "fecha_reporte":            str(fecha_reporte),
                    "tipo_evento":              tipo_evento,
                    "institucion_invitada":     institucion_invitada,
                    "tipo_institucion":         tipo_institucion,
                    "provincia":                provincia,
                    "canton":                   canton,
                    "contacto_nombre":          contacto_nombre,
                    "contacto_celular":         contacto_celular,
                    "tipo_actividad_productiva": tipo_actividad_productiva,
                    "publico_objetivo_capacitado": publico_objetivo_capacitado,
                    "fecha_evento":             fecha_evento_texto,
                    "hora_inicio":              hora_inicio_str,
                    "hora_fin":                 hora_fin_str,
                    "modalidad":                modalidad,
                    "tema":                     tema,
                    "capacitadores":            json.dumps(capacitadores_lista, ensure_ascii=False),
                    "publico_objetivo":         publico_objetivo,
                    "descripcion":              descripcion,
                    "observaciones":            observaciones,
                    "adjuntos":                 adjuntos,
                    "elaborado_por":            elaborado_por,
                    "revisado_por":             revisado_por,
                    "num_personas_capacitadas": int(num_personas),
                    "encuestas_realizadas":     int(encuestas_realizadas),
                    "corresponde_convenio":     corresponde_convenio,
                    "numero_convenio":          numero_convenio,
                    "convenio_contraparte":     convenio_contraparte,
                }
                insertar_reporte_capacitacion(con, datos_db)

            pdf_bytes = generar_reporte_drac(
                numero_reporte=numero,
                year_reporte=anio_actual,
                fecha_reporte=str(fecha_reporte),
                tipo_evento=tipo_evento,
                institucion_invitada=institucion_invitada,
                fecha_evento=fecha_evento_texto,
                hora_inicio=hora_inicio_str,
                hora_fin=hora_fin_str,
                modalidad=modalidad,
                tema=tema,
                capacitadores=capacitadores_str,
                publico_objetivo=publico_objetivo,
                descripcion=descripcion,
                observaciones=observaciones,
                adjuntos=adjuntos,
                elaborado_por=elaborado_por,
                revisado_por=revisado_por,
                fecha_elaboracion=str(fecha_reporte),
                lineas_institucion=lineas_institucion,
                area_elaborado=area_elaborado,
                num_personas_capacitadas=int(num_personas),
                tipo_institucion=tipo_institucion,
                provincia=provincia,
                canton=canton,
                publico_objetivo_capacitado=publico_objetivo_capacitado,
            )

            # Guardar en sesión para inhabilitar el botón y mostrar la descarga
            st.session_state["rep_pdf"] = {
                "bytes": pdf_bytes, "numero": numero, "year": anio_actual,
            }
            st.rerun()

    # Si ya se generó un reporte: mostrar descarga + opción de empezar otro
    if st.session_state.get("rep_pdf"):
        info = st.session_state["rep_pdf"]
        st.success(f"✅ Reporte **DRAC-{info['numero']:03d}-{info['year']}** generado correctamente.")
        st.download_button(
            label=f"📥 Descargar DRAC-{info['numero']:03d}-{info['year']}.pdf",
            data=info["bytes"],
            file_name=f"DRAC-{info['numero']:03d}-{info['year']}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.info("El botón de generar está deshabilitado para no crear un reporte duplicado. "
                "Para registrar otro reporte, pulsa **Generar un nuevo reporte**.")
        if st.button("✏️ Generar un nuevo reporte", use_container_width=True):
            del st.session_state["rep_pdf"]
            st.rerun()

    # Historial de reportes de la oficina
    st.divider()
    st.subheader("Reportes generados en esta oficina")
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(con, oficina=oficina_id)

    if reportes:
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in reportes])
        cols_mostrar = ["numero_reporte", "year_reporte", "fecha_reporte",
                        "tipo_evento", "tema", "num_personas_capacitadas"]
        cols_ex = [c for c in cols_mostrar if c in df.columns]
        st.dataframe(
            df[cols_ex].rename(columns={
                "numero_reporte": "N.° Reporte",
                "year_reporte": "Año",
                "fecha_reporte": "Fecha",
                "tipo_evento": "Tipo Evento",
                "tema": "Tema",
                "num_personas_capacitadas": "Personas",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Aún no hay reportes registrados para esta oficina.")


# ---------------------------------------------------------------------------
# TAB 2 — Actas de Asambleas Productivas
# ---------------------------------------------------------------------------

def _codigo_asamblea(numero) -> str:
    """Formatea el código de acta a partir del número secuencial."""
    try:
        return f"Asamblea Productiva {int(numero):03d}"
    except (TypeError, ValueError):
        return "Asamblea Productiva —"


def _fmt_responsables(v) -> str:
    """Convierte el JSON de responsables guardado en 'a / b' (tolera texto plano)."""
    if not v:
        return ""
    try:
        val = json.loads(v)
        if isinstance(val, list):
            return " / ".join(str(x) for x in val)
    except (ValueError, TypeError):
        pass
    return str(v)


def _parse_compromisos(v) -> list[dict]:
    """Devuelve la lista de compromisos [{'texto','estado'}] tolerando texto plano viejo."""
    if not v:
        return []
    try:
        val = json.loads(v)
        if isinstance(val, list):
            out = []
            for c in val:
                if isinstance(c, dict) and c.get("texto"):
                    out.append({
                        "texto":  str(c["texto"]),
                        "estado": c.get("estado") or "Pendiente",
                    })
                elif isinstance(c, str) and c.strip():
                    out.append({"texto": c.strip(), "estado": "Pendiente"})
            return out
    except (ValueError, TypeError):
        pass
    # Texto plano (acta vieja): un único compromiso
    return [{"texto": str(v).strip(), "estado": "Pendiente"}]


def _fmt_compromisos(v) -> str:
    """Resume los compromisos como 'texto1 (Pendiente); texto2 (Cumplido)'."""
    comps = _parse_compromisos(v)
    return "; ".join(f"{c['texto']} ({c['estado']})" for c in comps)


def _estado_global_compromisos(comps: list[dict]) -> str:
    """'Pendiente' si algún compromiso está pendiente; si no, 'Cumplido'."""
    if not comps:
        return "Cumplido"
    return "Pendiente" if any(c.get("estado") != "Cumplido" for c in comps) else "Cumplido"


def _tab_asamblea_productiva(oficina_id: str, oficina_nombre: str) -> None:
    import pandas as pd

    st.subheader("Actas de Asambleas Productivas")
    st.markdown("Registra el acta completa de cada asamblea productiva.")
    st.divider()

    cfg = _cfg_oficina(oficina_id)

    # Preview del número secuencial (global, por orden de ingreso)
    with get_connection() as _con:
        ultimo = _con.execute(
            "SELECT ultimo_numero FROM contador_asamblea WHERE id = 1"
        ).fetchone()
    proximo = (ultimo["ultimo_numero"] if ultimo else 17) + 1
    st.info(f"Se registrará: **{_codigo_asamblea(proximo)}**")

    # --- Datos generales del acta ---
    col_fecha, col_personas = st.columns(2)
    with col_fecha:
        fecha_asamblea = st.date_input(
            "Fecha de la Asamblea", value=date.today(), key="asm_fecha")
    with col_personas:
        num_asistentes = st.number_input(
            "N.° de participantes", min_value=0, value=0, step=1, key="asm_num_asistentes")

    ch1, ch2 = st.columns(2)
    with ch1:
        hora_inicio_val = st.time_input("Hora de inicio", value=time(9, 0), key="asm_hora_ini")
    with ch2:
        hora_cierre_val = st.time_input("Hora de cierre", value=time(12, 0), key="asm_hora_fin")

    ca1, ca2 = st.columns(2)
    with ca1:
        asociacion = st.text_input("Asociación / Agrupación", key="asm_asociacion")
    with ca2:
        lugar = st.text_input("Lugar de realización", key="asm_lugar")

    # Provincia, Cantón y Parroquia/Recinto — desplegables encadenados
    ub1, ub2, ub3 = st.columns(3)
    with ub1:
        asm_provincia = st.selectbox(
            "Provincia", options=sorted(PROVINCIAS_CANTONES),
            index=None, placeholder="Selecciona la provincia", key="asm_provincia",
        )
    asm_cantones_opts = sorted(PROVINCIAS_CANTONES[asm_provincia]) if asm_provincia else []
    if (st.session_state.get("asm_canton") is not None
            and st.session_state.get("asm_canton") not in asm_cantones_opts):
        del st.session_state["asm_canton"]
    with ub2:
        asm_canton = st.selectbox(
            "Cantón", options=asm_cantones_opts,
            index=None, placeholder="Selecciona el cantón", key="asm_canton",
        )
    with ub3:
        asm_parroquia = st.text_input("Parroquia / Recinto", key="asm_parroquia")

    tematica = st.text_input("Tema tratado", key="asm_tematica")

    # Datos de contacto (obligatorios)
    st.markdown("**Datos de contacto** (obligatorios)")
    dc1, dc2 = st.columns(2)
    with dc1:
        contacto_nombre = st.text_input("Nombres y apellidos del contacto", key="asm_contacto_nombre")
    with dc2:
        contacto_celular = st.text_input("Celular", key="asm_contacto_celular")
    contacto_institucion = st.text_input(
        "Nombre de la institución a la que pertenece", key="asm_contacto_inst")

    # Instituciones invitadas — campos separados
    st.markdown("**Instituciones invitadas**")
    num_inst = st.number_input(
        "¿Cuántas instituciones invitadas?",
        min_value=1, max_value=15, value=1, step=1, key="asm_num_inst",
    )
    instituciones_lista: list[str] = []
    for i in range(int(num_inst)):
        inst = st.text_input(
            f"Institución {i + 1}", key=f"asm_inst_{i}",
            placeholder="Nombre de la institución",
        )
        if inst.strip():
            instituciones_lista.append(inst.strip())
    instituciones_str = json.dumps(instituciones_lista, ensure_ascii=False) if instituciones_lista else None

    # --- Responsable(s) de la asamblea ---
    st.markdown("**Responsable(s) de la asamblea**")
    num_responsables = st.number_input(
        "¿Cuántos responsables participaron?",
        min_value=1, max_value=10, value=1, step=1, key="asm_num_resp",
    )
    responsables_lista: list[str] = []
    cols_resp = st.columns(min(int(num_responsables), 3))
    for i in range(int(num_responsables)):
        with cols_resp[i % 3]:
            nombre_resp = st.text_input(
                f"Responsable {i + 1}", key=f"asm_resp_{i}", placeholder="Nombre completo")
            responsables_lista.append(nombre_resp)
    responsables_lista = [r.strip() for r in responsables_lista if r.strip()]
    responsables_str = json.dumps(responsables_lista, ensure_ascii=False) if responsables_lista else None

    st.divider()

    # --- Secciones narrativas del acta ---
    antecedentes = st.text_area("Antecedentes", key="asm_antecedentes")
    objetivo = st.text_area("Objetivo de la Asamblea", key="asm_objetivo")
    temas_abordados = st.text_area("Temas abordados", key="asm_temas_abordados")

    st.divider()

    # --- Compromisos (multi, con institución, funcionario, fecha tentativa y estado) ---
    st.markdown("**Compromisos generados**")
    num_compromisos = st.number_input(
        "¿Cuántos compromisos / acuerdos?",
        min_value=1, max_value=15, value=1, step=1, key="asm_num_comp",
    )
    compromisos_lista: list[dict] = []
    for i in range(int(num_compromisos)):
        st.markdown(f"**Compromiso {i + 1}**")
        cc1, cc2 = st.columns([3, 1])
        with cc1:
            texto_comp = st.text_input(
                f"Descripción del compromiso {i + 1}", key=f"asm_comp_txt_{i}",
                placeholder="Describe el acuerdo / compromiso", label_visibility="collapsed")
        with cc2:
            estado_comp = st.selectbox(
                "Estado", options=["Pendiente", "Cumplido"], key=f"asm_comp_est_{i}")
        cd1, cd2, cd3 = st.columns(3)
        with cd1:
            opciones_inst = (instituciones_lista or []) + ["Otro"]
            inst_sel = st.selectbox(
                "Institución responsable", options=opciones_inst, key=f"asm_comp_inst_sel_{i}")
            if inst_sel == "Otro":
                inst_comp = st.text_input(
                    "Nombre de la institución", key=f"asm_comp_inst_otro_{i}",
                    placeholder="Ej: SCE, GAD...").strip()
            else:
                inst_comp = inst_sel
        with cd2:
            func_comp = st.text_input(
                "Funcionario seguimiento", key=f"asm_comp_func_{i}", placeholder="Nombre completo")
        with cd3:
            fecha_tent = st.date_input(
                "Fecha tentativa", key=f"asm_comp_fecha_{i}", value=None)
        if texto_comp.strip():
            compromisos_lista.append({
                "texto": texto_comp.strip(),
                "estado": estado_comp,
                "institucion": inst_comp.strip() or "",
                "funcionario_seguimiento": func_comp.strip() or "",
                "fecha_tentativa": str(fecha_tent) if fecha_tent else "",
            })

    acuerdos_str = json.dumps(compromisos_lista, ensure_ascii=False) if compromisos_lista else None
    estado_global = _estado_global_compromisos(compromisos_lista)

    st.divider()

    # --- Responsable(s) del seguimiento (dropdown + Otros, multi) ---
    st.markdown("**Responsable(s) del seguimiento**")
    num_resp_seg = st.number_input(
        "¿Cuántos responsables del seguimiento?",
        min_value=1, max_value=10, value=1, step=1, key="asm_num_resp_seg",
    )
    opciones_seg = (responsables_lista or []) + ["Otros"]
    resp_seg_lista: list[str] = []
    for i in range(int(num_resp_seg)):
        sel = st.selectbox(
            f"Responsable del seguimiento {i + 1}", options=opciones_seg,
            key=f"asm_resp_seg_sel_{i}")
        if sel == "Otros":
            otro = st.text_input(
                f"Nombre del responsable del seguimiento {i + 1}",
                key=f"asm_resp_seg_otro_{i}", placeholder="Nombre completo")
            if otro.strip():
                resp_seg_lista.append(otro.strip())
        elif sel:
            resp_seg_lista.append(sel)
    resp_seg_lista = list(dict.fromkeys(resp_seg_lista))
    resp_seg_str = json.dumps(resp_seg_lista, ensure_ascii=False) if resp_seg_lista else None

    # --- Observaciones (Ninguna / Otro) ---
    obs_opcion = st.selectbox("Observaciones", options=["Ninguna", "Otro"], key="asm_obs_opcion")
    if obs_opcion == "Otro":
        observaciones = st.text_area("Detalle de la observación", key="asm_observaciones").strip() or "Ninguna"
    else:
        observaciones = "Ninguna"

    # --- Cierre y seguimiento (default / Otro) ---
    _CIERRE_DEFAULT = (
        "Los asistentes expresan su conformidad con los compromisos señalados. "
        "La Superintendencia de Competencia Económica realizará el seguimiento "
        "técnico de los compromisos previamente establecidos."
    )
    cierre_opcion = st.selectbox(
        "Cierre y seguimiento",
        options=[_CIERRE_DEFAULT, "Otro"],
        key="asm_cierre_opcion",
    )
    if cierre_opcion == "Otro":
        cierre_seguimiento = st.text_area(
            "Texto de cierre y seguimiento", key="asm_cierre_texto").strip() or _CIERRE_DEFAULT
    else:
        cierre_seguimiento = _CIERRE_DEFAULT

    st.divider()

    # --- Flujo post-registro: tras registrar, solo se muestra el botón de descarga ---
    if st.session_state.get("asm_registrado"):
        pdf_bytes = st.session_state.get("asm_pdf_bytes", b"")
        num_reg = st.session_state.get("asm_num_registrado", 0)
        st.success(f"✅ {_codigo_asamblea(num_reg)} registrada exitosamente.")
        if pdf_bytes:
            st.download_button(
                "📄 Descargar Acta en PDF",
                pdf_bytes,
                file_name=f"Acta_Asamblea_Productiva_{num_reg:03d}.pdf",
                mime="application/pdf",
            )
        if st.button("📝 Registrar otra asamblea", type="secondary", use_container_width=True):
            st.session_state.pop("asm_registrado", None)
            st.session_state.pop("asm_pdf_bytes", None)
            st.session_state.pop("asm_num_registrado", None)
            st.rerun()
    elif st.button("✅ Registrar Asamblea Productiva", type="primary", use_container_width=True):
        if num_asistentes <= 0:
            st.error("Ingresa un número de participantes mayor a 0.")
        elif not responsables_lista:
            st.error("Ingresa al menos un responsable.")
        elif not (contacto_celular.strip().isdigit() and len(contacto_celular.strip()) == 10):
            st.error("El celular debe tener exactamente 10 dígitos numéricos.")
        else:
            with get_connection() as con:
                numero = obtener_siguiente_numero_asamblea(con)
                insertar_asamblea_productiva(con, {
                    "numero_reporte":          numero,
                    "oficina":                 oficina_id,
                    "fecha":                   str(fecha_asamblea),
                    "num_asistentes":          int(num_asistentes),
                    "responsables":            responsables_str,
                    "tematica":                tematica.strip() or None,
                    "asociacion_agrupacion":   asociacion.strip() or None,
                    "lugar_realizacion":       lugar.strip() or None,
                    "instituciones_invitadas": instituciones_str,
                    "acuerdos_compromisos":    acuerdos_str,
                    "responsable_seguimiento": resp_seg_str,
                    "estado_compromisos":      estado_global,
                    "observaciones":           observaciones,
                    "hora_inicio":             hora_inicio_val.strftime("%H:%M"),
                    "hora_cierre":             hora_cierre_val.strftime("%H:%M"),
                    "antecedentes":            antecedentes.strip() or None,
                    "objetivo":                objetivo.strip() or None,
                    "temas_abordados":         temas_abordados.strip() or None,
                    "cierre_seguimiento":      cierre_seguimiento,
                    "contacto_nombre":         contacto_nombre.strip() or None,
                    "contacto_celular":        contacto_celular.strip() or None,
                    "contacto_institucion":    contacto_institucion.strip() or None,
                    "provincia":               asm_provincia or None,
                    "canton":                  asm_canton or None,
                    "parroquia_recinto":       asm_parroquia.strip() or None,
                })

            from utils.acta_asamblea_pdf import generar_acta_asamblea_pdf
            pdf_bytes = generar_acta_asamblea_pdf(
                numero_reporte=numero,
                year_reporte=date.today().year,
                fecha=str(fecha_asamblea),
                hora_inicio=hora_inicio_val.strftime("%H:%M"),
                hora_cierre=hora_cierre_val.strftime("%H:%M"),
                lugar_realizacion=lugar.strip(),
                instituciones_invitadas="; ".join(instituciones_lista) if instituciones_lista else "",
                asociacion_agrupacion=asociacion.strip(),
                tematica=tematica.strip(),
                antecedentes=antecedentes.strip(),
                objetivo=objetivo.strip(),
                temas_abordados=temas_abordados.strip(),
                compromisos=compromisos_lista,
                observaciones=observaciones,
                cierre_seguimiento=cierre_seguimiento,
                responsables=responsables_lista,
                responsable_seguimiento=resp_seg_lista,
                num_asistentes=int(num_asistentes),
                lineas_institucion=cfg["lineas_institucion"],
                area_elaborado=cfg["area_elaborado"],
            )
            st.session_state["asm_registrado"] = True
            st.session_state["asm_pdf_bytes"] = pdf_bytes
            st.session_state["asm_num_registrado"] = numero
            st.rerun()

    st.divider()
    st.subheader("Asambleas registradas en esta oficina")
    with get_connection() as con:
        asambleas = consultar_asambleas_productivas(con, oficina=oficina_id)

    if asambleas:
        df = pd.DataFrame([dict(a) for a in asambleas])
        if "responsables" in df.columns:
            df["responsables"] = df["responsables"].map(_fmt_responsables)
        if "responsable_seguimiento" in df.columns:
            df["responsable_seguimiento"] = df["responsable_seguimiento"].map(_fmt_responsables)
        if "instituciones_invitadas" in df.columns:
            df["instituciones_invitadas"] = df["instituciones_invitadas"].map(_fmt_responsables)
        if "acuerdos_compromisos" in df.columns:
            df["acuerdos_compromisos"] = df["acuerdos_compromisos"].map(_fmt_compromisos)
        if "numero_reporte" in df.columns:
            df["numero_reporte"] = df["numero_reporte"].map(_codigo_asamblea)
        cols_ex = [c for c in [
            "numero_reporte", "fecha", "asociacion_agrupacion", "tematica", "responsables",
            "num_asistentes", "lugar_realizacion", "instituciones_invitadas",
            "acuerdos_compromisos", "responsable_seguimiento", "estado_compromisos",
            "observaciones", "fecha_registro",
        ] if c in df.columns]
        st.dataframe(
            df[cols_ex].rename(columns={
                "numero_reporte": "N° Reporte",
                "fecha": "Fecha Asamblea",
                "asociacion_agrupacion": "Asociación/Agrupación",
                "tematica": "Tema Tratado",
                "responsables": "Responsable",
                "num_asistentes": "# Participantes",
                "lugar_realizacion": "Lugar de Realización",
                "instituciones_invitadas": "Instituciones Invitadas",
                "acuerdos_compromisos": "Acuerdos y Compromisos",
                "responsable_seguimiento": "Responsable del Seguimiento",
                "estado_compromisos": "Estado de los Compromisos",
                "observaciones": "Observaciones",
                "fecha_registro": "Registrado",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Aún no hay asambleas registradas para esta oficina.")

    # --- Compromisos pendientes (seguimiento) ---------------------------------
    st.divider()
    st.subheader("Compromisos pendientes")
    pendientes = [
        dict(a) for a in (asambleas or [])
        if (dict(a).get("estado_compromisos") or "Pendiente") == "Pendiente"
    ]
    if pendientes:
        opciones = {
            f"{_codigo_asamblea(a['numero_reporte'])} — {a.get('tematica') or 's/tema'}": a
            for a in pendientes
        }
        sel = st.selectbox(
            "Selecciona el acta con compromisos pendientes",
            options=list(opciones.keys()),
            key="asm_pendiente_sel",
        )
        acta = opciones[sel]
        comps = _parse_compromisos(acta.get("acuerdos_compromisos"))
        if acta.get("responsable_seguimiento"):
            st.markdown(f"**Responsable del seguimiento:** {_fmt_responsables(acta['responsable_seguimiento'])}")

        st.markdown("**Marca los compromisos cumplidos:**")
        nuevos_estados: list[str] = []
        for j, c in enumerate(comps):
            cumplido = st.checkbox(
                c["texto"],
                value=(c["estado"] == "Cumplido"),
                key=f"asm_comp_chk_{acta['id']}_{j}",
            )
            nuevos_estados.append("Cumplido" if cumplido else "Pendiente")

        if st.button("💾 Guardar estado de compromisos", type="primary", key="asm_guardar_comp"):
            comps_actualizados = [
                {"texto": c["texto"], "estado": nuevos_estados[j]}
                for j, c in enumerate(comps)
            ]
            estado_overall = _estado_global_compromisos(comps_actualizados)
            with get_connection() as con:
                actualizar_compromisos(
                    con, acta["id"],
                    json.dumps(comps_actualizados, ensure_ascii=False),
                    estado_overall,
                )
            st.success(f"{_codigo_asamblea(acta['numero_reporte'])}: estado de compromisos actualizado.")
            st.rerun()
    else:
        st.info("No hay compromisos pendientes en esta oficina.")


# ---------------------------------------------------------------------------
# TAB 3 — Estadísticas del Mes
# ---------------------------------------------------------------------------

def _tab_estadisticas(oficina_id: str, oficina_nombre: str) -> None:
    st.subheader("Estadísticas Mensuales")
    st.markdown("Resumen de actividades del mes seleccionado.")
    st.divider()

    es_master = st.session_state.get("oficina_rol", "") == "master"

    hoy = date.today()

    # Guayaquil (master) puede elegir ver todas las oficinas o una específica
    if es_master:
        _OPCIONES_OFICINA = {
            "todas":      "Todas las oficinas",
            "guayaquil":  "Guayaquil",
            "manabi":     "Portoviejo",
            "loja":       "Loja",
            "cuenca":     "Cuenca",
        }
        col_of, col_anio, col_mes = st.columns(3)
        with col_of:
            sel_of = st.selectbox(
                "Oficina",
                options=list(_OPCIONES_OFICINA.keys()),
                format_func=lambda k: _OPCIONES_OFICINA[k],
                key="stats_oficina",
            )
        oficina_filtro = None if sel_of == "todas" else sel_of
        label_oficina  = _OPCIONES_OFICINA[sel_of]
    else:
        col_anio, col_mes = st.columns(2)
        oficina_filtro = oficina_id
        label_oficina  = oficina_nombre

    with col_anio:
        anio_sel = st.selectbox(
            "Año",
            options=list(range(hoy.year, hoy.year - 5, -1)),
            index=0,
            key="stats_anio",
        )
    with col_mes:
        mes_sel = st.selectbox(
            "Mes",
            options=list(_MESES_ESP.keys()),
            format_func=lambda m: _MESES_ESP[m],
            index=hoy.month - 1,
            key="stats_mes",
        )

    with get_connection() as con:
        stats = estadisticas_mensuales(
            con,
            oficina=oficina_filtro,
            anio=int(anio_sel),
            mes=int(mes_sel),
        )

    mes_label = f"{_MESES_ESP[int(mes_sel)]} {int(anio_sel)}"
    st.markdown(f"### Resultados — {label_oficina} · {mes_label}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Capacitaciones realizadas",     stats["num_capacitaciones"])
    c2.metric("Personas capacitadas",          stats["personas_capacitadas"])
    c3.metric("Asambleas productivas",         stats["num_asambleas"])
    c4.metric("Personas en asambleas",         stats["personas_asambleas"])

    st.divider()
    st.markdown("**Detalle de Capacitaciones del mes:**")
    with get_connection() as con:
        reportes = consultar_reportes_capacitacion(
            con, oficina=oficina_filtro, anio=int(anio_sel), mes=int(mes_sel)
        )

    if reportes:
        import pandas as pd
        df_r = pd.DataFrame([dict(r) for r in reportes])
        # Cuando se muestran todas las oficinas, incluir columna "oficina"
        cols_base = ["numero_reporte", "fecha_reporte", "tipo_evento",
                     "tema", "elaborado_por", "num_personas_capacitadas"]
        if es_master and oficina_filtro is None:
            cols_base = ["oficina"] + cols_base
        cols = [c for c in cols_base if c in df_r.columns]
        st.dataframe(
            df_r[cols].rename(columns={
                "oficina":                  "Oficina",
                "numero_reporte":           "N.° Reporte",
                "fecha_reporte":            "Fecha",
                "tipo_evento":              "Tipo",
                "tema":                     "Tema",
                "elaborado_por":            "Elaborado por",
                "num_personas_capacitadas": "Personas",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No hay capacitaciones en el período seleccionado.")

    st.markdown("**Detalle de Asambleas del mes:**")
    with get_connection() as con:
        asambleas = consultar_asambleas_productivas(
            con, oficina=oficina_filtro, anio=int(anio_sel), mes=int(mes_sel)
        )

    if asambleas:
        import pandas as pd
        df_a = pd.DataFrame([dict(a) for a in asambleas])
        cols_a_base = ["fecha", "num_asistentes"]
        if es_master and oficina_filtro is None:
            cols_a_base = ["oficina"] + cols_a_base
        cols_a = [c for c in cols_a_base if c in df_a.columns]
        st.dataframe(
            df_a[cols_a].rename(columns={
                "oficina":       "Oficina",
                "fecha":         "Fecha",
                "num_asistentes": "Personas Asistentes",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No hay asambleas registradas en el período seleccionado.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalizar_rango_fechas(valor) -> tuple[date | None, date | None]:
    if isinstance(valor, (list, tuple)):
        if not valor:
            return None, None
        inicio = valor[0]
        fin = valor[1] if len(valor) > 1 else None
        if inicio and fin and fin < inicio:
            inicio, fin = fin, inicio
        return inicio, fin
    if isinstance(valor, date):
        return valor, valor
    return None, None


def _formatear_fecha_evento_para_guardar(
    inicio: date | None,
    fin: date | None,
) -> str:
    if not inicio:
        return ""
    if fin and fin != inicio:
        return f"{inicio.isoformat()} al {fin.isoformat()}"
    return inicio.isoformat()


def _validar_campos_reporte(
    institucion: str,
    tema: str,
    capacitadores: list[str],
    publico: str,
    descripcion: str,
) -> list[str]:
    errores = []
    if not institucion.strip():
        errores.append("El campo 'Nombre de la institución / asociación capacitada' es obligatorio.")
    if not tema.strip():
        errores.append("El campo 'Tema' es obligatorio.")
    if not capacitadores:
        errores.append("Ingresa al menos un capacitador.")
    if not publico.strip():
        errores.append("El campo 'Público Objetivo' es obligatorio.")
    if not descripcion.strip():
        errores.append("El campo 'Descripción de la Capacitación' es obligatorio.")
    return errores
