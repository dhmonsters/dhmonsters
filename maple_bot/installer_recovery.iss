// Claude 설치기가 복구용 JSON과 설치 파일 무결성 정보를 생성하는 공용 Pascal 코드

function RecoveryJsonEscape(const Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
  StringChangeEx(Result, #13, '\r', True);
  StringChangeEx(Result, #10, '\n', True);
end;

function ShouldPrepareCurrentVersionRecovery(
  const InstalledVersion, NewVersion: String): Boolean;
begin
  Result := (Trim(InstalledVersion) <> '') and
    (CompareText(Trim(InstalledVersion), Trim(NewVersion)) <> 0);
end;

function BuildReleaseSetupFileName(const Version: String): String;
begin
  Result := 'Claude_v' + Trim(Version) + '_Setup.exe';
end;

function BuildReleaseSetupUrl(const Version: String): String;
begin
  Result :=
    'https://github.com/dhmonsters/dhmonsters/releases/download/v' +
    Trim(Version) + '/' + BuildReleaseSetupFileName(Version);
end;

procedure WriteReleaseMetadata(
  const SourceSetup, AppDirectory, Version, DownloadUrl: String);
var
  Lines: TArrayOfString;
  JsonText: String;
  Digest: String;
  OutputPath: String;
begin
  if not FileExists(SourceSetup) then
    RaiseException('현재 설치 파일을 찾지 못했습니다: ' + SourceSetup);
  if not ForceDirectories(AppDirectory) then
    RaiseException('설치 메타데이터 폴더를 만들지 못했습니다: ' + AppDirectory);

  Digest := Lowercase(GetSHA256OfFile(SourceSetup));
  JsonText :=
    '{"version":"' + RecoveryJsonEscape(Version) + '",' +
    '"download_url":"' + RecoveryJsonEscape(DownloadUrl) + '",' +
    '"sha256":"' + Digest + '"}';
  SetArrayLength(Lines, 1);
  Lines[0] := JsonText;
  OutputPath := AddBackslash(AppDirectory) + 'release.json';
  if not SaveStringsToUTF8FileWithoutBOM(OutputPath, Lines, False) then
    RaiseException('release.json을 저장하지 못했습니다: ' + OutputPath);
end;

procedure WriteRecoveryMetadataFile(
  const OutputPath, PreviousVersion, CurrentVersion,
  InstallationPath, PreviousSha256: String);
var
  Lines: TArrayOfString;
  JsonText: String;
begin
  JsonText :=
    '{"previous_version":"' + RecoveryJsonEscape(PreviousVersion) + '",' +
    '"current_version":"' + RecoveryJsonEscape(CurrentVersion) + '",' +
    '"installation_path":"' + RecoveryJsonEscape(InstallationPath) + '",' +
    '"previous_sha256":"' + Lowercase(PreviousSha256) + '",' +
    '"created_at":"' + GetDateTimeString('yyyy-mm-dd"T"hh:nn:ss', '-', ':') + '"}';
  SetArrayLength(Lines, 1);
  Lines[0] := JsonText;
  if not SaveStringsToUTF8FileWithoutBOM(OutputPath, Lines, False) then
    RaiseException('recovery.json을 저장하지 못했습니다: ' + OutputPath);
end;

procedure StoreRecoverySetup(
  const SourceSetup, RecoveryDirectory, PreviousVersion, CurrentVersion,
  InstallationPath: String);
var
  RecoverySha: String;
  NewSetup: String;
  NewMetadata: String;
begin
  if not FileExists(SourceSetup) then
    RaiseException('복구할 설치 파일을 찾지 못했습니다: ' + SourceSetup);
  RecoverySha := Lowercase(GetSHA256OfFile(SourceSetup));
  if Length(RecoverySha) <> 64 then
    RaiseException('복구할 설치 파일의 SHA-256 계산에 실패했습니다.');
  if not ForceDirectories(RecoveryDirectory) then
    RaiseException('복구 폴더를 만들지 못했습니다: ' + RecoveryDirectory);

  NewSetup := AddBackslash(RecoveryDirectory) + 'previous_setup.new';
  NewMetadata := AddBackslash(RecoveryDirectory) + 'recovery.json.new';
  DeleteFile(NewSetup);
  DeleteFile(NewMetadata);
  if not FileCopy(SourceSetup, NewSetup, False) then
    RaiseException('현재 버전 설치 파일을 복구 폴더에 복사하지 못했습니다.');
  if CompareText(GetSHA256OfFile(NewSetup), RecoverySha) <> 0 then
    RaiseException('복구 폴더에 복사한 설치 파일의 무결성 검증에 실패했습니다.');
  WriteRecoveryMetadataFile(
    NewMetadata,
    PreviousVersion,
    CurrentVersion,
    InstallationPath,
    RecoverySha
  );

  DeleteFile(AddBackslash(RecoveryDirectory) + 'previous_setup.exe');
  if not RenameFile(NewSetup, AddBackslash(RecoveryDirectory) + 'previous_setup.exe') then
    RaiseException('복구 설치 파일을 확정하지 못했습니다.');
  DeleteFile(AddBackslash(RecoveryDirectory) + 'recovery.json');
  if not RenameFile(NewMetadata, AddBackslash(RecoveryDirectory) + 'recovery.json') then
    RaiseException('복구 메타데이터를 확정하지 못했습니다.');
end;
