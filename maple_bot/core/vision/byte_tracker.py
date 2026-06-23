# 투명 도형 ByteTrack 경량 MOT — 2단계 헝가리안 association으로 약검출 타겟 ID 유지 + 배경 공통속도 이상탐지
from __future__ import annotations

import os
import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

BT_GATE         = 30     # 예측위치 매칭 게이트 기본(px)
BT_GATE_GROW    = 8      # 미검출 1프레임당 게이트 확장(px)
BT_GATE_MAX     = 280    # 게이트 상한(px)
BT_JUMP_CAP     = 30     # 타겟 점프 상한(직전속도 위 여유, px) — 빠른 도형 매칭 위해 30
                         #   (GT 채점: 15→30으로 035137 평균오차 186→80px)
BT_REL_MIN      = 7.0    # 배경과 다른 속도 임계(px/f) — 흐림 재선택(이상탐지)
BT_REL_EMA      = 0.3    # rel_ema 현재반영 비율 — 다중가설 누적 증거(클수록 즉각)
BT_BG_REJECT    = 20     # 타겟 매칭 배경동조 거부(px) — 예측보다 배경흐름에 가까우면 데칼
                         #   (모양별 전문 검출은 후보 2배 → 데칼 매칭↑, 거부 강화로 배제.
                         #    GT 062325(circle): 12→20으로 51→25px, 이탈 0)
BT_HOLD_JUMP    = 15     # 점프 보류 임계 — 매칭이 직전속도+이 값 초과 점프면 데칼 의심
BT_HOLD_SCORE   = 0.40   # 약검출 임계 — 점프+이 score 미만이면 즉시 갈아타지 않고 coast
BT_HIGH_THR     = 0.30   # 1단계 high score
BT_LOW_THR      = 0.10   # 2단계 low score 하한(반투명 타겟 0.18이 여기서 ID 유지)
BT_LOST_MAX     = 15     # 타겟 lost coast 유지 한계(프레임)
BT_TRK_MISS_MAX = 10     # 비타겟 트랙 제거 전 허용 미매칭
BT_DECAL_N      = 3      # 배경 계산에 쓸 대표 데칼 수(age 큰 상위 N개 — 전부 불필요)
BT_DECAL_AGE    = 3      # 배경 중앙값에 넣을 데칼 최소 age

# 호모그래피 강체위반 약한 사전(hviol) — 데칼 점구름에 RANSAC 호모그래피 정합 후 각 트랙
# 재투영오차=강체위반. 데칼은 배경정렬돼 ~0, 타겟만 큼(검출점 7x, 픽셀무관). 단독 최대화는
# 스푸리어스 데칼에 발산하므로, 타겟 lost 시 공간게이트 내 '흐림 재선택' 랭킹에만 약하게 주입.
BT_VIOL_EMA   = 0.3   # viol_ema 현재반영 비율(누적 증거)
BT_VIOL_MIN   = 6.0   # 재선택 풀 위반 하한(px) — 미만은 배경동조 데칼
BT_VIOL_PAIRS = 8     # 호모그래피 추정 최소 데칼 대응쌍

# rel-bg 이상도 복구(relrec) — 갈아타기 락아웃 해제. 타겟이 데칼로 새면 트랙 rel_ema(배경
# 대비 속도차)가 낮아지고, 진짜 타겟은 배경과 달라 rel_ema 높음(035137 타겟25 vs 데칼15 측정).
# 현재 타겟보다 rel_ema가 마진 이상 큰 근처 트랙이 K프레임 지속되면 점프상한 우회 ID전환.
# 자기게이팅(더 이질적인 것으로만) — 단 타겟이 배경동행인 판에선 멀쩡한 타겟 이탈 위험 → 토글 격리.
BT_RELREC_MARGIN = 7.0    # 근처 트랙 순간 rel이 현재 타겟보다 이만큼 커야 후보
BT_RELREC_MIN    = 16.0   # 후보 순간 rel 절대 하한(노이즈 단발 방지)
BT_RELREC_R      = 100.0  # 복구 탐색 반경(px) — 반대로 멀어지는 진짜 타겟 도달용
BT_RELREC_HOLD   = 2      # 같은 후보 연속 프레임 확정(1~2 지연 허용)
BT_RELREC_AGE    = 2      # 후보 최소 age(순간 vel 안정 — 새 트랙 age0은 vel=0)

# CMC(전역 운동 보상) — 회전 배경을 어파인(회전+균일스케일+이동)으로 모델링.
# 단일 이동 벡터(데칼 속도 중앙값)는 회전장에서 무의미 → 안정화 좌표계 잔차로 타겟 판별.
BT_CMC_MIN_PAIRS  = 6     # 데칼 대응쌍 최소(미만이면 ORB 폴백)
BT_CMC_INLIER     = 0.5   # RANSAC inlier 비율 하한(미만이면 ORB 폴백)
BT_CMC_MAX_DTHETA = 0.20  # 프레임당 회전각 상한(rad) — 초과 시 reject+coast
BT_CMC_RANSAC_T   = 3.0   # RANSAC 재투영 임계(px)
BT_CMC_OMEGA_EMA  = 0.2   # 각속도 ω EMA 반영비
BT_CMC_ORB_N      = 400   # ORB 특징점 수

# occlusion(겹침) 3-state 상태머신 — NMS가 같은-모양 박스를 IoU>0.45(중심거리 floor~14px,
# 측정 확증)에서 한 박스로 뭉침. 흡수 구간엔 검출이 타겟인지 데칼인지 구분 불가 → 검출 무관
# 무조건 coast(v_pre)로 통과해 '겹침 후 갈아타기' 차단. 중심거리 히스테리시스(IoU 불필요).
BT_OCC_ENTER = 14    # 흡수 진입(px) = NMS floor. 근방 데칼이 검출 잃고 이 거리내면 흡수
BT_OCC_EXIT  = 25    # 분리(px). 타겟 예측 근방 제2후보 재출현 = split (히스테리시스 갭 11px)
BT_OCC_NPRE  = 5     # v_pre 평균낼 직전 프레임 수(진입 직전 한 프레임 동조 오염 방지)
BT_OCC_MAX   = 10    # OCCLUDING 최대 지속(≤BT_TRK_MISS_MAX, 초과 시 강제 종료)

# orphan 재출현 재획득 — 턴 오매칭(타겟이 꺾이며 트랙이 옛방향 데칼로 샘) 복구.
# 과거연속성 신호(rel/검출지지/v_pre)는 턴에서 전부 죽음(측정) → '페이드 자리에서 새로
# 태어나 강해지는' 미래신호로 재획득. 공간(anchor)×시간(지속) 이중게이트로 271px 방지.
BT_REACQ_N          = 5    # anchor = 타겟 트랙 위치 N프레임 전(N3 오염·N8 stale, 측정상 5 최적)
BT_REACQ_ANCHOR_MAX = 100  # anchor 최근접 orphan 게이트(px) — 회복56~96 통과/데칼>200 거부
BT_REACQ_AGE        = 4    # orphan young 상한(데칼 지속이라 age 큼 → 컬링)
BT_REACQ_SCORE      = 0.6  # orphan 강검출 하한
BT_REACQ_HOLD       = 3    # 같은 orphan 연속 프레임 확정(단발 far 강검출 발동불가 = 271px 방지)
BT_REACQ_MIN_SEP    = 50   # orphan이 현재 타겟서 이만큼 떨어져야 발동(옆 데칼 오발 차단)
                           #   035137 진짜재출현은 새는트랙서 72~96px / 백색단계 오발은 ~0px
BT_REACQ_NUDGE_GAP  = 5    # 마지막 nudge(백색추적) 후 이만큼 지나야 발동 — 백색단계 오발 차단
                           #   (백색은 밝기추적이 정확, re-acq 불필요. 투명전환 후에만 작동)
BT_REACQ_TGT_NEAR   = 50   # 현재 타겟이 anchor서 이 안일 때만 발동(트랙 갇힘=샘/스톨 신호).
                           #   035137 새는트랙 anchor 31~35px / 정상판은 steady 이동해 멀어짐


class _BTrack:
    __slots__ = ("tid", "x", "y", "vx", "vy", "score", "age", "miss", "rel_ema", "viol_ema")

    def __init__(self, tid, x, y, score):
        self.tid = tid
        self.x = float(x); self.y = float(y)
        self.vx = 0.0; self.vy = 0.0
        self.score = float(score)
        self.age = 0; self.miss = 0
        self.rel_ema = 0.0   # 배경과 다른 정도의 누적 EMA(다중가설 채택 근거)
        self.viol_ema = 0.0  # 호모그래피 강체위반 누적 EMA(hviol — 검출점 7x 신호)


class ByteTracker:
    """ByteTrack 경량 MOT — 2단계 헝가리안 association + 배경 공통속도 이상탐지.
    흰색 잠금 타겟에 ID 부여, 모든 후보를 트랙으로 추적, 약검출(반투명 타겟)도
    2단계 매칭으로 ID 유지. 타겟 흐림 시 배경과 다른 속도 트랙으로 ID 승계."""

    def __init__(self, cmc: bool = False, occl: bool = False, reacq: bool = False,
                 hviol: bool = False, relrec: bool = False):
        # cmc=False(기본)면 어파인 보상 일체 비활성 → 원본 ByteTrack 좌표계(속도차) 판별로
        # 완전 복귀. CMC는 단일 스위치 뒤 격리(부분 켜짐 상태 없음). 실험은 CMC_ON=1 env.
        self._cmc_on = bool(cmc) or os.environ.get("CMC_ON") == "1"
        # occl=False(기본)면 occlusion 상태머신 일체 비활성 → IDLE 경로(baseline)만.
        # 측정상 035137 지배실패는 occlusion 아닌 '턴 오매칭'이라 주력에서 내림. VOT 진짜
        # 겹침 대비 격리 보관(삭제 아님). 실험은 OCCL_ON=1 env.
        self._occ_on = bool(occl) or os.environ.get("OCCL_ON") == "1"
        # reacq=False(기본)면 재획득 비활성. 턴 오매칭 복구 주력(035137). 실험은 REACQ_ON=1.
        self._reacq_on = bool(reacq) or os.environ.get("REACQ_ON") == "1"
        # hviol=False(기본)면 호모그래피 위반 약한사전 비활성(원본 rel_ema 재선택). 실험은 HVIOL_ON=1.
        self._hviol_on = bool(hviol) or os.environ.get("HVIOL_ON") == "1"
        # relrec=False(기본)면 rel-bg 이상도 복구 비활성. 갈아타기 락아웃 해제. 실험은 RELREC_ON=1.
        self._relrec_on = bool(relrec) or os.environ.get("RELREC_ON") == "1"
        self._relrec_tid = None   # 복구 후보 트랙 tid(지속 확정용)
        self._relrec_cnt = 0      # 그 후보가 마진 우세로 연속된 프레임 수
        self._prev = None
        self._tracks: list[_BTrack] = []
        self._tid = None
        self._next = 0
        self._bgvx = 0.0; self._bgvy = 0.0
        self._H = None         # 현재 프레임 어파인(2×3, 직전→현재)
        self._H_last = None    # 마지막 정상 H(coast용)
        self._omega = 0.0      # 등속회전 각속도 EMA(rad/frame)
        self._cx = 0.0; self._cy = 0.0   # 외삽 회전 중심(프레임 중심)
        self._orb = None       # ORB 검출기(지연 생성)
        # occlusion 상태머신
        self._state = "IDLE"   # IDLE / OCCLUDING / SEPARATING
        self._occ_ids = set()  # 흡수에 연루된 데칼 tid(컬링 면제 + 분리 시 후보 한정)
        self._vpre = (0.0, 0.0)  # OCCLUDING 진입 시 스냅샷한 타겟 속도(coast 방향)
        self._vhist = []       # 최근 타겟 속도 이력(v_pre 평균용)
        self._occ_cnt = 0      # OCCLUDING 지속 프레임
        self._near_prev = {}   # 직전 프레임 타겟 근방(검출됨) 데칼 tid→위치(흡수 감지용)
        # orphan 재획득
        self._anchor_hist = []  # 타겟 트랙 위치 이력(anchor = N프레임 전)
        self._reacq_tid = None  # 재획득 후보 orphan tid(지속 확정용)
        self._reacq_cnt = 0     # 그 후보가 anchor 최근접으로 연속된 프레임 수
        self._nudge_age = 999   # 마지막 nudge(백색추적) 후 경과 프레임(백색 중 re-acq 차단)

    def reset(self):
        self._prev = None; self._tracks = []; self._tid = None
        self._next = 0; self._bgvx = 0.0; self._bgvy = 0.0
        self._H = None; self._H_last = None; self._omega = 0.0
        self._cx = 0.0; self._cy = 0.0
        self._state = "IDLE"; self._occ_ids = set(); self._vpre = (0.0, 0.0)
        self._vhist = []; self._occ_cnt = 0; self._near_prev = {}
        self._anchor_hist = []; self._reacq_tid = None; self._reacq_cnt = 0
        self._nudge_age = 999
        self._relrec_tid = None; self._relrec_cnt = 0

    @property
    def locked(self):
        return self._tid is not None

    @property
    def bg_vel(self):
        return (self._bgvx, self._bgvy)

    @property
    def track_count(self):
        return len(self._tracks)

    def _new(self, x, y, score):
        t = _BTrack(self._next, x, y, score)
        self._next += 1
        self._tracks.append(t)
        return t

    def lock(self, x, y):
        """흰색 위치 최근접 트랙을 타겟으로 지정(없으면 생성). 간헐 표시 시 재확정."""
        best, bd = None, BT_GATE * BT_GATE
        for t in self._tracks:
            d = (t.x - x) ** 2 + (t.y - y) ** 2
            if d < bd:
                bd = d; best = t
        if best is None:
            best = self._new(x, y, 1.0)
        self._tid = best.tid

    def nudge(self, x, y):
        """흰색 가시 구간 — 타겟 트랙 위치를 밝기 중심으로 보정 + 운동(속도) 반영.
        흰색이 움직이면 그 속도를 타겟 트랙 vx,vy에 EMA로 누적 → 투명 전환 순간
        운동 방향이 끊기지 않아 진짜 도형을 이어간다(흰색 정지면 vx≈0 유지)."""
        self._nudge_age = 0   # 백색 추적 중 — re-acq 차단(투명 전환 후에만 작동)
        for t in self._tracks:
            if t.tid == self._tid:
                t.vx = t.vx * 0.6 + (x - t.x) * 0.4
                t.vy = t.vy * 0.6 + (y - t.y) * 0.4
                t.x = float(x); t.y = float(y); t.miss = 0
                return

    def _match(self, tracks, dets, bx, by):
        """예측위치 중심거리 헝가리안. 반환: (matches[(ti,di)], 미매칭트랙idx, 미매칭det idx)."""
        if not tracks or not dets:
            return [], list(range(len(tracks))), list(range(len(dets)))
        cost = np.full((len(tracks), len(dets)), 1e6, dtype=np.float64)
        for i, t in enumerate(tracks):
            if t.age > 0:
                px, py = t.x + t.vx, t.y + t.vy
            else:
                px, py = t.x + bx, t.y + by
            gate = min(BT_GATE_MAX, BT_GATE + BT_GATE_GROW * t.miss)
            if t.tid == self._tid:   # 타겟은 점프 상한 게이트로 갈아타기 차단
                spd = (t.vx * t.vx + t.vy * t.vy) ** 0.5
                gate = min(gate, spd + BT_JUMP_CAP)
            g2 = gate * gate
            for j, d in enumerate(dets):
                dd = (d[0] - px) ** 2 + (d[1] - py) ** 2
                if dd <= g2:
                    cost[i, j] = dd ** 0.5
        rows, cols = linear_sum_assignment(cost)
        matches = []
        ut = set(range(len(tracks))); ud = set(range(len(dets)))
        for r, c in zip(rows, cols):
            if cost[r, c] < 1e6:
                matches.append((r, c)); ut.discard(r); ud.discard(c)
        return matches, sorted(ut), sorted(ud)

    def _apply(self, t, d):
        t.vx = t.vx * 0.6 + (d[0] - t.x) * 0.4
        t.vy = t.vy * 0.6 + (d[1] - t.y) * 0.4
        t.x = float(d[0]); t.y = float(d[1]); t.score = float(d[2])
        t.age += 1; t.miss = 0

    def _warp(self, x, y, bx, by):
        """배경 예측 위치 = 어파인 H(직전→현재)로 점 워핑. H 없으면 이동 폴백(x+bx, y+by)."""
        H = self._H
        if H is None:
            return x + bx, y + by
        return (H[0, 0] * x + H[0, 1] * y + H[0, 2],
                H[1, 0] * x + H[1, 1] * y + H[1, 2])

    @staticmethod
    def _sane(M):
        """추정 어파인의 프레임당 회전각이 물리적 범위 내인지."""
        if M is None:
            return False, 0.0
        dtheta = float(np.arctan2(M[1, 0], M[0, 0]))
        return (abs(dtheta) <= BT_CMC_MAX_DTHETA), dtheta

    def _estimate_cmc(self, prev_pos, prev_gray, cur_gray):
        """전역 운동 보상 어파인 H(직전→현재) 추정. 3단 폴백: 데칼 대응쌍 → ORB → ω 외삽.
        prev_pos: {tid:(x,y)} 프레임 시작 스냅샷. 회전하는 배경을 강체 유사변환(4DOF)으로 모델."""
        # 1) 데칼 대응쌍(비타겟, 이번 프레임 매칭됨, age>=2)
        src = []; dst = []
        for t in self._tracks:
            if (t.tid != self._tid and t.miss == 0 and t.age >= 2
                    and t.tid in prev_pos):
                src.append(prev_pos[t.tid]); dst.append((t.x, t.y))
        if len(src) >= BT_CMC_MIN_PAIRS:
            M, inl = cv2.estimateAffinePartial2D(
                np.float32(src), np.float32(dst),
                method=cv2.RANSAC, ransacReprojThreshold=BT_CMC_RANSAC_T)
            ratio = float(inl.mean()) if inl is not None else 0.0
            ok, dtheta = self._sane(M)
            if M is not None and ratio >= BT_CMC_INLIER and ok:
                self._accept(M, dtheta); return "decal"

        # 2) ORB 폴백 — 데칼 부족/품질 저하 시(겹침 구간) gray 특징점으로 어파인
        if prev_gray is not None and cur_gray is not None:
            M = self._orb_affine(prev_gray, cur_gray)
            ok, dtheta = self._sane(M)
            if M is not None and ok:
                self._accept(M, dtheta); return "orb"

        # 3) 등속회전 ω 외삽 — 둘 다 실패. 직전 H의 이동분 보존 + ω 회전. coast.
        if abs(self._omega) > 1e-4 and (cur_gray is not None or self._H_last is not None):
            R = cv2.getRotationMatrix2D((self._cx, self._cy),
                                        -np.degrees(self._omega), 1.0)
            if self._H_last is not None:
                R[0, 2] += self._H_last[0, 2]; R[1, 2] += self._H_last[1, 2]
            self._H = R; return "omega"

        # 폴백 불가 → H 없음(이동 보상으로 복귀)
        self._H = self._H_last
        return "none"

    def _accept(self, M, dtheta):
        M = M.astype(np.float64)
        if os.environ.get("CMC_TRANS") == "1":
            # 길 B — 어파인을 프레임 중심 이동량으로 투영(회전/스케일 제거, 순수 병진 2DOF)
            tx = M[0, 0] * self._cx + M[0, 1] * self._cy + M[0, 2] - self._cx
            ty = M[1, 0] * self._cx + M[1, 1] * self._cy + M[1, 2] - self._cy
            M = np.array([[1.0, 0.0, tx], [0.0, 1.0, ty]], dtype=np.float64)
            dtheta = 0.0
        self._H = M
        self._H_last = self._H
        self._omega = self._omega * (1 - BT_CMC_OMEGA_EMA) + dtheta * BT_CMC_OMEGA_EMA
        self._last_dtheta = dtheta

    def _orb_affine(self, prev_gray, cur_gray):
        """직전/현재 gray ORB 매칭 → RANSAC 어파인. 특징점 부족/매칭 부족 시 None."""
        try:
            if self._orb is None:
                self._orb = cv2.ORB_create(BT_CMC_ORB_N)
            p8 = prev_gray.astype(np.uint8); c8 = cur_gray.astype(np.uint8)
            k1, d1 = self._orb.detectAndCompute(p8, None)
            k2, d2 = self._orb.detectAndCompute(c8, None)
            if d1 is None or d2 is None or len(k1) < BT_CMC_MIN_PAIRS:
                return None
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(d1, d2)
            if len(matches) < BT_CMC_MIN_PAIRS:
                return None
            src = np.float32([k1[m.queryIdx].pt for m in matches])
            dst = np.float32([k2[m.trainIdx].pt for m in matches])
            M, _ = cv2.estimateAffinePartial2D(
                src, dst, method=cv2.RANSAC, ransacReprojThreshold=BT_CMC_RANSAC_T)
            return M
        except Exception:
            return None

    def _homography_viol(self, prev_pos):
        """배경 데칼 대응쌍(직전→현재)에 RANSAC 호모그래피 → 각 트랙 재투영오차=강체위반.
        데칼은 배경정렬돼 ~0, 타겟은 큰 위반(검출점 기반, 픽셀/희미함 무관). {tid: 위반px}."""
        src = []; dst = []; ids = []
        for t in self._tracks:
            pp = prev_pos.get(t.tid)
            if pp is None:
                continue
            ids.append((t.tid, pp, (t.x, t.y)))
            if t.tid != self._tid and t.miss == 0 and t.age >= 2:
                src.append(pp); dst.append((t.x, t.y))
        if len(src) < BT_VIOL_PAIRS:
            return {}
        try:
            H, _ = cv2.findHomography(np.float32(src).reshape(-1, 1, 2),
                                      np.float32(dst).reshape(-1, 1, 2),
                                      cv2.RANSAC, 4.0)
        except cv2.error:
            return {}
        if H is None:
            return {}
        pts = np.float32([pp for _, pp, _ in ids]).reshape(-1, 1, 2)
        proj = cv2.perspectiveTransform(pts, H).reshape(-1, 2)
        return {ids[k][0]: float(np.hypot(proj[k, 0] - ids[k][2][0],
                                          proj[k, 1] - ids[k][2][1]))
                for k in range(len(ids))}

    def update(self, gray_f32, dets):
        """매 프레임. dets=[(cx,cy,score),...]. 타겟 트랙 위치 (x,y)|None 반환.
        gray_f32=None이면 phaseCorrelate 생략(jsonl 재시뮬용)."""
        self._nudge_age += 1   # 마지막 nudge(백색) 후 경과 — re-acq 백색 차단용
        # 타겟 직전 상태 보관(배경동조 매칭 검증용)
        _tg0 = next((t for t in self._tracks if t.tid == self._tid), None)
        _tg0_state = (_tg0.x, _tg0.y, _tg0.vx, _tg0.vy) if _tg0 is not None else None

        # CMC용 직전 스냅샷 — 각 트랙의 직전 위치(어파인 대응쌍·잔차) + 직전 gray(ORB)
        prev_pos = {t.tid: (t.x, t.y) for t in self._tracks}
        prev_gray = self._prev

        # 배경 전역 변위(폴백용)
        bx = by = 0.0
        if (gray_f32 is not None and self._prev is not None
                and gray_f32.shape == self._prev.shape):
            (bx, by), _ = cv2.phaseCorrelate(self._prev, gray_f32)
        if gray_f32 is not None:
            self._prev = gray_f32
            _h, _w = gray_f32.shape[:2]
            self._cx = _w / 2.0; self._cy = _h / 2.0

        high = [d for d in dets if d[2] >= BT_HIGH_THR]
        low = [d for d in dets if BT_LOW_THR <= d[2] < BT_HIGH_THR]

        # 1단계: high score ↔ 전체 트랙
        m1, ut1, ud1 = self._match(self._tracks, high, bx, by)
        for ti, di in m1:
            self._apply(self._tracks[ti], high[di])
        # 2단계: low score ↔ 1단계 미매칭 트랙 (반투명 타겟 ID 유지의 핵심)
        rem = [self._tracks[i] for i in ut1]
        m2, _ut2, _ud2 = self._match(rem, low, bx, by)
        matched_rem = set()
        for ti, di in m2:
            self._apply(rem[ti], low[di]); matched_rem.add(ti)
        # 미매칭 트랙 coast
        for k, t in enumerate(rem):
            if k not in matched_rem:
                if t.age > 0:
                    t.x += t.vx; t.y += t.vy
                else:
                    t.x += bx; t.y += by
                t.miss += 1
                if t.tid == self._tid:   # 타겟 coast 시 속도 감쇠(폭주 방지)
                    t.vx *= 0.9; t.vy *= 0.9
        # 미매칭 high det 새 트랙
        for di in ud1:
            self._new(high[di][0], high[di][1], high[di][2])

        # 배경 공통속도 = 데칼 대표 3개(age 큰=오래 추적돼 안정) 속도 중앙값. 데칼 전부는
        # 불필요(3개로 전체와 동일 정확도, 인게임 확인) — 사용자 설계: 타겟1 + 데칼3 = 4개,
        # 데칼 많으면 상위 3개만. 타겟 위치와 무관한 독립 샘플. 2개 미만이면 phaseCorrelate.
        _decals = sorted(
            (t for t in self._tracks
             if t.tid != self._tid and t.age >= BT_DECAL_AGE and t.miss == 0),
            key=lambda t: -t.age)[:BT_DECAL_N]
        if len(_decals) >= 2:
            self._bgvx = float(np.median([t.vx for t in _decals]))
            self._bgvy = float(np.median([t.vy for t in _decals]))
        else:
            self._bgvx, self._bgvy = bx, by

        # [CMC 격리] 켜진 경우만 전역 운동 보상 어파인 H 추정. 꺼지면 H=None 유지(원본 복귀).
        if self._cmc_on:
            self._estimate_cmc(prev_pos, prev_gray, gray_f32)

        # 다중가설 누적: 모든 트랙의 '배경과 다른 정도'를 EMA로 누적. 데칼은 배경동조라
        # rel≈0 수렴, 진짜 도형은 랜덤이라 rel 누적이 큼 → 재선택 채택 근거.
        #   CMC 켜짐: 안정화 좌표계 위치 잔차 ||현재 - H·직전||.
        #   CMC 꺼짐: 원본 ByteTrack 속도차 ||(vx-bgvx, vy-bgvy)|| (어파인 이전 베이스라인).
        _resid = {}
        for t in self._tracks:
            if self._cmc_on:
                pp = prev_pos.get(t.tid)
                if pp is None:
                    continue   # 신규 트랙 — 직전 위치 없음, 이번 프레임 누적 보류
                _wx, _wy = self._warp(pp[0], pp[1], bx, by)
                _r = ((t.x - _wx) ** 2 + (t.y - _wy) ** 2) ** 0.5
            else:
                _r = ((t.vx - self._bgvx) ** 2 + (t.vy - self._bgvy) ** 2) ** 0.5
            _resid[t.tid] = _r
            t.rel_ema = t.rel_ema * (1 - BT_REL_EMA) + _r * BT_REL_EMA

        # [hviol] 호모그래피 강체위반 누적(약한 사전) — 재선택 랭킹에만 쓰임.
        if self._hviol_on:
            _viol = self._homography_viol(prev_pos)
            for t in self._tracks:
                if t.tid in _viol:
                    t.viol_ema = t.viol_ema * (1 - BT_VIOL_EMA) + _viol[t.tid] * BT_VIOL_EMA

        tgt = next((t for t in self._tracks if t.tid == self._tid), None)

        if self._state == "OCCLUDING" and tgt is not None:
            # 흡수 구간 — 뭉친 1개 검출이 타겟인지 데칼인지 구분 불가(NMS는 고score 잔류).
            # 헝가리안 오배정 위험까지 단일 정책으로 차단: score 무관 무조건 v_pre coast.
            if _tg0_state is not None:
                tgt.x = _tg0_state[0] + self._vpre[0]
                tgt.y = _tg0_state[1] + self._vpre[1]
                tgt.vx, tgt.vy = self._vpre
                tgt.miss += 1
            self._occ_cnt += 1
            # 종료 — 타겟 예측 근방 EXIT 내 제2후보(데칼) 재출현 = split, 또는 최대 지속 초과
            _sep = any((t.x - tgt.x) ** 2 + (t.y - tgt.y) ** 2 <= BT_OCC_EXIT ** 2
                       for t in self._tracks
                       if t.tid != self._tid and t.miss == 0)
            if _sep or self._occ_cnt > BT_OCC_MAX:
                # (3단계 SEPARATING 재결합 자리) 현재는 IDLE 복귀 → 다음 프레임 정상 매칭 재포착
                self._state = "IDLE"; self._occ_ids = set(); self._occ_cnt = 0

        elif self._state == "IDLE":
            # ── 기존 IDLE 경로(baseline 동일) — bg_reject + HOLD 단발 + 흐림 재선택 ──
            # 타겟이 배경동조 데칼을 매칭했으면 취소 → coast (예측보다 배경흐름에 더 가까움).
            if tgt is not None and tgt.miss == 0 and _tg0_state is not None:
                _px = _tg0_state[0] + _tg0_state[2]
                _py = _tg0_state[1] + _tg0_state[3]
                # 배경 예측 — CMC 켜짐: 어파인 H 워핑 / 꺼짐: 원본 이동 bgvx,bgvy
                if self._cmc_on:
                    _bgpx, _bgpy = self._warp(_tg0_state[0], _tg0_state[1],
                                              self._bgvx, self._bgvy)
                else:
                    _bgpx = _tg0_state[0] + self._bgvx
                    _bgpy = _tg0_state[1] + self._bgvy
                _dpr = ((tgt.x - _px) ** 2 + (tgt.y - _py) ** 2) ** 0.5
                _dbg = ((tgt.x - _bgpx) ** 2 + (tgt.y - _bgpy) ** 2) ** 0.5
                if _dbg < _dpr and _dbg < BT_BG_REJECT:
                    tgt.x, tgt.y = _px, _py     # 배경동조 데칼 — 예측 복귀(coast)
                    tgt.miss = 1
                    tgt.vx *= 0.9; tgt.vy *= 0.9
                else:
                    # 점프 보류 — 매칭이 직전속도 크게 초과(점프) + 약검출이면 데칼 의심,
                    # 즉시 갈아타지 않고 coast(예측).
                    _disp = ((tgt.x - _tg0_state[0]) ** 2
                             + (tgt.y - _tg0_state[1]) ** 2) ** 0.5
                    _spd = (_tg0_state[2] ** 2 + _tg0_state[3] ** 2) ** 0.5
                    if _disp > _spd + BT_HOLD_JUMP and tgt.score < BT_HOLD_SCORE:
                        tgt.x, tgt.y = _px, _py
                        tgt.miss = 1
                        tgt.vx *= 0.9; tgt.vy *= 0.9

            # 타겟 흐림(lost) → 배경과 다른 속도(이상) 트랙으로 ID 승계.
            if tgt is not None and tgt.miss > 0:
                _gate = min(BT_GATE_MAX, BT_GATE + BT_GATE_GROW * tgt.miss)
                _jlim = ((tgt.vx * tgt.vx + tgt.vy * tgt.vy) ** 0.5
                         + BT_JUMP_CAP + BT_GATE_GROW * tgt.miss * 0.5)
                r2 = min(_gate, _jlim)
                # hviol: 누적 호모그래피 위반(7x)으로 풀 필터·랭킹. 꺼지면 원본 rel_ema.
                if self._hviol_on:
                    _val = lambda t: t.viol_ema; _thr = BT_VIOL_MIN
                else:
                    _val = lambda t: _resid.get(t.tid, 0.0); _thr = BT_REL_MIN
                _ev = (lambda t: t.viol_ema) if self._hviol_on else (lambda t: t.rel_ema)
                pool = [t for t in self._tracks
                        if t.tid != self._tid and t.miss == 0
                        and (t.x - tgt.x) ** 2 + (t.y - tgt.y) ** 2 <= r2 * r2
                        and _val(t) >= _thr]
                if pool:
                    best = max(pool, key=lambda t: _ev(t)
                               - ((t.x - tgt.x) ** 2 + (t.y - tgt.y) ** 2) ** 0.5 * 0.05)
                    self._tid = best.tid
                    tgt = best

            # ── 흡수 진입 감지(방법 A) — 직전 근방(검출됨) 데칼이 검출 잃고 타겟 ENTER 내로 ──
            if self._occ_on and tgt is not None:
                _absorbed = {
                    _did for _did, _ in self._near_prev.items()
                    for _d in [next((t for t in self._tracks if t.tid == _did), None)]
                    if _d is not None and _d.miss > 0
                    and (_d.x - tgt.x) ** 2 + (_d.y - tgt.y) ** 2 <= BT_OCC_ENTER ** 2}
                if _absorbed:
                    self._state = "OCCLUDING"
                    self._occ_ids = _absorbed
                    self._occ_cnt = 0
                    if self._vhist:
                        self._vpre = (float(np.mean([v[0] for v in self._vhist])),
                                      float(np.mean([v[1] for v in self._vhist])))
                    else:
                        self._vpre = (tgt.vx, tgt.vy)

        # ── orphan 재출현 재획득(턴 오매칭 복구) — 035137형 ──────────────────────────
        # 트랙이 옛방향 데칼로 새면(런타임엔 score 높아 안 보임), 페이드 자리(anchor=N프레임
        # 전 트랙위치)에서 진짜 타겟이 young+고정+강 orphan으로 재출현. anchor 최근접 orphan이
        # 3프레임 연속이면 jump-cap 우회해 ID 직접 전환. 공간(anchor)×시간(지속) 이중게이트.
        if self._reacq_on and tgt is not None and self._nudge_age >= BT_REACQ_NUDGE_GAP:
            _anchor = (self._anchor_hist[0]
                       if len(self._anchor_hist) >= BT_REACQ_N else None)
            _orphans = [t for t in self._tracks
                        if t.tid != self._tid and t.age <= BT_REACQ_AGE
                        and t.miss == 0 and t.score > BT_REACQ_SCORE]
            _cand = None
            # 현재 타겟이 anchor 근처(트랙이 갇힘=샘/스톨)일 때만 — 정상 이동 중엔 발동 안 함
            _tgt_stuck = ((tgt.x - _anchor[0]) ** 2 + (tgt.y - _anchor[1]) ** 2
                          <= BT_REACQ_TGT_NEAR ** 2) if _anchor is not None else False
            if _anchor is not None and _orphans and _tgt_stuck:
                _nr = min(_orphans, key=lambda t: (t.x - _anchor[0]) ** 2
                          + (t.y - _anchor[1]) ** 2)
                # anchor 최근접 + 현재 타겟서 충분히 떨어짐(옆 데칼 오발 차단, 새는 진짜재출현만)
                if (((_nr.x - _anchor[0]) ** 2 + (_nr.y - _anchor[1]) ** 2
                        <= BT_REACQ_ANCHOR_MAX ** 2)
                        and ((_nr.x - tgt.x) ** 2 + (_nr.y - tgt.y) ** 2
                             >= BT_REACQ_MIN_SEP ** 2)):
                    _cand = _nr
            if _cand is not None and _cand.tid == self._reacq_tid:
                self._reacq_cnt += 1
            elif _cand is not None:
                self._reacq_tid = _cand.tid; self._reacq_cnt = 1
            else:
                self._reacq_tid = None; self._reacq_cnt = 0
            if self._reacq_cnt >= BT_REACQ_HOLD and self._reacq_tid is not None:
                self._tid = self._reacq_tid     # 재획득 — ID 직접 전환(jump-cap 우회)
                tgt = next((t for t in self._tracks if t.tid == self._tid), None)
                self._reacq_tid = None; self._reacq_cnt = 0
                self._anchor_hist = []          # 새 타겟 기준 anchor 재시작

        # anchor 이력 — 타겟 트랙 위치(재획득 anchor=N프레임 전). 매 프레임 말미 갱신.
        if self._reacq_on and tgt is not None:
            self._anchor_hist.append((tgt.x, tgt.y))
            if len(self._anchor_hist) > BT_REACQ_N:
                self._anchor_hist.pop(0)

        # ── rel-bg 이상도 복구 — 갈아타기 락아웃 해제(035137형) ───────────────────────
        # 타겟이 데칼로 새면 트랙 rel_ema↓, 진짜 타겟은 배경과 달라 rel_ema↑. 현재 타겟보다
        # rel_ema가 마진 이상 큰 근처 트랙이 K프레임 지속되면 점프상한 우회해 그리로 전환.
        if self._relrec_on and tgt is not None and self._nudge_age >= BT_REACQ_NUDGE_GAP:
            # 이상도 = raw 프레임속도(현재−직전위치) − 배경(phaseCorrelate bx,by). 트랙 EMA속도·
            # 데칼중앙값 bg는 신호를 뭉개므로(검증), raw·phaseCorr로 직접 계산.
            def _ranom(t):
                pp = prev_pos.get(t.tid)
                if pp is None:
                    return 0.0
                return ((t.x - pp[0] - bx) ** 2 + (t.y - pp[1] - by) ** 2) ** 0.5
            base = _ranom(tgt)
            cand = None; bestr = base + BT_RELREC_MARGIN
            for t in self._tracks:
                if t.tid == self._tid or t.miss != 0 or t.age < BT_RELREC_AGE:
                    continue
                if (t.x - tgt.x) ** 2 + (t.y - tgt.y) ** 2 > BT_RELREC_R ** 2:
                    continue
                rt = _ranom(t)
                if rt >= BT_RELREC_MIN and rt > bestr:
                    bestr = rt; cand = t
            if cand is not None and cand.tid == self._relrec_tid:
                self._relrec_cnt += 1
            elif cand is not None:
                self._relrec_tid = cand.tid; self._relrec_cnt = 1
            else:
                self._relrec_tid = None; self._relrec_cnt = 0
            if self._relrec_cnt >= BT_RELREC_HOLD and self._relrec_tid is not None:
                self._tid = self._relrec_tid       # 복구 — jump-cap 우회 ID전환
                tgt = next((t for t in self._tracks if t.tid == self._tid), None)
                self._relrec_tid = None; self._relrec_cnt = 0
                if self._reacq_on:
                    self._anchor_hist = []

        # v_pre 이력 갱신(IDLE·검출됨 — 진입 전 깨끗한 운동만 평균에 반영) — occlusion 전용
        if self._occ_on and self._state == "IDLE" and tgt is not None and tgt.miss == 0:
            self._vhist.append((tgt.vx, tgt.vy))
            if len(self._vhist) > BT_OCC_NPRE:
                self._vhist.pop(0)

        # 다음 프레임 흡수 감지용 — 현재 타겟 근방(검출됨) 데칼 스냅샷(EXIT 밴드) — occlusion 전용
        if self._occ_on and tgt is not None:
            self._near_prev = {t.tid: (t.x, t.y) for t in self._tracks
                               if t.tid != self._tid and t.miss == 0
                               and (t.x - tgt.x) ** 2 + (t.y - tgt.y) ** 2 <= BT_OCC_EXIT ** 2}
        else:
            self._near_prev = {}

        # 비타겟 트랙 정리 — occ_ids(흡수 연루 데칼)는 컬링 면제(분리 시 ID 대조 보장)
        self._tracks = [t for t in self._tracks
                        if t.miss <= BT_TRK_MISS_MAX or t.tid == self._tid
                        or t.tid in self._occ_ids]

        if tgt is not None:
            return (tgt.x, tgt.y) if tgt.miss <= BT_LOST_MAX else None
        return None
