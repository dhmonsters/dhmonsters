; MapleBot Inno Setup 설치 스크립트
; ISCC.exe installer.iss 로 빌드

#define AppName    "Claude"
#define AppVersion "2.1.5"
#define AppExe     "Claude.exe"
#define AppPublisher "Claude"
#define SourceDir  "03_output\Claude_v2.1.5_portable\Claude"

[Setup]
AppId={{7C8A5E21-4B6D-49F3-A2C1-9E7D5B4A603F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=https://github.com/dhmonsters/dhmonsters
AppSupportURL=https://github.com/dhmonsters/dhmonsters
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UsePreviousAppDir=no
OutputDir=03_output
OutputBaseFilename=Claude_v{#AppVersion}_Setup_v2
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}

; 설치 완료 후 바로 실행 옵션
[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; version.txt를 루트에서 직접 포함 — dist 빌드 누락 시에도 항상 정확한 버전이 설치됨
Source: "version.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[UninstallDelete]
; 앱이 생성하는 캐시/로그 파일 제거 (설정은 AppData에 있어 유지)
Type: filesandordirs; Name: "{app}\__pycache__"
