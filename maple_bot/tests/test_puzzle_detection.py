# 투명도형 퍼즐 감지 게이트의 연속 감지와 노이즈 리셋을 검증한다.
from core.puzzle.detection import DetectionGate


def test_detection_gate_requires_consecutive_hits_before_detected():
    gate = DetectionGate(threshold=0.7, required_hits=3)

    first = gate.update(score=0.8, frame_index=10)
    second = gate.update(score=0.81, frame_index=11)
    third = gate.update(score=0.82, frame_index=12)

    assert first.event_type == "DETECTION_PENDING"
    assert first.detected is False
    assert first.hit_count == 1
    assert second.event_type == "DETECTION_PENDING"
    assert second.detected is False
    assert second.hit_count == 2
    assert third.event_type == "PUZZLE_DETECTED"
    assert third.detected is True
    assert third.hit_count == 3
    assert third.frame_index == 12


def test_detection_gate_resets_hit_count_on_noise():
    gate = DetectionGate(threshold=0.7, required_hits=2)

    gate.update(score=0.9, frame_index=1)
    noise = gate.update(score=0.2, frame_index=2)
    recovered = gate.update(score=0.95, frame_index=3)

    assert noise.event_type == "DETECTION_NOISE"
    assert noise.detected is False
    assert noise.hit_count == 0
    assert noise.reason == "below_threshold"
    assert recovered.event_type == "DETECTION_PENDING"
    assert recovered.hit_count == 1


def test_detection_gate_rejects_invalid_settings():
    try:
        DetectionGate(threshold=0.5, required_hits=0)
    except ValueError as exc:
        assert "required_hits" in str(exc)
    else:
        raise AssertionError("DetectionGate should reject non-positive required_hits")
