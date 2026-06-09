# planet_solver_noauth.py — Planet_solver v2 GUI (서버인증/라이선스 제거, 탐지엔진 자체 탑재)
"""
Planet_solver_v1.0.5.exe 의 GUI/UX를 그대로 유지하되:
  - LicenseDialog / fetch_secure_code / inject_into_macro 완전 제거
  - 탐지 엔진: planet_yolo_verify.py (M1Ensemble + HyungYolo, ncnn)
  - 마우스: PostMessage 백그라운드 클릭
  - 창 자동 탐지: win32gui (board_roi.json 불필요)
  - 해상도 강제: 1920×1080
  - 단축키: F1 시작/정지 (exe와 동일)

실행: python planet_solver_noauth.py
"""
from __future__ import annotations

import ctypes, json, os, sys, threading, time, winsound
# Qt6가 자체적으로 DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 설정 → 별도 호출 불필요
# (SetProcessDPIAware 중복 호출 시 Qt 경고 발생)
import win32api, win32con, win32gui
import cv2, mss, numpy as np

from PyQt6.QtCore    import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui     import QFont, QImage, QPixmap, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QPlainTextEdit,
    QLineEdit, QFrame, QSizePolicy,
)

# ── 경로 ──────────────────────────────────────────────────────────────────
ROOT        = os.path.dirname(os.path.abspath(__file__))
EXTRACT     = os.path.join(ROOT, "_planet_solver_extract",
                           "Planet_solver_v1.0.5.exe_extracted")
ASSETS      = os.path.join(EXTRACT, "assets")
CONFIG_FILE = os.path.join(ROOT, "planet_solver_config.json")
MH_ASSETS   = os.path.join(ROOT, "_maplehunter_extract",
                            "MapleHunter_v3.1.17.exe_extracted", "assets")

# ── 팝업 감지 / 보드 ROI 상대 좌표 ─────────────────────────────────────────
# 참조: 00412.PNG / popup_range.png (게임 클라이언트 1920×1080 기준)
# 기준: popup_range.png 실측 + 미리보기 피드백 미세 보정
HDR_X1_R, HDR_X2_R = 0.320, 0.678   # 🟡 노란선: 팝업 타이틀바 (HDR 감지)
HDR_Y1_R, HDR_Y2_R = 0.202, 0.263
BRD_X1_R, BRD_X2_R = 0.318, 0.680   # 🔴 전체 팝업 영역
BRD_Y1_R, BRD_Y2_R = 0.188, 0.775
DET_X1_R, DET_X2_R = 0.320, 0.678   # 🟠 주황선: 퍼즐 도형 구역
DET_Y1_R, DET_Y2_R = 0.265, 0.728

_POPUP_TEMPLATES: list = []
for _tname in ("minigame.png", "xz.bmp", "xz1.bmp", "xz2.bmp", "xz4.bmp"):
    _tp = os.path.join(MH_ASSETS, _tname)
    if os.path.exists(_tp):
        _img = cv2.imread(_tp)
        if _img is not None:
            _POPUP_TEMPLATES.append(_img)

# ── 팝업 감지용 템플릿 (templates/ 폴더 — 그레이스케일 사전 변환) ───────────
# 용도: 노란색 HDR 영역 매칭으로 "투명 도형 찾기" 팝업 존재 여부 판별
# templates/ 폴더에 이미지 파일을 넣으면 재시작 없이 자동 감지
TMPL_DIR = os.path.join(ROOT, "templates")
_POPUP_TMPLS: list[tuple[np.ndarray, int, int]] = []  # (gray, h, w)

_TMPL_MIN_W, _TMPL_MIN_H = 100, 50  # 팝업 타이틀 이미지 최소 크기 (소형 이미지 제외)

def _reload_templates() -> int:
    """templates/ 폴더의 이미지를 그레이스케일로 로드. 로드된 개수 반환.

    크기 필터: 너비 < 100 또는 높이 < 50 이면 로드 제외
      - 통과: 01.png(213×63), 02.png(928×73), 03.png(675×53), lie_detector_1.png(219×63)
      - 제외: map_name_ref, monster_capture, name_tag, xz*.bmp 등
    """
    _POPUP_TMPLS.clear()
    if not os.path.isdir(TMPL_DIR):
        return 0
    exts = {".bmp", ".png", ".jpg", ".jpeg"}
    for fname in sorted(os.listdir(TMPL_DIR)):
        if os.path.splitext(fname)[1].lower() not in exts:
            continue
        fpath = os.path.join(TMPL_DIR, fname)
        img = cv2.imread(fpath)
        if img is None:
            continue
        h, w = img.shape[:2]
        if w < _TMPL_MIN_W or h < _TMPL_MIN_H:
            continue  # 팝업 타이틀이 아닌 소형 이미지 제외
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _POPUP_TMPLS.append((gray, h, w))
    return len(_POPUP_TMPLS)

_n = _reload_templates()

# ── 탐지 엔진 로드 ─────────────────────────────────────────────────────────
from planet_yolo_verify import M1Ensemble, HyungYolo

def _load_models(use_gpu: bool = False):
    param = os.path.join(ASSETS, "hyung_m1.param")

    # M1 specialists: bin a/b/c/d 각각이 cls 0/1/2/3 전담 탐지기
    # target_cls 확정 후 m1_specialists[target_cls] 하나만 사용 (원본 정통 방식)
    m1_specialists = [
        HyungYolo(param, os.path.join(ASSETS, f"hyung_m1_{s}.bin"),
                  num_cls=1, use_gpu=use_gpu)
        for s in "abcd"
    ]
    # M1 ensemble: target_cls 미확정 시 fallback
    m1_ensemble = M1Ensemble(
        param,
        [os.path.join(ASSETS, f"hyung_m1_{s}.bin") for s in "abcd"],
        use_gpu=use_gpu,
    )

    m2_raw = HyungYolo(
        os.path.join(ASSETS, "hyung_m2.param"),
        os.path.join(ASSETS, "hyung_m2.bin"),
        num_cls=4, use_gpu=use_gpu,
    )
    # mypyc 버전은 classify_crop(img, score_thr), 일반은 classify_crop(img, imgsz, score_thr)
    import inspect
    sig = inspect.signature(m2_raw.classify_crop)
    if len(sig.parameters) == 2:
        _orig = m2_raw.classify_crop
        class _M2Wrap:
            def classify_crop(self_, img, imgsz=192, score_thr=0.0):
                return _orig(img, score_thr)
            def detect(self_, img, imgsz=192, score_thr=0.2, iou_thr=0.45):
                return m2_raw.detect(img, imgsz, score_thr, iou_thr)
        m2 = _M2Wrap()
    else:
        m2 = m2_raw
    return m1_specialists, m1_ensemble, m2

# ── 창 탐지 / 해상도 ──────────────────────────────────────────────────────
_GAME_CLASSES  = ("MapleStoryClass", "UnityWndClass", "NEXON Plug-in Window")
_GAME_KEYWORDS = ("maplestory", "메이플스토리", "worlds")
TARGET_W, TARGET_H = 1920, 1080

def _find_hwnd():
    found = []
    def _cb(h, _):
        if not win32gui.IsWindowVisible(h): return
        cls   = win32gui.GetClassName(h).lower()
        title = win32gui.GetWindowText(h).lower()
        if any(c.lower() in cls for c in _GAME_CLASSES) or \
           any(k in title for k in _GAME_KEYWORDS):
            found.append(h)
    win32gui.EnumWindows(_cb, None)
    return found[0] if found else None

def _enforce_res(hwnd):
    cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
    cw, ch = cr - cl, cb - ct
    if cw == TARGET_W and ch == TARGET_H: return
    wr, wt, wrr, wb = win32gui.GetWindowRect(hwnd)
    bx = (wrr - wr) - cw; by = (wb - wt) - ch
    win32gui.SetWindowPos(hwnd, 0, wr, wt, TARGET_W + bx, TARGET_H + by,
                          win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)

def _client_roi(hwnd):
    cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
    pt = win32gui.ClientToScreen(hwnd, (cl, ct))
    return pt[0], pt[1], cr - cl, cb - ct

# ── 텔레그램 전송 ────────────────────────────────────────────────────────
def _send_telegram(token: str, chat_id: str, img_bgr, caption: str = "") -> tuple[bool, str]:
    """전체화면 캡쳐 이미지를 텔레그램으로 전송. (urllib 사용, requests 불필요)"""
    import urllib.request, urllib.parse, io, uuid
    try:
        ok, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return False, "이미지 인코딩 실패"
        img_bytes = buf.tobytes()

        boundary = uuid.uuid4().hex
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            f"{chat_id}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n'
            f"{caption}\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="capture.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode() + img_bytes + f"\r\n--{boundary}--\r\n".encode()

        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, ""
    except Exception as e:
        return False, str(e)


# ── 팝업 보드 ROI 감지 ────────────────────────────────────────────────────
def _detect_popup_board(client_frame, bx, by, bw, bh,
                        score_thr=0.65, dark_ratio_thr=0.50):
    """노란색 HDR 영역으로 팝업 감지.

    반환: (board_mon, hdr_score, gray_r, bright_r)
      - board_mon : 팝업 감지 시 BRD mss mon dict, 미감지 시 None
      - hdr_score : 최고 감지 점수 (0.0~1.0, 미리보기 표시용)
      - gray_r    : 저채도(회색) 픽셀 비율 (진단용)
      - bright_r  : 흰색 픽셀 비율 (진단용)

    1차: 저채도 회색 배경 + 흰 텍스트 픽셀 비율 (다크/미디엄 그레이 모두 감지)
    2차: 템플릿 매칭 (보조)
    """
    hx1 = int(bw * HDR_X1_R); hy1 = int(bh * HDR_Y1_R)
    hx2 = int(bw * HDR_X2_R); hy2 = int(bh * HDR_Y2_R)
    hdr_crop = client_frame[hy1:hy2, hx1:hx2]

    board_mon = {
        "left":   bx + int(bw * BRD_X1_R),
        "top":    by + int(bh * BRD_Y1_R),
        "width":  int(bw * (BRD_X2_R - BRD_X1_R)),
        "height": int(bh * (BRD_Y2_R - BRD_Y1_R)),
    }

    # ── HDR 영역에서 원본 크기 그대로 매칭 (스케일 계산 없음) ─────────────────
    # 기존 문제: HDR 높이 62px → 63px 템플릿 1px 초과 → 강제 축소 후 매칭
    # 수정: 상하 2px 여유를 주어 63px 템플릿이 원본 크기로 매칭되도록 함
    # (비율 상수는 그대로 유지, crop만 ±2px 확장)
    _hy1 = max(0,  int(bh * HDR_Y1_R) - 2)
    _hy2 = min(bh, int(bh * HDR_Y2_R) + 2)
    hdr_match = client_frame[_hy1:_hy2, hx1:hx2]
    hdr_gray  = cv2.cvtColor(hdr_match, cv2.COLOR_BGR2GRAY)
    dh, dw    = hdr_gray.shape

    bright_r = float(np.all(hdr_crop > 175, axis=2).mean())   # 진단용
    brd_mean = 0.0                                             # 진단용 placeholder

    best_score = 0.0
    for (tmpl, th, tw) in _POPUP_TMPLS:
        if th > dh or tw > dw:
            continue   # 그래도 안 맞으면 skip
        res = cv2.matchTemplate(hdr_gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, _ = cv2.minMaxLoc(res)
        if mx > best_score:
            best_score = mx

    # ── 최종 판정 ────────────────────────────────────────────────────────────
    hdr_score = best_score
    if best_score >= score_thr:
        return board_mon, hdr_score, brd_mean, bright_r
    return None, hdr_score, brd_mean, bright_r


# ── PostMessage 백그라운드 클릭 ───────────────────────────────────────────
def _focus_game(hwnd: int) -> None:
    """게임 창 포그라운드 확보 (추적 시작 시 1회만 호출)."""
    if hwnd:
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.05)
        except Exception:
            pass

def _real_click(abs_x: int, abs_y: int) -> None:
    """커서를 지정 좌표로 이동 (원본과 동일 — fg_move 방식, 클릭 없음)."""
    try:
        win32api.SetCursorPos((abs_x, abs_y))
    except Exception:
        pass

# ── 탐지 스레드 ────────────────────────────────────────────────────────────
class _Sig(QObject):
    log     = pyqtSignal(str)
    status  = pyqtSignal(str)   # "running" | "stopped" | "error:..."
    capcha  = pyqtSignal(int, int)
    preview = pyqtSignal(object)  # annotated board BGR ndarray | None

class _MacroThread(threading.Thread):
    IMGSZ = 160   # 원본 M1Ensemble 상수값 (96으로 낮추면 정확도 손실)
    SCORE = 0.2

    def __init__(self, sig: _Sig, use_gpu: bool, sound: bool,
                 tg_enabled: bool = False, tg_token: str = "", tg_chat: str = ""):
        super().__init__(daemon=True)
        self._sig      = sig
        self._gpu      = use_gpu
        self._sound    = sound
        self._tg       = tg_enabled and bool(tg_token) and bool(tg_chat)
        self._tg_token = tg_token
        self._tg_chat  = tg_chat
        self._stop     = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        # 시작마다 templates/ 폴더 재로드 (파일 추가 후 재시작하면 반영)
        n = _reload_templates()
        self._sig.log.emit(f"[*] 템플릿 {n}개 로드 완료 ({TMPL_DIR})")
        self._sig.log.emit("[*] 모델 로드 중...")
        try:
            m1_specialists, m1_ensemble, m2 = _load_models(self._gpu)
        except Exception as e:
            self._sig.status.emit(f"error:모델 로드 실패: {e}")
            return

        self._sig.log.emit("[*] 메이플 창 탐색...")
        hwnd = _find_hwnd()
        if hwnd is None:
            # 테스트 모드: 메이플 창 없으면 모니터 전체를 캡처 영역으로 사용
            # (팝업 스크린샷을 화면에 띄워서 감지 테스트 가능)
            self._sig.log.emit("[!] 메이플 창 없음 → 모니터 전체 영역으로 테스트 모드 진행")
            hwnd = 0
            import mss as _mss_init
            with _mss_init.mss() as _s0:
                _m0 = _s0.monitors[1]
                bx = _m0["left"]; by = _m0["top"]
                bw = _m0["width"]; bh = _m0["height"]
        else:
            title = win32gui.GetWindowText(hwnd)
            self._sig.log.emit(f"[✓] 창: {title}")
            _enforce_res(hwnd)
            bx, by, bw, bh = _client_roi(hwnd)
        self._sig.log.emit(f"[좌표] {bx},{by}  {bw}×{bh}")
        self._sig.status.emit("running")

        success = miss = 0
        tracking = False
        popup_logged = False         # 팝업 감지 첫 로그 중복 방지
        _target_cls      = None      # _on_trigger_start: M2 분류한 도형 클래스 ID
        _last_marker_pos = (0, 0)    # _track_once: 직전 프레임 도형 중심 (det 내 좌표)
        CAPCHA_END_MISS_COUNT = 3    # 원본과 동일 — 연속 미탐지 3회 → 퍼즐 종료 판정
        TRACK_INTERVAL = 0.05        # 원본과 동일 — 추적 루프 주기 (20fps)
        MAX_JUMP = 180               # 프레임 간 허용 최대 이동거리(px) — 초과 시 miss 처리
        MAX_MISS_RESET = 5           # 연속 miss 이 횟수 도달 시 마커 리셋 → 재획득
        BOX_MIN_SIZE = 15            # 박스 최소 너비/높이(px) — 미만이면 노이즈로 제거
        BOX_MAX_SIZE = 300           # 박스 최대 너비/높이(px) — 초과이면 오감지로 제거
        last_alert = 0.0
        last_tg      = 0.0   # 텔레그램 전송 쿨다운
        preview_cnt  = 0     # 미리보기 emit 카운터 (5프레임마다 1회)

        with mss.mss() as sct:
            full_mon = {"left": 0, "top": 0, "width": 0, "height": 0}  # 초기화 후 갱신
            try:
                m = sct.monitors[1]
                full_mon = {"left": m["left"], "top": m["top"],
                            "width": m["width"], "height": m["height"]}
            except Exception:
                pass

            client_mon = {"left": bx, "top": by, "width": bw, "height": bh}

            while not self._stop.is_set():
                try:
                    # 60회마다 좌표 갱신
                    if (success + miss) % 60 == 0 and (success + miss) > 0:
                        try:
                            bx, by, bw, bh = _client_roi(hwnd)
                            client_mon = {"left": bx, "top": by, "width": bw, "height": bh}
                        except Exception:
                            pass

                    client = cv2.cvtColor(np.array(sct.grab(client_mon)), cv2.COLOR_BGRA2BGR)
                    board_mon, hdr_score, _dbg_gray, _dbg_bright = _detect_popup_board(client, bx, by, bw, bh)

                    # 빨간 영역: 전체 팝업 (HDR_Y1 ~ BRD_Y2) — 항상 캡처해서 미리보기에 사용
                    _pop_x1 = bx + int(bw * BRD_X1_R)
                    _pop_y1 = by + int(bh * HDR_Y1_R)
                    _pop_w  = int(bw * (BRD_X2_R - BRD_X1_R))
                    _pop_h  = int(bh * (BRD_Y2_R - HDR_Y1_R))
                    popup_mon = {"left": _pop_x1, "top": _pop_y1,
                                 "width": _pop_w, "height": _pop_h}
                    popup = cv2.cvtColor(np.array(sct.grab(popup_mon)), cv2.COLOR_BGRA2BGR)

                    if board_mon is None:
                        # 팝업 사라짐 → 추적 중이었으면 퍼즐 완료 판정
                        if tracking:
                            tracking = False
                            _last_marker_pos = (0, 0)
                            _target_cls = None
                            success += 1
                            self._sig.capcha.emit(success % 100, success)
                            self._sig.log.emit(f"[✓] 퍼즐 완료 — 누적 {success}회")
                        popup_logged = False
                        preview_cnt += 1
                        # 60프레임(~1초)마다 진단 값을 텍스트 로그에 출력
                        if preview_cnt % 60 == 1:
                            self._sig.log.emit(
                                f"[HDR 진단] score={hdr_score:.2f} bright={_dbg_bright:.2f}"
                                f"  (기준: score≥0.65)"
                            )
                        if preview_cnt % 5 == 0:
                            # 팝업 없음 — HDR 노란 테두리 + score + "대기 중" 표시
                            standby = popup.copy()
                            _sb_hdr_ry = int(bh * (HDR_Y2_R - HDR_Y1_R))
                            _sb_pop_w  = standby.shape[1]
                            cv2.rectangle(standby, (0, 0), (_sb_pop_w, _sb_hdr_ry),
                                          (0, 230, 255), 2)
                            cv2.putText(standby,
                                        f"HDR score={hdr_score:.2f} / thr=0.65",
                                        (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                                        (0, 230, 255), 1, cv2.LINE_AA)
                            cv2.putText(standby, "팝업 대기 중",
                                        (10, _sb_hdr_ry + 24), cv2.FONT_HERSHEY_SIMPLEX,
                                        0.8, (0, 215, 255), 2, cv2.LINE_AA)
                            self._sig.preview.emit(standby)
                        time.sleep(0.016)  # 팝업 대기 중 60fps
                        continue

                    # ── 팝업 첫 감지 → _on_trigger_start ────────────────────
                    if not popup_logged:
                        popup_logged = True
                        _CLS_NAMES = {0: "원", 1: "사각형", 2: "삼각형", 3: "별"}

                        self._sig.log.emit(
                            f"[팝업 감지] HDR score={hdr_score:.2f} (임계값 0.65 초과) "
                            f"→ _on_trigger_start 진입"
                        )

                        det_mon = {
                            "left":   bx + int(bw * DET_X1_R),
                            "top":    by + int(bh * DET_Y1_R),
                            "width":  int(bw * (DET_X2_R - DET_X1_R)),
                            "height": int(bh * (DET_Y2_R - DET_Y1_R)),
                        }
                        # 이미 캡처된 client 프레임에서 DET 영역 크롭 (추가 grab 없음)
                        _dy1 = int(bh * DET_Y1_R)
                        _dy2 = _dy1 + int(bh * (DET_Y2_R - DET_Y1_R))
                        _dx1 = int(bw * DET_X1_R)
                        _dx2 = _dx1 + int(bw * (DET_X2_R - DET_X1_R))
                        det_init = client[_dy1:_dy2, _dx1:_dx2]

                        # M2로 중앙 도형 클래스 분류 (아직 흰색으로 보이는 순간)
                        dh, dw = det_init.shape[:2]
                        center_crop = det_init[dh//4:3*dh//4, dw//4:3*dw//4]
                        # ── M2 디버그 이미지 저장 (m2_debug 폴더) ──────────────
                        try:
                            import datetime
                            _dbg_dir = os.path.join(ROOT, "m2_debug")
                            os.makedirs(_dbg_dir, exist_ok=True)
                            _ts = datetime.datetime.now().strftime("%H%M%S_%f")[:9]
                            cv2.imwrite(os.path.join(_dbg_dir, f"{_ts}_det.png"), det_init)
                            cv2.imwrite(os.path.join(_dbg_dir, f"{_ts}_crop.png"), center_crop)
                        except Exception:
                            pass
                        # ────────────────────────────────────────────────────────
                        self._sig.log.emit(
                            f"[M2] DET 영역 캡처 완료 ({dw}x{dh}px) "
                            f"→ center_crop {center_crop.shape[1]}x{center_crop.shape[0]}px 분류 중..."
                        )
                        try:
                            if center_crop.shape[0] >= 32 and center_crop.shape[1] >= 32:
                                _target_cls = m2.classify_crop(center_crop, 192)
                                cls_name = _CLS_NAMES.get(_target_cls, "알수없음") if _target_cls is not None else "None"
                                self._sig.log.emit(
                                    f"[M2] 분류 완료 → target_cls={_target_cls} ({cls_name}) "
                                    f"→ M1 {'specialist[' + str(_target_cls) + ']' if _target_cls is not None else 'ensemble(fallback)'} 사용"
                                )
                            else:
                                _target_cls = None
                                self._sig.log.emit(
                                    f"[M2] center_crop 너무 작음 {center_crop.shape[:2]} → 분류 스킵, ensemble 사용"
                                )
                        except Exception as e:
                            _target_cls = None
                            self._sig.log.emit(f"[M2] 분류 실패: {e} → ensemble fallback")
                        _last_marker_pos = (dw // 2, dh // 2)

                        _focus_game(hwnd)  # 게임 창 포그라운드 (1회)
                        self._sig.log.emit(
                            f"[포그라운드] 게임 창 활성화 → 추적 시작 "
                            f"(초기 마커 중앙 {_last_marker_pos})"
                        )

                    # 주황 영역: 퍼즐 해제 구역 — M1 YOLO 도형 감지
                    det_mon = {
                        "left":   bx + int(bw * DET_X1_R),
                        "top":    by + int(bh * DET_Y1_R),
                        "width":  int(bw * (DET_X2_R - DET_X1_R)),
                        "height": int(bh * (DET_Y2_R - DET_Y1_R)),
                    }
                    det = cv2.cvtColor(np.array(sct.grab(det_mon)), cv2.COLOR_BGRA2BGR)

                    # target_cls 확정 시 전담 specialist, 미확정 시 ensemble fallback
                    # 원본 정통: M2 cls 분류 → M1[cls] specialist 하나만 사용
                    _CLS_NAMES = {0: "원", 1: "사각형", 2: "삼각형", 3: "별"}
                    if _target_cls is not None and 0 <= _target_cls <= 3:
                        detector = m1_specialists[_target_cls]
                        _det_label = f"M1 specialist[{_target_cls}]({_CLS_NAMES[_target_cls]})"
                    else:
                        detector = m1_ensemble
                        _det_label = "M1 ensemble(fallback)"
                    boxes = detector.detect(det, self.IMGSZ, self.SCORE)

                    # 박스 크기 필터 (노이즈 및 과대 오감지 제거)
                    if len(boxes):
                        _bw = boxes[:, 2] - boxes[:, 0]
                        _bh = boxes[:, 3] - boxes[:, 1]
                        _size_mask = (
                            (_bw >= BOX_MIN_SIZE) & (_bh >= BOX_MIN_SIZE) &
                            (_bw <= BOX_MAX_SIZE) & (_bh <= BOX_MAX_SIZE)
                        )
                        boxes = boxes[_size_mask]

                    # ── _track_once: 박스 선택 (MAX_JUMP 필터 포함) ──────────
                    _best = None
                    _select_method = ""
                    if len(boxes):
                        if _last_marker_pos != (0, 0):
                            lx, ly = _last_marker_pos
                            centers = np.array([
                                ((b[0]+b[2])/2, (b[1]+b[3])/2) for b in boxes
                            ])
                            dists = np.hypot(centers[:,0]-lx, centers[:,1]-ly)

                            valid_mask = dists <= MAX_JUMP
                            if valid_mask.any():
                                valid_boxes = boxes[valid_mask]
                                valid_dists = dists[valid_mask]
                                _best = valid_boxes[valid_dists.argmin()]
                                _select_method = (
                                    f"거리기반(유효{valid_mask.sum()}/{len(boxes)}개, "
                                    f"dist={valid_dists.min():.0f}px)"
                                )
                            else:
                                # 모든 박스가 MAX_JUMP 초과 → miss 처리
                                self._sig.log.emit(
                                    f"[점프차단] 최근접 {dists.min():.0f}px "
                                    f"> {MAX_JUMP}px → miss 처리"
                                )
                        else:
                            # 첫 프레임: 마커 없으므로 최고점수 박스 무조건 선택
                            _best = boxes[boxes[:, 4].argmax()]
                            _select_method = f"최고점수(boxes={len(boxes)})"

                    if _best is not None:
                        cx = int((_best[0] + _best[2]) / 2)
                        cy = int((_best[1] + _best[3]) / 2)
                        _last_marker_pos = (cx, cy)

                        abs_x = det_mon["left"] + cx
                        abs_y = det_mon["top"]  + cy
                        _real_click(abs_x, abs_y)
                        miss = 0

                        if not tracking:
                            tracking = True
                            self._sig.log.emit(
                                f"[{_det_label}] 첫 감지 score={float(_best[4]):.2f} "
                                f"→ 커서 ({abs_x}, {abs_y})  선택방식={_select_method}"
                            )
                        elif preview_cnt % 30 == 0:
                            # 30프레임(~1.5초)마다 추적 상태 요약
                            self._sig.log.emit(
                                f"[추적중] {_det_label}  score={float(_best[4]):.2f} "
                                f"pos=({abs_x},{abs_y})  {_select_method}  miss={miss}"
                            )
                            now = time.time()
                            if self._sound and now - last_alert > 2.0:
                                last_alert = now
                                def _beep():
                                    for _ in range(2):
                                        winsound.Beep(1000, 200)
                                threading.Thread(target=_beep, daemon=True).start()
                            if self._tg and now - last_tg > 30.0:
                                last_tg = now
                                try:
                                    full = cv2.cvtColor(
                                        np.array(sct.grab(full_mon)), cv2.COLOR_BGRA2BGR)
                                except Exception:
                                    full = popup
                                token, chat = self._tg_token, self._tg_chat
                                threading.Thread(
                                    target=self._tg_send,
                                    args=(full, token, chat, success + 1),
                                    daemon=True,
                                ).start()
                    else:
                        # M1 미감지 — 커서를 마지막 위치에 유지 (fg_move 방식과 동일)
                        if tracking and _last_marker_pos != (0, 0):
                            abs_x = det_mon["left"] + _last_marker_pos[0]
                            abs_y = det_mon["top"]  + _last_marker_pos[1]
                            _real_click(abs_x, abs_y)
                        miss += 1
                        if miss == 1:
                            self._sig.log.emit(
                                f"[{_det_label}] 미감지(1회) — "
                                f"마지막 위치 {_last_marker_pos} 유지 중..."
                            )
                        elif miss % 10 == 0:
                            self._sig.log.emit(
                                f"[{_det_label}] 미감지 {miss}회 연속 — "
                                f"마지막 위치 {_last_marker_pos}"
                            )
                        # 연속 miss가 MAX_MISS_RESET 도달 → 마커 초기화 후 재획득
                        if miss >= MAX_MISS_RESET and _last_marker_pos != (0, 0):
                            _last_marker_pos = (0, 0)
                            self._sig.log.emit(
                                f"[재획득] miss {miss}회 → 마커 초기화, 다음 프레임 최고점수로 재획득"
                            )

                    # ── 미리보기 emit (5프레임마다) ──────────────────────────
                    preview_cnt += 1
                    if preview_cnt % 5 == 0:
                        vis = popup.copy()
                        _hdr_ry = int(bh * (HDR_Y2_R - HDR_Y1_R))
                        _det_lx = det_mon["left"] - _pop_x1
                        _det_ly = det_mon["top"]  - _pop_y1
                        _det_rx = _det_lx + det_mon["width"]
                        _det_ry = _det_ly + det_mon["height"]
                        # 노란색: 상단 검정바 + HDR 매칭 score
                        cv2.rectangle(vis, (0, 0), (_pop_w, _hdr_ry),
                                      (0, 230, 255), 2)
                        cv2.putText(vis,
                                    f"HDR score={hdr_score:.2f} / thr=0.65",
                                    (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                                    (0, 230, 255), 1, cv2.LINE_AA)
                        # 주황색: 퍼즐 해제 구역
                        cv2.rectangle(vis, (_det_lx, _det_ly), (_det_rx, _det_ry),
                                      (0, 140, 255), 2)
                        cv2.putText(vis, "DET", (_det_lx + 4, _det_ly + 14),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                                    (0, 140, 255), 1, cv2.LINE_AA)
                        # 초록색: M1 detection 박스 (det → popup 좌표 변환)
                        for b in boxes:
                            dx1 = _det_lx + int(b[0]); dy1 = _det_ly + int(b[1])
                            dx2 = _det_lx + int(b[2]); dy2 = _det_ly + int(b[3])
                            cv2.rectangle(vis, (dx1, dy1), (dx2, dy2),
                                          (80, 255, 0), 2)
                        if len(boxes):
                            best2 = boxes[boxes[:, 4].argmax()]
                            cx2 = _det_lx + int((best2[0] + best2[2]) / 2)
                            cy2 = _det_ly + int((best2[1] + best2[3]) / 2)
                            cv2.drawMarker(vis, (cx2, cy2),
                                           (0, 255, 80), cv2.MARKER_CROSS, 22, 2)
                            sc = float(best2[4])
                            cv2.putText(vis, f"score={sc:.2f}",
                                        (_det_lx + 4, _det_ry - 6),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.4, (255, 220, 0), 1, cv2.LINE_AA)
                        self._sig.preview.emit(vis)

                    # 추적 중: TRACK_INTERVAL(0.05s=20fps), 대기 중: 60fps
                    time.sleep(TRACK_INTERVAL if tracking else 0.016)

                except Exception as e:
                    self._sig.log.emit(f"[!] {e}")
                    time.sleep(0.5)

        self._sig.status.emit("stopped")

    def _tg_send(self, img, token, chat, count):
        ok, err = _send_telegram(token, chat, img, f"Planet 거탐 감지 #{count}")
        if ok:
            self._sig.log.emit(f"[📨] 텔레그램 전송 완료 (#{count})")
        else:
            self._sig.log.emit(f"[!] 텔레그램 전송 실패: {err[:60]}")


# ── 다크 테마 CSS (toss_wrapper 원본 그대로) ────────────────────────────
_CSS = """
QWidget#root {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #0F1419, stop:0.5 #161B23, stop:1 #0B0F14);
    color: #E5E8EB;
    font-family: 'Pretendard','Apple SD Gothic Neo','Segoe UI',sans-serif;
    font-size: 13px;
}
QWidget { color: #E5E8EB; background: transparent; font-size: 13px;
    font-family: 'Pretendard','Apple SD Gothic Neo','Segoe UI',sans-serif; }
QLabel#title { font-size: 16px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.5px; }
QLabel#subtitle { font-size: 11px; color: #6B7684; letter-spacing: 0.3px; }
QLabel#status_label { font-size: 20px; font-weight: 800; color: #3182F6; letter-spacing: -1px; }
QLabel#status_label[state="running"] { color: #1AAD7E; }
QLabel#status_label[state="error"]   { color: #F04452; }
QLabel#hint  { color: #6B7684; font-size: 10px; }
QLabel#stat  { color: #8B95A1; font-size: 10px; font-weight: 500; }
QLabel#stat_value { color: #FFFFFF; font-size: 15px; font-weight: 700; letter-spacing: -0.5px; }
QLabel#section { color: #E5E8EB; font-size: 11px; font-weight: 700; }
QPushButton#toggle {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #4592FF, stop:1 #2872E6);
    color: #FFFFFF; border: none; border-radius: 14px; padding: 16px 24px;
    font-size: 15px; font-weight: 700;
}
QPushButton#toggle:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5BA0FF, stop:1 #3380F0);
}
QPushButton#toggle[state="running"] {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FF5662, stop:1 #E03844);
}
QPushButton#toggle[state="running"]:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FF6B76, stop:1 #E84954);
}
QFrame#card {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(40,48,60,230), stop:1 rgba(28,34,44,230));
    border-radius: 18px; border: 1px solid rgba(255,255,255,12);
}
QCheckBox { color: #E5E8EB; spacing: 8px; font-size: 12px; }
QCheckBox::indicator { width:18px; height:18px; border-radius:5px;
    border:1px solid rgba(255,255,255,40); background:rgba(20,26,34,180); }
QCheckBox::indicator:checked { background:#3182F6; border-color:#3182F6; }
QPlainTextEdit {
    background: rgba(15,20,25,180); color:#8B95A1;
    font-family: Consolas; font-size:10px; border-radius:10px; padding:8px;
    border: none;
}
QLineEdit {
    background: rgba(40,48,60,200); color:#FFFFFF;
    border:1px solid rgba(255,255,255,15); border-radius:8px; padding:8px;
    font-size:11px;
}
"""


# ── 감지 영역 미리보기 창 ───────────────────────────────────────────────────
class PreviewWindow(QWidget):
    """board_mon 영역의 실시간 캡처와 detection 박스를 보여주는 플로팅 창."""

    _NO_BOARD_MSG = "팝업 미감지 중"
    _IDLE_MSG     = "실행 후 표시됩니다"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("감지 영역 미리보기")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.resize(380, 260)
        self.setStyleSheet("background:#0a0d10;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 이미지 레이블
        self.lbl_img = QLabel(self._IDLE_MSG)
        self.lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_img.setStyleSheet(
            "color:#555; font-size:12px; background:#0a0d10;"
        )
        self.lbl_img.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.lbl_img.setMinimumSize(100, 60)
        layout.addWidget(self.lbl_img)

        # 하단 정보 레이블
        self.lbl_info = QLabel("대기 중")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_info.setStyleSheet("color:#555; font-size:10px;")
        self.lbl_info.setFixedHeight(18)
        layout.addWidget(self.lbl_info)

    def update_frame(self, frame_bgr) -> None:
        """numpy BGR 프레임 또는 None을 받아 표시."""
        if frame_bgr is None:
            self.lbl_img.setPixmap(QPixmap())
            self.lbl_img.setText(self._NO_BOARD_MSG)
            self.lbl_info.setText("보드 영역 미감지")
            return

        h, w = frame_bgr.shape[:2]
        rgb  = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pm   = QPixmap.fromImage(qimg)

        lbl_sz = self.lbl_img.size()
        pm = pm.scaled(lbl_sz,
                       Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        self.lbl_img.setPixmap(pm)
        self.lbl_img.setText("")
        self.lbl_info.setText(f"board {w}×{h}")

    def reset(self) -> None:
        self.lbl_img.setPixmap(QPixmap())
        self.lbl_img.setText(self._IDLE_MSG)
        self.lbl_info.setText("대기 중")


# ── 메인 윈도우 ────────────────────────────────────────────────────────────
class MainUI(QWidget):
    def __init__(self):
        super().__init__()
        self._macro: _MacroThread | None = None
        self._is_running = False
        self._start_time: float | None = None

        self._sig = _Sig()
        self._sig.log.connect(self._append_log)
        self._sig.status.connect(self._on_status)
        self._sig.capcha.connect(lambda t, n: self.capcha_value.setText(str(n)))
        self._sig.preview.connect(self._on_preview)
        self._preview_win: PreviewWindow | None = None

        self.setObjectName("root")
        self.setWindowTitle("Planet-투명도형 v2")
        self.resize(400, 620)
        self.setMinimumSize(360, 540)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )
        self._build_ui()
        self.setStyleSheet(_CSS)

        self._load_config()

        # F1 전역 핫키 (keyboard 모듈 없이 폴링 방식)
        self._hk_timer = QTimer()
        self._hk_timer.timeout.connect(self._poll_f1)
        self._hk_timer.start(80)

        # 업타임 타이머
        self._tick_timer = QTimer()
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(1000)

    # ── UI 빌드 ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 20, 20, 20)

        # 타이틀
        t = QLabel("Planet-투명도형 v2")
        t.setObjectName("title")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(t)

        sub = QLabel("제작자: @kdk15351  |  서버인증 제거 빌드")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)

        # 상태
        self.status_label = QLabel("대기 중")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setProperty("state", "idle")
        root.addWidget(self.status_label)

        # 통계 카드
        card = QFrame(); card.setObjectName("card")
        row = QHBoxLayout(card); row.setContentsMargins(20, 14, 20, 14)
        for attr, label in [("uptime_value", "작동 시간"), ("capcha_value", "거탐 횟수")]:
            col = QVBoxLayout(); col.setSpacing(2)
            lbl = QLabel(label); lbl.setObjectName("stat")
            val = QLabel("--:--:--" if "uptime" in attr else "0")
            val.setObjectName("stat_value")
            setattr(self, attr, val)
            col.addWidget(lbl); col.addWidget(val)
            row.addLayout(col)
        root.addWidget(card)

        # 옵션
        opt_card = QFrame(); opt_card.setObjectName("card")
        opt = QVBoxLayout(opt_card); opt.setContentsMargins(16, 12, 16, 12)
        self.chk_gpu   = QCheckBox("GPU 사용 (Vulkan, fp32)")
        self.chk_sound = QCheckBox("소리 알람 (도형찾기 감지 시)")
        self.chk_sound.setChecked(True)
        opt.addWidget(self.chk_gpu)
        opt.addWidget(self.chk_sound)
        root.addWidget(opt_card)

        # 텔레그램 (UI 유지, 기능은 선택)
        tg_card = QFrame(); tg_card.setObjectName("card")
        tg = QVBoxLayout(tg_card); tg.setContentsMargins(16, 12, 16, 12)
        tg_hdr = QLabel("📨 텔레그램 알람"); tg_hdr.setObjectName("section")
        self.chk_tg = QCheckBox("켜기 (도형찾기 감지 시 캡쳐 전송)")
        self.tg_token   = QLineEdit(); self.tg_token.setPlaceholderText("봇 토큰 (예: 123456:ABC...)")
        self.tg_chat    = QLineEdit(); self.tg_chat.setPlaceholderText("Chat ID (예: 123456789)")
        tg.addWidget(tg_hdr); tg.addWidget(self.chk_tg)
        tg.addWidget(self.tg_token); tg.addWidget(self.tg_chat)
        root.addWidget(tg_card)

        # 미리보기 버튼
        btn_preview = QPushButton("🔍 감지 영역 미리보기")
        btn_preview.setObjectName("preview_btn")
        btn_preview.setFixedHeight(32)
        btn_preview.setStyleSheet(
            "QPushButton { background: rgba(40,48,60,220); color:#8B95A1; "
            "border:1px solid rgba(255,255,255,15); border-radius:10px; "
            "font-size:11px; }"
            "QPushButton:hover { color:#FFFFFF; border-color:rgba(255,255,255,40); }"
        )
        btn_preview.clicked.connect(self._open_preview)
        root.addWidget(btn_preview)

        # 토글 버튼
        self.toggle_btn = QPushButton("▶  시작  (F1)")
        self.toggle_btn.setObjectName("toggle")
        self.toggle_btn.setProperty("state", "idle")
        self.toggle_btn.clicked.connect(self.on_toggle)
        root.addWidget(self.toggle_btn)

        # 로그
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(400)
        root.addWidget(self.log)

    # ── 핫키 폴링 ──────────────────────────────────────────────────────────
    def _poll_f1(self):
        if win32api.GetAsyncKeyState(0x70) & 0x8000:  # VK_F1
            self.on_toggle()
            # 연속 토글 방지 — 키 올라올 때까지 대기
            for _ in range(20):
                time.sleep(0.05)
                if not (win32api.GetAsyncKeyState(0x70) & 0x8000):
                    break

    # ── 시작/정지 ──────────────────────────────────────────────────────────
    def on_toggle(self):
        if self._is_running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._is_running = True
        self.toggle_btn.setEnabled(False)
        self.log.clear()
        self._macro = _MacroThread(
            self._sig,
            use_gpu=self.chk_gpu.isChecked(),
            sound=self.chk_sound.isChecked(),
            tg_enabled=self.chk_tg.isChecked(),
            tg_token=self.tg_token.text().strip(),
            tg_chat=self.tg_chat.text().strip(),
        )
        self._macro.start()

    def _stop(self):
        if self._macro:
            self._macro.stop()

    # ── 상태 핸들러 ────────────────────────────────────────────────────────
    def _on_status(self, status: str):
        if status == "running":
            self._start_time = time.time()
            self.status_label.setText("자동 중")
            self.status_label.setProperty("state", "running")
            self.toggle_btn.setText("■  정지  (F1)")
            self.toggle_btn.setProperty("state", "running")
            self.toggle_btn.setEnabled(True)
        elif status == "stopped":
            self._is_running = False
            self._start_time = None
            self.status_label.setText("대기 중")
            self.status_label.setProperty("state", "idle")
            self.toggle_btn.setText("▶  시작  (F1)")
            self.toggle_btn.setProperty("state", "idle")
            self.toggle_btn.setEnabled(True)
        elif status.startswith("error:"):
            self._is_running = False
            msg = status[6:]
            self.status_label.setText(f"오류: {msg}")
            self.status_label.setProperty("state", "error")
            self.toggle_btn.setText("▶  시작  (F1)")
            self.toggle_btn.setProperty("state", "idle")
            self.toggle_btn.setEnabled(True)
        self._refresh_style()

    def _refresh_style(self):
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

    def _open_preview(self) -> None:
        if self._preview_win is None:
            self._preview_win = PreviewWindow()
        self._preview_win.show()
        self._preview_win.raise_()
        self._preview_win.activateWindow()

    def _on_preview(self, frame) -> None:
        if self._preview_win is not None and self._preview_win.isVisible():
            self._preview_win.update_frame(frame)

    def _append_log(self, msg: str):
        self.log.appendPlainText(msg)

    def _tick(self):
        if self._start_time is None:
            return
        s = int(time.time() - self._start_time)
        h, r = divmod(s, 3600); m, sec = divmod(r, 60)
        self.uptime_value.setText(f"{h:02d}:{m:02d}:{sec:02d}")

    def _save_config(self):
        cfg = {
            "use_gpu":    self.chk_gpu.isChecked(),
            "sound":      self.chk_sound.isChecked(),
            "tg_enabled": self.chk_tg.isChecked(),
            "tg_token":   self.tg_token.text().strip(),
            "tg_chat":    self.tg_chat.text().strip(),
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_config(self):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            self.chk_gpu.setChecked(cfg.get("use_gpu", False))
            self.chk_sound.setChecked(cfg.get("sound", True))
            self.chk_tg.setChecked(cfg.get("tg_enabled", False))
            self.tg_token.setText(cfg.get("tg_token", ""))
            self.tg_chat.setText(cfg.get("tg_chat", ""))
        except Exception:
            pass  # 파일 없으면 기본값 유지

    def closeEvent(self, ev):
        self._save_config()
        if self._macro:
            self._macro.stop()
        if self._preview_win:
            self._preview_win.close()
        self._hk_timer.stop()
        self._tick_timer.stop()
        super().closeEvent(ev)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = MainUI()
    ui.show()
    sys.exit(app.exec())
