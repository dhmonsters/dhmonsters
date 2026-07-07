# 시간별 성과 데이터 중심으로 원인 후보를 분석한다.
from dataclasses import dataclass


@dataclass(frozen=True)
class PerformancePoint:
    minutes_since_upload: int
    views: int
    impressions: int
    ctr: float
    retention_3s: float


@dataclass(frozen=True)
class CauseCandidate:
    code: str
    label: str
    probability: float
    reason: str


@dataclass(frozen=True)
class AnalysisResult:
    cause_candidates: list[CauseCandidate]
    next_experiments: list[str]


class PerformanceAnalysisService:
    def analyze(self, snapshots: list[PerformancePoint], production_facts: dict) -> AnalysisResult:
        if not snapshots:
            return AnalysisResult([], ["성과 스냅샷을 먼저 입력합니다."])
        ordered = sorted(snapshots, key=lambda item: item.minutes_since_upload)
        latest = ordered[-1]
        exposed_points = [point for point in ordered if point.impressions >= 1000]
        clicked_points = [point for point in ordered if point.ctr >= 0.08]
        candidates: list[CauseCandidate] = []
        if latest.impressions >= 1000 and latest.ctr < 0.03 and self._has_sustained_low_ctr(exposed_points):
            candidates.append(
                CauseCandidate(
                    "title_thumbnail_mismatch",
                    "제목/썸네일 문제 가능성",
                    0.78,
                    "노출은 충분하지만 클릭률이 낮습니다.",
                )
            )
        if latest.ctr >= 0.08 and latest.retention_3s < 0.35 and self._has_sustained_weak_retention(clicked_points):
            candidates.append(
                CauseCandidate(
                    "weak_first_three_seconds",
                    "첫 3초 후킹 문제 가능성",
                    0.82,
                    "클릭은 되었지만 초반 유지율이 낮습니다.",
                )
            )
        if not candidates:
            candidates.append(
                CauseCandidate(
                    "insufficient_signal",
                    "추가 데이터 필요",
                    0.45,
                    "성과 패턴이 아직 명확하지 않습니다.",
                )
            )
        return AnalysisResult(
            cause_candidates=sorted(candidates, key=lambda item: item.probability, reverse=True),
            next_experiments=self._experiments(candidates, production_facts),
        )

    def _has_sustained_low_ctr(self, points: list[PerformancePoint]) -> bool:
        return bool(points) and all(point.ctr < 0.03 for point in points)

    def _has_sustained_weak_retention(self, points: list[PerformancePoint]) -> bool:
        return bool(points) and all(point.retention_3s < 0.35 for point in points)

    def _experiments(self, candidates: list[CauseCandidate], production_facts: dict) -> list[str]:
        experiments = []
        for candidate in candidates:
            if candidate.code == "title_thumbnail_mismatch":
                experiments.append("같은 키워드로 제목 첫 12자를 더 직접적으로 바꾼 버전을 비교합니다.")
            if candidate.code == "weak_first_three_seconds":
                experiments.append("첫 장면에 줌인 또는 흔들림 모션과 더 짧은 후킹 문장을 적용합니다.")
        return experiments or ["동일 카테고리 영상 3개 이상과 시간별 성과를 비교합니다."]
