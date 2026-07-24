; MapleBot Inno Setup ??쇳뒄 ??쎄쾿?깆???
; ISCC.exe installer.iss 嚥???슢諭?

#define AppName    "Claude"
#define AppVersion "2.2.0"
#define AppExe     "Claude.exe"
#define AppPublisher "Claude"
#define SourceDir  "dist\Claude"

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

; ??쇳뒄 ?袁⑥┷ ??獄쏅뗀以???쎈뻬 ????
[Run]
Filename: "{app}\drivers\Interception\install-interception.exe"; Parameters: "/install"; StatusMsg: "Interception ??뺤뵬??苡?몴???쇳뒄??롫뮉 餓λ쵐???덈뼄..."; Flags: runhidden waituntilterminated; Tasks: interceptiondriver
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
; version.txt???룐뫂??癒?퐣 筌욊낯????釉???dist ??슢諭??袁⑥뵭 ??뽯퓠????湲??類μ넇??甕곌쑴?????쇳뒄??Source: "version.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{autoprograms}\{#AppName}\Interception Driver Guide"; Filename: "{app}\drivers\Interception\Interception_guide.txt"

[UninstallDelete]
; ?源놁뵠 ??밴쉐??롫뮉 筌?Ŋ??嚥≪뮄?????뵬 ??볤탢 (??쇱젟?? AppData????됰선 ?醫?)
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
      'Interception ??뺤뵬??苡???쇳뒄???遺욧퍕??됰뮸??덈뼄.' + #13#10 + #13#10 +
      '?뚮똾踰?怨? ?????뉖퉸????뺤뵬??苡?첎? ??뽮쉐?遺얜쭢??덈뼄.' + #13#10 +
      '??????袁⑸퓠??Claude????쎈????낆젾????덉삂??? ??놁뱽 ????됰뮸??덈뼄.',
      mbInformation, MB_OK
    );
end;







