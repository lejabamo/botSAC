@echo off
cd /d "%~dp0"
echo ==============================================
echo       Iniciando BotSAC (FastAPI + React)
echo ==============================================

echo Iniciando Backend API (FastAPI en http://127.0.0.1:8000)...
start "BotSAC Backend API" cmd /k ".venv\Scripts\uvicorn app.api:app --host 127.0.0.1 --port 8000"

echo Iniciando Frontend (React + Vite en http://127.0.0.1:5173)...
cd frontend
start "BotSAC Frontend React" cmd /k "npx vite --port 5173 --host 0.0.0.0"
cd ..

echo Esperando a que los servicios esten listos...
.venv\Scripts\python -c "import urllib.request, time; [None for _ in range(30) if not time.sleep(0.5) and not urllib.request.urlopen('http://127.0.0.1:5173', timeout=1)]" >nul 2>nul

echo.
echo ==============================================
echo Aplicacion iniciada correctamente:
echo -> Cliente React: http://127.0.0.1:5173
echo -> API REST:      http://127.0.0.1:8000/api/inbox
echo ==============================================
start http://127.0.0.1:5173
