; 설치기 공용 복구 코드가 실제 설치 후 release.json을 생성하는지 검증하는 하네스
#ifndef TestOutput
  #error TestOutput is required
#endif
#ifndef TestPayloadSha
  #error TestPayloadSha is required
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

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteReleaseMetadata(
      ExpandConstant('{srcexe}'),
      ExpandConstant('{app}'),
      '9.9.9',
      'https://github.com/dhmonsters/dhmonsters/releases/download/v9.9.9/Claude_v9.9.9_Setup.exe'
    );
    WriteRecoveryMetadata(
      AddBackslash(ExpandConstant('{app}')) + 'Recovery',
      '9.9.8',
      '9.9.9',
      ExpandConstant('{app}'),
      'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
    );
    ForceDirectories(AddBackslash(ExpandConstant('{app}')) + 'Recovery');
    if not SaveStringToFile(
      AddBackslash(ExpandConstant('{app}')) + 'Recovery\previous_setup.exe',
      'payload',
      False
    ) then
      RaiseException('recovery cache fixture creation failed');
    if not RecoveryCacheMatches(
      AddBackslash(ExpandConstant('{app}')) + 'Recovery',
      '{#TestPayloadSha}'
    ) then
      RaiseException('valid recovery cache was rejected');
    if RecoveryCacheMatches(
      AddBackslash(ExpandConstant('{app}')) + 'Recovery',
      '0000000000000000000000000000000000000000000000000000000000000000'
    ) then
      RaiseException('invalid recovery cache was accepted');
end;
