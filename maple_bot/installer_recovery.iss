// Claude 설치기가 복구용 JSON과 설치 파일 무결성 정보를 생성하는 공용 Pascal 코드

function RecoveryJsonEscape(const Value: String): String;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
  StringChangeEx(Result, #13, '\r', True);
  StringChangeEx(Result, #10, '\n', True);
end;

function RecoveryCacheMatches(
  const RecoveryDirectory, ExpectedSha256: String): Boolean;
var
  InstallerPath: String;
begin
  Result := False;
  InstallerPath := AddBackslash(RecoveryDirectory) + 'previous_setup.exe';
  if not FileExists(InstallerPath) then
    Exit;
  try
    Result := CompareText(
      GetSHA256OfFile(InstallerPath),
      ExpectedSha256
    ) = 0;
  except
    Result := False;
  end;
end;

function ShouldPrepareStableRecovery(
  const InstalledVersion: String;
  const StableCacheMatches: Boolean): Boolean;
begin
  Result := (Trim(InstalledVersion) <> '') and not StableCacheMatches;
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

procedure WriteRecoveryMetadata(
  const RecoveryDirectory, PreviousVersion, CurrentVersion,
  InstallationPath, PreviousSha256: String);
begin
  if not ForceDirectories(RecoveryDirectory) then
    RaiseException('복구 메타데이터 폴더를 만들지 못했습니다: ' + RecoveryDirectory);
  WriteRecoveryMetadataFile(
    AddBackslash(RecoveryDirectory) + 'recovery.json',
    PreviousVersion,
    CurrentVersion,
    InstallationPath,
    PreviousSha256
  );
end;
