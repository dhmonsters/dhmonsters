# 받은 V6497 추적 코어의 위치와 필수 파일을 검증해 불러온다.
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


DEVELOPMENT_VENDOR_ROOT = Path(
    r"C:\Users\PC\Downloads\Telegram Desktop\1테스트\V6497_LIVE_ONE_SHOT_1280_SELF_CLEAN"
)


def resolve_vendor_root(
    *,
    frozen: bool | None = None,
    executable: str | Path | None = None,
) -> Path:
    packaged = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if not packaged:
        return DEVELOPMENT_VENDOR_ROOT
    executable_path = Path(executable or sys.executable).resolve()
    return executable_path.parent / "vendor"


DEFAULT_VENDOR_ROOT = resolve_vendor_root()


@dataclass(frozen=True)
class VendorLayout:
    root: Path = DEFAULT_VENDOR_ROOT

    REQUIRED_FILES = (
        "live_core.py",
        "win32_live.py",
        "autoseed.py",
        "motion_tracker_v35_base.py",
        "motion_tracker_v645.py",
        "v645_owner_guard.py",
        "v6494_owner_guard.py",
        "triangle_guard_v6496.py",
        "deep_identity_model.py",
    )

    @property
    def required_paths(self) -> tuple[Path, ...]:
        return tuple(self.root / name for name in self.REQUIRED_FILES)

    def validate(self) -> list[str]:
        return [str(path) for path in self.required_paths if not path.is_file()]

    def load_backend(self) -> ModuleType:
        missing = self.validate()
        if missing:
            raise FileNotFoundError("V6497 필수 파일 누락: " + ", ".join(missing))

        root_text = str(self.root)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)

        module = importlib.import_module("live_core")
        module_file = Path(str(getattr(module, "__file__", ""))).resolve()
        if module_file.parent != self.root.resolve():
            raise RuntimeError(f"다른 live_core가 로드됨: {module_file}")
        return module


def load_default_backend() -> ModuleType:
    return VendorLayout().load_backend()
