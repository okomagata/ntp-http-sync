@echo off
setlocal
 
set PYTHON_EXE=C:\msys64\ucrt64\bin\python.exe
set SCRIPT_DIR=%~dp0
 
REM Force Python's stdout/stderr to be encoded as UTF-8,
REM regardless of the active console code page.
set PYTHONIOENCODING=utf-8
set LOG_FILE=%SCRIPT_DIR%ntp_sync.log
set PY_SCRIPT=%SCRIPT_DIR%ntp_http_sync.py
 
echo ---------------------------------------- >> "%LOG_FILE%"
echo %date% %time% >> "%LOG_FILE%"
echo PYTHON_EXE=%PYTHON_EXE% >> "%LOG_FILE%"
echo PY_SCRIPT=%PY_SCRIPT% >> "%LOG_FILE%"
 
"%PYTHON_EXE%" "%PY_SCRIPT%" >> "%LOG_FILE%" 2>&1
 
endlocal
 