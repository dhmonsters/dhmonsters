#define AppName "Claude"
#define AppVersion "2.1.5"
#define AppPublisher "Claude"
#define AppExeName "Claude.exe"
#define SourceDir "C:\Users\PC\Desktop\02_work\05_AI\maple_bot\03_output\Claude_v2.1.5_portable_2point_fix\Claude"

[Setup]
AppId={{7C8A5E21-4B6D-49F3-A2C1-9E7D5B4A603F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=C:\Users\PC\Desktop\02_work\05_AI\maple_bot\03_output
OutputBaseFilename=Claude_Setup_v{#AppVersion}_v3
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; 기존 설치 업그레이드 시 config/license 보존
UsePreviousAppDir=no
; 64비트 설치
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로 가기 만들기"; GroupDescription: "추가 작업:"

[Files]
; MapleBot.exe 및 _internal 폴더 (config.json, license.dat 제외)
Source: "{#SourceDir}\Claude.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\version.txt"; DestDir: "{app}"; Flags: ignoreversion
; config.json — 없을 때만 복사 (기존 설정 보존)
Source: "{#SourceDir}\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\제거"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; 설치 후 Windows Defender 제외 폴더 등록 (백신 차단 방지)
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -Command ""Add-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue"""; \
  Flags: runhidden waituntilterminated; \
  StatusMsg: "보안 프로그램 예외 설정 중..."
; 설치 완료 후 실행 여부 선택
Filename: "{app}\{#AppExeName}"; Description: "Claude 실행"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 제거 시 Defender 제외 해제
Filename: "powershell.exe"; \
  Parameters: "-ExecutionPolicy Bypass -Command ""Remove-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue"""; \
  Flags: runhidden waituntilterminated

[UninstallDelete]
; 제거 시 로그 파일 등 정리 (config/license는 보존)
Type: files; Name: "{app}\version.txt"
