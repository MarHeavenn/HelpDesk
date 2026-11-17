@echo off
setlocal
set "ROOT=%~dp0"

if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
    echo No se encontro backend\.venv\Scripts\python.exe.
    echo Crea el entorno e instala backend\requirements.txt antes de continuar.
    exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
    echo No se encontraron las dependencias del frontend.
    echo Ejecuta npm.cmd install desde frontend\ antes de continuar.
    exit /b 1
)

start "HelpDesk Backend" /D "%ROOT%backend" cmd /k ".venv\Scripts\python.exe dev_server.py"
start "HelpDesk Frontend" /D "%ROOT%frontend" cmd /k "npm.cmd run dev -- --host localhost"

echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo Cierra cada ventana o pulsa Ctrl+C en ellas para detener los servidores.
