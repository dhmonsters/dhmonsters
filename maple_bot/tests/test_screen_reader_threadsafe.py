# ScreenReader가 스레드마다 별도 mss를 써서 다른 스레드 캡처가 실패하지 않는지 검증
import threading

from core.screen_reader import ScreenReader


def test_per_thread_mss_instances_differ():
    sr = ScreenReader()
    seen = {}

    def grab(name):
        seen[name] = id(sr._sct())   # 현재 스레드의 mss 인스턴스 id

    main_id = id(sr._sct())
    t = threading.Thread(target=grab, args=("worker",))
    t.start(); t.join()
    # 워커 스레드는 메인과 다른 mss 인스턴스를 가져야 한다(thread-local)
    assert seen["worker"] != main_id


def test_same_thread_reuses_instance():
    sr = ScreenReader()
    assert sr._sct() is sr._sct()   # 같은 스레드면 재사용
