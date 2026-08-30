@rem Qt 없이 실행되는 Claude 복구 실행기를 Framework64 C# 컴파일러로 빌드한다.
@echo off
setlocal
if "%~1"=="" exit /b 2
set "OUTPUT_DIR=%~1"
set "CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" exit /b 3
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if errorlevel 1 exit /b 4
pushd "%~dp0.."
"%CSC%" /nologo /target:winexe /platform:x64 /optimize+ /main:Program /out:"%OUTPUT_DIR%\Claude.exe" /win32manifest:"recovery_launcher\app.manifest" /win32icon:"assets\claude_logo.ico" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll "recovery_launcher\Program.cs" "recovery_launcher\RecoveryModels.cs" "recovery_launcher\RecoveryStore.cs" "recovery_launcher\UpdateClient.cs" "recovery_launcher\RecoveryForm.cs" "recovery_launcher\RollbackWorker.cs"
set "BUILD_EXIT=%ERRORLEVEL%"
popd
exit /b %BUILD_EXIT%
