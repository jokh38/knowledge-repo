@echo off
REM Knowledge Repository Start Script for Windows

setlocal enabledelayedexpansion

echo [INFO] Starting Knowledge Repository...

REM Check if virtual environment exists
if not exist "venv" (
    echo [WARNING] Virtual environment not found. Creating...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if requirements are installed
echo [INFO] Checking dependencies...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
)

REM Check if .env file exists
if not exist ".env" (
    echo [ERROR] .env file not found. Please create it based on .env.example
    pause
    exit /b 1
)

REM Create necessary directories
echo [INFO] Creating necessary directories...
if not exist "logs" mkdir logs
if not exist "chroma_db" mkdir chroma_db

REM Check if Obsidian vault path exists
for /f "tokens=*" %%i in ('python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('OBSIDIAN_VAULT_PATH', ''))"') do set VAULT_PATH=%%i

if "!VAULT_PATH!"=="" (
    echo [WARNING] OBSIDIAN_VAULT_PATH not set in .env file
) else (
    if not exist "!VAULT_PATH!" (
        echo [WARNING] Obsidian vault path does not exist: !VAULT_PATH!
        echo [INFO] Creating vault directory structure...
        mkdir "!VAULT_PATH!\00_Inbox\Clippings" 2>nul
        mkdir "!VAULT_PATH!\01_Processed" 2>nul
    )
)

REM Start services
echo [INFO] Starting Knowledge Repository services...

REM Start API server in background
echo [INFO] Starting API server on port 8000...
start "API Server" cmd /c "python main.py"

REM Wait a moment for API server to start
timeout /t 3 /nobreak >nul

REM Start Simple Web UI (same as Linux/macOS)
echo [INFO] Starting Simple Web UI on port 7860...
start "Web UI" cmd /c "python src/simple_server.py"

echo [INFO] Services started successfully!
echo [INFO] API Server: http://localhost:8000
echo [INFO] Simple UI: http://localhost:7860/simple_ui.html
echo [INFO] API Docs: http://localhost:8000/docs
echo.
echo [INFO] Close this window to stop all services
pause