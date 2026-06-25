# 투명 퍼즐 live 추적 건강도 selector의 상태 전환을 검증합니다.
import unittest

from core.vision.transparent_track_health import TransparentTrackHealthSelector


class TransparentTrackHealthSelectorTest(unittest.TestCase):
    def test_uses_rescue_immediately_when_primary_leaves_screen(self):
        selector = TransparentTrackHealthSelector(margin=20.0)
        selector.update(primary=(50.0, 50.0), rescue=None, frame_shape=(100, 100))

        decision = selector.update(
            primary=(60.0, -80.0),
            rescue=(60.0, 55.0),
            frame_shape=(100, 100),
        )

        self.assertEqual(decision.source, "rescue")
        self.assertEqual(decision.reason, "primary_out_of_bounds")
        self.assertEqual(decision.point, (60.0, 55.0))
        self.assertTrue(decision.unhealthy)

    def test_waits_for_repeated_inside_jump_before_using_rescue(self):
        selector = TransparentTrackHealthSelector(
            suspect_jump_px=30.0,
            suspect_frames_required=2,
            rescue_hold_frames=0,
        )
        selector.update(primary=(10.0, 10.0), rescue=None, frame_shape=(200, 200))
        selector.update(primary=(20.0, 10.0), rescue=None, frame_shape=(200, 200))

        first = selector.update(
            primary=(90.0, 10.0),
            rescue=(30.0, 10.0),
            frame_shape=(200, 200),
        )
        second = selector.update(
            primary=(100.0, 10.0),
            rescue=(40.0, 10.0),
            frame_shape=(200, 200),
        )

        self.assertEqual(first.source, "primary")
        self.assertEqual(first.reason, "primary_suspect")
        self.assertEqual(second.source, "rescue")
        self.assertEqual(second.reason, "primary_repeated_jump")
        self.assertEqual(second.point, (40.0, 10.0))

    def test_force_primary_resets_suspicion(self):
        selector = TransparentTrackHealthSelector(
            suspect_jump_px=20.0,
            suspect_frames_required=2,
        )
        selector.update(primary=(10.0, 10.0), rescue=None, frame_shape=(200, 200))
        selector.update(primary=(80.0, 10.0), rescue=(20.0, 10.0), frame_shape=(200, 200))

        forced = selector.update(
            primary=(85.0, 10.0),
            rescue=(30.0, 10.0),
            frame_shape=(200, 200),
            force_primary=True,
        )

        self.assertEqual(forced.source, "primary")
        self.assertEqual(forced.reason, "force_primary")
        self.assertEqual(forced.suspect_frames, 0)


if __name__ == "__main__":
    unittest.main()
