# 2.4.9 시작 오류 및 복구 핫픽스 작업 기록

## 확인된 원인

- 2.4.8에서 `--collect-submodules core`를 제거하고 개별 hidden import로 전환했다.
- PyArmor 처리된 `run_integrated.py`가 시작 직후 가져오는 `core.recovery_protocol`이 hidden import 목록에서 누락됐다.
- 해당 import는 오류 기록기 설치보다 먼저 실행되므로 `last_crash.json`도 생성되지 않았다.
- 기존 5초 실행 검사는 PyInstaller 오류 대화상자가 프로세스를 유지하는 경우를 정상 시작으로 오판할 수 있었다.
- 설치기의 복구본 생성은 설치된 버전이 정확히 2.4.7인 경우에만 실행됐다.
- 따라서 2.4.6 등에서 2.4.8로 건너뛴 PC에는 `previous_setup.exe`와 `recovery.json`이 만들어지지 않았다.

## 확정한 수정 원칙

- 전체 `core` 수집을 되돌리지 않고 필요한 복구 모듈만 명시한다.
- 실행 성공은 프로세스 생존이 아니라 `recovery_protocol.write_ready()`가 생성한 준비 신호로 판정한다.
- 2.4.8은 복구 대상으로 사용하지 않고 검증된 2.4.7 설치본을 2.4.9의 로컬 복구본으로 보관한다.
- 이전 버전은 별도 설치하지 않고 `C:\ProgramData\Claude\Recovery`에 설치 파일 하나로만 보관한다.
- 사용자의 기존 `tests/test_block_runner.py` 변경과 무관한 산출물은 수정하거나 삭제하지 않는다.

## 테스트 기록

- 수정 전 재현 테스트는 4건 실패했다.
- 필수 모듈 검사, UI 준비 신호 검사, 안정 복구본 정책을 구현한 뒤 관련 테스트 31건이 통과했다.
- 게임창이 없는 빌드 PC에서는 정상 시작 경로가 게임창 오류 대화상자에서 대기하므로, 봇이나 라이선스를 우회하지 않는 `--release-startup-check` 자체검사를 추가했다.
- 자체검사는 `core.recovery_protocol`, `core.update_recovery`, `core.updater`, `ui.dialog_update`를 실제로 가져오고 오프스크린 Qt `MainShell`을 생성한 뒤 준비 신호를 기록한다.
- 자체검사 추가 후 관련 테스트 32건이 통과했다.
- 전체 테스트 수집은 이미 제거된 퍼즐·검증 실험 파일을 참조하는 테스트 28개 때문에 중단됐다.
- 실험 테스트를 제외한 운영 테스트에서는 834개가 통과하고, 제거된 Humanizer API·폐기된 구형 동선 UI·이전 테마값을 기대하는 기존 테스트 59개가 실패했다. 이번 핫픽스 파일과 무관한 기존 상태이므로 복원하지 않았다.
- `build.bat` 전체 실행이 종료 코드 0으로 통과했다.
- 최종 배포 묶음에는 런타임 로그가 없고 필수 모듈 4개가 PyInstaller 분석 목록에 포함됐다.
- `Claude_v2.4.9_Setup.exe`를 신규 검증 경로에 설치한 뒤 설치 버전 2.4.9, release.json URL·SHA-256, 실제 Qt 준비 신호를 확인했다.
- 최종 설치 파일 크기는 69,134,225바이트이고 SHA-256은 `4a8bca3098633610b485e690e9a1a6c2be96dfb567ee7eed014d440c7da3c1f2`다.
- 핫픽스 코드는 `c88aa94`로 원격 브랜치에 푸시했다.
- GitHub Release `v2.4.9`를 생성하고 업로드된 자산의 크기와 digest를 로컬 설치 파일과 대조했다.
- main의 공개 업데이트 메타데이터는 `f6ee534`로 갱신했으며 원격 raw 파일에서 2.4.9 URL과 SHA-256을 재확인했다.
