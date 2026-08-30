; Claude Inno Setup installer script
; Build with ISCC.exe installer.iss

#define AppName    "Claude"
#define AppVersion "2.4.7"
#define AppExe     "Claude.exe"
#define AppPublisher "Claude"
#define SourceDir  "dist\Claude_" + AppVersion
#define PreviousVersion "2.4.6"
#define PreviousSetupUrl "https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.6/Claude_v2.4.6_Setup.exe"
#define PreviousSetupSha "7a7e066479b273fb22fa74ef42cfe5c959925b34b38c02cb9c68baf18fa63b8a"
#define CurrentSetupUrl "https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.7/Claude_v2.4.7_Setup.exe"

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
CloseApplications=yes
RestartApplications=no

[Dirs]
Name: "{commonappdata}\Claude\Recovery"; Permissions: admins-full system-full users-readexec

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
#include "installer_recovery.iss"

var
  RemoveRecoveryCache: Boolean;

function OnDownloadProgress(
  const Url, FileName: String;
  const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

function ReadInstalledVersion(): String;
var
  Lines: TArrayOfString;
begin
  Result := '';
  if LoadStringsFromFile(ExpandConstant('{app}\version.txt'), Lines) and
     (GetArrayLength(Lines) > 0) then
    Result := Trim(Lines[0]);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RecoveryDirectory: String;
  DownloadedSetup: String;
  NewSetup: String;
  NewMetadata: String;
begin
  Result := '';
  if CompareText(ReadInstalledVersion(), '{#PreviousVersion}') <> 0 then
    Exit;

  RecoveryDirectory := ExpandConstant('{commonappdata}\Claude\Recovery');
  if RecoveryCacheMatches(RecoveryDirectory, '{#PreviousSetupSha}') then
    Exit;

  try
    DownloadedSetup := DownloadTemporaryFile(
      '{#PreviousSetupUrl}',
      'Claude_v{#PreviousVersion}_Setup.exe',
      '{#PreviousSetupSha}',
      @OnDownloadProgress
    );
    if CompareText(GetSHA256OfFile(DownloadedSetup), '{#PreviousSetupSha}') <> 0 then
      RaiseException('이전 버전 설치 파일의 무결성 검증에 실패했습니다.');
    if not ForceDirectories(RecoveryDirectory) then
      RaiseException('복구 폴더를 만들지 못했습니다: ' + RecoveryDirectory);

    NewSetup := AddBackslash(RecoveryDirectory) + 'previous_setup.new';
    NewMetadata := AddBackslash(RecoveryDirectory) + 'recovery.json.new';
    DeleteFile(NewSetup);
    DeleteFile(NewMetadata);
    if not FileCopy(DownloadedSetup, NewSetup, False) then
      RaiseException('이전 버전 설치 파일을 복구 폴더에 복사하지 못했습니다.');
    if CompareText(GetSHA256OfFile(NewSetup), '{#PreviousSetupSha}') <> 0 then
      RaiseException('복구 폴더에 복사한 설치 파일의 무결성 검증에 실패했습니다.');
    WriteRecoveryMetadataFile(
      NewMetadata,
      '{#PreviousVersion}',
      '{#AppVersion}',
      ExpandConstant('{app}'),
      '{#PreviousSetupSha}'
    );

    DeleteFile(AddBackslash(RecoveryDirectory) + 'previous_setup.exe');
    if not RenameFile(NewSetup, AddBackslash(RecoveryDirectory) + 'previous_setup.exe') then
      RaiseException('복구 설치 파일을 확정하지 못했습니다.');
    DeleteFile(AddBackslash(RecoveryDirectory) + 'recovery.json');
    if not RenameFile(NewMetadata, AddBackslash(RecoveryDirectory) + 'recovery.json') then
      RaiseException('복구 메타데이터를 확정하지 못했습니다.');
  except
    Result := '2.4.6 복구본을 안전하게 보관하지 못해 업데이트를 중단했습니다.' + #13#10 +
      GetExceptionMessage;
  end;
end;

function NeedRestart(): Boolean;
begin
  Result := WizardIsTaskSelected('interceptiondriver');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WriteReleaseMetadata(
      ExpandConstant('{srcexe}'),
      ExpandConstant('{app}'),
      '{#AppVersion}',
      '{#CurrentSetupUrl}'
    );
    if RecoveryCacheMatches(
      ExpandConstant('{commonappdata}\Claude\Recovery'),
      '{#PreviousSetupSha}'
    ) then
      WriteRecoveryMetadata(
        ExpandConstant('{commonappdata}\Claude\Recovery'),
        '{#PreviousVersion}',
        '{#AppVersion}',
        ExpandConstant('{app}'),
        '{#PreviousSetupSha}'
      );
  end;
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('interceptiondriver') then
    MsgBox(
      'Interception driver installation has finished.' + #13#10 + #13#10 +
      'Please restart Windows before using driver input.' + #13#10 +
      'If you skip restart, Claude can still run, but driver input may not work.',
      mbInformation, MB_OK
    );
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  RemoveRecoveryCache := False;
  if not UninstallSilent then
    RemoveRecoveryCache := MsgBox(
      '이전 버전 되돌리기에 사용하는 복구 설치 파일도 삭제하시겠습니까?',
      mbConfirmation,
      MB_YESNO
    ) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and RemoveRecoveryCache then
    DelTree(ExpandConstant('{commonappdata}\Claude\Recovery'), True, True, True);
end;
