@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Instalador - Entre Platos y Copas
color 0A

echo ============================================================
echo   ENTRE PLATOS Y COPAS - CONFIGURACION DEL PROYECTO
echo ============================================================
echo.

REM 1. Buscar Python
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo [ERROR] No se encontro Python instalado.
        echo Instala Python 3.12 o superior y vuelve a ejecutar este archivo.
        echo Recuerda marcar "Add Python to PATH".
        pause
        exit /b 1
    )
)

echo [OK] Python encontrado:
%PYTHON_CMD% --version
echo.

REM 2. Crear entorno virtual
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creando entorno virtual .venv...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
) else (
    echo [OK] El entorno virtual .venv ya existe.
)
echo.

REM 3. Activar entorno virtual
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] No se pudo activar el entorno virtual.
    pause
    exit /b 1
)
echo [OK] Entorno virtual activado.
echo.

REM 4. Actualizar herramientas
echo [INFO] Actualizando pip, setuptools y wheel...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [ERROR] No se pudo actualizar pip.
    pause
    exit /b 1
)
echo.

REM 5. Instalar dependencias
if exist "requirements.txt" (
    echo [INFO] Se encontro requirements.txt.
    echo [INFO] Instalando dependencias del proyecto...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Ocurrio un problema instalando requirements.txt.
        pause
        exit /b 1
    )
) else (
    echo [INFO] No se encontro requirements.txt.
    echo [INFO] Instalando dependencias base del proyecto...
    echo.

    pip install "Django>=6.0,<7.0"
    if errorlevel 1 goto :install_error

    pip install "psycopg[binary]>=3.2"
    if errorlevel 1 goto :install_error

    pip install "python-dotenv>=1.0"
    if errorlevel 1 goto :install_error

    pip install "whitenoise>=6.8"
    if errorlevel 1 goto :install_error

    echo.
    echo [INFO] Generando requirements.txt...
    pip freeze > requirements.txt
    echo [OK] requirements.txt creado.
)
echo.

REM 6. Mostrar versiones
echo ============================================================
echo   DEPENDENCIAS INSTALADAS
echo ============================================================
python -c "import django; print('Django:', django.get_version())"
python -c "import psycopg; print('psycopg:', psycopg.__version__)"
echo.

REM 7. Verificar proyecto Django
if exist "manage.py" (
    echo [OK] Se encontro manage.py.
    echo.
    echo [INFO] Verificando configuracion de Django...
    python manage.py check

    if errorlevel 1 (
        echo.
        echo [ADVERTENCIA] Django encontro un problema de configuracion.
        echo Revisa settings.py, PostgreSQL y las variables de entorno.
        echo La instalacion de dependencias ya fue realizada.
        echo.
    ) else (
        echo [OK] La configuracion de Django paso la verificacion.
        echo.
        choice /C SN /N /M "¿Deseas ejecutar las migraciones ahora? [S/N]: "
        if errorlevel 2 goto :skip_migrations
        if errorlevel 1 goto :run_migrations
    )
) else (
    echo [ADVERTENCIA] No se encontro manage.py en esta carpeta.
    echo Ejecuta este BAT desde la carpeta raiz del proyecto Django.
    goto :finish
)

:run_migrations
echo.
echo [INFO] Creando migraciones...
python manage.py makemigrations
if errorlevel 1 (
    echo [ADVERTENCIA] No fue posible ejecutar makemigrations.
    goto :finish
)

echo.
echo [INFO] Aplicando migraciones...
python manage.py migrate
if errorlevel 1 (
    echo [ADVERTENCIA] No fue posible aplicar las migraciones.
    echo Verifica que PostgreSQL este iniciado y que la base de datos exista.
    goto :finish
)

echo [OK] Migraciones aplicadas.
goto :finish

:skip_migrations
echo.
echo [INFO] Migraciones omitidas.
goto :finish

:install_error
echo.
echo [ERROR] Ocurrio un problema instalando las dependencias.
echo Revisa tu conexion a Internet y vuelve a ejecutar el archivo.
pause
exit /b 1

:finish
echo.
echo ============================================================
echo   INSTALACION FINALIZADA
echo ============================================================
echo.
echo Para activar el entorno en otra consola:
echo     .venv\Scripts\activate
echo.
echo Para iniciar Django:
echo     python manage.py runserver
echo.
echo Para salir del entorno virtual:
echo     deactivate
echo.
pause
endlocal
