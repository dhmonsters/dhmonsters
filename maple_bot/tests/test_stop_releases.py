# 정지 시 유지 중인 이동키가 해제되는지 검증(종료 후 계속 이동 방지)
from core.navigation.block_runner import BlockRunner
from core.navigation.floor_hunt_runner import FloorHuntRunner


class _FakeHumanizer:
    def __init__(self):
        self.released = 0
    def release_all(self):
        self.released += 1
    # BlockRunner 생성에 필요한 최소 인터페이스
    def hold_dir(self, *a): pass
    def release_dir(self): pass


def test_block_runner_release_inputs_calls_release_all():
    h = _FakeHumanizer()
    br = BlockRunner(humanizer=h, pos_fn=lambda: (0, 0))
    br.release_inputs()
    assert h.released == 1


def test_floor_hunt_runner_releases_on_exit():
    h = _FakeHumanizer()
    br = BlockRunner(humanizer=h, pos_fn=lambda: (0, 0))
    fhr = FloorHuntRunner(br, get_blocks=lambda: [], is_active=lambda: False)
    fhr._stop.set()      # 정지 상태로 _run 진입 → 루프 미실행, finally에서 해제
    fhr._run()
    assert h.released == 1
