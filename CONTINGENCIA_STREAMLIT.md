# Contingencia de Streamlit Cloud

## Estado actual

- Inicio: 8 de septiembre de 2026. **Revertida: 21 de septiembre de 2026.**
- Motivo: Streamlit Community Cloud no podía procesar `packages.txt` porque el
  índice `bullseye-security` de Debian aparecía vencido durante `apt-get`.
  Streamlit confirmó en su foro que publicó el fix a producción el 9 de
  septiembre de 2026.
- Objetivo (mientras estuvo activa): permitir que la aplicación iniciara sin
  eliminar módulos ni consumir códigos de certificados que no pudieran
  convertirse a PDF.
- Verificación previa a revertir: generación local de certificado (relleno de
  plantilla + conversión a PDF con LibreOffice) confirmada visualmente
  correcta (placeholders, tildes, autoajuste de fuente y firma).
  **Pendiente:** confirmar en el primer despliegue de Streamlit Cloud que
  `packages.txt` instala LibreOffice sin error y que un certificado masivo,
  uno individual y uno de capacitación virtual generan PDF correctamente.

## Inhabilitaciones temporales

Las secciones continúan visibles, pero están deshabilitadas estas acciones:

1. Generación masiva y descarga ZIP de certificados PDF.
2. Generación de certificado individual PDF.
3. Descarga del certificado al aprobar la capacitación virtual.

Continúan habilitados la carga y consulta de información, los reportes PDF que
usan ReportLab, los dashboards, el historial de certificados y todo el flujo de
la capacitación virtual hasta mostrar el resultado del test.

## Cambios aplicados

- `packages.txt` se conservó como `packages.txt.disabled` para impedir que
  Streamlit ejecute APT durante el despliegue.
- `utils/feature_flags.py` centraliza el estado y el mensaje de contingencia.
- Los botones dependientes de LibreOffice están visibles pero deshabilitados.

## Cómo revertir la contingencia

Cuando Streamlit confirme la solución y una prueba de despliegue pueda instalar
LibreOffice:

1. Renombrar `packages.txt.disabled` a `packages.txt`.
2. Cambiar `CERTIFICATE_GENERATION_ENABLED` a `True` en
   `utils/feature_flags.py`.
3. Desplegar y verificar un certificado masivo, uno individual y uno de la
   capacitación virtual.
4. Actualizar este documento con la fecha de reactivación.
