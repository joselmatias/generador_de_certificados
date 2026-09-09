# Contingencia de Streamlit Cloud

## Estado actual

- Inicio: 8 de septiembre de 2026.
- Motivo: Streamlit Community Cloud no puede procesar `packages.txt` porque el
  índice `bullseye-security` de Debian aparece vencido durante `apt-get`.
- Objetivo: permitir que la aplicación inicie sin eliminar módulos ni consumir
  códigos de certificados que no puedan convertirse a PDF.

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
