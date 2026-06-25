# planet_solver_noauth.py — Planet_solver v2 GUI (서버인증/라이선스 제거, 탐지엔진 자체 탑재)
"""
Planet_solver_v1.0.5.exe 의 GUI/UX를 그대로 유지하되:
  - LicenseDialog / fetch_secure_code / inject_into_macro 완전 제거
  - 탐지 엔진: planet_yolo_verify.py (M1Ensemble + HyungYolo, ncnn)
  - 마우스: PostMessage 백그라운드 클릭
  - 창 자동 탐지: win32gui (board_roi.json 불필요)
  - 해상도 강제: 1920×1080
  - 단축키: F1 시작/자동 일시정지·재개, F3 녹화 정지/종료

실행: python planet_solver_noauth.py
"""
from __future__ import annotations

import collections, ctypes, json, os, sys, threading, time, winsound
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
VIT_MODEL_PATH = os.path.join(ROOT, "models", "transparent", "vittrack.onnx")
# 적응형 2단 임계 (투명도형 YOLO) — 모든 후보에 점프 게이트, 확실한 것만 강 등급
SHAPE_STRONG_THR = 0.50   # 진단 로그의 '강N' 표기용
SHAPE_PICK_THR   = 0.30   # 선택 후보 필터 — 노이즈 제거용. 반투명 타겟(score~0.47)을
                          #   제외 안 하도록 0.3 (0.5면 약해진 타겟 빠져 데칼로 갈아탐)
SHAPE_SCORE_W   = 60.0    # 선택 결합 점수의 score 가중(px/score) — 예측거리−λ·score, 오프라인 최적
SHAPE_WEAK_THR   = 0.10   # 약 후보 하한 — 비상관화 모델은 배경 FP 1%라 0.1까지 안전(게이트 내 한정)
SHAPE_WEAK_GATE  = 110    # 점프 게이트 기본 반경(px) — 도형은 ~2px/frame이라 순간 점프는 가짜
SHAPE_GATE_GROW  = 12     # 미검출 1프레임당 게이트 확장(px) — 오래 놓치면 점점 넓게 재탐색
SHAPE_GATE_MAX   = 280    # 게이트 확장 상한(px)
SHAPE_BG_REJECT  = 12     # 배경동조 판정 반경(px) — 후보가 '직전위치+배경변위'(=배경 따라
                          #   흘러온 데칼)에서 이 거리 이상이면 '배경과 다른 움직임'(비동조=타겟 후보)
SHAPE_PRED_GATE  = 30     # ID 추적 예측위치 게이트(px) — 좁게 잡아 같은 객체만 연결(데칼 튐 방지)
SHAPE_PRED_GROW  = 8      # 미검출 1프레임당 예측 게이트 확장(px) — 놓치면 점점 넓게 재포착
SHAPE_JUMP_CAP   = 15     # 한 프레임 점프 상한(직전속도 위 여유, px) — 초과는 갈아타기로 거부
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
from core.vision.vit_shape_tracker import VitShapeTracker, acquire_white
from core.shape_yolo import ShapeYolo
from core.vision.byte_tracker import ByteTracker
from core.vision.shape_classifier import ShapeClassifier
from core.vision.transparent_puzzle_engine import (
    PuzzleEngineInput,
    TransparentPuzzleEngine,
    candidate_from_live_row,
)
from core.vision.transparent_box_selector import TransparentBoxSelector
from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime
from core.vision.transparent_live_family_pool import TransparentLiveFamilyPool
from core.vision.transparent_selector_shadow import TransparentSelectorShadow
from core.vision.transparent_track_health import TransparentTrackHealthSelector
from core.vision.transparent_visual_rescue import TransparentVisualRescueTracker
from core.vision.tracking_alert import should_emit_tracking_alert

# 흰색 단계 분류 모양 → 추적 최적 전문 검출기(GT 검증: 별→star, 나머지→circle).
# 모양별 전문은 '그 모양 특화'가 아니라 모델별 분포 민감도 — circle이 범용 강세.
_SHAPE2MODEL = {"star": "star", "square": "circle",
                "circle": "circle", "triangle": "circle"}

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

def _detect_cursor(bgr):
    """화면 마우스 커서(핑크) 중심 검출 — GetCursorPos가 게임 가로챔으로 부정확하므로
    실제 표시되는 커서 위치를 색으로 직접 인지(det 좌표). 없으면 None."""
    try:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        m = cv2.inRange(hsv, np.array([140, 80, 80]), np.array([175, 255, 255]))
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        c = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(c) < 15:
            return None
        M = cv2.moments(c)
        if M["m00"] == 0:
            return None
        return (M["m10"] / M["m00"], M["m01"] / M["m00"])
    except Exception:
        return None

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
                 tg_enabled: bool = False, tg_token: str = "", tg_chat: str = "",
                 reacq: bool = False):
        super().__init__(daemon=True)
        self._sig      = sig
        self._gpu      = use_gpu
        self._sound    = sound
        self._tg       = tg_enabled and bool(tg_token) and bool(tg_chat)
        self._tg_token = tg_token
        self._tg_chat  = tg_chat
        self._reacq    = reacq   # 턴 재획득(orphan re-acquisition) — A/B 실험용 토글
        self._stop     = threading.Event()
        self._auto     = threading.Event(); self._auto.set()  # 자동(마우스) 제어 on. clear=일시정지(캡처·녹화는 유지)
        self._stop_rec = threading.Event()                    # 녹화 즉시 마감 신호(수동 정지 버튼)

    def stop(self):
        self._stop.set()

    def pause_auto(self):
        self._auto.clear()

    def resume_auto(self):
        self._auto.set()

    def stop_recording(self):
        self._stop_rec.set()

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

        # ViT 추적기 로드 — 투명 도형 추적 본체. 실패 시 추적 비활성(팝업 감지만)
        try:
            _vit = VitShapeTracker(VIT_MODEL_PATH)
            self._sig.log.emit("[*] ViT 추적기 로드 완료")
        except Exception as e:
            _vit = None
            self._sig.log.emit(f"[!] ViT 추적기 로드 실패: {e} → 추적 비활성")

        # YOLO 주 검출기 — 직접 학습한 모델(models/shape_yolo.param/.bin) 있으면 우선 사용
        try:
            _syolo = ShapeYolo()
            if _syolo.enabled:
                self._sig.log.emit("[*] ShapeYolo 로드 완료 — YOLO 주 검출 활성 (ViT는 폴백)")
            else:
                self._sig.log.emit("[*] ShapeYolo 모델 없음 — ViT 추적만 사용")
        except Exception as e:
            _syolo = None
            self._sig.log.emit(f"[!] ShapeYolo 로드 실패: {e} → ViT 추적만 사용")

        # 모양별 전문 검출기 — 한 판=한 모양. 흰색 단계에서 모양 판별 후 그 전문 모델로
        # 투명 단계 검출(검출율↑ — GT 062325 통합72%→circle89%). 없으면 통합 _syolo 폴백.
        _syolo_shapes = {}
        for _sh in ("circle", "triangle", "square", "star"):
            try:
                _sy = ShapeYolo(
                    param_path=os.path.join(ROOT, "models", f"shape_yolo_{_sh}.param"),
                    bin_path=os.path.join(ROOT, "models", f"shape_yolo_{_sh}.bin"))
                if _sy.enabled:
                    _syolo_shapes[_sh] = _sy
            except Exception:
                pass
        if _syolo_shapes:
            self._sig.log.emit(
                f"[*] 모양별 전문 검출기 {len(_syolo_shapes)}개 로드: {list(_syolo_shapes)}")
        # 모양 분류기(YOLO-cls ncnn) — 흰색 도형 crop을 4모양 분류, 검출 score보다 정확.
        _cls_dir = os.path.join(ROOT, "models", "shape_cls_ncnn_model")
        _shape_cls = ShapeClassifier(
            os.path.join(_cls_dir, "model.ncnn.param"),
            os.path.join(_cls_dir, "model.ncnn.bin"))
        if _shape_cls.enabled:
            self._sig.log.emit("[*] 모양 분류기(shape_cls) 로드 완료")

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
            try:
                _enforce_res(hwnd)                       # 1920×1080 강제(실패해도 계속)
            except Exception as _ee:
                self._sig.log.emit(
                    f"[!] 창 크기 자동조정 실패({_ee}) — 게임이 관리자 권한이면 창 조작이 막힙니다. "
                    f"게임 해상도를 직접 1920×1080으로 맞추거나, 이 프로그램을 관리자 권한으로 실행하세요. "
                    f"현재 창 크기로 계속 진행합니다.")
            bx, by, bw, bh = _client_roi(hwnd)
        self._sig.log.emit(f"[좌표] {bx},{by}  {bw}×{bh}")
        self._sig.status.emit("running")

        success = 0
        tracking = False
        popup_logged = False         # 팝업 감지 첫 로그 중복 방지
        _vit_active = False          # 현재 팝업에 대해 ViT 추적기가 초기화됐는지
        _last_marker_pos = (0, 0)    # 직전 프레임 도형 중심 (det 내 좌표) — 미리보기/클릭용
        _miss_run = 0                # YOLO 연속 미검출 카운트 (직전 위치 유지·게이트 확장용)
        _diag_cnt = 0                # YOLO 검출 진단 로그 카운터
        _white_prev = None           # 흰색 잠금 안정화(2프레임 연속 동일 위치) 비교용
        _tvx = _tvy = 0.0            # 추적 속도 EMA — 교차(겹침) 시 데칼 갈아타기 방지용 예측
        _prev_gray = None           # 직전 프레임 gray(배경 변위 측정용)
        _bgx = _bgy = 0.0           # 배경 전역 변위(phaseCorrelate) — 투명 단계 배경동조 데칼 거부
        _bt = ByteTracker(reacq=self._reacq)   # ByteTrack MOT(+턴 재획득 토글)
        _boxsel = TransparentBoxSelector()
        _healthsel = TransparentTrackHealthSelector()
        _visual_rescue = TransparentVisualRescueTracker()
        _transparent_engine = TransparentPuzzleEngine()
        _live_family_pool = TransparentLiveFamilyPool()
        _family_selector = TransparentFamilySelectorRuntime()
        _selector_shadow = TransparentSelectorShadow(
            _family_selector,
            clip_id="live",
            window=24,
            min_frames=8,
            emit_every=10,
            max_candidates=8,
        )
        self._sig.log.emit(f"[설정] 턴 재획득(re-acq) {'ON' if self._reacq else 'OFF'}")
        self._sig.log.emit("[setting] transparent box selector ON")
        self._sig.log.emit("[setting] transparent puzzle engine shadow ON")
        if _family_selector.available:
            self._sig.log.emit("[setting] GT-free family selector model loaded")
            self._sig.log.emit("[setting] GT-free family selector shadow log ON")
        else:
            self._sig.log.emit(f"[setting] GT-free family selector disabled: {_family_selector.load_error}")
        _vortex = None
        _idea6 = None
        _target_shape = None        # 흰색 단계 판별된 타겟 모양(이후 전문 검출기 사용)
        _shape_votes = {}           # 흰색 단계 분류기 투표(3프레임 다수결로 모양 확정)
        _shape_cnt = 0              # 흰색 단계 분류 프레임 수
        # 검출 모델: 판별 전엔 흰색 누적 1위(없으면 첫 전문가), 판별 후 그 전문가. 통합 미사용.
        _syolo_active = (next(iter(_syolo_shapes.values()))
                         if _syolo_shapes else _syolo)
        _cursor_off_x = _cursor_off_y = 0.0   # 게임 좌표 오프셋(핑크 커서 검출로 학습)
        _trace_buf = collections.deque(maxlen=90)  # 점진 표류→멈춤 진단용 궤적 ring buffer
        _stall_dumped = False        # 멈춤 궤적 덤프 중복 방지(판당 1회)
        _drift_last = -999           # 마지막 점진표류 덤프 프레임(쿨다운용)
        _rec_writer = None           # 판 전 구간 녹화 VideoWriter (흰색 잠금~팝업 종료)
        _rec_jf = None               # 판 궤적 jsonl 파일 핸들
        _rec_size = None             # 녹화 프레임 크기 (w,h) — VideoWriter.get()은 0이라 직접 보관
        _rec_png_dir = None          # 무손실 PNG 프레임 폴더(압축 없음 — ⑥/광류 검증용)
        _rec_fi = 0                  # PNG 프레임 인덱스
        TRACK_INTERVAL = 0.05        # 추적 루프 주기 (20fps)
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
                    # 수동 '녹화 정지' 신호 — 즉시 녹화 마감(스레드·캡처는 계속)
                    if self._stop_rec.is_set():
                        self._stop_rec.clear()
                        if _rec_writer is not None:
                            try:
                                _rec_writer.release(); _rec_jf.close()
                                self._sig.log.emit("[녹화종료] 수동 정지 — 영상 저장됨")
                            except Exception:
                                pass
                            _rec_writer = None; _rec_jf = None; _rec_png_dir = None
                    # 60회마다 좌표 갱신
                    if preview_cnt % 60 == 0 and preview_cnt > 0:
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
                            _vit_active = False
                            _last_marker_pos = (0, 0)
                            _miss_run = 0
                            _white_prev = None
                            _tvx = _tvy = 0.0
                            _bt.reset()             # 다음 판 위해 MOT 트랙 초기화
                            _boxsel.reset()
                            _healthsel.reset()
                            _visual_rescue.reset()
                            _transparent_engine.reset()
                            _live_family_pool.reset()
                            _selector_shadow.reset(clip_id="live")
                            _target_shape = None    # 다음 판 모양 재판별
                            _shape_votes = {}
                            _shape_cnt = 0
                            _syolo_active = (next(iter(_syolo_shapes.values()))
                                             if _syolo_shapes else _syolo)
                            success += 1
                            self._sig.capcha.emit(success % 100, success)
                            # 판 종료 — 녹화 마감
                            if _rec_writer is not None:
                                try:
                                    _rec_writer.release()
                                    _rec_jf.close()
                                    self._sig.log.emit("[녹화종료] 판 완료 — 영상 저장됨")
                                except Exception:
                                    pass
                                _rec_writer = None
                                _rec_jf = None
                                _rec_png_dir = None
                                _stall_dumped = False
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

                    # ── 팝업 첫 감지 → 게임 창 포그라운드 1회 ────────────────
                    if not popup_logged:
                        popup_logged = True
                        self._sig.log.emit(
                            f"[팝업 감지] HDR score={hdr_score:.2f} (임계값 0.65 초과) "
                            f"→ ViT 추적 시작"
                        )
                        _focus_game(hwnd)  # 게임 창 포그라운드 (1회)

                    # DET(퍼즐 해제 구역) 캡처
                    det_mon = {
                        "left":   bx + int(bw * DET_X1_R),
                        "top":    by + int(bh * DET_Y1_R),
                        "width":  int(bw * (DET_X2_R - DET_X1_R)),
                        "height": int(bh * (DET_Y2_R - DET_Y1_R)),
                    }
                    det = cv2.cvtColor(np.array(sct.grab(det_mon)), cv2.COLOR_BGRA2BGR)
                    _dh, _dw = det.shape[:2]

                    # 커서 제거 — 우리 마우스가 도형 위에 있으면 ViT가 커서를 쫓음. 매 프레임 inpaint
                    det_masked = det
                    _cmask_res = None   # 잔차 검출용 소형 커서 마스크(커서 실크기) — 대형 inpaint 원을 쓰면 도형 림까지 가려짐
                    try:
                        _mcx, _mcy = win32api.GetCursorPos()
                        _mrx = _mcx - det_mon["left"]
                        _mry = _mcy - det_mon["top"]
                        if 0 <= _mrx < _dw and 0 <= _mry < _dh:
                            _cr = max(20, int(min(_dw, _dh) * 0.05))
                            _cmask = np.zeros((_dh, _dw), dtype=np.uint8)
                            cv2.circle(_cmask, (_mrx, _mry), _cr, 255, -1)
                            det_masked = cv2.inpaint(det, _cmask, 5, cv2.INPAINT_TELEA)
                            _crr = max(14, int(min(_dw, _dh) * 0.03))
                            _cmask_res = np.zeros((_dh, _dw), dtype=np.uint8)
                            cv2.circle(_cmask_res, (_mrx, _mry), _crr, 255, -1)
                    except Exception:
                        det_masked = det
                        _cmask_res = None

                    # 배경 전역 변위(phaseCorrelate) — 데칼 다수가 지배하므로 배경 흐름 측정.
                    # 투명 단계에서 '배경 따라 흘러온' 후보(데칼)를 거부하는 데 쓴다.
                    _cur_gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
                    if _prev_gray is not None and _prev_gray.shape == _cur_gray.shape:
                        (_bgx, _bgy), _ = cv2.phaseCorrelate(_prev_gray, _cur_gray)
                    else:
                        _bgx = _bgy = 0.0
                    _prev_gray = _cur_gray

                    # ── 추적: YOLO 주 검출 (학습 모델 있으면) / 없으면 ViT 폴백 ──────
                    track_pos = None        # (cx, cy) in det 좌표 — 클릭/미리보기용
                    _cands = []             # YOLO 후보 (미리보기 박스 표시용)
                    _engine_out = None      # 새 투명 퍼즐 엔진 shadow 결과
                    if _syolo is not None and _syolo.enabled:
                        # 전부검출(v3) 체제 — 모델은 글라스 도형을 타겟·배경 구분 없이 다 잡는다.
                        # 시작: 흰색 도형(시작 시 유일하게 밝음)으로 잠금. 이후: 직전 위치
                        # 최근접 + 점프 게이트(연속성)만으로 추적 — 오프라인 투명후기 99%.
                        # 커서가 타겟을 정통으로 덮으면(우리가 커서로 도형을 쫓으니 늘 그럼)
                        # 원본 det 검출은 score 0.02로 미검출 → 데칼로 갈아탐. 작은 커서
                        # 마스크(14px)로 inpaint하면 타겟이 score 0.6+로 복원(큰 23px는 도형까지 지움).
                        if _cmask_res is not None:
                            det_detect = cv2.inpaint(det, _cmask_res, 5, cv2.INPAINT_TELEA)
                        else:
                            det_detect = det
                        _det_model = _syolo_active if _syolo_active is not None else _syolo
                        _cands = _det_model.detect_all(det_detect, score_thr=SHAPE_WEAK_THR)
                        _strong = [c for c in _cands if c[2] >= SHAPE_STRONG_THR]  # 진단 표기용
                        _pick = [c for c in _cands if c[2] >= SHAPE_PICK_THR]      # 진단 표기용
                        _dets = [(c[0], c[1], c[2]) for c in _cands]   # ByteTracker 입력
                        _via_white = False   # 이번 프레임 선택이 흰색(밝기) 추적인지
                        _bg_rejected = False # 타겟 트랙 소실(coast 한계) 여부
                        _box_mode = None
                        _box_innov = 0.0
                        # 흰색 도형 검출(밝기). 잠금용 ≥20, 가시 보정용 ≥50.
                        _wb = acquire_white(det_masked)
                        _wc = None
                        if _wb is not None and _wb[2] >= 20:
                            _wc = (_wb[0] + _wb[2] / 2.0, _wb[1] + _wb[3] / 2.0)
                        _engine_white = None
                        try:
                            _engine_white = (
                                _wc if (_wb is not None and _wb[2] >= 50 and _wb[3] >= 50)
                                else None
                            )
                            _engine_out = _transparent_engine.update(PuzzleEngineInput(
                                frame_index=preview_cnt,
                                candidates=[candidate_from_live_row(c) for c in _cands if len(c) >= 5],
                                white_anchor=_engine_white,
                                gray_frame=_cur_gray,
                            ))
                        except Exception as _eng_exc:
                            _engine_out = None
                            if _diag_cnt % 60 == 0:
                                self._sig.log.emit(f"[engine-shadow-error] {_eng_exc}")
                        # 흰색이 크게(≥50) 보이고 잠금 타겟 근처면 밝기 위치로 보정(흰색 우선).
                        # 흰색 단계는 밝기 GT가 완벽 — ByteTracker 타겟 트랙을 그 위치로 끌어준다.
                        if (_bt.locked and _wc is not None
                                and _wb[2] >= 50 and _wb[3] >= 50):
                            _tg = next((t for t in _bt._tracks if t.tid == _bt._tid), None)
                            if _tg is not None and ((_wc[0] - _tg.x) ** 2
                                                    + (_wc[1] - _tg.y) ** 2) <= 35 ** 2:
                                _bt.nudge(_wc[0], _wc[1])
                                _via_white = True
                        # 모양 판별 — 흰색 단계 매 프레임 4 전문가 score 누적, 누적 1위 모델로
                        # 다음 프레임 검출(통합 미사용, 단일 프레임은 박빙이라 누적). 흰색 소실 시 확정.
                        # 모양 판별 — 흰색 도형 crop을 분류기로 4모양 분류(검출 score보다
                        # 정확, 세모/네모도 구분). 3프레임 다수결 확정 → 추적 최적 전문 검출기.
                        # 흰색 active는 첫 전문가 고정(매프레임 교체는 트랙 혼란), 확정 후 교체.
                        if _target_shape is None and _shape_cls.enabled and _syolo_shapes:
                            if _wb is not None and _wb[2] >= 50 and _wc is not None:
                                _x0 = max(0, _wb[0] - 10); _y0 = max(0, _wb[1] - 10)
                                _x1 = min(_dw, _wb[0] + _wb[2] + 10)
                                _y1 = min(_dh, _wb[1] + _wb[3] + 10)
                                _sh, _sc = _shape_cls.classify(det[_y0:_y1, _x0:_x1])
                                if _sh is not None:
                                    _shape_votes[_sh] = _shape_votes.get(_sh, 0) + 1
                                    _shape_cnt += 1
                                    if _shape_cnt >= 3:    # 3프레임 다수결 → 모양 확정
                                        _target_shape = max(_shape_votes,
                                                            key=_shape_votes.get)
                                        _mdl = _SHAPE2MODEL.get(_target_shape, "circle")
                                        _syolo_active = _syolo_shapes.get(_mdl, _syolo)
                                        self._sig.log.emit(
                                            f"[모양확정] {_target_shape} → {_mdl} 검출기 "
                                            f"{dict(_shape_votes)}")
                        # ByteTrack MOT — 모든 후보 ID 트랙 + 2단계 association + 배경 이상탐지
                        _pos = _bt.update(_cur_gray, _dets)
                        if not _bt.locked:
                            # 흰색 잠금 — 2프레임 연속 같은 위치(팝업 플래시 오인 방지)
                            if _wc is not None:
                                if (_white_prev is not None and
                                        (_wc[0] - _white_prev[0]) ** 2
                                        + (_wc[1] - _white_prev[1]) ** 2 <= 15 ** 2):
                                    _bt.lock(_wc[0], _wc[1])
                                    _boxsel.reset(_wc)
                                    _healthsel.reset(_wc)
                                    _transparent_engine.reset()
                                    _live_family_pool.reset()
                                    track_pos = _wc
                                    tracking = True
                                    self._sig.log.emit(
                                        f"[잠금] 흰색 도형 ({int(_wc[0])},{int(_wc[1])}) → 추적 시작")
                                    # 이 판 전 구간 녹화 시작(영상+궤적)
                                    try:
                                        _rc_dir = os.path.join(ROOT, "_record_debug")
                                        os.makedirs(_rc_dir, exist_ok=True)
                                        _stamp = time.strftime("%m%d_%H%M%S")
                                        _live_family_pool.reset()
                                        _selector_shadow.reset(clip_id=f"{success:03d}_{_stamp}")
                                        _rc_base = os.path.join(_rc_dir, f"{success:03d}_{_stamp}")
                                        _rec_size = (det.shape[1], det.shape[0])
                                        _rec_writer = cv2.VideoWriter(
                                            _rc_base + ".mp4",
                                            cv2.VideoWriter_fourcc(*"mp4v"),
                                            20.0, _rec_size)
                                        _rec_jf = open(_rc_base + ".jsonl", "w", encoding="utf-8")
                                        # 무손실 PNG 프레임 폴더(압축 없음 — 라이브와 동일 품질)
                                        _rec_png_dir = _rc_base + "_png"
                                        os.makedirs(_rec_png_dir, exist_ok=True)
                                        _rec_fi = 0
                                        self._sig.log.emit(f"[녹화시작] _record_debug/{success:03d}_{_stamp} (+무손실PNG)")
                                    except Exception:
                                        _rec_writer = None
                                        _rec_jf = None
                                        _rec_png_dir = None
                                _white_prev = _wc
                        else:
                            # 잠금됨: 흰색 우선(밝기) / ByteTracker ID 추적 / 소실
                            if _via_white:
                                track_pos = _wc
                                tracking = True
                            elif _pos is not None:
                                track_pos = (_pos[0], _pos[1])
                                tracking = True
                            else:
                                _bg_rejected = True   # 타겟 트랙 lost(coast 한계 초과)
                            # vortex 모드 — 투명 단계는 ByteTrack 대신 광류 소용돌이로 추적.
                            # 백색(밝기 보임)이면 그 위치로 잠금, 아니면 소용돌이 추적.
                            if _vortex is not None:
                                _gray_u8 = cv2.cvtColor(det_detect, cv2.COLOR_BGR2GRAY)
                                # 백색 핸드오프(ByteTrack과 분리) — 큰 흰색이 vortex 중심
                                # 근처면 밝기 우선(백색 단계). 아니면 투명 vortex.
                                _wcen = None
                                if (_wc is not None and _wb is not None
                                        and _wb[2] >= 50 and _wb[3] >= 50
                                        and _vortex.locked
                                        and (_wc[0]-_vortex.center[0]) ** 2
                                        + (_wc[1]-_vortex.center[1]) ** 2 <= 60 ** 2):
                                    _wcen = _wc
                                _vpos = _vortex.update(_gray_u8, white_center=_wcen)
                                if _vpos is not None:
                                    track_pos = _vpos
                                    tracking = True
                                    _via_white = (_wcen is not None)   # 명시적 재판정
                                    _via_vortex = (_wcen is None)
                            # ⑥ 주기차분 모드 — 투명 단계는 frame[t]−frame[t−T] 잔차 peak로 추적.
                            if _idea6 is not None:
                                _gray_i6 = cv2.cvtColor(det_detect, cv2.COLOR_BGR2GRAY)
                                _wcen6 = None     # 백색 핸드오프(큰 흰색이 ⑥ 중심 근처면 밝기 우선)
                                if (_wc is not None and _wb is not None
                                        and _wb[2] >= 50 and _wb[3] >= 50
                                        and _idea6.locked
                                        and (_wc[0]-_idea6.center[0]) ** 2
                                        + (_wc[1]-_idea6.center[1]) ** 2 <= 60 ** 2):
                                    _wcen6 = _wc
                                _ipos = _idea6.update(_gray_i6, white_center=_wcen6)
                                if _ipos is not None:
                                    track_pos = _ipos
                                    tracking = True
                                    _via_white = (_wcen6 is not None)
                                    _via_idea6 = (_wcen6 is None)
                        # 진단/트레이스/캡처 호환 — 타겟 트랙에서 속도·miss 동기화
                        _tg = next((t for t in _bt._tracks if t.tid == _bt._tid), None)
                        if _tg is not None:
                            _tvx, _tvy = _tg.vx, _tg.vy
                            _miss_run = _tg.miss
                        _pre_box_pos = track_pos
                        _box_dec = None
                        _health_dec = None
                        _visual_dec = None
                        _live_family_dec = None
                        if track_pos is not None:
                            _box_dec = _boxsel.update(
                                _cands, track_pos,
                                force_fallback=_via_white)
                        elif _bt.locked:
                            _box_dec = _boxsel.update(_cands, None)
                        if _box_dec is not None:
                            track_pos = _box_dec.point
                            tracking = True
                            _box_mode = _box_dec.mode
                            _box_innov = _box_dec.innovation
                        _health_rescue = None
                        _health_rescue_source = None
                        try:
                            _visual_dec = _visual_rescue.update(
                                _cur_gray,
                                _cands,
                                white_anchor=_engine_white,
                                track_point=track_pos,
                            )
                            if _visual_dec.available and _visual_dec.point is not None:
                                _health_rescue = _visual_dec.point
                                _health_rescue_source = "visual"
                        except Exception as _vis_exc:
                            _visual_dec = None
                            if _diag_cnt % 60 == 0:
                                self._sig.log.emit(f"[visual-rescue-error] {_vis_exc}")
                        if (_engine_out is not None and _engine_out.x is not None
                                and _engine_out.y is not None
                                and _health_rescue is None):
                            _health_rescue = (_engine_out.x, _engine_out.y)
                            _health_rescue_source = "engine"
                        if track_pos is not None or _health_rescue is not None:
                            _health_dec = _healthsel.update(
                                primary=track_pos,
                                rescue=_health_rescue,
                                frame_shape=det.shape[:2],
                                force_primary=_via_white,
                            )
                            if _health_dec.point is not None:
                                if _health_dec.source == "rescue":
                                    _boxsel.reset(_health_dec.point)
                                    if _bt.locked:
                                        _bt.nudge(_health_dec.point[0], _health_dec.point[1])
                                track_pos = _health_dec.point
                                tracking = True
                        try:
                            _live_family_dec = _live_family_pool.update(
                                preview_cnt,
                                candidates=_cands,
                                gray_frame=_cur_gray,
                                white_anchor=_engine_white,
                            )
                        except Exception as _fam_exc:
                            _live_family_dec = None
                            if _diag_cnt % 60 == 0:
                                self._sig.log.emit(f"[live-family-error] {_fam_exc}")
                        _selector_shadow_rec = None
                        try:
                            _shadow_anchors = {}
                            if _live_family_dec is not None:
                                for _family, _point in _live_family_dec.points.items():
                                    _shadow_anchors[_family] = _point
                            if _pre_box_pos is not None:
                                _shadow_anchors["panel_default_center_mild_state_mild"] = _pre_box_pos
                            if _box_dec is not None and track_pos is not None:
                                _shadow_anchors["balanced_viterbi_center_mild_state_mild"] = track_pos
                            if (_engine_out is not None and _engine_out.x is not None
                                    and _engine_out.y is not None):
                                _shadow_anchors["phase_catalog_center_mild_state_mild"] = (
                                    _engine_out.x, _engine_out.y)
                            if _shadow_anchors:
                                _selector_shadow_rec = _selector_shadow.update(
                                    preview_cnt,
                                    candidates=_cands,
                                    anchors=_shadow_anchors,
                                )
                        except Exception as _sel_exc:
                            _selector_shadow_rec = {
                                "clip": "live",
                                "frame": preview_cnt,
                                "available": False,
                                "error": str(_sel_exc),
                            }
                            if _diag_cnt % 60 == 0:
                                self._sig.log.emit(f"[selector-shadow-error] {_sel_exc}")
                        # 트랙 급감 진단 — 잠금 후 트랙이 5개 미만이면 후보 수와 함께 기록
                        # (후보 많은데 트랙 적으면 _bt 버그, 후보도 적으면 검출 공백)
                        if _bt.locked and _bt.track_count < 5:
                            self._sig.log.emit(
                                f"[트랙급감] 후보{len(_dets)}개(전체{len(_cands)}) "
                                f"트랙{_bt.track_count} miss={_miss_run}")
                        _diag_cnt += 1
                        if _diag_cnt % 15 == 0:
                            _tp = None if track_pos is None else (int(track_pos[0]), int(track_pos[1]))
                            _src = ("흰색" if _via_white
                                    else ("ByteTrack" if track_pos is not None
                                          else ("소실" if _bt.locked else "잠금대기")))
                            _health_src = "-" if _health_dec is None else _health_dec.reason
                            _rescue_src = "-" if _health_rescue_source is None else _health_rescue_source
                            self._sig.log.emit(
                                f"[진단] 후보{len(_cands)}개(강{len(_strong)}) 트랙{_bt.track_count} "
                                f"miss={_miss_run} → track={_tp} ({_src}) "
                                f"box={_box_mode or '-'}:{_box_innov:.0f} "
                                f"health={_health_src} rescue={_rescue_src}")
                            if _selector_shadow_rec and _selector_shadow_rec.get("available"):
                                self._sig.log.emit(
                                    f"[selector-shadow] {_selector_shadow_rec.get('family')} "
                                    f"point={_selector_shadow_rec.get('point')} "
                                    f"rows={_selector_shadow_rec.get('rows')}")
                        # 점진 표류 진단: 매 프레임 궤적 기록 + 멈춤(track 소실) 시 직전 90프레임 덤프
                        _frame_rec = {
                            "i": preview_cnt,
                            "track": (None if track_pos is None
                                      else [int(track_pos[0]), int(track_pos[1])]),
                            "vel": [round(_tvx, 1), round(_tvy, 1)],
                            "miss": _miss_run,
                            "n": len(_cands),
                            "box": (None if _box_mode is None
                                    else {"mode": _box_mode,
                                          "innov": round(_box_innov, 1)}),
                            "health": (None if _health_dec is None
                                       else {"source": _health_dec.source,
                                             "reason": _health_dec.reason,
                                             "unhealthy": _health_dec.unhealthy,
                                             "suspect": _health_dec.suspect_frames,
                                             "hold": _health_dec.rescue_hold,
                                             "err": round(_health_dec.primary_error, 1),
                                             "oob": _health_dec.out_of_bounds}),
                            "visual": (None if _visual_dec is None
                                       else {"available": _visual_dec.available,
                                             "source": _visual_dec.source,
                                             "period": _visual_dec.period,
                                             "best": round(_visual_dec.visual_best, 1),
                                             "point": (None if _visual_dec.point is None
                                                       else [int(_visual_dec.point[0]),
                                                             int(_visual_dec.point[1])])}),
                            "engine": (None if _engine_out is None
                                       else {"track": (None if _engine_out.x is None
                                                       else [int(_engine_out.x), int(_engine_out.y)]),
                                              "confidence": round(_engine_out.confidence, 2),
                                              "candidate": _engine_out.candidate_index,
                                              "state": _engine_out.state}),
                            "live_family": (None if _live_family_dec is None
                                            else {"points": {
                                                _name: [int(_pt[0]), int(_pt[1])]
                                                for _name, _pt in _live_family_dec.points.items()
                                            },
                                                  "debug": dict(_live_family_dec.debug)}),
                            "selector_shadow": _selector_shadow_rec,
                            "cands": [[int(c[0]), int(c[1]), round(c[2], 2),
                                       int(c[3]), int(c[4])] for c in _cands],
                        }
                        _trace_buf.append(_frame_rec)
                        # 판 전 구간 녹화 — 영상 프레임 + 궤적 한 줄
                        if _rec_writer is not None:
                            try:
                                _wf = det
                                if (det.shape[1], det.shape[0]) != _rec_size:
                                    _wf = cv2.resize(det, _rec_size)
                                _rec_writer.write(_wf)
                                # 무손실 PNG 프레임(라이브 동일 품질 — ⑥/광류 검증)
                                if _rec_png_dir is not None:
                                    cv2.imwrite(os.path.join(_rec_png_dir, f"f{_rec_fi:04d}.png"), _wf)
                                    _rec_fi += 1
                                _rec_jf.write(json.dumps(_frame_rec, ensure_ascii=False) + "\n")
                                _rec_jf.flush()
                            except Exception as _re:
                                self._sig.log.emit(f"[녹화오류] {_re}")
                        if _miss_run == 16 and not _stall_dumped:
                            _stall_dumped = True
                            try:
                                _st_dir = os.path.join(ROOT, "_stall_debug")
                                os.makedirs(_st_dir, exist_ok=True)
                                _ts = f"{success:03d}_{preview_cnt:05d}"
                                cv2.imwrite(os.path.join(_st_dir, f"{_ts}.png"), det)
                                with open(os.path.join(_st_dir, f"{_ts}.json"),
                                          "w", encoding="utf-8") as _jf:
                                    json.dump(list(_trace_buf), _jf, ensure_ascii=False)
                                self._sig.log.emit(
                                    f"[멈춤캡처] track 소실 → _stall_debug/{_ts} (직전 {len(_trace_buf)}프레임)")
                            except Exception:
                                pass
                        elif _miss_run == 0:
                            _stall_dumped = False   # 재획득 시 다음 멈춤도 잡도록 리셋
                        # 점진 표류 감지 — 최근 8프레임 track이 '한 방향'으로 누적 이동
                        # (데칼로 매 프레임 조금씩 흘러감). 멈춤도 급점프도 아닌 갈아타기 패턴.
                        if (track_pos is not None and len(_trace_buf) >= 9
                                and preview_cnt - _drift_last > 40):
                            _pts = [t["track"] for t in list(_trace_buf)[-9:]
                                    if t["track"] is not None]
                            if len(_pts) >= 9:
                                _cum = sum(((_pts[k + 1][0] - _pts[k][0]) ** 2
                                            + (_pts[k + 1][1] - _pts[k][1]) ** 2) ** 0.5
                                           for k in range(len(_pts) - 1))
                                _net = ((_pts[-1][0] - _pts[0][0]) ** 2
                                        + (_pts[-1][1] - _pts[0][1]) ** 2) ** 0.5
                                # 누적 크고 + 직선성 높음(왕복 아닌 한 방향) = 표류
                                if _cum > 50 and _net > 40 and _net > _cum * 0.7:
                                    _drift_last = preview_cnt
                                    try:
                                        _dr_dir = os.path.join(ROOT, "_drift_debug")
                                        os.makedirs(_dr_dir, exist_ok=True)
                                        _ts = f"{success:03d}_{preview_cnt:05d}"
                                        cv2.imwrite(os.path.join(_dr_dir, f"{_ts}.png"), det)
                                        with open(os.path.join(_dr_dir, f"{_ts}.json"),
                                                  "w", encoding="utf-8") as _jf:
                                            json.dump(list(_trace_buf), _jf, ensure_ascii=False)
                                        self._sig.log.emit(
                                            f"[표류캡처] 8프레임 {_net:.0f}px 한방향 이동 "
                                            f"→ _drift_debug/{_ts}")
                                    except Exception:
                                        pass
                    elif _vit is not None:
                        # YOLO 모델 없을 때만 기존 ViT 경로 (회귀 방지)
                        if not _vit_active:
                            _bbox = acquire_white(det_masked)
                            if _bbox is not None and _bbox[2] >= 20:
                                _vit.init(det_masked, _bbox)
                                _vit_active = True
                                tracking = True
                                track_pos = (_bbox[0] + _bbox[2] / 2,
                                             _bbox[1] + _bbox[3] / 2)
                                self._sig.log.emit(f"[ViT] 흰색 락온 bbox={_bbox} → 추적 시작")
                        else:
                            _tcx, _tcy, _tsc, _tacc = _vit.update(det_masked, _cmask_res, det)
                            track_pos = (_tcx, _tcy)
                            if _vit.needs_reacquire():
                                _bbox = acquire_white(det_masked)
                                if _bbox is not None and _bbox[2] >= 20:
                                    _vit.init(det_masked, _bbox)
                                    self._sig.log.emit(f"[ViT] 재획득 — acquire_white bbox={_bbox}")

                    # ── 갈아타기 순간 자동 캡처 (디버그) — track 급점프 시 데이터 저장 ──
                    if (track_pos is not None and _last_marker_pos != (0, 0)
                            and _syolo is not None and _syolo.enabled):
                        _jump = ((track_pos[0] - _last_marker_pos[0]) ** 2
                                 + (track_pos[1] - _last_marker_pos[1]) ** 2) ** 0.5
                        if _jump > 30:   # 30px+ 점프 = 이탈 의심(점진 이탈 45px도 포착)
                            try:
                                _sw_dir = os.path.join(ROOT, "_switch_debug")
                                os.makedirs(_sw_dir, exist_ok=True)
                                _ts = f"{success:03d}_{preview_cnt:05d}"
                                cv2.imwrite(os.path.join(_sw_dir, f"{_ts}.png"), det)
                                _meta = {
                                    "jump_px": round(_jump, 1),
                                    "from": [int(_last_marker_pos[0]), int(_last_marker_pos[1])],
                                    "to": [int(track_pos[0]), int(track_pos[1])],
                                    "vel": [round(_tvx, 1), round(_tvy, 1)],
                                    "cands": [[int(c[0]), int(c[1]), round(c[2], 2),
                                               int(c[3]), int(c[4])]
                                              for c in _cands],
                                }
                                with open(os.path.join(_sw_dir, f"{_ts}.json"),
                                          "w", encoding="utf-8") as _jf:
                                    json.dump(_meta, _jf, ensure_ascii=False)
                                self._sig.log.emit(
                                    f"[갈아타기캡처] {_jump:.0f}px 점프 → _switch_debug/{_ts}")
                            except Exception:
                                pass

                    # ── 마우스 이동(클릭) + 상태 로그 ────────────────────────
                    if track_pos is not None:
                        cx = int(max(0, min(det_mon["width"] - 1, track_pos[0])))
                        cy = int(max(0, min(det_mon["height"] - 1, track_pos[1])))
                        _last_marker_pos = (cx, cy)
                        # 화면 실제 커서(핑크) 검출 → 게임 좌표 오프셋 학습(GetCursorPos는
                        # 게임 가로챔으로 부정확). 목표(도형중심 cx,cy)와 실제 커서 위치 차이를
                        # 누적 오프셋에 EMA 반영 → 마우스를 도형 중심으로 끌어온다(±200 발산한계).
                        # 자동 일시정지(F1) 시엔 마우스 제어 건너뜀 — 캡처·녹화만 계속(수동 플레이 녹화)
                        if self._auto.is_set():
                            _cur = _detect_cursor(det)
                            if _cur is not None:
                                _cursor_off_x += (cx - _cur[0]) * 0.5
                                _cursor_off_y += (cy - _cur[1]) * 0.5
                                _cursor_off_x = max(-200.0, min(200.0, _cursor_off_x))
                                _cursor_off_y = max(-200.0, min(200.0, _cursor_off_y))
                            abs_x = det_mon["left"] + int(cx + _cursor_off_x)
                            abs_y = det_mon["top"]  + int(cy + _cursor_off_y)
                            _real_click(abs_x, abs_y)

                        if should_emit_tracking_alert(
                                self._auto.is_set(), tracking, preview_cnt):
                            self._sig.log.emit(f"[추적중] pos=({abs_x},{abs_y})")
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
                        # 초록색: YOLO 검출 박스 전부 표시 (det → popup 좌표 변환)
                        # 채택된 후보=굵은 밝은 초록+score, 나머지=얇은 초록 (어디를 잡는지 가시화)
                        for _ycx, _ycy, _ysc, _yw, _yh in _cands:
                            _x1 = _det_lx + int(_ycx - _yw / 2)
                            _y1 = _det_ly + int(_ycy - _yh / 2)
                            _x2 = _det_lx + int(_ycx + _yw / 2)
                            _y2 = _det_ly + int(_ycy + _yh / 2)
                            _sel = (track_pos is not None and (
                                    (abs(_ycx - track_pos[0]) < 2
                                     and abs(_ycy - track_pos[1]) < 2)
                                    or (_ycx - _yw / 2 <= track_pos[0] <= _ycx + _yw / 2
                                        and _ycy - _yh / 2 <= track_pos[1] <= _ycy + _yh / 2)))
                            _col = (0, 255, 80) if _sel else (0, 190, 0)
                            cv2.rectangle(vis, (_x1, _y1), (_x2, _y2),
                                          _col, 2 if _sel else 1)
                            cv2.putText(vis, f"{_ysc:.2f}", (_x1, _y1 - 3),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                                        _col, 1, cv2.LINE_AA)
                        # 추적 위치 십자 마커
                        if track_pos is not None:
                            mcx = _det_lx + int(track_pos[0])
                            mcy = _det_ly + int(track_pos[1])
                            cv2.drawMarker(vis, (mcx, mcy),
                                           (0, 255, 80), cv2.MARKER_CROSS, 22, 2)
                            _eng = ("YOLO" if (_syolo is not None and _syolo.enabled)
                                    else ("ViT" if _vit_active else "WAIT"))
                            cv2.putText(vis, _eng,
                                        (_det_lx + 4, _det_ry - 6),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        0.4, (255, 220, 0), 1, cv2.LINE_AA)
                        self._sig.preview.emit(vis)

                    # 추적 중: TRACK_INTERVAL(0.05s=20fps), 대기 중: 60fps
                    time.sleep(TRACK_INTERVAL if tracking else 0.016)

                except Exception as e:
                    self._sig.log.emit(f"[!] {e}")
                    time.sleep(0.5)

        # 스레드 종료 — 녹화 중이던 판 안전 마감(사용자 중지 시 영상 보존)
        if _rec_writer is not None:
            try:
                _rec_writer.release()
                _rec_jf.close()
            except Exception:
                pass
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
        self._auto_on = True              # 자동(마우스) 제어 on 여부 (F1로 토글)
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

        # 토글 버튼 (F1) — 자동(마우스) 시작 / 일시정지·재개. 녹화는 유지
        self.toggle_btn = QPushButton("▶  시작  (F1)")
        self.toggle_btn.setObjectName("toggle")
        self.toggle_btn.setProperty("state", "idle")
        self.toggle_btn.clicked.connect(self.on_toggle)
        root.addWidget(self.toggle_btn)

        # 녹화 정지/종료 버튼 — 녹화 마감 + 프로그램 완전 종료 (F1과 분리)
        self.rec_stop_btn = QPushButton("⏹  녹화 정지 / 종료  (F3)")
        self.rec_stop_btn.setStyleSheet(
            "QPushButton { background: rgba(60,40,46,220); color:#FF9BA3; "
            "border:1px solid rgba(255,120,130,40); border-radius:10px; font-size:12px; }"
            "QPushButton:hover { color:#FFFFFF; border-color:rgba(255,120,130,90); }"
            "QPushButton:disabled { color:#5A6068; border-color:rgba(255,255,255,12); }"
        )
        self.rec_stop_btn.setEnabled(False)
        self.rec_stop_btn.clicked.connect(self.on_rec_stop)
        root.addWidget(self.rec_stop_btn)

        # 로그
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(400)
        root.addWidget(self.log)

    # ── 핫키 폴링 ──────────────────────────────────────────────────────────
    def _poll_f1(self):
        if win32api.GetAsyncKeyState(0x70) & 0x8000:  # VK_F1 — 시작/자동 일시정지·재개
            self.on_toggle()
            # 연속 토글 방지 — 키 올라올 때까지 대기
            for _ in range(20):
                time.sleep(0.05)
                if not (win32api.GetAsyncKeyState(0x70) & 0x8000):
                    break
        if win32api.GetAsyncKeyState(0x72) & 0x8000:  # VK_F3 — 녹화 정지/종료
            if self._is_running:
                self.on_rec_stop()
            for _ in range(20):
                time.sleep(0.05)
                if not (win32api.GetAsyncKeyState(0x72) & 0x8000):
                    break

    # ── 시작 / 자동 일시정지·재개 (F1) ─────────────────────────────────────
    def on_toggle(self):
        if not self._is_running:
            self._start()                       # 대기 → 시작(자동 on)
        elif self._auto_on:
            # 실행 중 → 자동(마우스) 일시정지. 캡처·녹화는 계속(수동 플레이 녹화)
            if self._macro:
                self._macro.pause_auto()
            self._auto_on = False
            self.status_label.setText("자동 멈춤 (녹화중)")
            self.toggle_btn.setText("▶  자동 재개  (F1)")
        else:
            # 일시정지 → 자동 재개
            if self._macro:
                self._macro.resume_auto()
            self._auto_on = True
            self.status_label.setText("자동 중")
            self.toggle_btn.setText("■  자동 정지  (F1)")

    # ── 녹화 정지 + 완전 종료 (F1과 분리된 별도 버튼) ──────────────────────
    def on_rec_stop(self):
        if self._macro:
            self._macro.stop_recording()        # 녹화 즉시 마감
            self._macro.stop()                  # 스레드 완전 종료 → 대기

    def _start(self):
        self._is_running = True
        self._auto_on = True
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
            self._auto_on = True
            self.status_label.setText("자동 중")
            self.status_label.setProperty("state", "running")
            self.toggle_btn.setText("■  자동 정지  (F1)")
            self.toggle_btn.setProperty("state", "running")
            self.toggle_btn.setEnabled(True)
            self.rec_stop_btn.setEnabled(True)
        elif status == "stopped":
            self._is_running = False
            self._auto_on = True
            self.rec_stop_btn.setEnabled(False)
            self._start_time = None
            self.status_label.setText("대기 중")
            self.status_label.setProperty("state", "idle")
            self.toggle_btn.setText("▶  시작  (F1)")
            self.toggle_btn.setProperty("state", "idle")
            self.toggle_btn.setEnabled(True)
        elif status.startswith("error:"):
            self._is_running = False
            self._auto_on = True
            self.rec_stop_btn.setEnabled(False)
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
    # 관리자 권한 자동 요청 — 게임 관리자 실행 시 봇도 관리자여야 핫키 인게임 동작(UIPI)
    from core.admin_util import ensure_admin
    ensure_admin()
    app = QApplication(sys.argv)
    ui = MainUI()
    ui.show()
    sys.exit(app.exec())
