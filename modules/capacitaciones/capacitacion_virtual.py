"""
capacitacion_virtual.py — Módulo de capacitación virtual con video, test y certificado.

Flujo:
1. Registro del participante (primer nombre, segundo nombre, primer apellido,
   segundo apellido, cédula).
2. Visualización del video de YouTube embebido.
3. Confirmación de visualización y acceso al test.
4. Test de 5 preguntas sobre competencia económica (2 puntos c/u = 10 pts).
5. Si calificación ≥ 8/10 → descarga del certificado .docx.
"""

from __future__ import annotations

import uuid
from datetime import date

import streamlit as st

from utils.docx_generator import generar_certificado_docx, generar_certificado_pdf

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
_NOMBRE_CURSO   = "Competencia Económica: Fundamentos y Marco Regulatorio"
_VIDEO_ID        = "rcztQzGXYvI"
_VIDEO_URL       = f"https://www.youtube.com/watch?v={_VIDEO_ID}&t=924s"
_VIDEO_THUMBNAIL = f"https://img.youtube.com/vi/{_VIDEO_ID}/hqdefault.jpg"
_NOTA_APROBACION = 8   # calificación mínima para obtener certificado (≥ 8/10)

# ---------------------------------------------------------------------------
# Banco de preguntas (opciones A-D, respuesta correcta = índice 0-based)
# ---------------------------------------------------------------------------
_PREGUNTAS: list[dict] = [
    {
        "enunciado": "¿Qué busca proteger la competencia económica en un mercado?",
        "opciones": [
            "Que una sola empresa domine todo el mercado",
            "Que existan condiciones justas para competir",
            "Que los precios siempre sean iguales",
            "Que el Estado fije todos los precios",
        ],
        "correcta": 1,   # índice de la opción correcta (0-based)
    },
    {
        "enunciado": "¿Cuál de los siguientes es un ejemplo de práctica anticompetitiva?",
        "opciones": [
            "Mejorar la calidad de un producto",
            "Bajar precios por mayor eficiencia",
            "Acuerdo entre competidores para fijar precios",
            "Hacer publicidad de un producto",
        ],
        "correcta": 2,
    },
    {
        "enunciado": "¿Qué es un monopolio?",
        "opciones": [
            "Cuando hay muchas empresas pequeñas compitiendo",
            "Cuando una sola empresa controla la oferta de un bien o servicio",
            "Cuando los consumidores deciden el precio",
            "Cuando el mercado está regulado por ley",
        ],
        "correcta": 1,
    },
    {
        "enunciado": "¿Por qué puede ser perjudicial la falta de competencia?",
        "opciones": [
            "Porque suele generar mejores precios para el consumidor",
            "Porque puede reducir la innovación y aumentar los precios",
            "Porque beneficia siempre a los consumidores",
            "Porque hace que existan más opciones en el mercado",
        ],
        "correcta": 1,
    },
    {
        "enunciado": "¿Qué hacen normalmente las autoridades de competencia?",
        "opciones": [
            "Promueven acuerdos secretos entre empresas",
            "Vigilan y sancionan conductas que afectan la competencia",
            "Obligan a todas las empresas a tener el mismo tamaño",
            "Deciden qué productos deben comprar los consumidores",
        ],
        "correcta": 1,
    },
]

_LETRAS = ["A", "B", "C", "D"]


# ---------------------------------------------------------------------------
# Helpers de session_state
# ---------------------------------------------------------------------------
def _get(key: str, default=None):
    return st.session_state.get(key, default)


def _set(key: str, value) -> None:
    st.session_state[key] = value


def _reset_modulo() -> None:
    """Borra todas las claves del módulo para reiniciar el flujo."""
    for k in [
        "cv_registrado", "cv_primer_nombre", "cv_segundo_nombre",
        "cv_primer_apellido", "cv_segundo_apellido", "cv_cedula",
        "cv_nombre_completo", "cv_paso", "cv_video_confirmado",
        "cv_respuestas", "cv_calificacion", "cv_codigo",
    ]:
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Punto de entrada del módulo
# ---------------------------------------------------------------------------
def mostrar_capacitacion_virtual() -> None:
    st.title("🎓 Capacitación Virtual")
    st.markdown(f"**Curso:** {_NOMBRE_CURSO}")
    st.divider()

    paso = _get("cv_paso", 0)

    if paso == 0:
        _paso_registro()
    elif paso == 1:
        _paso_video()
    elif paso == 2:
        _paso_test()
    elif paso == 3:
        _paso_resultado()


# ---------------------------------------------------------------------------
# Paso 0 — Registro / identificación del participante
# ---------------------------------------------------------------------------
def _paso_registro() -> None:
    st.subheader("📝 Registro del participante")
    st.markdown(
        "Completa el formulario con tus datos personales para acceder a la capacitación."
    )

    with st.form("form_registro_cv", clear_on_submit=False):
        col1, col2 = st.columns(2)

        with col1:
            primer_nombre   = st.text_input("Primer nombre *", placeholder="Ej. María")
            primer_apellido = st.text_input("Primer apellido *", placeholder="Ej. García")

        with col2:
            segundo_nombre   = st.text_input("Segundo nombre *", placeholder="Ej. Elena")
            segundo_apellido = st.text_input("Segundo apellido *", placeholder="Ej. López")

        cedula = st.text_input(
            "Número de cédula *",
            placeholder="Ej. 1712345678",
            max_chars=13,
        )

        st.markdown("")
        enviado = st.form_submit_button(
            "Registrarme e ingresar al curso →",
            use_container_width=True,
            type="primary",
        )

    if enviado:
        errores = _validar_registro(
            primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, cedula
        )
        if errores:
            for e in errores:
                st.error(e)
            return

        nombre_completo = (
            f"{primer_nombre.strip().title()} {segundo_nombre.strip().title()} "
            f"{primer_apellido.strip().title()} {segundo_apellido.strip().title()}"
        )

        _set("cv_primer_nombre",   primer_nombre.strip().title())
        _set("cv_segundo_nombre",  segundo_nombre.strip().title())
        _set("cv_primer_apellido", primer_apellido.strip().title())
        _set("cv_segundo_apellido", segundo_apellido.strip().title())
        _set("cv_cedula",          cedula.strip())
        _set("cv_nombre_completo", nombre_completo)
        _set("cv_registrado",      True)
        _set("cv_paso",            1)
        st.rerun()


def _validar_registro(
    primer_nombre: str,
    segundo_nombre: str,
    primer_apellido: str,
    segundo_apellido: str,
    cedula: str,
) -> list[str]:
    errores: list[str] = []

    for campo, valor in [
        ("Primer nombre",   primer_nombre),
        ("Segundo nombre",  segundo_nombre),
        ("Primer apellido", primer_apellido),
        ("Segundo apellido", segundo_apellido),
    ]:
        v = valor.strip()
        if not v:
            errores.append(f"El campo '{campo}' es obligatorio.")
        elif not v.replace(" ", "").isalpha():
            errores.append(f"'{campo}' solo debe contener letras.")
        elif len(v) < 2:
            errores.append(f"'{campo}' debe tener al menos 2 caracteres.")

    ced = cedula.strip()
    if not ced:
        errores.append("El número de cédula es obligatorio.")
    elif not ced.isdigit():
        errores.append("La cédula solo debe contener dígitos.")
    elif len(ced) not in (10, 13):
        errores.append("La cédula debe tener 10 o 13 dígitos.")

    return errores


# ---------------------------------------------------------------------------
# Paso 1 — Video de YouTube
# ---------------------------------------------------------------------------
def _paso_video() -> None:
    nombre = _get("cv_nombre_completo", "")
    st.subheader(f"👋 Bienvenido/a, {nombre}")
    st.markdown(
        "Antes de realizar el test, **mira el video completo** sobre competencia económica. "
        "Una vez finalizado, confirma que lo has visto para continuar."
    )
    st.markdown("")

    # Thumbnail clicable que abre YouTube en el navegador / app nativa
    st.markdown(
        f"""
        <a href="{_VIDEO_URL}" target="_blank" rel="noopener noreferrer"
           style="display:block;position:relative;border-radius:10px;
                  overflow:hidden;cursor:pointer;text-decoration:none;">
            <img src="{_VIDEO_THUMBNAIL}"
                 style="width:100%;display:block;border-radius:10px;" />
            <div style="position:absolute;top:50%;left:50%;
                        transform:translate(-50%,-50%);
                        background:rgba(255,0,0,0.85);border-radius:50%;
                        width:64px;height:64px;display:flex;
                        align-items:center;justify-content:center;">
                <svg viewBox="0 0 24 24" width="32" height="32" fill="white">
                    <path d="M8 5v14l11-7z"/>
                </svg>
            </div>
        </a>
        <p style="text-align:center;color:#888;font-size:0.85rem;margin-top:6px;">
            Toca la imagen para abrir el video en YouTube
        </p>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        "📺 El video se abrirá en YouTube (o en la app de YouTube si la tienes instalada). "
        "Una vez que lo hayas visto completo, regresa aquí y presiona el botón para continuar."
    )
    st.markdown("")

    if st.button(
        "✅ Ya vi el video completo — Continuar al test",
        type="primary",
        use_container_width=True,
    ):
        _set("cv_video_confirmado", True)
        _set("cv_paso", 2)
        st.rerun()

    if st.button("← Volver al registro", use_container_width=True):
        _reset_modulo()
        st.rerun()


# ---------------------------------------------------------------------------
# Paso 2 — Test de conocimientos
# ---------------------------------------------------------------------------
def _paso_test() -> None:
    st.subheader("📋 Test de conocimientos")
    st.markdown(
        "Responde las 5 preguntas a continuación. "
        f"Cada pregunta correcta vale **2 puntos** (total 10). "
        f"Necesitas obtener **{_NOTA_APROBACION} o más** para aprobar y recibir tu certificado."
    )
    st.divider()

    with st.form("form_test_cv", clear_on_submit=False):
        respuestas: dict[int, int] = {}

        for i, preg in enumerate(_PREGUNTAS):
            st.markdown(f"**Pregunta {i + 1}.** {preg['enunciado']}")
            opciones_label = [
                f"{_LETRAS[j]}) {op}" for j, op in enumerate(preg["opciones"])
            ]
            seleccion = st.radio(
                label=f"preg_{i}",
                options=opciones_label,
                label_visibility="collapsed",
                key=f"cv_preg_{i}",
                index=None,
            )
            respuestas[i] = seleccion
            st.markdown("")

        enviado = st.form_submit_button(
            "Enviar respuestas →",
            use_container_width=True,
            type="primary",
        )

    if enviado:
        # Verificar que todas las preguntas fueron respondidas
        sin_respuesta = [i + 1 for i, r in respuestas.items() if r is None]
        if sin_respuesta:
            faltantes = ", ".join(str(n) for n in sin_respuesta)
            st.error(f"Por favor responde las preguntas: {faltantes}")
            return

        # Calcular calificación
        aciertos = 0
        detalle: list[bool] = []
        for i, preg in enumerate(_PREGUNTAS):
            resp_label = respuestas[i]
            # Determinar la letra seleccionada (primer carácter antes del ")")
            letra_sel = resp_label[0] if resp_label else ""
            correcta  = _LETRAS[preg["correcta"]]
            correcto  = letra_sel == correcta
            detalle.append(correcto)
            if correcto:
                aciertos += 1

        calificacion = aciertos * 2   # cada acierto = 2 puntos

        _set("cv_respuestas",   detalle)
        _set("cv_calificacion", calificacion)
        _set("cv_codigo",       _generar_codigo())
        _set("cv_paso",         3)
        st.rerun()


def _generar_codigo() -> str:
    """Genera un código único de certificado."""
    uid = str(uuid.uuid4()).upper().replace("-", "")[:8]
    return f"CVE-{date.today().year}-{uid}"


# ---------------------------------------------------------------------------
# Paso 3 — Resultado y certificado
# ---------------------------------------------------------------------------
def _paso_resultado() -> None:
    calificacion  = _get("cv_calificacion", 0)
    detalle       = _get("cv_respuestas",   [])
    nombre        = _get("cv_nombre_completo", "")
    cedula        = _get("cv_cedula", "")
    codigo        = _get("cv_codigo", "")
    aprobado      = calificacion >= _NOTA_APROBACION

    # -----------------------------------------------------------------------
    # Encabezado con resultado
    # -----------------------------------------------------------------------
    if aprobado:
        st.success(f"🎉 ¡Felicitaciones, {nombre}! Has aprobado el test.")
    else:
        st.error(f"❌ {nombre}, no has alcanzado la nota mínima para certificarte.")

    st.markdown("")

    # Métrica principal
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Calificación obtenida", f"{calificacion} / 10")
    with col2:
        aciertos = calificacion // 2
        st.metric("Respuestas correctas", f"{aciertos} / 5")
    with col3:
        st.metric("Nota mínima para aprobar", f"{_NOTA_APROBACION} / 10")

    st.divider()

    # -----------------------------------------------------------------------
    # Retroalimentación por pregunta
    # -----------------------------------------------------------------------
    st.subheader("Revisión de respuestas")
    for i, (preg, correcto) in enumerate(zip(_PREGUNTAS, detalle)):
        icono = "✅" if correcto else "❌"
        resp_correcta = f"{_LETRAS[preg['correcta']]}) {preg['opciones'][preg['correcta']]}"
        with st.expander(f"{icono} Pregunta {i + 1}: {preg['enunciado']}"):
            if correcto:
                st.success(f"**Correcto.** Respuesta: {resp_correcta}")
            else:
                st.error(f"**Incorrecto.** La respuesta correcta era: {resp_correcta}")

    st.divider()

    # -----------------------------------------------------------------------
    # Certificado (solo si aprobó)
    # -----------------------------------------------------------------------
    if aprobado:
        st.subheader("📄 Descarga tu certificado")
        st.markdown(
            f"**Código de certificado:** `{codigo}`  \n"
            f"**Curso:** {_NOMBRE_CURSO}  \n"
            f"**Participante:** {nombre}  \n"
            f"**Cédula:** {cedula}"
        )
        st.markdown("")

        try:
            pdf_bytes = generar_certificado_pdf(
                nombre=nombre,
                cedula=cedula,
                nombre_curso=_NOMBRE_CURSO,
                fecha_capacitacion=str(date.today()),
                codigo_certificado=codigo,
            )
            nombre_archivo = f"certificado_{cedula}_{_NOMBRE_CURSO[:30].replace(' ', '_')}.pdf"
            st.download_button(
                label="📥 Descargar certificado (PDF)",
                data=pdf_bytes,
                file_name=nombre_archivo,
                mime="application/pdf",
                type="primary",
                use_container_width=False,
            )
        except Exception as exc:
            st.warning(
                f"No se pudo generar el PDF: {exc}. "
                "Intentando con formato Word..."
            )
            try:
                docx_bytes = generar_certificado_docx(
                    nombre=nombre,
                    cedula=cedula,
                    nombre_curso=_NOMBRE_CURSO,
                    fecha_capacitacion=str(date.today()),
                    codigo_certificado=codigo,
                )
                nombre_archivo = f"certificado_{cedula}_{_NOMBRE_CURSO[:30].replace(' ', '_')}.docx"
                st.download_button(
                    label="📥 Descargar certificado (.docx)",
                    data=docx_bytes,
                    file_name=nombre_archivo,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                    use_container_width=False,
                )
            except Exception as exc2:
                st.error(
                    f"No se pudo generar el certificado: {exc2}. "
                    "Comunícate con el administrador indicando tu código de certificado."
                )
    else:
        st.info(
            f"Obtuviste {calificacion}/10. Necesitas **{_NOTA_APROBACION}/10** para certificarte. "
            "Puedes volver a ver el video y repetir el test cuando quieras."
        )

    st.divider()

    # -----------------------------------------------------------------------
    # Acciones finales
    # -----------------------------------------------------------------------
    col_a, col_b = st.columns(2)
    with col_a:
        if not aprobado:
            if st.button("🔄 Repetir el test", use_container_width=True, type="primary"):
                for k in ["cv_respuestas", "cv_calificacion", "cv_codigo", "cv_paso"]:
                    st.session_state.pop(k, None)
                _set("cv_paso", 1)   # volver al video antes del test
                st.rerun()
    with col_b:
        if st.button("🏠 Volver al inicio del módulo", use_container_width=True):
            _reset_modulo()
            st.rerun()
