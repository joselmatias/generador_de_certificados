# ============================================================
# SCRIPT COMPLETO - CONFIGURAR GIT Y SUBIR PROYECTO A GITHUB
# ============================================================
# PASO 1: Edita estas 4 variables con tus datos
# ============================================================

$nombre      = "Tu Nombre"                  # Tu nombre completo
$email       = "tuemail@gmail.com"          # Email de tu cuenta GitHub
$usuario     = "TU_USUARIO_GITHUB"          # Tu usuario de GitHub
$repositorio = "TU_NOMBRE_REPOSITORIO"      # Nombre del repo en GitHub

# ============================================================

Write-Host ""
Write-Host "=== VERIFICANDO GIT ===" -ForegroundColor Yellow

# Verificar si git esta instalado
try {
    $gitVersion = git --version
    Write-Host "Git encontrado: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "Git NO esta instalado." -ForegroundColor Red
    Write-Host "Descargalo desde: https://git-scm.com/download/win" -ForegroundColor Red
    Write-Host "Instala y vuelve a ejecutar este script." -ForegroundColor Red
    pause
    exit
}

Write-Host ""
Write-Host "=== CONFIGURANDO USUARIO GIT ===" -ForegroundColor Yellow

git config --global user.name  "$nombre"
git config --global user.email "$email"

Write-Host "Usuario configurado: $nombre <$email>" -ForegroundColor Green

Write-Host ""
Write-Host "=== INICIALIZANDO REPOSITORIO ===" -ForegroundColor Yellow

git init
Write-Host "Repositorio local creado." -ForegroundColor Green

Write-Host ""
Write-Host "=== AGREGANDO ARCHIVOS ===" -ForegroundColor Yellow

git add .
Write-Host "Archivos agregados (respetando .gitignore)." -ForegroundColor Green

Write-Host ""
Write-Host "=== CREANDO COMMIT INICIAL ===" -ForegroundColor Yellow

git commit -m "Initial commit - Streamlit SCE App"
Write-Host "Commit creado." -ForegroundColor Green

Write-Host ""
Write-Host "=== CONECTANDO CON GITHUB ===" -ForegroundColor Yellow

git branch -M main
git remote add origin "https://github.com/$usuario/$repositorio.git"
Write-Host "Remoto configurado: https://github.com/$usuario/$repositorio.git" -ForegroundColor Green

Write-Host ""
Write-Host "=== SUBIENDO CODIGO A GITHUB ===" -ForegroundColor Yellow
Write-Host "(Se pedira tu usuario y token de GitHub)" -ForegroundColor Cyan

git push -u origin main

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " LISTO! Proyecto disponible en:" -ForegroundColor Green
Write-Host " https://github.com/$usuario/$repositorio" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
pause
