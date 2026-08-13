# Puzzle2 배포본의 CUDA 아키텍처와 V6497 모델 추론을 자체 검사한다.
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

from core.puzzle2.vendor import VendorLayout


def build_owner_connection_report(vendor_root: str | Path) -> dict[str, Any]:
    root = Path(vendor_root)
    live_core_path = root / "live_core.py"
    tracker_path = root / "motion_tracker_v645.py"
    guard_path = root / "v6494_owner_guard.py"
    missing = [
        str(path)
        for path in (live_core_path, tracker_path, guard_path)
        if not path.is_file()
    ]
    if missing:
        return {
            "status": "FAIL",
            "reasons": ["owner_source_missing"],
            "metrics": {"missing": missing},
        }

    live_core = live_core_path.read_text(encoding="utf-8")
    tracker = tracker_path.read_text(encoding="utf-8")
    guard = guard_path.read_text(encoding="utf-8")

    owner_enabled = bool(re.search(r"owner_guard_enabled\s*=\s*True", live_core))
    deep_model_empty = bool(re.search(r"deep_model\s*=\s*(['\"])\1", live_core))
    global_recovery_enabled = not bool(
        re.search(r"global_recovery_enabled\s*=\s*False", live_core)
    )
    guard_imported = "V6494OwnerGuard" in tracker
    guard_constructed = bool(re.search(r"V6494OwnerGuard\s*\(", tracker))
    apply_connected = bool(re.search(r"owner_guard\.apply\s*\(", tracker))
    guard_defined = "class V6494OwnerGuard" in guard

    reasons: list[str] = []
    if not owner_enabled:
        reasons.append("owner_guard_disabled")
    if not guard_imported or not guard_constructed or not guard_defined:
        reasons.append("owner_guard_not_constructed")
    if not apply_connected:
        reasons.append("owner_apply_path_missing")

    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "metrics": {
            "mode": (
                "CLASSICAL_TEMPORAL_OWNER_GUARD"
                if deep_model_empty
                else "DEEP_ASSISTED_TEMPORAL_OWNER_GUARD"
            ),
            "owner_guard_enabled": owner_enabled,
            "owner_guard_class": "V6494OwnerGuard",
            "owner_guard_constructed": guard_imported and guard_constructed and guard_defined,
            "owner_apply_connected": apply_connected,
            "deep_checkpoint_required": not deep_model_empty,
            "global_recovery_enabled": global_recovery_enabled,
        },
    }


def build_runtime_report(
    *,
    torch_module: Any,
    guard: Any,
    scores: list[float | None],
    required_arch: str,
) -> dict[str, Any]:
    cuda = torch_module.cuda
    cuda_available = bool(cuda.is_available())
    arch_list = list(cuda.get_arch_list()) if cuda_available else []
    inference_ok = bool(
        scores
        and scores[0] is not None
        and math.isfinite(float(scores[0]))
    )

    reasons: list[str] = []
    if not cuda_available:
        reasons.append("cuda_unavailable")
    if required_arch not in arch_list:
        reasons.append("required_arch_missing")
    if not bool(getattr(guard, "loaded", False)):
        reasons.append("model_not_loaded")
    if str(getattr(guard, "device", "")) != "cuda":
        reasons.append("model_not_on_cuda")
    if not inference_ok:
        reasons.append("model_inference_failed")

    metrics = {
        "torch_version": str(torch_module.__version__),
        "cuda_version": str(torch_module.version.cuda),
        "cuda_available": cuda_available,
        "gpu_name": cuda.get_device_name(0) if cuda_available else "",
        "arch_list": arch_list,
        "required_arch": required_arch,
        "model_loaded": bool(getattr(guard, "loaded", False)),
        "model_device": str(getattr(guard, "device", "")),
        "model_inference_ok": inference_ok,
        "model_score": float(scores[0]) if inference_ok else None,
    }
    return {
        "status": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "metrics": metrics,
    }


def _load_triangle_guard(layout: VendorLayout) -> type[Any]:
    module_path = layout.root / "triangle_guard_v6496.py"
    spec = importlib.util.spec_from_file_location(
        "puzzle2_runtime_triangle_guard",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"삼각형 모델 로더를 열 수 없습니다: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.TriangleAppearanceGuard


def run_runtime_check(
    *,
    vendor_root: str | Path,
    required_arch: str = "sm_61",
) -> dict[str, Any]:
    try:
        import numpy as np
        import torch

        layout = VendorLayout(Path(vendor_root))
        missing = layout.validate()
        if missing:
            raise FileNotFoundError("V6497 필수 파일 누락: " + ", ".join(missing))

        owner_report = build_owner_connection_report(layout.root)
        if owner_report["status"] != "PASS":
            return owner_report

        guard_type = _load_triangle_guard(layout)
        model_path = layout.root / "triangle_models" / "triangle_guard_v6496.pt"
        guard = guard_type(model_path)
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        candidates = [(None, 0.5, (640.0, 360.0), 0.5, 0.5, 0.5)]
        scores = guard.score(frame, candidates)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        report = build_runtime_report(
            torch_module=torch,
            guard=guard,
            scores=scores,
            required_arch=required_arch,
        )
        report["metrics"]["owner_connection"] = owner_report["metrics"]
        return report
    except Exception as exc:
        return {
            "status": "FAIL",
            "reasons": ["runtime_exception"],
            "error": f"{type(exc).__name__}: {exc}",
            "metrics": {"required_arch": required_arch},
        }


def save_runtime_report(report: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_input_module_report(interception_module: Any) -> dict[str, Any]:
    required = ("auto_capture_devices", "move_to", "click")
    missing = [
        name
        for name in required
        if not callable(getattr(interception_module, name, None))
    ]
    return {
        "status": "PASS" if not missing else "FAIL",
        "reasons": ["interception_api_missing"] if missing else [],
        "metrics": {
            "module": str(getattr(interception_module, "__file__", "bundled")),
            "required_api": list(required),
            "missing_api": missing,
        },
    }


def run_input_module_check() -> dict[str, Any]:
    try:
        import interception

        return build_input_module_report(interception)
    except Exception as exc:
        return {
            "status": "FAIL",
            "reasons": ["interception_import_failed"],
            "error": f"{type(exc).__name__}: {exc}",
            "metrics": {},
        }
