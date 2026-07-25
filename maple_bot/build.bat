@echo off
chcp 65001 > nul
echo ========================================
echo  Claude v2.2.7 Build (PyArmor + PyInstaller)
echo ========================================

set PYTHON=C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe

"%PYTHON%" -m pip show pyarmor >nul 2>&1
if errorlevel 1 "%PYTHON%" -m pip install pyarmor

"%PYTHON%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 "%PYTHON%" -m pip install pyinstaller

if exist dist\Claude_2.2.7 rmdir /s /q dist\Claude_2.2.7
if exist build rmdir /s /q build
if exist .obf_build rmdir /s /q .obf_build

echo.
echo [1/3] PyArmor obfuscating...
set SCRIPTS=C:\Users\PC\AppData\Local\Programs\Python\Python314\Scripts
set PYARMOR=%SCRIPTS%\pyarmor.exe
set PYINSTALLER=%SCRIPTS%\pyinstaller.exe
"%PYARMOR%" gen -r --output .obf_build run_integrated.py
if errorlevel 1 (echo PyArmor failed & pause & exit /b 1)

xcopy /E /I /Y core .obf_build\core
xcopy /E /I /Y core_ui .obf_build\core_ui
xcopy /E /I /Y ui .obf_build\ui
if exist assets xcopy /E /I /Y assets .obf_build\assets
if exist templates xcopy /E /I /Y templates .obf_build\templates
if exist monsters xcopy /E /I /Y monsters .obf_build\monsters
if exist models xcopy /E /I /Y models .obf_build\models

echo.
echo [2/3] PyInstaller building...
cd .obf_build
"%PYINSTALLER%" --onedir --name Claude --icon "assets\claude_logo.ico" --noconsole --add-data "core;core" --add-data "core_ui;core_ui" --add-data "ui;ui" --add-data "templates;templates" --add-data "monsters;monsters" --add-data "models;models" --add-data "assets;assets" --paths "C:/Users/PC/AppData/Roaming/Python/Python314/site-packages" --collect-all certifi --collect-all rapidocr_onnxruntime --collect-all ncnn --collect-submodules core --collect-submodules core_ui --collect-submodules core.humanize --collect-submodules core.sensing --collect-submodules core.acting --collect-submodules core.navigation --collect-submodules core.orchestrator --collect-submodules core.minigame --collect-submodules core.notify --hidden-import ncnn --hidden-import win32api --hidden-import win32con --hidden-import win32gui --hidden-import win32clipboard --hidden-import pywintypes --hidden-import mss --hidden-import mss.windows --hidden-import cv2 --hidden-import numpy --hidden-import ui --hidden-import ui.main_window --hidden-import ui.tab_main --hidden-import ui.tab_hunt --hidden-import ui.tab_attack --hidden-import ui.tab_recovery --hidden-import ui.tab_position --hidden-import ui.tab_coordinate --hidden-import ui.tab_settings1 --hidden-import ui.tab_settings2 --hidden-import ui.tab_misc --hidden-import ui.widgets --hidden-import ui.region_selector --hidden-import ui.dialog_license --hidden-import core --hidden-import core.runtime --hidden-import core.admin_util --hidden-import core.bot_loop --hidden-import core.config_manager --hidden-import core.config_adapter --hidden-import core.detector --hidden-import core.hotkey_manager --hidden-import core.hw_fingerprint --hidden-import core.hunter --hidden-import core.input_controller --hidden-import core.key_hunter --hidden-import core.license_manager --hidden-import core.map_navigator --hidden-import core.minimap_reader --hidden-import core.pattern --hidden-import core.potion_manager --hidden-import core.ocr_detector --hidden-import core.screen_reader --hidden-import core.humanize --hidden-import core.humanize.backend --hidden-import core.humanize.humanizer --hidden-import core.humanize.intent --hidden-import core_ui.shell --hidden-import core_ui.theme --hidden-import core_ui.pages --hidden-import core_ui.widgets --hidden-import core_ui.branding --hidden-import core_ui.world_map_editor --hidden-import core_ui.minimap_canvas --hidden-import select --hidden-import selectors --hidden-import socket --exclude-module tkinter --exclude-module ultralytics --exclude-module torch --exclude-module torchvision --exclude-module torchaudio --exclude-module onnxruntime.tools --exclude-module onnxruntime.transformers --exclude-module onnxruntime.quantization run_integrated.py
cd ..
if errorlevel 1 (echo PyInstaller failed & pause & exit /b 1)

echo.
echo [3/3] Copying files...
if not exist dist mkdir dist
xcopy /E /I /Y .obf_build\dist\Claude dist\Claude_2.2.7
xcopy /E /I /Y .obf_build\core dist\Claude_2.2.7\core
xcopy /E /I /Y .obf_build\core_ui dist\Claude_2.2.7\core_ui
xcopy /E /I /Y .obf_build\ui dist\Claude_2.2.7\ui
if exist dist\Claude_2.2.7\_internal xcopy /E /I /Y .obf_build\core dist\Claude_2.2.7\_internal\core
if exist dist\Claude_2.2.7\_internal xcopy /E /I /Y .obf_build\core_ui dist\Claude_2.2.7\_internal\core_ui
if exist dist\Claude_2.2.7\_internal xcopy /E /I /Y .obf_build\ui dist\Claude_2.2.7\_internal\ui
copy /Y config.json dist\Claude_2.2.7\config.json
copy /Y version.txt dist\Claude_2.2.7\version.txt
if exist templates xcopy /E /I /Y templates dist\Claude_2.2.7\templates
if exist monsters xcopy /E /I /Y monsters dist\Claude_2.2.7\monsters
if exist models xcopy /E /I /Y models dist\Claude_2.2.7\models
if exist "third_party\Interception-v1.0.1\Interception\library\x64\interception.dll" copy /Y "third_party\Interception-v1.0.1\Interception\library\x64\interception.dll" "dist\Claude_2.2.7\interception.dll"

echo.
echo ========================================
echo  Done! dist\Claude_2.2.7\Claude.exe
echo ========================================
pause













