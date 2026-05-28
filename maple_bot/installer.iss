; MapleBot Inno Setup 설치 스크립트
; ISCC.exe installer.iss 로 빌드

#define AppName    "DHMONSTERS"
#define AppVersion "1.2.3"
#define AppExe     "dhmonsters.exe"
#define AppPublisher "dhmonsters"
#define SourceDir  "dist\dhmonsters"

[Setup]
AppId={{B3F2A1C4-7E5D-4F8A-9B2C-3D6E8F1A2B5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL=https://github.com/dhmonsters/dhmonsters
AppSupportURL=https://github.com/dhmonsters/dhmonsters
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=DHMONSTERS_v{#AppVersion}_Setup
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

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[UninstallDelete]
; 앱이 생성하는 캐시/로그 파일 제거 (설정은 AppData에 있어 유지)
Type: filesandordirs; Name: "{app}\__pycache__"
