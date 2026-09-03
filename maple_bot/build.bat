@echo off
chcp 65001 > nul
echo ========================================
echo  Claude v2.4.11 Build (PyArmor + PyInstaller + Recovery Launcher)
echo ========================================

set PYTHON_HOME=C:\Users\PC\AppData\Local\Programs\Python\Python314
set PYTHON=%PYTHON_HOME%\python.exe

if not exist run_integrated.py (echo Missing run_integrated.py & exit /b 1)
if not exist assets\claude_logo.ico (echo Missing assets\claude_logo.ico & exit /b 1)
if not exist templates\lie_detector\title.png (echo Missing lie detector template & exit /b 1)
if not exist third_party\Interception-v1.0.1\Interception\library\x64\interception.dll (echo Missing interception.dll & exit /b 1)

"%PYTHON%" -m pip show pyarmor >nul 2>&1
if errorlevel 1 "%PYTHON%" -m pip install pyarmor

"%PYTHON%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 "%PYTHON%" -m pip install pyinstaller

if exist dist\Claude_2.4.11 rmdir /s /q dist\Claude_2.4.11
if exist build rmdir /s /q build
if exist .obf_build rmdir /s /q .obf_build

echo.
echo [1/3] PyArmor obfuscating...
set SCRIPTS=C:\Users\PC\AppData\Local\Programs\Python\Python314\Scripts
set PYARMOR=%SCRIPTS%\pyarmor.exe
set PYINSTALLER=%SCRIPTS%\pyinstaller.exe
"%PYTHON%" -m pyarmor.cli gen -r --output .obf_build run_integrated.py
if errorlevel 1 (echo PyArmor failed & exit /b 1)

xcopy /E /I /Y core .obf_build\core
xcopy /E /I /Y core_ui .obf_build\core_ui
if not exist .obf_build\ui mkdir .obf_build\ui
copy /Y ui\__init__.py .obf_build\ui\__init__.py
copy /Y ui\region_selector.py .obf_build\ui\region_selector.py
copy /Y ui\dialog_license.py .obf_build\ui\dialog_license.py
copy /Y ui\dialog_update.py .obf_build\ui\dialog_update.py
if exist .obf_build\core\puzzle rmdir /s /q .obf_build\core\puzzle
if exist .obf_build\core\puzzle2 rmdir /s /q .obf_build\core\puzzle2
if exist .obf_build\core\minigame rmdir /s /q .obf_build\core\minigame
for /d /r .obf_build %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
del /s /q ".obf_build\*.pyc" >nul 2>&1
if not exist .obf_build\assets mkdir .obf_build\assets
copy /Y assets\claude_logo.ico .obf_build\assets\claude_logo.ico
if exist assets\fonts xcopy /E /I /Y assets\fonts .obf_build\assets\fonts
if exist assets\monster_templates xcopy /E /I /Y assets\monster_templates .obf_build\assets\monster_templates
if exist assets\player xcopy /E /I /Y assets\player .obf_build\assets\player
if exist templates xcopy /E /I /Y templates .obf_build\templates
if exist monsters xcopy /E /I /Y monsters .obf_build\monsters
if exist maps xcopy /E /I /Y maps .obf_build\maps

echo.
echo [2/3] PyInstaller building...
set "PATH=%PYTHON_HOME%;%SCRIPTS%;%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem"
cd .obf_build
"%PYINSTALLER%" --onedir --name ClaudeApp --icon "assets\claude_logo.ico" --noconsole --disable-windowed-traceback --add-data "templates;templates" --add-data "monsters;monsters" --add-data "assets\claude_logo.ico;assets" --add-data "assets\fonts;assets\fonts" --add-data "assets\monster_templates;assets\monster_templates" --add-data "assets\player;assets\player" --add-data "maps;maps" --paths "C:/Users/PC/AppData/Roaming/Python/Python314/site-packages" --collect-all certifi --hidden-import win32api --hidden-import win32con --hidden-import win32gui --hidden-import win32clipboard --hidden-import pywintypes --hidden-import mss --hidden-import mss.windows --hidden-import cv2 --hidden-import numpy --hidden-import ui.region_selector --hidden-import ui.dialog_license --hidden-import ui.dialog_update --hidden-import core.recovery_protocol --hidden-import core.update_recovery --hidden-import core.updater --hidden-import core.runtime --hidden-import core.input_backend --hidden-import core.input_timing --hidden-import core.admin_util --hidden-import core.config_manager --hidden-import core.config_adapter --hidden-import core.detector --hidden-import core.hotkey_manager --hidden-import core.hw_fingerprint --hidden-import core.input_controller --hidden-import core.license_manager --hidden-import core.minimap_reader --hidden-import core.pattern --hidden-import core.screen_reader --hidden-import core_ui.shell --hidden-import core_ui.theme --hidden-import core_ui.pages --hidden-import core_ui.widgets --hidden-import core_ui.branding --hidden-import core_ui.world_map_editor --hidden-import core_ui.minimap_canvas --hidden-import select --hidden-import selectors --hidden-import socket --exclude-module tkinter --exclude-module ultralytics --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module ncnn --exclude-module easyocr --exclude-module rapidocr_onnxruntime --exclude-module onnxruntime --exclude-module scipy --exclude-module matplotlib run_integrated.py
set PYINSTALLER_EXIT=%ERRORLEVEL%
cd ..
if not "%PYINSTALLER_EXIT%"=="0" (echo PyInstaller failed & exit /b %PYINSTALLER_EXIT%)
echo.
echo [3/3] Copying files...
if not exist dist mkdir dist
xcopy /E /I /Y .obf_build\dist\ClaudeApp dist\Claude_2.4.11
"%PYTHON%" build_release_config.py config.json dist\Claude_2.4.11\config.json
if errorlevel 1 (echo Release config generation failed & exit /b 1)
copy /Y version.txt dist\Claude_2.4.11\version.txt
if exist templates xcopy /E /I /Y templates dist\Claude_2.4.11\templates
if exist monsters xcopy /E /I /Y monsters dist\Claude_2.4.11\monsters
if exist maps xcopy /E /I /Y maps dist\Claude_2.4.11\maps
if exist "third_party\Interception-v1.0.1\Interception\library\x64\interception.dll" copy /Y "third_party\Interception-v1.0.1\Interception\library\x64\interception.dll" "dist\Claude_2.4.11\interception.dll"

call recovery_launcher\build_launcher.bat "dist\Claude_2.4.11"
if errorlevel 1 (echo Recovery launcher build failed & exit /b 1)
"%PYTHON%" release_bundle_validation.py ".obf_build\build\ClaudeApp\Analysis-00.toc" "dist\Claude_2.4.11" --startup-executable "dist\Claude_2.4.11\ClaudeApp.exe" --startup-argument=--release-startup-check --startup-timeout 30
if errorlevel 1 (echo Release native dependency validation failed & exit /b 1)

for /d /r "dist\Claude_2.4.11" %%D in (__pycache__) do @if exist "%%D" rmdir /s /q "%%D"
del /s /q "dist\Claude_2.4.11\*.pyc" >nul 2>&1

echo.
echo ========================================
echo  Done! dist\Claude_2.4.11\Claude.exe + ClaudeApp.exe
echo ========================================




