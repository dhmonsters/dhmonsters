@echo off
chcp 65001 > nul
echo ========================================
echo  MapleBot v1.2.1 Build (PyArmor + PyInstaller)
echo ========================================

py -m pip show pyarmor >nul 2>&1
if errorlevel 1 py -m pip install pyarmor

py -m pip show pyinstaller >nul 2>&1
if errorlevel 1 py -m pip install pyinstaller

if exist dist\dhmonsters rmdir /s /q dist\dhmonsters
if exist build rmdir /s /q build
if exist .obf_build rmdir /s /q .obf_build

echo.
echo [1/3] PyArmor obfuscating...
set SCRIPTS=C:\Users\PC\AppData\Local\Programs\Python\Python314\Scripts
set PYARMOR=%SCRIPTS%\pyarmor.exe
set PYINSTALLER=%SCRIPTS%\pyinstaller.exe
"%PYARMOR%" gen -r --output .obf_build main.py
if errorlevel 1 (echo PyArmor failed & pause & exit /b 1)

xcopy /E /I /Y core .obf_build\core
xcopy /E /I /Y ui .obf_build\ui
if exist templates xcopy /E /I /Y templates .obf_build\templates
if exist monsters xcopy /E /I /Y monsters .obf_build\monsters

echo.
echo [2/3] PyInstaller building...
cd .obf_build
"%PYINSTALLER%" --onedir --name dhmonsters --noconsole --add-data "templates;templates" --add-data "monsters;monsters" --paths "C:/Users/PC/AppData/Roaming/Python/Python314/site-packages" --collect-all PyQt6 --collect-all certifi --collect-all rapidocr_onnxruntime --collect-all onnxruntime --hidden-import win32api --hidden-import win32con --hidden-import win32gui --hidden-import win32clipboard --hidden-import pywintypes --hidden-import mss --hidden-import mss.windows --hidden-import cv2 --hidden-import numpy --hidden-import ui --hidden-import ui.main_window --hidden-import ui.tab_main --hidden-import ui.tab_hunt --hidden-import ui.tab_attack --hidden-import ui.tab_recovery --hidden-import ui.tab_position --hidden-import ui.tab_coordinate --hidden-import ui.tab_settings1 --hidden-import ui.tab_settings2 --hidden-import ui.tab_misc --hidden-import ui.widgets --hidden-import ui.region_selector --hidden-import ui.dialog_license --hidden-import core --hidden-import core.bot_loop --hidden-import core.config_manager --hidden-import core.detector --hidden-import core.hotkey_manager --hidden-import core.hw_fingerprint --hidden-import core.hunter --hidden-import core.input_controller --hidden-import core.key_hunter --hidden-import core.license_manager --hidden-import core.map_navigator --hidden-import core.minimap_reader --hidden-import core.pattern --hidden-import core.potion_manager --hidden-import core.ocr_detector --hidden-import core.screen_reader --hidden-import select --hidden-import selectors --hidden-import socket --exclude-module tkinter main.py
cd ..
if errorlevel 1 (echo PyInstaller failed & pause & exit /b 1)

echo.
echo [3/3] Copying files...
if not exist dist mkdir dist
xcopy /E /I /Y .obf_build\dist\dhmonsters dist\dhmonsters
copy /Y config.json dist\dhmonsters\config.json
copy /Y version.txt dist\dhmonsters\version.txt

echo.
echo ========================================
echo  Done! dist\dhmonsters\MapleBot.exe
echo ========================================
pause
