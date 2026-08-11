# Puzzle2 배포본의 CUDA 및 V6497 모델 자체 검사 판정을 검증한다.
from __future__ import annotations

from types import SimpleNamespace

from core.puzzle2.runtime_check import build_input_module_report, build_runtime_report


class FakeCuda:
    def __init__(self, *, available: bool = True) -> None:
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def get_device_name(self, index: int) -> str:
        assert index == 0
        return "NVIDIA GeForce GT 1030"

    def get_arch_list(self) -> list[str]:
        return ["sm_61", "sm_75"]

    def synchronize(self) -> None:
        return None


def test_runtime_report_passes_only_after_cuda_model_inference() -> None:
    torch = SimpleNamespace(
        __version__="2.5.1+cu118",
        version=SimpleNamespace(cuda="11.8"),
        cuda=FakeCuda(),
    )
    guard = SimpleNamespace(loaded=True, device="cuda")

    report = build_runtime_report(
        torch_module=torch,
        guard=guard,
        scores=[0.73],
        required_arch="sm_61",
    )

    assert report["status"] == "PASS"
    assert report["reasons"] == []
    assert report["metrics"]["model_inference_ok"] is True
    assert report["metrics"]["required_arch"] == "sm_61"


def test_runtime_report_fails_when_required_arch_is_missing() -> None:
    torch = SimpleNamespace(
        __version__="2.5.1+cu118",
        version=SimpleNamespace(cuda="11.8"),
        cuda=FakeCuda(),
    )
    torch.cuda.get_arch_list = lambda: ["sm_75", "sm_86"]
    guard = SimpleNamespace(loaded=True, device="cuda")

    report = build_runtime_report(
        torch_module=torch,
        guard=guard,
        scores=[0.73],
        required_arch="sm_61",
    )

    assert report["status"] == "FAIL"
    assert "required_arch_missing" in report["reasons"]


def test_input_module_report_requires_kernel_mouse_api() -> None:
    complete = SimpleNamespace(
        __file__="interception/__init__.py",
        auto_capture_devices=lambda **kwargs: None,
        move_to=lambda x, y: None,
        click=lambda **kwargs: None,
    )
    incomplete = SimpleNamespace(auto_capture_devices=lambda **kwargs: None)

    assert build_input_module_report(complete)["status"] == "PASS"
    failed = build_input_module_report(incomplete)
    assert failed["status"] == "FAIL"
    assert failed["metrics"]["missing_api"] == ["move_to", "click"]


def test_runtime_report_fails_when_model_did_not_run_on_cuda() -> None:
    torch = SimpleNamespace(
        __version__="2.5.1+cu118",
        version=SimpleNamespace(cuda="11.8"),
        cuda=FakeCuda(),
    )
    guard = SimpleNamespace(loaded=True, device="cpu")

    report = build_runtime_report(
        torch_module=torch,
        guard=guard,
        scores=[0.73],
        required_arch="sm_61",
    )

    assert report["status"] == "FAIL"
    assert "model_not_on_cuda" in report["reasons"]
