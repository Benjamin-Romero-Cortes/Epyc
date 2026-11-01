@echo off
setlocal
cd /d "%~dp0"
title EPYC - Servidor Django

if not exist "manage.py" (
    echo [ERROR] No se encontro manage.py. Ejecuta este archivo desde la carpeta del proyecto.
    pause
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import django, psycopg.pq" >nul 2>&1
    if not errorlevel 1 goto :start_server
    echo [INFO] El entorno virtual esta incompleto o es incompatible. Se va a recrear.
)

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv --clear .venv
    if not errorlevel 1 goto :install_dependencies
)

where python >nul 2>&1
if not errorlevel 1 (
    python -m venv --clear .venv
    if not errorlevel 1 goto :install_dependencies
)

echo [ERROR] No se encontro un Python compatible.
echo Instala Python 3.12 o superior y vuelve a ejecutar este archivo.
pause
exit /b 1

:install_dependencies
if not exist "requirements.txt" (
    echo [ERROR] No se encontro requirements.txt.
    pause
    exit /b 1
)

echo [INFO] Instalando dependencias. Esto puede tardar la primera vez...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERROR] No se pudieron instalar las dependencias. Revisa tu conexion a Internet.
    pause
    exit /b 1
)

:start_server
echo.
echo [OK] Iniciando el servicio en http://127.0.0.1:8000/
echo Presiona Ctrl+C para detenerlo.
echo.
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
set "SERVER_EXIT=%ERRORLEVEL%"
if not "%SERVER_EXIT%"=="0" echo [ERROR] Django termino con codigo %SERVER_EXIT%.
pause
exit /b %SERVER_EXIT%
