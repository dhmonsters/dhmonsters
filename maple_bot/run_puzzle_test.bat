REM 투명도형 퍼즐 기본 테스트를 실행하는 배치 파일
@echo off
setlocal

cd /d "%~dp0"

set "MAX_FRAMES=%~1"
if "%MAX_FRAMES%"=="" set "MAX_FRAMES=5"

set "PYTHON_EXE="
if exist "C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe" set "PYTHON_EXE=C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe"
if not defined PYTHON_EXE if exist "C:\Users\PC\AppData\Local\Programs\Python\Python313\python.exe" set "PYTHON_EXE=C:\Users\PC\AppData\Local\Programs\Python\Python313\python.exe"
if not defined PYTHON_EXE if exist "C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe" set "PYTHON_EXE=C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe"
if not defined PYTHON_EXE set "PYTHON_EXE=python"

set "PYTHONPATH=%~dp0;%~dp0.codex_pydeps;%PYTHONPATH%"

echo [puzzle] transparent test start. max_frames=%MAX_FRAMES%
"%PYTHON_EXE%" "%~dp0puzzle.py" --transparent-test --max-frames %MAX_FRAMES%
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
    echo [puzzle] done. Check 03_output\YYYY-MM-DD_transparent_puzzle_sessions.
) else (
    echo [puzzle] failed. exit_code=%EXIT_CODE%
)

pause
exit /b %EXIT_CODE%
