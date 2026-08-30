# Claude Native Recovery Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PyQt6 또는 PyInstaller 초기화가 실패해도 열리는 독립 복구창에서 직전 버전 복원, 업데이트 확인, 같은 버전 재설치와 오류 복사를 제공한다.

**Architecture:** 관리자 권한의 .NET Framework Windows Forms 실행기 `Claude.exe`가 실제 PyInstaller 앱 `ClaudeApp.exe`를 자식 프로세스로 감시한다. Python 앱은 준비 완료와 치명적 오류를 `%ProgramData%\Claude\Recovery`에 기록하고, 정상 업데이트는 현재 설치본을 검증된 직전 버전 설치 파일로 원자적으로 보관한다. 롤백은 임시 복구 작업자가 현재 프로그램 파일만 허용 목록으로 정리한 뒤 직전 설치기를 같은 경로에 실행한다.

**Tech Stack:** Python 3.14, pytest, PyInstaller onedir, C#/.NET Framework 4 Windows Forms, Inno Setup 6 Pascal Script, GitHub Release/Raw JSON.

**Spec:** `docs/superpowers/specs/2026-08-30-native-recovery-launcher-design.md`

## Global Constraints

- 첫 적용 버전은 Claude 2.4.7이다.
- 사용자 실행 파일은 `Claude.exe`, 실제 PyInstaller 앱은 `ClaudeApp.exe`이다.
- 복구 실행기는 Python, PyQt6, Qt DLL에 의존하지 않는다.
- 설치된 프로그램은 한 버전만 유지하고 복구 설치 파일은 직전 버전 한 개만 유지한다.
- 복구 저장소는 `%ProgramData%\Claude\Recovery`이다.
- 설정, 라이선스, 맵, 템플릿 사용자 데이터와 Interception 드라이버는 롤백 정리 대상이 아니다.
- 다운로드는 HTTPS GitHub Release URL만 허용하고 실행 전 SHA-256을 검증한다.
- 일반 감지 실패와 기능별 재시도는 복구창을 열지 않는다.
- PyInstaller 부트로더를 수정하지 않는다.
- C# 소스는 Windows 기본 .NET Framework 4 컴파일러가 처리할 수 있는 C# 5 문법만 사용한다.
- 새 소스 파일 첫 줄에는 역할을 설명하는 한국어 주석을 둔다.

---

## File map

- `core/recovery_protocol.py` — Python 앱의 준비 완료·치명적 오류 기록 규약.
- `core/update_recovery.py` — 현재 버전 설치본 다운로드, SHA-256 검증, 복구 캐시 원자 교체.
- `core/updater.py` — 원격 메타데이터 검증과 업데이트 적용 전 복구본 확보.
- `ui/dialog_update.py` — 검증된 설치 파일과 업데이트 정보를 적용 계층에 전달.
- `run_integrated.py` — 런처 관리 여부 판정, 준비 완료 신호, 최상위 치명적 오류 기록.
- `recovery_launcher/Program.cs` — 단일 인스턴스, 관리자 실행, 자식 프로세스 감시와 작업자 모드 진입점.
- `recovery_launcher/RecoveryModels.cs` — JSON 모델과 종료 판정 값.
- `recovery_launcher/RecoveryStore.cs` — 경로 제한, JSON, SHA-256, 복구 파일 검증.
- `recovery_launcher/UpdateClient.cs` — GitHub Raw 조회와 검증 다운로드.
- `recovery_launcher/RecoveryForm.cs` — 네 가지 복구 버튼과 상태 표시.
- `recovery_launcher/RollbackWorker.cs` — 런처 종료 대기, 허용 목록 정리, 이전 설치기 실행.
- `recovery_launcher/app.manifest` — `requireAdministrator` 실행 수준.
- `recovery_launcher/build_launcher.bat` — Framework64 `csc.exe`를 사용한 재현 가능한 빌드.
- `tests/test_recovery_protocol.py` — Python 신호·오류 파일 테스트.
- `tests/test_update_recovery.py` — 해시·URL·원자 교체·업데이트 분기 테스트.
- `tests/recovery_launcher/RecoveryLauncherTests.cs` — C# 종료 판정·경로·복구 저장소 테스트.
- `tests/test_recovery_launcher_build.py` — C# 테스트와 런처 빌드 호출 테스트.
- `tests/test_release_bundle_validation.py` — 두 실행 파일과 Qt 독립성 검증.
- `release_bundle_validation.py` — 새 산출물 구조 검증.
- `build.bat`, `installer.iss`, `version.txt`, `version.json` — 2.4.7 빌드와 설치 메타데이터.
- `03_output/2026-08-30_native-recovery-launcher_v1_checklist.md` — 실행 체크리스트.
- `03_output/2026-08-30_native-recovery-launcher_v1_context-notes.md` — 결정과 검증 기록.

### Task 1: Python 치명적 오류·준비 완료 프로토콜

**Files:**
- Create: `core/recovery_protocol.py`
- Modify: `run_integrated.py`
- Test: `tests/test_recovery_protocol.py`

**Interfaces:**
- Produces: `is_launcher_managed() -> bool`, `write_ready() -> bool`, `write_normal_exit(reason: str) -> bool`, `write_fatal(kind: str, message: str, traceback_text: str = "", exit_code: int = 1) -> bool`.
- Environment: `CLAUDE_RECOVERY_MANAGED=1`, `CLAUDE_RECOVERY_READY_FILE`, `CLAUDE_RECOVERY_CRASH_FILE`, `CLAUDE_RECOVERY_NORMAL_FILE`.

- [ ] **Step 1: Write failing protocol tests**

```python
def test_write_ready_uses_launcher_path_atomically(tmp_path, monkeypatch):
    target = tmp_path / "ready.json"
    monkeypatch.setenv("CLAUDE_RECOVERY_READY_FILE", str(target))
    assert recovery_protocol.write_ready() is True
    assert json.loads(target.read_text(encoding="utf-8"))["status"] == "ready"
    assert not target.with_suffix(".tmp").exists()

def test_write_fatal_never_raises_when_path_is_unwritable(monkeypatch):
    monkeypatch.setenv("CLAUDE_RECOVERY_CRASH_FILE", "Z:\\missing\\crash.json")
    assert recovery_protocol.write_fatal("BOOT", "QtWidgets load failed") is False
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/test_recovery_protocol.py -q`

Expected: collection fails because `core.recovery_protocol` does not exist.

- [ ] **Step 3: Implement the protocol with atomic UTF-8 JSON writes**

```python
# 복구 실행기와 실제 앱 사이의 준비 완료 및 치명적 오류 파일 규약을 제공한다.
def is_launcher_managed() -> bool:
    return os.environ.get("CLAUDE_RECOVERY_MANAGED") == "1"

def write_ready() -> bool:
    return _write_json_from_env("CLAUDE_RECOVERY_READY_FILE", {
        "status": "ready", "pid": os.getpid(), "created_at": _utc_now(),
    })

def write_fatal(kind: str, message: str, traceback_text: str = "", exit_code: int = 1) -> bool:
    return _write_json_from_env("CLAUDE_RECOVERY_CRASH_FILE", {
        "kind": kind, "message": message, "traceback": traceback_text,
        "exit_code": int(exit_code), "pid": os.getpid(), "created_at": _utc_now(),
    })

def write_normal_exit(reason: str) -> bool:
    return _write_json_from_env("CLAUDE_RECOVERY_NORMAL_FILE", {
        "status": "normal", "reason": reason, "pid": os.getpid(), "created_at": _utc_now(),
    })
```

- [ ] **Step 4: Integrate the protocol at the real lifecycle boundaries**

In `run_integrated.py`, call `ensure_admin()` only when `is_launcher_managed()` is false, call `write_ready()` immediately after `shell.show()`, call `write_normal_exit("user_close")` after `app.exec()` returns 0, and make the top-level exception hook write the complete traceback before the process exits nonzero. `core.updater.apply_update()` calls `write_normal_exit("update_handoff")` before starting the installer. Thread exceptions remain log-only because they do not terminate the app.

```python
if not recovery_protocol.is_launcher_managed():
    ensure_admin()

shell.show()
recovery_protocol.write_ready()
```

- [ ] **Step 5: Run tests and compile check**

Run: `python -m pytest tests/test_recovery_protocol.py tests/test_admin_util.py -q`

Run: `python -m py_compile core/recovery_protocol.py run_integrated.py`

Expected: all tests pass and compilation exits 0.

- [ ] **Step 6: Commit**

```bash
git add core/recovery_protocol.py run_integrated.py tests/test_recovery_protocol.py
git commit -m "치명적 오류 복구 신호 추가"
```

### Task 2: 업데이트 전 직전 버전 복구본 확보

**Files:**
- Create: `core/update_recovery.py`
- Modify: `core/updater.py`
- Modify: `ui/dialog_update.py`
- Test: `tests/test_update_recovery.py`

**Interfaces:**
- Consumes: remote update dict keys `version`, `notes`, `download_url`, `sha256`.
- Produces: `validate_release_url(url: str) -> None`, `sha256_file(path: Path) -> str`, `ensure_previous_installer(current_release: dict, downloader: Callable) -> Path`, `download_update(url: str, expected_sha256: str, progress_cb=None) -> str`.
- Local metadata: `{app}\release.json` with `version`, `download_url`, `sha256`.

- [ ] **Step 1: Write failing URL, hash and atomic replacement tests**

```python
def test_rejects_non_github_or_non_https_release_url():
    with pytest.raises(ValueError):
        update_recovery.validate_release_url("http://github.com/a/b.exe")
    with pytest.raises(ValueError):
        update_recovery.validate_release_url("https://example.com/a.exe")

def test_ensure_previous_installer_replaces_only_after_hash_matches(tmp_path):
    current = {"version": "2.4.7", "download_url": GOOD_URL, "sha256": GOOD_HASH}
    old = tmp_path / "previous_setup.exe"
    old.write_bytes(b"old")
    result = update_recovery.ensure_previous_installer(
        current, lambda *_args, **_kwargs: b"current", recovery_dir=tmp_path)
    assert result.read_bytes() == b"current"
    assert json.loads((tmp_path / "recovery.json").read_text("utf-8"))["previous_version"] == "2.4.7"
```

- [ ] **Step 2: Verify the focused tests fail**

Run: `python -m pytest tests/test_update_recovery.py -q`

Expected: collection fails because `core.update_recovery` does not exist.

- [ ] **Step 3: Implement strict URL, streaming SHA-256 and atomic cache replacement**

```python
# 업데이트 전 현재 버전 설치 파일을 검증해 직전 버전 복구본으로 보관한다.
def validate_release_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError("공식 GitHub HTTPS Release URL만 허용됩니다.")
    if "/dhmonsters/dhmonsters/releases/download/" not in parsed.path:
        raise ValueError("공식 Claude Release 경로가 아닙니다.")
```

Download to `previous_setup.download`, verify lowercase 64-hex SHA-256, write `recovery.json.download`, then use `os.replace` for both final files only after every validation succeeds. On failure, remove only the temporary files and preserve the prior cache.

- [ ] **Step 4: Require SHA-256 in updater metadata and downloaded installers**

`check_for_update()` must reject missing or malformed `download_url` and `sha256`. `download_update()` must delete a mismatched temporary file and raise `RuntimeError`. `apply_update()` must call `ensure_previous_installer()` before launching a higher version installer.

```python
def apply_update(installer_path: str, update_info: dict) -> None:
    current_release = update_recovery.read_local_release()
    update_recovery.ensure_previous_installer(current_release)
    subprocess.Popen([installer_path], close_fds=True)
    sys.exit(0)
```

- [ ] **Step 5: Pass the full update dict from the dialog**

Change `UpdateDialog._download_thread()` to pass `self._info["sha256"]`, and `_apply()` to call `apply_update(self._installer_path, self._info)`.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_update_recovery.py -q`

Expected: all URL, hash mismatch, atomic preservation, and apply-order tests pass.

- [ ] **Step 7: Commit**

```bash
git add core/update_recovery.py core/updater.py ui/dialog_update.py tests/test_update_recovery.py
git commit -m "업데이트 전 직전 버전 복구본 확보"
```

### Task 3: 독립 실행기 프로세스 감시 기반

**Files:**
- Create: `recovery_launcher/Program.cs`
- Create: `recovery_launcher/RecoveryModels.cs`
- Create: `recovery_launcher/RecoveryStore.cs`
- Create: `recovery_launcher/app.manifest`
- Create: `tests/recovery_launcher/RecoveryLauncherTests.cs`
- Create: `tests/test_recovery_launcher_build.py`

**Interfaces:**
- Produces: `LaunchDecision.ShouldShowRecovery(int exitCode, bool readySeen, bool normalMarkerSeen) -> bool`, `LaunchDecision.GetFailurePhase(bool readySeen) -> FailurePhase`.
- Produces: `RecoveryStore.Load()`, `RecoveryStore.ValidatePreviousInstaller()`, `RecoveryStore.ReadLastCrash()`.
- Child environment contains the four `CLAUDE_RECOVERY_*` values defined in Task 1.

- [ ] **Step 1: Write the failing C# decision and store tests**

```csharp
// 복구 실행기의 종료 판정과 저장소 무결성을 검증한다.
AssertFalse(LaunchDecision.ShouldShowRecovery(0, true, false), "normal exit");
AssertFalse(LaunchDecision.ShouldShowRecovery(23, true, true), "update handoff");
AssertTrue(LaunchDecision.ShouldShowRecovery(1, false, false), "boot failure");
AssertTrue(LaunchDecision.ShouldShowRecovery(unchecked((int)0xC0000005), true, false), "native crash");
AssertEqual(FailurePhase.Startup, LaunchDecision.GetFailurePhase(false), "before ready");
AssertEqual(FailurePhase.Runtime, LaunchDecision.GetFailurePhase(true), "after ready");
```

- [ ] **Step 2: Add a pytest wrapper that compiles and runs the C# test executable**

Use `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`, references `System.Windows.Forms.dll`, `System.Drawing.dll`, `System.Web.Extensions.dll`, and assert the test process prints `PASS` with exit code 0.

Run: `python -m pytest tests/test_recovery_launcher_build.py -q`

Expected: fail because launcher sources are absent.

- [ ] **Step 3: Implement models, store validation and exit classification**

```csharp
// 복구 상태 JSON 모델과 자식 프로세스 종료 판정을 정의한다.
internal static class LaunchDecision
{
    internal static bool ShouldShowRecovery(int exitCode, bool readySeen, bool normalMarkerSeen)
    {
        if (normalMarkerSeen) return false;
        return exitCode != 0;
    }
}
```

`RecoveryStore` normalizes `%ProgramData%\Claude\Recovery`, accepts only files directly inside that directory, validates a 64-hex SHA-256, and returns a disabled rollback reason instead of throwing on malformed JSON. Directory ACL inheritance is disabled and only `SYSTEM` and `Administrators` receive full control; ordinary users receive read/execute only.

- [ ] **Step 4: Implement the launcher entry and child monitoring**

Acquire a global named mutex, remove stale per-run ready/crash files, start `{app}\ClaudeApp.exe` with inherited arguments and recovery environment, wait for exit, then show no UI on normal exit and pass abnormal state to the recovery form. The embedded manifest uses `<requestedExecutionLevel level="requireAdministrator" uiAccess="false" />`.

- [ ] **Step 5: Run C# tests**

Run: `python -m pytest tests/test_recovery_launcher_build.py -q`

Expected: all C# compile and behavioral tests pass.

- [ ] **Step 6: Commit**

```bash
git add recovery_launcher/Program.cs recovery_launcher/RecoveryModels.cs recovery_launcher/RecoveryStore.cs recovery_launcher/app.manifest tests/recovery_launcher/RecoveryLauncherTests.cs tests/test_recovery_launcher_build.py
git commit -m "독립 복구 실행기 프로세스 감시 추가"
```

### Task 4: 복구창, 업데이트 확인과 안전한 롤백 작업자

**Files:**
- Create: `recovery_launcher/UpdateClient.cs`
- Create: `recovery_launcher/RecoveryForm.cs`
- Create: `recovery_launcher/RollbackWorker.cs`
- Modify: `recovery_launcher/Program.cs`
- Modify: `tests/recovery_launcher/RecoveryLauncherTests.cs`

**Interfaces:**
- Produces: `UpdateClient.FetchLatest() -> ReleaseInfo`, `UpdateClient.DownloadVerified(ReleaseInfo, string) -> string`.
- Produces: `RecoveryStore.PrepareCurrentAsPrevious(ReleaseInfo currentRelease) -> RecoveryMetadata` before a higher-version install.
- Produces: `RollbackWorker.StartDetached(RecoveryMetadata) -> void`, worker CLI `--rollback-worker <parentPid> <metadataPath>`.
- UI buttons: `이전 버전으로 되돌리기`, `업데이트 확인`, `오류 내용 복사`, `닫기`.

- [ ] **Step 1: Add failing tests for URL allowlist, same-version reinstall and cleanup allowlist**

```csharp
AssertTrue(UpdateClient.IsAllowedReleaseUrl(
    "https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.7/Claude_v2.4.7_Setup.exe"), "official release");
AssertFalse(UpdateClient.IsAllowedReleaseUrl("https://example.com/Claude.exe"), "foreign host");
AssertEqual(UpdateAction.Reinstall, UpdatePolicy.Decide("2.4.7", "2.4.7"), "same version");
AssertFalse(RollbackWorker.IsCleanupTarget("drivers"), "driver preserved");
AssertTrue(RollbackWorker.IsCleanupTarget("_internal"), "runtime removed");
```

- [ ] **Step 2: Verify C# tests fail**

Run: `python -m pytest tests/test_recovery_launcher_build.py -q`

Expected: compile failures for the undefined update and rollback types.

- [ ] **Step 3: Implement the update client**

Use `HttpWebRequest` with a finite timeout, deserialize UTF-8 JSON with `JavaScriptSerializer`, validate `version`, official HTTPS URL and 64-hex `sha256`, stream to a temporary file, and compare SHA-256 before returning the path. Validate the initial Release URL before allowing redirects and rely on the required SHA-256 for redirected CDN content. A same-version response is exposed as reinstall; an older remote version is rejected. Before installing a higher version from the recovery form, read `{app}\release.json`, download and validate the currently installed version, and atomically replace the previous cache. A same-version reinstall leaves the existing previous cache unchanged.

- [ ] **Step 4: Implement the recovery form**

Show error kind, message, exit code and expandable traceback. Disable rollback with a visible reason when cache validation fails. Run download/hash work asynchronously, keep the window open on errors, copy the full UTF-8 error text to the clipboard, and leave `닫기` always enabled.

- [ ] **Step 5: Implement the detached rollback worker**

The launcher copies itself to `%TEMP%\ClaudeRecovery\ClaudeRecoveryWorker.exe`, starts worker mode with metadata path, then exits. The worker waits for the parent PID, revalidates install path and installer SHA-256, deletes only this allowlist, then launches the previous installer with `/SILENT /SUPPRESSMSGBOXES /NORESTART /DIR="<recorded path>"`, waits for exit code 0, and starts the restored `{app}\Claude.exe`.

```csharp
private static readonly string[] CleanupNames = {
    "Claude.exe", "ClaudeApp.exe", "_internal", "core", "core_ui", "ui",
    "assets", "templates", "monsters", "models", "maps", "config.json",
    "version.txt", "release.json"
};
```

Reject empty paths, filesystem roots, paths outside the metadata installation directory, and metadata not located under `%ProgramData%\Claude\Recovery`. Preserve `drivers`, `%APPDATA%\Claude`, `%LOCALAPPDATA%\Claude`, and the recovery directory.

- [ ] **Step 6: Run C# tests**

Run: `python -m pytest tests/test_recovery_launcher_build.py -q`

Expected: exit policy, update policy, URL validation, hash validation and cleanup allowlist tests pass.

- [ ] **Step 7: Commit**

```bash
git add recovery_launcher tests/recovery_launcher/RecoveryLauncherTests.cs tests/test_recovery_launcher_build.py
git commit -m "복구창과 안전한 이전 버전 복원 추가"
```

### Task 5: 빌드 산출물을 Claude.exe와 ClaudeApp.exe로 분리

**Files:**
- Create: `recovery_launcher/build_launcher.bat`
- Modify: `build.bat`
- Modify: `release_bundle_validation.py`
- Modify: `tests/test_release_bundle_validation.py`

**Interfaces:**
- Consumes: Task 3–4 C# sources and manifest.
- Produces: `dist\Claude_2.4.7\Claude.exe`, `dist\Claude_2.4.7\ClaudeApp.exe` and `_internal`.

- [ ] **Step 1: Extend failing release bundle tests**

```python
def test_requires_launcher_and_real_app(tmp_path):
    bundle = tmp_path / "Claude"
    bundle.mkdir()
    errors = validate_release_bundle(tmp_path / "Analysis-00.toc", bundle)
    assert "복구 실행기 Claude.exe가 없습니다." in errors
    assert "실제 앱 ClaudeApp.exe가 없습니다." in errors
```

Also assert `Claude.exe` has no imports or colocated dependency requirement for Qt6/Python by checking the launcher build inputs and that Qt DLLs remain under the PyInstaller `_internal` tree only.

- [ ] **Step 2: Verify the release validation test fails**

Run: `python -m pytest tests/test_release_bundle_validation.py -q`

Expected: new launcher/app presence assertions fail.

- [ ] **Step 3: Add the launcher build script**

```bat
@rem Qt 없이 실행되는 Claude 복구 실행기를 빌드한다.
@echo off
set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
"%CSC%" /nologo /target:winexe /platform:x64 /optimize+ /out:"%~1\Claude.exe" /win32manifest:recovery_launcher\app.manifest /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll recovery_launcher\Program.cs recovery_launcher\RecoveryModels.cs recovery_launcher\RecoveryStore.cs recovery_launcher\UpdateClient.cs recovery_launcher\RecoveryForm.cs recovery_launcher\RollbackWorker.cs
exit /b %ERRORLEVEL%
```

- [ ] **Step 4: Change the PyInstaller app name and suppress its default traceback dialog**

Use `--name ClaudeApp --disable-windowed-traceback`, validate `.obf_build\dist\ClaudeApp`, copy it to `dist\Claude_2.4.7`, then compile the independent launcher into that directory. Update every old `Claude` build path consistently.

- [ ] **Step 5: Implement and run bundle validation**

Run: `python -m pytest tests/test_release_bundle_validation.py tests/test_recovery_launcher_build.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add recovery_launcher/build_launcher.bat build.bat release_bundle_validation.py tests/test_release_bundle_validation.py
git commit -m "배포 실행기와 실제 앱 빌드 분리"
```

### Task 6: Inno Setup 복구 캐시와 2.4.7 최초 전환

**Files:**
- Modify: `installer.iss`
- Create: `tests/test_installer_recovery_contract.py`

**Interfaces:**
- Consumes: official 2.4.6 URL and SHA-256 `7a7e066479b273fb22fa74ef42cfe5c959925b34b38c02cb9c68baf18fa63b8a`.
- Produces: `{app}\release.json`, `%ProgramData%\Claude\Recovery\previous_setup.exe`, `%ProgramData%\Claude\Recovery\recovery.json`.

- [ ] **Step 1: Write failing installer contract tests**

Assert `installer.iss` targets `Claude.exe`, contains `DownloadTemporaryFile`, validates the exact 2.4.6 SHA-256 before copying, uses `GetSHA256OfFile(ExpandConstant('{srcexe}'))` for the installed 2.4.7 metadata, writes UTF-8 JSON, and never includes `previous_setup.exe` in `[Files]`.

- [ ] **Step 2: Verify installer contract tests fail**

Run: `python -m pytest tests/test_installer_recovery_contract.py -q`

Expected: missing bootstrap and local release metadata assertions fail.

- [ ] **Step 3: Add the pre-install 2.4.6 bootstrap**

In `PrepareToInstall`, when `{app}\version.txt` is exactly `2.4.6` and no valid 2.4.6 cache exists, call the documented Inno API below. Any exception returns a non-empty error string so file installation does not begin.

```pascal
DownloadTemporaryFile(
  'https://github.com/dhmonsters/dhmonsters/releases/download/v2.4.6/Claude_v2.4.6_Setup.exe',
  'Claude_v2.4.6_Setup.exe',
  '7a7e066479b273fb22fa74ef42cfe5c959925b34b38c02cb9c68baf18fa63b8a',
  @OnDownloadProgress);
```

Copy the verified temporary file to `previous_setup.new`, write `recovery.json.new`, then rename both into final names. An offline fresh install with no existing version continues without rollback cache; an offline upgrade from 2.4.6 stops before file replacement.

- [ ] **Step 4: Generate current release metadata after successful installation**

Use `GetSHA256OfFile(ExpandConstant('{srcexe}'))` and write `{app}\release.json` with version `2.4.7`, deterministic official URL and the computed hash. Update `recovery.json.current_version` to `2.4.7` without replacing the stored 2.4.6 installer.

- [ ] **Step 5: Add installer process and shortcut rules**

Shortcuts and post-install launch target `{app}\Claude.exe`. Enable normal application closing for `Claude.exe` and `ClaudeApp.exe`. Preserve the existing AppData-based settings and license locations and exclude `drivers` from rollback cleanup.

Add an uninstall confirmation that separately asks whether `%ProgramData%\Claude\Recovery` should also be removed. A normal uninstall removes program files but keeps the recovery cache unless the user explicitly selects its removal.

Create the recovery directory with restricted ACLs matching Task 3 and verify that inherited ordinary-user write permission is not retained.

- [ ] **Step 6: Run tests and compile the installer script**

Run: `python -m pytest tests/test_installer_recovery_contract.py -q`

Run: `"C:\Users\PC\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss`

Expected: tests pass and Inno Setup exits 0 with `03_output\Claude_v2.4.7_Setup.exe`.

- [ ] **Step 7: Commit**

```bash
git add installer.iss tests/test_installer_recovery_contract.py
git commit -m "설치기 직전 버전 복구 캐시 추가"
```

### Task 7: 2.4.7 메타데이터와 실제 장애 복구 검증

**Files:**
- Modify: `version.txt`
- Modify: `version.json`
- Modify: `build.bat`
- Modify: `installer.iss`
- Modify: `03_output/2026-08-30_native-recovery-launcher_v1_checklist.md`
- Modify: `03_output/2026-08-30_native-recovery-launcher_v1_context-notes.md`

**Interfaces:**
- Produces: release-ready `03_output\Claude_v2.4.7_Setup.exe` and matching SHA-256 in `version.json`.

- [ ] **Step 1: Set every required version field to 2.4.7**

Set `version.txt`, `installer.iss #define AppVersion`, and the `build.bat` title/output paths. Set `version.json.version`, `notes`, and `download_url`; leave `sha256` to be filled from the final installer hash in Step 4.

- [ ] **Step 2: Run focused and existing regression tests**

Run: `python -m pytest tests/test_recovery_protocol.py tests/test_update_recovery.py tests/test_recovery_launcher_build.py tests/test_installer_recovery_contract.py tests/test_release_bundle_validation.py tests/test_admin_util.py -q`

Expected: all focused tests pass.

- [ ] **Step 3: Build the PyInstaller bundle and installer**

Run: `build.bat`

Run: `"C:\Users\PC\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss`

Expected: both commands exit 0 and the final setup exists.

- [ ] **Step 4: Record the final installer SHA-256**

Run: `Get-FileHash -Algorithm SHA256 03_output\Claude_v2.4.7_Setup.exe`

Write the lowercase result to `version.json.sha256`, then run a JSON parse assertion and the release checklist test.

- [ ] **Step 5: Verify the installed healthy path**

Install to an isolated test directory, launch `Claude.exe`, confirm UAC applies to the launcher, confirm `ClaudeApp.exe` is its monitored child, confirm the UI readiness file is written, close normally, and verify no recovery window appears.

Confirm `%ProgramData%\Claude\Recovery` grants write access only to `SYSTEM` and `Administrators` and that the normal user cannot replace `previous_setup.exe`.

- [ ] **Step 6: Verify the Qt boot-failure path**

In the isolated test installation only, rename one required Qt DLL, launch `Claude.exe`, confirm the independent recovery window appears with error text and four buttons, then restore the DLL. Do not alter the real installed copy.

- [ ] **Step 7: Verify rollback and same-version reinstall**

Use a disposable install directory and copied recovery metadata. Confirm rollback removes new-only runtime files, preserves a sentinel settings file and `drivers`, installs 2.4.6, and launches its `Claude.exe`. Reinstall 2.4.7 afterward and confirm `업데이트 확인` offers `현재 버전 다시 설치` when remote and local versions match.

- [ ] **Step 8: Run final source and bundle verification**

Run: `python -m pytest tests/test_recovery_protocol.py tests/test_update_recovery.py tests/test_recovery_launcher_build.py tests/test_installer_recovery_contract.py tests/test_release_bundle_validation.py -q`

Run: `python release_bundle_validation.py ".obf_build\build\ClaudeApp\Analysis-00.toc" "dist\Claude_2.4.7"`

Expected: all tests pass and bundle validation exits 0.

- [ ] **Step 9: Complete notes and commit release-ready sources**

```bash
git add version.txt version.json build.bat installer.iss 03_output/2026-08-30_native-recovery-launcher_v1_checklist.md 03_output/2026-08-30_native-recovery-launcher_v1_context-notes.md
git commit -m "Claude 2.4.7 복구 실행기 배포 준비"
```

The GitHub push and Release publication are intentionally excluded until the user explicitly authorizes remote deployment after local recovery verification.
