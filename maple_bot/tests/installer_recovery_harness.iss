; 설치기 공용 복구 코드가 실제 설치 후 release.json을 생성하는지 검증하는 하네스
#ifndef TestOutput
  #error TestOutput is required
#endif
#ifndef TestPayloadSha
  #error TestPayloadSha is required
#endif
#ifndef TestPayload
  #error TestPayload is required
#endif

[Setup]
AppId={{A09348D8-C878-4F57-A98C-92EB564C96E1}
AppName=Claude Recovery Harness
AppVersion=9.9.9
DefaultDirName={tmp}\ClaudeRecoveryHarness
OutputDir={#TestOutput}
OutputBaseFilename=InstallerRecoveryHarness
PrivilegesRequired=lowest
Uninstallable=no
Compression=zip

[Code]
#include "..\installer_recovery.iss"

procedure VerifyCurrentVersionRecoveryPolicy();
begin
  if not ShouldPrepareCurrentVersionRecovery('2.4.1', '2.4.9') then
    RaiseException('2.4.1 must be preserved before update');
  if not ShouldPrepareCurrentVersionRecovery('2.4.5', '2.4.9') then
    RaiseException('2.4.5 must be preserved before update');
  if not ShouldPrepareCurrentVersionRecovery('2.4.8', '2.4.9') then
    RaiseException('2.4.8 must be preserved before update');
  if ShouldPrepareCurrentVersionRecovery('', '2.4.9') then
    RaiseException('fresh install must not create previous-version recovery');
  if ShouldPrepareCurrentVersionRecovery('2.4.9', '2.4.9') then
    RaiseException('same-version reinstall must not replace recovery');

  if CompareText(
    BuildReleaseSetupFileName('2.4.1'),
    'Claude_v2.4.1_Setup.exe'
  ) <> 0 then
    RaiseException('2.4.1 recovery file name is wrong');
  if CompareText(
    BuildReleaseSetupUrl('2.4.5'),
    'https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.5/Claude_v2.4.5_Setup.exe'
  ) <> 0 then
    RaiseException('2.4.5 recovery URL is wrong');
  if CompareText(
    BuildReleaseSetupUrl('2.4.8'),
    'https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.8/Claude_v2.4.8_Setup.exe'
  ) <> 0 then
    RaiseException('2.4.8 recovery URL is wrong');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  RecoveryDirectory: String;
begin
  if CurStep = ssPostInstall then
  begin
    VerifyCurrentVersionRecoveryPolicy();
    WriteReleaseMetadata(
      ExpandConstant('{srcexe}'),
      ExpandConstant('{app}'),
      '9.9.9',
      'https://github.com/dhmonsters/dhmonsters/releases/download/v9.9.9/Claude_v9.9.9_Setup.exe'
    );
    RecoveryDirectory := AddBackslash(ExpandConstant('{app}')) + 'Recovery';
    StoreRecoverySetup(
      '{#TestPayload}',
      RecoveryDirectory,
      '2.4.5',
      '2.4.9',
      ExpandConstant('{app}')
    );
  end;
end;
