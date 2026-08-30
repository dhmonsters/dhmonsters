# 업데이트 전 현재 설치본을 직전 버전 복구 파일로 보관하는 동작을 검증한다.
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from core import update_recovery
from core import updater
from ui.dialog_update import UpdateDialog


GOOD_URL = (
    "https://github.com/dhmonsters/dhmonsters/releases/download/"
    "v2.4.7/Claude_v2.4.7_Setup.exe"
)
GOOD_BYTES = b"official-current-installer"
GOOD_HASH = hashlib.sha256(GOOD_BYTES).hexdigest()


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def test_release_url_allows_only_official_github_https_path() -> None:
    update_recovery.validate_release_url(GOOD_URL)

    for invalid in (
        "http://github.com/dhmonsters/dhmonsters/releases/download/v2/a.exe",
        "https://example.com/dhmonsters/dhmonsters/releases/download/v2/a.exe",
        "https://github.com/other/repo/releases/download/v2/a.exe",
        "https://github.com/dhmonsters/dhmonsters/archive/main.zip",
    ):
        with pytest.raises(ValueError):
            update_recovery.validate_release_url(invalid)


def test_hash_mismatch_preserves_existing_recovery_files(tmp_path: Path) -> None:
    previous = tmp_path / "previous_setup.exe"
    metadata = tmp_path / "recovery.json"
    previous.write_bytes(b"known-old-installer")
    metadata.write_text('{"previous_version":"2.4.6"}', encoding="utf-8")

    def download_wrong(_url: str, destination: Path) -> None:
        destination.write_bytes(b"tampered")

    with pytest.raises(RuntimeError, match="SHA-256"):
        update_recovery.ensure_previous_installer(
            {
                "version": "2.4.7",
                "download_url": GOOD_URL,
                "sha256": GOOD_HASH,
            },
            downloader=download_wrong,
            recovery_dir=tmp_path,
            install_dir=Path("C:/Program Files/Claude"),
        )

    assert previous.read_bytes() == b"known-old-installer"
    assert metadata.read_text(encoding="utf-8") == '{"previous_version":"2.4.6"}'
    assert not (tmp_path / "previous_setup.download").exists()
    assert not (tmp_path / "recovery.json.download").exists()


def test_valid_current_installer_replaces_cache_and_metadata(tmp_path: Path) -> None:
    (tmp_path / "previous_setup.exe").write_bytes(b"old")
    (tmp_path / "recovery.json").write_text("{}", encoding="utf-8")

    def download_current(url: str, destination: Path) -> None:
        assert url == GOOD_URL
        destination.write_bytes(GOOD_BYTES)

    result = update_recovery.ensure_previous_installer(
        {"version": "2.4.7", "download_url": GOOD_URL, "sha256": GOOD_HASH},
        downloader=download_current,
        recovery_dir=tmp_path,
        install_dir=Path("C:/Program Files/Claude"),
    )

    assert result == tmp_path / "previous_setup.exe"
    assert result.read_bytes() == GOOD_BYTES
    payload = json.loads((tmp_path / "recovery.json").read_text(encoding="utf-8"))
    assert payload["previous_version"] == "2.4.7"
    assert payload["current_version"] == "2.4.7"
    assert payload["previous_sha256"] == GOOD_HASH
    assert payload["installation_path"] == "C:\\Program Files\\Claude"
    assert payload["created_at"].endswith("Z")


def test_matching_cached_current_installer_skips_download(tmp_path: Path) -> None:
    previous = tmp_path / "previous_setup.exe"
    previous.write_bytes(GOOD_BYTES)
    (tmp_path / "recovery.json").write_text(
        json.dumps(
            {
                "previous_version": "2.4.7",
                "previous_sha256": GOOD_HASH,
                "installation_path": "C:\\Program Files\\Claude",
            }
        ),
        encoding="utf-8",
    )

    def unexpected_download(_url: str, _destination: Path) -> None:
        raise AssertionError("matching cache must not download again")

    result = update_recovery.ensure_previous_installer(
        {"version": "2.4.7", "download_url": GOOD_URL, "sha256": GOOD_HASH},
        downloader=unexpected_download,
        recovery_dir=tmp_path,
        install_dir=Path("C:/Program Files/Claude"),
    )

    assert result == previous


def test_read_local_release_rejects_missing_required_fields(tmp_path: Path) -> None:
    (tmp_path / "release.json").write_text(
        json.dumps({"version": "2.4.7", "download_url": GOOD_URL}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="sha256"):
        update_recovery.read_local_release(tmp_path)


def test_check_for_update_returns_verified_sha256(monkeypatch) -> None:
    class Response:
        content = json.dumps(
            {
                "version": "2.4.8",
                "notes": "recovery update",
                "download_url": GOOD_URL.replace("2.4.7", "2.4.8"),
                "sha256": "a" * 64,
            }
        ).encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(updater, "_read_local_version", lambda: "2.4.7")
    monkeypatch.setattr("requests.get", lambda *_args, **_kwargs: Response())

    result = updater.check_for_update()

    assert result is not None
    assert result["version"] == "2.4.8"
    assert result["sha256"] == "a" * 64


def test_check_for_update_rejects_missing_sha256(monkeypatch) -> None:
    class Response:
        content = json.dumps(
            {
                "version": "2.4.8",
                "notes": "missing digest",
                "download_url": GOOD_URL.replace("2.4.7", "2.4.8"),
            }
        ).encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(updater, "_read_local_version", lambda: "2.4.7")
    monkeypatch.setattr("requests.get", lambda *_args, **_kwargs: Response())

    with pytest.raises(RuntimeError, match="sha256"):
        updater.check_for_update()


def test_download_update_removes_file_when_sha256_mismatches(
    tmp_path: Path, monkeypatch
) -> None:
    destination = tmp_path / "download.exe"

    class Response:
        headers = {"content-length": "8"}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 65536
            yield b"tampered"

    monkeypatch.setattr("requests.get", lambda *_args, **_kwargs: Response())
    monkeypatch.setattr(
        updater.tempfile,
        "mkstemp",
        lambda **_kwargs: (os.open(destination, os.O_CREAT | os.O_RDWR), str(destination)),
    )

    with pytest.raises(RuntimeError, match="SHA-256"):
        updater.download_update(GOOD_URL, GOOD_HASH)

    assert not destination.exists()


def test_apply_update_secures_current_version_before_starting_installer(
    tmp_path: Path, monkeypatch
) -> None:
    events: list[str] = []
    setup = tmp_path / "new_setup.exe"
    setup.write_bytes(b"new")
    current = {"version": "2.4.7", "download_url": GOOD_URL, "sha256": GOOD_HASH}

    monkeypatch.setattr(update_recovery, "read_local_release", lambda: current)
    monkeypatch.setattr(
        update_recovery,
        "ensure_previous_installer",
        lambda release: events.append("cache") or tmp_path / "previous_setup.exe",
    )
    monkeypatch.setattr(
        "core.recovery_protocol.write_normal_exit",
        lambda reason: events.append(reason) or True,
    )
    monkeypatch.setattr(
        "subprocess.Popen", lambda *_args, **_kwargs: events.append("installer")
    )

    with pytest.raises(SystemExit) as stopped:
        updater.apply_update(str(setup), {"version": "2.4.8"})

    assert stopped.value.code == 0
    assert events == ["cache", "installer", "update_handoff"]


def test_update_dialog_passes_sha256_and_full_metadata_to_updater(
    qapp, monkeypatch, tmp_path: Path
) -> None:
    info = {
        "current": "2.4.7",
        "version": "2.4.8",
        "notes": "recovery",
        "download_url": GOOD_URL.replace("2.4.7", "2.4.8"),
        "sha256": "b" * 64,
    }
    installer = tmp_path / "setup.exe"
    installer.write_bytes(b"setup")
    calls: list[tuple] = []

    def fake_download(url: str, digest: str, progress_cb=None) -> str:
        calls.append(("download", url, digest, callable(progress_cb)))
        return str(installer)

    monkeypatch.setattr(updater, "download_update", fake_download)
    monkeypatch.setattr(
        updater,
        "apply_update",
        lambda path, metadata: calls.append(("apply", path, metadata)),
    )
    dialog = UpdateDialog(info)

    dialog._download_thread(info["download_url"])
    dialog._apply()

    assert calls[0] == (
        "download",
        info["download_url"],
        info["sha256"],
        True,
    )
    assert calls[1] == ("apply", str(installer), info)
