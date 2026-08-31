# Interception 커널 드라이버 입력 백엔드 - 드라이버 있으면 스텔스 입력, 없으면 자동 비활성(win32 폴백)
"""
설계 (MapleHunter input_backend.py 패턴 차용):
  - enable() 호출 시 interception 모듈 로드 + 드라이버 디바이스 캡처를 시도한다.
  - 성공하면 _active=True. InputController가 이 백엔드로 입력을 라우팅한다.
  - 실패(미설치/재부팅대기)하면 _active=False로 두고, 호출측은 기존 win32 SendInput으로 폴백한다.
  - 절대 예외를 밖으로 던지지 않는다 - 봇이 죽으면 안 되므로 항상 안전하게 폴백.

win32 SendInput 과의 차이:
  - SendInput 은 LLMHF_INJECTED 플래그를 남겨 후킹으로 탐지 가능.
  - Interception 은 커널 드라이버가 실제 디바이스인 척 입력을 주입 → injected 플래그 없음.
  - 단, 드라이버 자체가 디스크/레지스트리에 존재하므로 커널 안티치트 스캔에는 노출됨.
"""
from __future__ import annotations

import time
import threading

from core.input_timing import randomize_hold
from core.internal_trace import trace_event

_call_lock = threading.RLock()
_priority_condition = threading.Condition()
_priority_owner: int | None = None
_priority_depth = 0
_timing_local = threading.local()
_timing_log_fn = None

_DIRECTION_KEYS = {"left", "right", "up", "down"}
_TIMING_KEYS = _DIRECTION_KEYS | {"x", "alt"}

_intercept = None        # 로드된 interception 모듈
_active = False          # 드라이버 캡처 성공 여부


def _send_movement_key_immediate(key: str, *, is_down: bool) -> None:
    """Interception의 기본 25ms/sleep(0) 대기 없이 이동 키를 즉시 전송한다."""
    from interception import inputs

    key_data = inputs._keycodes.get_key_information(key)
    flag = inputs.KeyFlag.KEY_DOWN if is_down else inputs.KeyFlag.KEY_UP
    stroke = inputs.KeyStroke(key_data.scan_code, flag)
    if key_data.is_extended:
        stroke.flags |= inputs.KeyFlag.KEY_E0

    modifiers = (
        ("ctrl", key_data.ctrl),
        ("alt", key_data.alt),
        ("shift", key_data.shift),
    )
    for modifier, enabled in modifiers:
        if enabled:
            modifier_data = inputs._keycodes.get_key_information(modifier)
            modifier_stroke = inputs.KeyStroke(
                modifier_data.scan_code,
                inputs.KeyFlag.KEY_DOWN,
            )
            if modifier_data.is_extended:
                modifier_stroke.flags |= inputs.KeyFlag.KEY_E0
            inputs._g_context.send(inputs._g_context.keyboard, modifier_stroke)

    inputs._g_context.send(inputs._g_context.keyboard, stroke)

    for modifier, enabled in modifiers:
        if enabled:
            modifier_data = inputs._keycodes.get_key_information(modifier)
            modifier_stroke = inputs.KeyStroke(
                modifier_data.scan_code,
                inputs.KeyFlag.KEY_UP,
            )
            if modifier_data.is_extended:
                modifier_stroke.flags |= inputs.KeyFlag.KEY_E0
            inputs._g_context.send(inputs._g_context.keyboard, modifier_stroke)


def set_timing_log_callback(log_fn) -> None:
    """느린 입력 호출의 구간별 측정값을 UI 로그로 전달한다."""
    global _timing_log_fn
    _timing_log_fn = log_fn


def _emit_timing_log(message: str, total_sec: float | None = None) -> None:
    """콘솔에는 항상 기록하고 UI에는 20ms 이상 지연만 전달한다."""
    trace_event("input", "timing", message=message, total_sec=total_sec)
    print(message, flush=True)
    if _timing_log_fn is None or (total_sec is not None and total_sec < 0.020):
        return
    try:
        _timing_log_fn(message)
    except Exception:
        pass


def begin_priority() -> None:
    """현재 스레드를 사다리 중요 입력 소유자로 등록한다."""
    global _priority_owner, _priority_depth
    owner = threading.get_ident()
    with _priority_condition:
        while _priority_owner is not None and _priority_owner != owner:
            _priority_condition.wait()
        _priority_owner = owner
        _priority_depth += 1


def end_priority() -> None:
    """사다리 중요 입력 소유권을 해제하고 대기 중인 일반 입력을 재개한다."""
    global _priority_owner, _priority_depth
    owner = threading.get_ident()
    with _priority_condition:
        if _priority_owner != owner:
            return
        _priority_depth = max(0, _priority_depth - 1)
        if _priority_depth == 0:
            _priority_owner = None
            _priority_condition.notify_all()


def _wait_for_priority_turn() -> float:
    """사다리 중요 입력 중에는 다른 스레드의 새 입력 시작을 잠시 미룬다."""
    started_at = time.perf_counter()
    owner = threading.get_ident()
    with _priority_condition:
        while _priority_owner is not None and _priority_owner != owner:
            _priority_condition.wait()
    return time.perf_counter() - started_at


def _record_key_timing(operation: str, key: str, *, request_at: float,
                       priority_wait: float, lock_wait: float,
                       driver_call: float, driver_started_at: float,
                       driver_finished_at: float) -> dict:
    """입력 요청부터 드라이버 호출 완료까지의 구간별 시간을 기록한다."""
    event = {
        "operation": operation,
        "key": key,
        "request_at": request_at,
        "priority_wait": priority_wait,
        "lock_wait": lock_wait,
        "driver_call": driver_call,
        "driver_started_at": driver_started_at,
        "driver_finished_at": driver_finished_at,
        "total": driver_finished_at - request_at,
    }
    _timing_local.last_key_event = event
    if operation == "key_down" and key in _DIRECTION_KEYS:
        _timing_local.last_direction_down_at = driver_finished_at
        _timing_local.last_direction_key = key
    if key in _TIMING_KEYS:
        message = (
            "[input-timing] "
            f"{operation} key={key} "
            f"priority_wait={priority_wait * 1000.0:.3f}ms "
            f"lock_wait={lock_wait * 1000.0:.3f}ms "
            f"driver_call={driver_call * 1000.0:.3f}ms "
            f"total={event['total'] * 1000.0:.3f}ms"
        )
        _emit_timing_log(message, event["total"])
    return event


def get_last_timing() -> dict | None:
    """현재 스레드에서 마지막으로 실행한 키 입력의 시간 정보를 반환한다."""
    event = getattr(_timing_local, "last_key_event", None)
    return dict(event) if event is not None else None


def is_active() -> bool:
    """현재 Interception 백엔드가 활성화돼 있으면 True."""
    return _active


def _try_init() -> bool:
    """interception 모듈 로드 + 드라이버 디바이스 캡처. 성공 시 True."""
    global _intercept
    try:
        import interception  # pip: interception-python
    except Exception as e:
        print(f"[interception] 모듈 로드 실패(미설치): {e}")
        return False
    try:
        interception.auto_capture_devices(keyboard=True, mouse=True)
    except Exception as e:
        print(f"[interception] 드라이버 캡처 실패(미설치/재부팅 필요): {e}")
        return False
    _intercept = interception
    return True


def enable() -> bool:
    """Interception 백엔드 활성화 시도. 성공/실패 여부를 반환."""
    global _active
    _active = _try_init()
    if _active:
        print("[interception] 드라이버 활성화 - 스텔스 입력 사용")
    else:
        print("[interception] 비활성 - win32 SendInput 폴백")
    return _active


# ── 입력 프리미티브 (활성 상태에서만 호출) ────────────────────────────────
def key_down(key: str) -> None:
    normalized = str(key).strip().lower()
    request_at = time.perf_counter()
    priority_wait = _wait_for_priority_turn()
    lock_requested_at = time.perf_counter()
    with _call_lock:
        driver_started_at = time.perf_counter()
        if normalized in _TIMING_KEYS:
            _send_movement_key_immediate(normalized, is_down=True)
        else:
            _intercept.key_down(normalized)
        driver_finished_at = time.perf_counter()
    _record_key_timing(
        "key_down",
        normalized,
        request_at=request_at,
        priority_wait=priority_wait,
        lock_wait=driver_started_at - lock_requested_at,
        driver_call=driver_finished_at - driver_started_at,
        driver_started_at=driver_started_at,
        driver_finished_at=driver_finished_at,
    )


def key_up(key: str) -> None:
    normalized = str(key).strip().lower()
    request_at = time.perf_counter()
    lock_requested_at = time.perf_counter()
    with _call_lock:
        driver_started_at = time.perf_counter()
        if normalized in _TIMING_KEYS:
            _send_movement_key_immediate(normalized, is_down=False)
        else:
            _intercept.key_up(normalized)
        driver_finished_at = time.perf_counter()
    _record_key_timing(
        "key_up",
        normalized,
        request_at=request_at,
        priority_wait=0.0,
        lock_wait=driver_started_at - lock_requested_at,
        driver_call=driver_finished_at - driver_started_at,
        driver_started_at=driver_started_at,
        driver_finished_at=driver_finished_at,
    )


def press(key: str, hold_sec: float = 0.05) -> None:
    key = str(key).strip().lower()
    key_down(key)
    down_event = get_last_timing()
    applied_hold = randomize_hold(hold_sec)
    time.sleep(applied_hold)
    key_up(key)
    up_event = get_last_timing()
    if key in _TIMING_KEYS and down_event is not None and up_event is not None:
        actual_hold = up_event["driver_started_at"] - down_event["driver_finished_at"]
        direction_down_at = getattr(_timing_local, "last_direction_down_at", None)
        direction_key = getattr(_timing_local, "last_direction_key", None)
        direction_gap = None
        if key not in _DIRECTION_KEYS and direction_down_at is not None:
            direction_gap = down_event["driver_started_at"] - direction_down_at
        gap_text = (
            f" direction={direction_key} direction_to_action={direction_gap * 1000.0:.3f}ms"
            if direction_gap is not None
            else ""
        )
        message = (
            "[input-timing] "
            f"press key={key} requested_hold={hold_sec:.4f}s "
            f"applied_hold={applied_hold:.4f}s "
            f"actual_hold={actual_hold:.4f}s{gap_text}"
        )
        _emit_timing_log(message)


def move_to(x: int, y: int) -> None:
    _wait_for_priority_turn()
    with _call_lock:
        _intercept.move_to(int(x), int(y))


def click(x: int, y: int, button: str = "left") -> None:
    _wait_for_priority_turn()
    with _call_lock:
        _intercept.move_to(int(x), int(y))
        _intercept.click(button=button)


def mouse_down(button: str = "left") -> None:
    _wait_for_priority_turn()
    with _call_lock:
        _intercept.mouse_down(button)


def mouse_up(button: str = "left") -> None:
    with _call_lock:
        _intercept.mouse_up(button)
