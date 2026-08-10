# GT 1030 CUDA 검사기의 아키텍처 선택과 판정 기준을 검증한다.
from __future__ import annotations

import os
from pathlib import Path

from core.puzzle2.cuda_probe import (
    ProbeMetrics,
    _Nvrtc,
    compile_arch_option,
    evaluate_probe,
    temporary_working_directory,
)
from gt1030_probe import dialog_enabled


def test_compile_arch_option_uses_detected_compute_capability() -> None:
    assert compile_arch_option(6, 1) == "--gpu-architecture=compute_61"
    assert compile_arch_option(8, 9) == "--gpu-architecture=compute_89"


def test_probe_passes_when_all_hardware_gates_pass() -> None:
    metrics = ProbeMetrics(
        gpu_name="NVIDIA GeForce GT 1030",
        compute_major=6,
        compute_minor=1,
        dedicated_total_mb=4096.0,
        dedicated_free_mb=2100.0,
        allocation_512mb=True,
        kernel_ok=True,
        equivalent_fps=82.0,
    )

    decision = evaluate_probe(metrics)

    assert decision.status == "PASS"
    assert decision.reasons == ()


def test_probe_marks_working_but_slow_gpu_as_slow() -> None:
    metrics = ProbeMetrics(
        gpu_name="NVIDIA GeForce GT 1030",
        compute_major=6,
        compute_minor=1,
        dedicated_total_mb=4096.0,
        dedicated_free_mb=700.0,
        allocation_512mb=True,
        kernel_ok=True,
        equivalent_fps=42.0,
    )

    decision = evaluate_probe(metrics)

    assert decision.status == "SLOW"
    assert "FREE_VRAM_BELOW_1024_MB" in decision.reasons
    assert "BENCHMARK_BELOW_60_FPS" in decision.reasons


def test_probe_fails_when_cuda_kernel_does_not_run() -> None:
    metrics = ProbeMetrics(
        gpu_name="NVIDIA GeForce GT 1030",
        compute_major=6,
        compute_minor=1,
        dedicated_total_mb=4096.0,
        dedicated_free_mb=2100.0,
        allocation_512mb=False,
        kernel_ok=False,
        equivalent_fps=0.0,
    )

    decision = evaluate_probe(metrics)

    assert decision.status == "FAIL"
    assert "CUDA_KERNEL_FAILED" in decision.reasons


def test_nvrtc_registers_its_dll_directory_before_loading(monkeypatch, tmp_path) -> None:
    dll_path = tmp_path / "nvrtc64_120_0.dll"
    dll_path.write_bytes(b"fixture")
    calls: list[tuple[str, str]] = []

    class FakeFunction:
        argtypes = None
        restype = None

    class FakeDll:
        def __getattr__(self, name):
            return FakeFunction()

    monkeypatch.setattr(
        "core.puzzle2.cuda_probe.os.add_dll_directory",
        lambda path: calls.append(("directory", path)) or object(),
    )
    monkeypatch.setattr(
        "core.puzzle2.cuda_probe.ctypes.WinDLL",
        lambda path: calls.append(("load", path)) or FakeDll(),
    )

    _Nvrtc(dll_path)

    assert calls == [("directory", str(tmp_path)), ("load", str(dll_path))]


def test_temporary_working_directory_restores_original_path(tmp_path) -> None:
    original = os.getcwd()

    with temporary_working_directory(tmp_path):
        assert Path(os.getcwd()).resolve() == tmp_path.resolve()

    assert os.getcwd() == original


def test_no_dialog_argument_disables_result_message() -> None:
    assert dialog_enabled(["gt1030_probe.py", "--no-dialog"]) is False
    assert dialog_enabled(["gt1030_probe.py"]) is True
