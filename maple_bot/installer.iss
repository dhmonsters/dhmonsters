; Claude Inno Setup installer script
; Build with ISCC.exe installer.iss

#define AppName    "Claude"
#define AppVersion "2.3.6"
#define AppExe     "Claude.exe"
#define AppPublisher "Claude"
#define SourceDir  "dist\Claude_" + AppVersion

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
OutputBaseFilename=Claude_v{#AppVersion}_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\claude_logo.ico
UninstallDisplayIcon={app}\{#AppExe}

[Run]
Filename: "{app}\drivers\Interception\install-interception.exe"; Parameters: "/install"; StatusMsg: "Installing Interception driver. Please wait..."; Flags: runhidden waituntilterminated; Tasks: interceptiondriver
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent; Check: not WizardIsTaskSelected('interceptiondriver')

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional tasks"
Name: "interceptiondriver"; Description: "Install Interception driver (optional; restart required)"; GroupDescription: "Optional components"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "third_party\Interception-v1.0.1\Interception\command line installer\install-interception.exe"; DestDir: "{app}\drivers\Interception"; Flags: ignoreversion
Source: "third_party\Interception-v1.0.1\Interception\licenses\non-commercial-usage\LGPL 3.0.txt"; DestDir: "{app}\drivers\Interception\licenses"; Flags: ignoreversion
Source: "third_party\Interception-v1.0.1\Interception_guide.txt"; DestDir: "{app}\drivers\Interception"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{autoprograms}\{#AppName}\Interception Driver Guide"; Filename: "{app}\drivers\Interception\Interception_guide.txt"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
function NeedRestart(): Boolean;
begin
  Result := WizardIsTaskSelected('interceptiondriver');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('interceptiondriver') then
    MsgBox(
      'Interception driver installation has finished.' + #13#10 + #13#10 +
      'Please restart Windows before using driver input.' + #13#10 +
      'If you skip restart, Claude can still run, but driver input may not work.',
      mbInformation, MB_OK
    );
end;




