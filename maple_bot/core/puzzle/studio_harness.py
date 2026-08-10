# Lie Captcha Studio와 마우스 OFF 솔버 검증을 한 번에 실행하고 GT를 수집한다.
from __future__ import annotations

import base64
import json
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode


RuntimeFactory = Callable[..., Any]
DEDICATED_BROWSER_PATHS = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Users\PC\AppData\Local\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Users\PC\AppData\Local\Google\Chrome\Application\chrome.exe"),
)


@dataclass(frozen=True)
class StudioHarnessResult:
    output_dir: Path
    session_dir: Path
    gt_jsonl: Path
    trace_jsonl: Path
    report_path: Path
    studio_url: str


@dataclass
class StudioBrowserProcess:
    process: subprocess.Popen[Any]

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5.0)


BrowserOpener = Callable[[str], bool | StudioBrowserProcess]


class StudioHarnessState:
    def __init__(self, gt_jsonl: str | Path) -> None:
        self.gt_jsonl = Path(gt_jsonl)
        self.gt_jsonl.parent.mkdir(parents=True, exist_ok=True)
        self.gt_jsonl.write_text("", encoding="utf-8")
        self.ready = threading.Event()
        self.start = threading.Event()
        self.complete = threading.Event()
        self.ready_payload: dict[str, object] = {}
        self.complete_payload: dict[str, object] = {}
        self._write_lock = threading.Lock()
        self._gt_condition = threading.Condition()
        self.gt_count = 0
        self.latest_gt: dict[str, object] = {}
        self._latest_frame_data_url = ""
        self.step_token = 0

    def append_gt(self, payload: dict[str, object]) -> None:
        row = dict(payload)
        frame_data_url = row.pop("frame_png_data_url", "")
        with self._gt_condition:
            self.gt_count += 1
            self.latest_gt = row
            self._latest_frame_data_url = (
                frame_data_url if isinstance(frame_data_url, str) else ""
            )
            self._gt_condition.notify_all()

    def latest_frame_data_url(self) -> str:
        with self._gt_condition:
            return self._latest_frame_data_url

    def record_processed_gt(
        self,
        payload: dict[str, object],
        *,
        solver_frame_index: int,
    ) -> None:
        row = dict(payload)
        row["solver_frame_index"] = int(solver_frame_index)
        with self._write_lock:
            with self.gt_jsonl.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
                fp.write("\n")

    def wait_for_gt_count(
        self,
        expected_count: int,
        *,
        timeout_s: float,
    ) -> tuple[int, dict[str, object]]:
        deadline = time.monotonic() + timeout_s
        with self._gt_condition:
            while self.gt_count < expected_count:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    raise TimeoutError(f"Studio GT frame {expected_count} timed out")
                self._gt_condition.wait(remaining)
            return self.gt_count, dict(self.latest_gt)

    def allow_step(self) -> int:
        with self._gt_condition:
            self.step_token += 1
            self._gt_condition.notify_all()
            return self.step_token


class StudioFrameGrabber:
    window_title = ""
    direct_canvas = True

    def __init__(self, state: StudioHarnessState) -> None:
        self.state = state

    def __call__(self) -> Any:
        data_url = self.state.latest_frame_data_url()
        prefix = "data:image/png;base64,"
        if not data_url.startswith(prefix):
            raise RuntimeError("Studio did not provide a direct canvas PNG frame")
        try:
            encoded = base64.b64decode(data_url[len(prefix) :], validate=True)
        except ValueError as exc:
            raise RuntimeError("Studio canvas PNG frame is invalid") from exc

        import cv2
        import numpy as np

        frame = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Studio canvas PNG frame could not be decoded")
        return frame


class StudioHarnessServer:
    def __init__(self, studio_root: str | Path, gt_jsonl: str | Path) -> None:
        self.studio_root = Path(studio_root).resolve()
        if not (self.studio_root / "index.html").is_file():
            raise FileNotFoundError(f"Studio index.html not found: {self.studio_root}")
        self.state = StudioHarnessState(gt_jsonl)
        handler = _handler_factory(self.studio_root, self.state)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def allow_start(self) -> None:
        self.state.start.set()

    def allow_step(self) -> int:
        return self.state.allow_step()

    def __enter__(self) -> StudioHarnessServer:
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="StudioHarnessHttp",
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def run_studio_harness(
    studio_root: str | Path,
    output_root: str | Path,
    *,
    runs: int = 10,
    frames_per_run: int = 150,
    studio_fps: float = 20.0,
    capture_fps: float = 30.0,
    seed: str = "codex-v1",
    capture_window_title: str = "Lie Captcha Studio",
    browser_opener: BrowserOpener | None = None,
    runtime_factory: RuntimeFactory | None = None,
    timeout_s: float = 180.0,
) -> StudioHarnessResult:
    if runs <= 0 or frames_per_run <= 0:
        raise ValueError("runs and frames_per_run must be positive")
    if studio_fps <= 0 or capture_fps <= 0 or timeout_s <= 0:
        raise ValueError("fps and timeout must be positive")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_studio")
    output_dir = Path(output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    gt_jsonl = output_dir / "studio_gt.jsonl"
    opener = browser_opener or _open_background_studio_browser
    factory = runtime_factory or _default_runtime_factory

    with StudioHarnessServer(studio_root, gt_jsonl) as server:
        query = urlencode(
            {
                "harness": 1,
                "export_gt": 1,
                "batch": runs,
                "frames": frames_per_run,
                "fps": studio_fps,
                "run_id": run_id,
                "seed": seed,
            }
        )
        studio_url = f"{server.url}/?{query}"
        opened_browser = opener(studio_url)
        if opened_browser is False:
            raise RuntimeError("Studio browser could not be opened")
        try:
            if not server.state.ready.wait(timeout_s):
                raise TimeoutError("Studio ready signal timed out")

            ready_title = str(server.state.ready_payload.get("title", "") or "").strip()
            runtime = factory(
                output_root=output_dir / "sessions",
                capture_window_title=ready_title or capture_window_title,
                frame_grabber=StudioFrameGrabber(server.state),
                fps=capture_fps,
                mouse_enabled=False,
                visual_check_mode=True,
                record_video=False,
            )
            server.allow_start()
            total_frames = runs * frames_per_run
            session: Any | None = None
            previous_run_index: int | None = None
            try:
                for expected_count in range(1, total_frames + 1):
                    _, gt_payload = server.state.wait_for_gt_count(expected_count, timeout_s=timeout_s)
                    run_index = int(gt_payload.get("run_index", -1))
                    if run_index < 0:
                        raise ValueError("Studio GT run_index must not be negative")

                    if session is None:
                        session = _start_runtime(runtime, ready_payload=server.state.ready_payload)
                    else:
                        if previous_run_index is not None and run_index != previous_run_index:
                            runtime.reset_solver_state(
                                reason="studio_run_boundary",
                                run_index=run_index,
                            )
                        if runtime.pump_once() is not True:
                            raise RuntimeError("Studio visual runtime did not process the current GT frame")
                    solver_frame_index = int(getattr(runtime, "frame_count", 0)) - 1
                    if solver_frame_index < 0:
                        raise RuntimeError("Studio visual runtime did not expose its processed frame index")
                    server.state.record_processed_gt(
                        gt_payload,
                        solver_frame_index=solver_frame_index,
                    )
                    previous_run_index = run_index
                    server.allow_step()

                completed = server.state.complete.wait(timeout_s)
                if not completed:
                    raise TimeoutError("Studio batch completion timed out")
                runtime.stop_recording(reason="studio_batch_complete")
                report_path = Path(runtime.finish(reason="studio_batch_complete"))
            except BaseException:
                if session is not None:
                    runtime.stop_recording(reason="studio_batch_error")
                    runtime.finish(reason="studio_batch_error")
                raise
            if session is None:
                raise RuntimeError("Studio visual runtime did not start")
            session_dir = Path(session.output_dir)
            trace_jsonl = Path(session.trace_path)
        finally:
            _close_opened_browser(opened_browser)

    return StudioHarnessResult(
        output_dir=output_dir,
        session_dir=session_dir,
        gt_jsonl=gt_jsonl,
        trace_jsonl=trace_jsonl,
        report_path=report_path,
        studio_url=studio_url,
    )


def _start_runtime(runtime: Any, *, ready_payload: dict[str, object] | None = None) -> Any:
    frame_grabber = getattr(runtime, "frame_grabber", None)
    if not callable(frame_grabber):
        return runtime.start()
    from core.puzzle.defaults import fixed_detect_roi
    from core.puzzle.models import RoiSpec

    frame = frame_grabber()
    frame_h, frame_w = frame.shape[:2]
    if bool(getattr(frame_grabber, "direct_canvas", False)):
        canvas_roi = RoiSpec(
            name="studio_canvas",
            basis="window_client",
            x=0,
            y=0,
            w=frame_w,
            h=frame_h,
            x_ratio=0.0,
            y_ratio=0.0,
            w_ratio=1.0,
            h_ratio=1.0,
            window_title="",
        )
        return runtime.start(initial_frame=frame, detect_roi=canvas_roi, board_roi=canvas_roi)
    payload = ready_payload or {}
    canvas_rect = payload.get("canvas_rect")
    viewport_width = _positive_float(payload.get("viewport_width"))
    viewport_height = _positive_float(payload.get("viewport_height"))
    if (
        isinstance(canvas_rect, list)
        and len(canvas_rect) == 4
        and viewport_width is not None
        and viewport_height is not None
    ):
        rect = [_positive_float(value, allow_zero=index < 2) for index, value in enumerate(canvas_rect)]
    else:
        rect = []

    if len(rect) == 4 and all(value is not None for value in rect):
        left, top, width, height = (float(value) for value in rect)
        content_x = max(0.0, (float(frame_w) - viewport_width) / 2.0)
        content_y = max(0.0, float(frame_h) - viewport_height)
        x = min(max(0, int(round(content_x + left))), frame_w - 1)
        y = min(max(0, int(round(content_y + top))), frame_h - 1)
        w = min(max(1, int(round(width))), frame_w - x)
        h = min(max(1, int(round(height))), frame_h - y)
        canvas_roi = RoiSpec(
            name="studio_canvas",
            basis="window_client",
            x=x,
            y=y,
            w=w,
            h=h,
            x_ratio=x / float(frame_w),
            y_ratio=y / float(frame_h),
            w_ratio=w / float(frame_w),
            h_ratio=h / float(frame_h),
            window_title="Lie Captcha Studio",
        )
    else:
        canvas_roi = fixed_detect_roi(
            frame_w=frame_w,
            frame_h=frame_h,
            window_title="Lie Captcha Studio",
        )
    return runtime.start(initial_frame=frame, detect_roi=canvas_roi, board_roi=canvas_roi)


def _positive_float(value: object, *, allow_zero: bool = False) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 0.0 or (allow_zero and number >= 0.0):
        return number
    return None


def _open_dedicated_studio_browser(url: str) -> bool:
    for browser_path in DEDICATED_BROWSER_PATHS:
        if not browser_path.is_file():
            continue
        subprocess.Popen(
            _dedicated_browser_args(browser_path, url),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    return bool(webbrowser.open(url, new=1))


def _open_background_studio_browser(url: str) -> StudioBrowserProcess:
    for browser_path in DEDICATED_BROWSER_PATHS:
        if not browser_path.is_file():
            continue
        process = subprocess.Popen(
            _background_browser_args(browser_path, url),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return StudioBrowserProcess(process)
    raise FileNotFoundError("Edge or Chrome was not found for Studio background validation")


def _background_browser_args(browser_path: Path, url: str) -> list[str]:
    return [
        str(browser_path),
        "--headless=new",
        "--window-size=1310,1302",
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-gpu-sandbox",
        "--enable-webgl",
        "--ignore-gpu-blocklist",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]


def _close_opened_browser(opened_browser: object) -> None:
    close = getattr(opened_browser, "close", None)
    if callable(close):
        close()


def _dedicated_browser_args(browser_path: Path, url: str) -> list[str]:
    return [
        str(browser_path),
        "--new-window",
        f"--app={url}",
        "--window-position=0,0",
        "--window-size=1310,1302",
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
    ]


def _default_runtime_factory(**kwargs: object) -> Any:
    from core.puzzle.live_recording import LiveRecordingRuntime

    kwargs.pop("capture_window_title", None)
    return LiveRecordingRuntime(**kwargs)


def _handler_factory(studio_root: Path, state: StudioHarnessState) -> type[SimpleHTTPRequestHandler]:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(studio_root), **kwargs)

        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] == "/__harness/control":
                self._send_json({"start": state.start.is_set(), "step_token": state.step_token})
                return
            super().do_GET()

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            try:
                payload = self._read_json()
            except (ValueError, json.JSONDecodeError):
                self._send_json({"ok": False, "error": "invalid_json"}, status=400)
                return
            if path == "/__harness/ready":
                state.ready_payload = payload
                state.ready.set()
            elif path == "/__harness/gt":
                state.append_gt(payload)
            elif path == "/__harness/complete":
                state.complete_payload = payload
                state.complete.set()
            else:
                self._send_json({"ok": False, "error": "not_found"}, status=404)
                return
            self._send_json({"ok": True})

        def _read_json(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            return payload

        def _send_json(self, payload: dict[str, object], *, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler
