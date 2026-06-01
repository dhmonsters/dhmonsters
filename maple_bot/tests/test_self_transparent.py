# SelfTransparentEngine — 자체 거탐 엔진 (can_handle + 추적루프 + 실모델 로드)
import os
import numpy as np
import pytest
from core.minigame.self_transparent_engine import SelfTransparentEngine
from core.minigame.solver import SolveResult

MODELS = os.path.join(os.path.dirname(__file__), "..", "models", "transparent")


def test_can_handle():
    eng = SelfTransparentEngine(MODELS, lambda: None, lambda x, y: None)
    assert eng.can_handle("planet") is True
    assert eng.can_handle("transparent") is True
    assert eng.can_handle("lona") is False


def test_solve_tracks_then_completes(monkeypatch):
    """도형이 몇 프레임 보이다 사라지면: 추적 이동 후 success 완료."""
    moves = []
    frames = [(100, 50)] * 3 + [None] * 10   # 3프레임 검출 후 사라짐

    eng = SelfTransparentEngine(
        MODELS,
        board_capture_fn=lambda: np.zeros((10, 10, 3), np.uint8),
        move_cursor_fn=lambda x, y: moves.append((x, y)),
        max_sec=5.0, frame_interval=0.0,
    )
    # 모델 추론을 가짜로 — detect_center 가 frames 순서대로 반환
    class FakeDet:
        def __init__(self): self.i = 0
        def detect_center(self, board, score_thr=0.3):
            v = frames[self.i] if self.i < len(frames) else None
            self.i += 1
            return v
    eng._det = FakeDet()

    r = eng.solve(screenshot=None)
    assert isinstance(r, SolveResult)
    assert r.success is True
    assert "완료" in r.note
    assert moves == [(100, 50), (100, 50), (100, 50)]   # 검출된 3프레임만 이동


def test_solve_model_load_failure_safe():
    """모델 로드 실패해도 예외 안 터지고 실패 결과(봇 안멈춤)."""
    eng = SelfTransparentEngine("nonexistent_dir", lambda: None, lambda x, y: None)
    r = eng.solve(screenshot=None)
    assert r.success is False
    assert "로드 실패" in r.note


@pytest.mark.skipif(not os.path.exists(os.path.join(MODELS, "hyung_m2.param")),
                    reason="거탐 모델 없음")
def test_real_model_loads_and_infers():
    """실제 ncnn 모델 로드 + 추론 (secure_loader 우회 입증)."""
    from core.minigame.transparent_yolo import load_default
    det = load_default(MODELS, use_gpu=False)
    dummy = np.random.randint(0, 255, (400, 500, 3), dtype=np.uint8)
    boxes = det.detect(dummy, score_thr=0.3)
    # 추론이 돌고 결과 shape가 (N,6)
    assert boxes.shape[1] == 6
    if len(boxes):
        assert boxes[:, 4].max() <= 1.0   # score sigmoid 범위
