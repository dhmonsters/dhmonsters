# Studio 자동 검증 실행기의 HTTP 수집과 마우스 안전 실행 순서를 검증한다.
from __future__ import annotations

import base64
import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import numpy as np
import cv2

import core.puzzle.studio_harness as studio_harness


StudioHarnessServer = studio_harness.StudioHarnessServer
_dedicated_browser_args = studio_harness._dedicated_browser_args
_start_runtime = studio_harness._start_runtime
run_studio_harness = studio_harness.run_studio_harness


def _get_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=2.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=2.0) as response:
        return json.loads(response.read().decode("utf-8"))


class StudioHarnessServerTest(unittest.TestCase):
    def test_background_browser_is_headless_and_not_position_dependent(self) -> None:
        args = studio_harness._background_browser_args(
            Path("C:/browser.exe"),
            "http://127.0.0.1/studio",
        )

        self.assertIn("--headless=new", args)
        self.assertIn("--window-size=1310,1302", args)
        self.assertNotIn("--window-position=0,0", args)

    def test_dedicated_browser_uses_fixed_benchmark_window(self) -> None:
        args = _dedicated_browser_args(Path("C:/browser.exe"), "http://127.0.0.1/studio")

        self.assertIn("--window-size=1310,1302", args)
        self.assertIn("--window-position=0,0", args)

    def test_runtime_uses_studio_canvas_rect_inside_browser_client(self) -> None:
        starts: list[dict[str, object]] = []

        class Runtime:
            frame_grabber = staticmethod(lambda: np.zeros((1000, 2000, 3), dtype=np.uint8))

            def start(self, **kwargs: object) -> object:
                starts.append(kwargs)
                return SimpleNamespace()

        _start_runtime(
            Runtime(),
            ready_payload={
                "viewport_width": 1900,
                "viewport_height": 800,
                "canvas_rect": [100, 50, 600, 500],
            },
        )

        detect = starts[0]["detect_roi"]
        board = starts[0]["board_roi"]
        self.assertEqual(detect, board)
        self.assertEqual((150, 250, 600, 500), (detect.x, detect.y, detect.w, detect.h))

    def test_server_collects_gt_and_exposes_lockstep_control(self) -> None:
        with TemporaryDirectory(prefix="studio-harness-server-") as tmp:
            root = Path(tmp)
            studio = root / "studio"
            studio.mkdir()
            (studio / "index.html").write_text("<title>Lie Captcha Studio</title>", encoding="utf-8")
            gt_path = root / "gt.jsonl"

            with StudioHarnessServer(studio, gt_path) as server:
                self.assertEqual(
                    {"start": False, "step_token": 0},
                    _get_json(f"{server.url}/__harness/control"),
                )
                _post_json(f"{server.url}/__harness/ready", {"title": "Lie Captcha Studio"})
                self.assertTrue(server.state.ready.wait(1.0))

                server.allow_start()
                self.assertEqual(
                    {"start": True, "step_token": 0},
                    _get_json(f"{server.url}/__harness/control"),
                )
                _post_json(
                    f"{server.url}/__harness/gt",
                    {
                        "run_id": "r_001",
                        "run_index": 0,
                        "frame_id": 0,
                        "timestamp_ms": 1000,
                        "target_x": 10.0,
                        "target_y": 20.0,
                    },
                )
                count, latest = server.state.wait_for_gt_count(1, timeout_s=1.0)
                self.assertEqual(1, count)
                self.assertEqual(0, latest["run_index"])
                server.state.record_processed_gt(latest, solver_frame_index=7)
                server.allow_step()
                self.assertEqual(
                    {"start": True, "step_token": 1},
                    _get_json(f"{server.url}/__harness/control"),
                )
                _post_json(f"{server.url}/__harness/complete", {"runs": 1})
                self.assertTrue(server.state.complete.wait(1.0))

            rows = [json.loads(line) for line in gt_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual("r_001", rows[0]["run_id"])
            self.assertEqual(10.0, rows[0]["target_x"])
            self.assertEqual(7, rows[0]["solver_frame_index"])

    def test_server_exposes_direct_canvas_frame_without_writing_it_to_gt(self) -> None:
        with TemporaryDirectory(prefix="studio-harness-frame-") as tmp:
            root = Path(tmp)
            studio = root / "studio"
            studio.mkdir()
            (studio / "index.html").write_text("<title>Studio</title>", encoding="utf-8")
            source = np.zeros((3, 4, 3), dtype=np.uint8)
            source[:, :] = (17, 91, 203)
            ok, encoded = cv2.imencode(".png", source)
            self.assertTrue(ok)
            frame_url = "data:image/png;base64," + base64.b64encode(encoded.tobytes()).decode("ascii")

            with StudioHarnessServer(studio, root / "gt.jsonl") as server:
                _post_json(
                    f"{server.url}/__harness/gt",
                    {
                        "run_id": "r_001",
                        "run_index": 0,
                        "frame_id": 0,
                        "target_x": 2.0,
                        "target_y": 1.0,
                        "frame_png_data_url": frame_url,
                    },
                )
                _, latest = server.state.wait_for_gt_count(1, timeout_s=1.0)
                frame = studio_harness.StudioFrameGrabber(server.state)()
                server.state.record_processed_gt(latest, solver_frame_index=0)

            self.assertEqual((3, 4, 3), frame.shape)
            self.assertEqual([17, 91, 203], frame[1, 2].tolist())
            row = json.loads((root / "gt.jsonl").read_text(encoding="utf-8"))
            self.assertNotIn("frame_png_data_url", row)

    def test_runner_processes_one_solver_frame_per_gt_and_resets_next_run(self) -> None:
        with TemporaryDirectory(prefix="studio-harness-runner-") as tmp:
            root = Path(tmp)
            studio = root / "studio"
            studio.mkdir()
            (studio / "index.html").write_text("<title>Lie Captcha Studio</title>", encoding="utf-8")
            runtime_calls: list[dict[str, object]] = []
            runtime_started = threading.Event()
            reset_runs: list[int | None] = []

            class FakeRuntime:
                def __init__(self, **kwargs: object) -> None:
                    runtime_calls.append(kwargs)
                    session_dir = root / "session"
                    session_dir.mkdir(exist_ok=True)
                    trace_path = session_dir / "trace.jsonl"
                    trace_path.write_text("", encoding="utf-8")
                    self.session = SimpleNamespace(output_dir=session_dir, trace_path=trace_path)
                    self.frame_count = 0

                def start(self) -> object:
                    runtime_started.set()
                    self.frame_count += 1
                    return self.session

                def pump_once(self) -> bool:
                    self.frame_count += 1
                    return True

                def reset_solver_state(self, *, reason: str, run_index: int | None) -> bool:
                    reset_runs.append(run_index)
                    return True

                def finish(self, *, reason: str = "finished") -> Path:
                    report = self.session.output_dir / "report.md"
                    report.write_text("# report\n", encoding="utf-8")
                    return report

                def stop_recording(self, *, reason: str) -> bool:
                    return True

            client_errors: list[BaseException] = []

            def browser_opener(url: str) -> bool:
                def client() -> None:
                    try:
                        parsed = urlsplit(url)
                        origin = f"{parsed.scheme}://{parsed.netloc}"
                        self.assertEqual(["fixed-seed"], parse_qs(parsed.query)["seed"])
                        _post_json(f"{origin}/__harness/ready", {"title": "Lie Captcha Studio run-token"})
                        deadline = time.monotonic() + 2.0
                        while not _get_json(f"{origin}/__harness/control")["start"]:
                            if time.monotonic() >= deadline:
                                raise TimeoutError("start control was not enabled")
                            time.sleep(0.01)
                        _post_json(
                            f"{origin}/__harness/gt",
                            {
                                "run_id": "r_001",
                                "run_index": 0,
                                "frame_id": 0,
                                "timestamp_ms": 1000,
                                "target_x": 10.0,
                                "target_y": 20.0,
                            },
                        )
                        while _get_json(f"{origin}/__harness/control")["step_token"] < 1:
                            time.sleep(0.01)
                        if not runtime_started.is_set():
                            raise AssertionError("first GT was not processed")
                        _post_json(
                            f"{origin}/__harness/gt",
                            {
                                "run_id": "r_002",
                                "run_index": 1,
                                "frame_id": 0,
                                "timestamp_ms": 1100,
                                "target_x": 30.0,
                                "target_y": 40.0,
                            },
                        )
                        while _get_json(f"{origin}/__harness/control")["step_token"] < 2:
                            time.sleep(0.01)
                        _post_json(f"{origin}/__harness/complete", {"runs": 2})
                    except BaseException as exc:
                        client_errors.append(exc)

                threading.Thread(target=client, daemon=True).start()
                return True

            result = run_studio_harness(
                studio_root=studio,
                output_root=root / "output",
                runs=2,
                frames_per_run=1,
                seed="fixed-seed",
                browser_opener=browser_opener,
                runtime_factory=FakeRuntime,
                timeout_s=3.0,
            )

            self.assertEqual([], client_errors)
            self.assertEqual(False, runtime_calls[0]["mouse_enabled"])
            self.assertEqual(True, runtime_calls[0]["visual_check_mode"])
            self.assertEqual(False, runtime_calls[0]["record_video"])
            self.assertEqual("Lie Captcha Studio run-token", runtime_calls[0]["capture_window_title"])
            self.assertEqual([1], reset_runs)
            self.assertTrue(result.gt_jsonl.exists())
            gt_rows = [json.loads(line) for line in result.gt_jsonl.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([0, 1], [row["solver_frame_index"] for row in gt_rows])
            self.assertEqual(result.trace_jsonl, root / "session" / "trace.jsonl")


if __name__ == "__main__":
    unittest.main()
