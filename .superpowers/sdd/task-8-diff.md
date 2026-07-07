diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/performance.py b/shorts_growth_agent/backend/src/shorts_agent/api/performance.py
new file mode 100644
index 00000000..94359656
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/performance.py
@@ -0,0 +1,21 @@
+# 수동 성과 입력과 회고 리포트 생성을 제공한다.
+from fastapi import APIRouter
+from pydantic import BaseModel
+
+from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint
+
+router = APIRouter()
+
+
+class PerformanceAnalysisRequest(BaseModel):
+    snapshots: list[PerformancePoint]
+    production_facts: dict
+
+
+@router.post("/performance/analyze")
+def analyze_performance(request: PerformanceAnalysisRequest):
+    result = PerformanceAnalysisService().analyze(request.snapshots, request.production_facts)
+    return {
+        "cause_candidates": [candidate.__dict__ for candidate in result.cause_candidates],
+        "next_experiments": result.next_experiments,
+    }
diff --git a/shorts_growth_agent/backend/src/shorts_agent/main.py b/shorts_growth_agent/backend/src/shorts_agent/main.py
index 8fc43192..294b7048 100644
--- a/shorts_growth_agent/backend/src/shorts_agent/main.py
+++ b/shorts_growth_agent/backend/src/shorts_agent/main.py
@@ -1,15 +1,17 @@
 # FastAPI 앱 생성 및 라우터 등록을 담당합니다.
 from fastapi import FastAPI
 
 from shorts_agent.api.health import router as health_router
+from shorts_agent.api.performance import router as performance_router
 from shorts_agent.api.trends import router as trends_router
 
 
 def create_app() -> FastAPI:
     app = FastAPI(title="Shorts Growth Agent")
     app.include_router(health_router, prefix="/api")
+    app.include_router(performance_router, prefix="/api")
     app.include_router(trends_router, prefix="/api")
     return app
 
 
 app = create_app()
diff --git a/shorts_growth_agent/backend/src/shorts_agent/repositories/performance_repository.py b/shorts_growth_agent/backend/src/shorts_agent/repositories/performance_repository.py
new file mode 100644
index 00000000..007873af
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/repositories/performance_repository.py
@@ -0,0 +1,3 @@
+# 성능 스냅샷 저장/조회에 대한 저장소 자리표시자이다.
+class PerformanceRepository:
+    ...
diff --git a/shorts_growth_agent/backend/src/shorts_agent/services/performance_analysis.py b/shorts_growth_agent/backend/src/shorts_agent/services/performance_analysis.py
new file mode 100644
index 00000000..fec4eff3
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/services/performance_analysis.py
@@ -0,0 +1,82 @@
+# 시간별 성과 데이터 중심으로 원인 후보를 분석한다.
+from dataclasses import dataclass
+
+
+@dataclass(frozen=True)
+class PerformancePoint:
+    minutes_since_upload: int
+    views: int
+    impressions: int
+    ctr: float
+    retention_3s: float
+
+
+@dataclass(frozen=True)
+class CauseCandidate:
+    code: str
+    label: str
+    probability: float
+    reason: str
+
+
+@dataclass(frozen=True)
+class AnalysisResult:
+    cause_candidates: list[CauseCandidate]
+    next_experiments: list[str]
+
+
+class PerformanceAnalysisService:
+    def analyze(self, snapshots: list[PerformancePoint], production_facts: dict) -> AnalysisResult:
+        if not snapshots:
+            return AnalysisResult([], ["성과 스냅샷을 먼저 입력합니다."])
+        ordered = sorted(snapshots, key=lambda item: item.minutes_since_upload)
+        latest = ordered[-1]
+        exposed_points = [point for point in ordered if point.impressions >= 1000]
+        clicked_points = [point for point in ordered if point.ctr >= 0.08]
+        candidates: list[CauseCandidate] = []
+        if latest.impressions >= 1000 and latest.ctr < 0.03 and self._has_sustained_low_ctr(exposed_points):
+            candidates.append(
+                CauseCandidate(
+                    "title_thumbnail_mismatch",
+                    "제목/썸네일 문제 가능성",
+                    0.78,
+                    "노출은 충분하지만 클릭률이 낮습니다.",
+                )
+            )
+        if latest.ctr >= 0.08 and latest.retention_3s < 0.35 and self._has_sustained_weak_retention(clicked_points):
+            candidates.append(
+                CauseCandidate(
+                    "weak_first_three_seconds",
+                    "첫 3초 후킹 문제 가능성",
+                    0.82,
+                    "클릭은 되었지만 초반 유지율이 낮습니다.",
+                )
+            )
+        if not candidates:
+            candidates.append(
+                CauseCandidate(
+                    "insufficient_signal",
+                    "추가 데이터 필요",
+                    0.45,
+                    "성과 패턴이 아직 명확하지 않습니다.",
+                )
+            )
+        return AnalysisResult(
+            cause_candidates=sorted(candidates, key=lambda item: item.probability, reverse=True),
+            next_experiments=self._experiments(candidates, production_facts),
+        )
+
+    def _has_sustained_low_ctr(self, points: list[PerformancePoint]) -> bool:
+        return bool(points) and all(point.ctr < 0.03 for point in points)
+
+    def _has_sustained_weak_retention(self, points: list[PerformancePoint]) -> bool:
+        return bool(points) and all(point.retention_3s < 0.35 for point in points)
+
+    def _experiments(self, candidates: list[CauseCandidate], production_facts: dict) -> list[str]:
+        experiments = []
+        for candidate in candidates:
+            if candidate.code == "title_thumbnail_mismatch":
+                experiments.append("같은 키워드로 제목 첫 12자를 더 직접적으로 바꾼 버전을 비교합니다.")
+            if candidate.code == "weak_first_three_seconds":
+                experiments.append("첫 장면에 줌인 또는 흔들림 모션과 더 짧은 후킹 문장을 적용합니다.")
+        return experiments or ["동일 카테고리 영상 3개 이상과 시간별 성과를 비교합니다."]
diff --git a/shorts_growth_agent/backend/tests/test_performance_analysis.py b/shorts_growth_agent/backend/tests/test_performance_analysis.py
new file mode 100644
index 00000000..bee2256d
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_performance_analysis.py
@@ -0,0 +1,69 @@
+# 시간별 성과 곡선을 먼저 보고 제작 데이터를 보조로 사용한다.
+from fastapi.testclient import TestClient
+from shorts_agent.main import create_app
+from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint
+
+
+def test_low_ctr_after_good_impressions_points_to_title_thumbnail():
+    snapshots = [
+        PerformancePoint(
+            minutes_since_upload=60, views=100, impressions=5000, ctr=0.02, retention_3s=0.7
+        ),
+        PerformancePoint(
+            minutes_since_upload=360, views=130, impressions=9000, ctr=0.014, retention_3s=0.68
+        ),
+    ]
+
+    result = PerformanceAnalysisService().analyze(snapshots, {"hook_type": "question"})
+
+    assert result.cause_candidates[0].code == "title_thumbnail_mismatch"
+
+
+def test_latest_low_ctr_without_time_series_pattern_needs_more_data():
+    snapshots = [
+        PerformancePoint(
+            minutes_since_upload=60, views=500, impressions=5000, ctr=0.1, retention_3s=0.72
+        ),
+        PerformancePoint(
+            minutes_since_upload=360, views=130, impressions=9000, ctr=0.014, retention_3s=0.68
+        ),
+    ]
+
+    result = PerformanceAnalysisService().analyze(snapshots, {"hook_type": "question"})
+
+    assert result.cause_candidates[0].code == "insufficient_signal"
+
+
+def test_high_ctr_low_three_second_retention_points_to_hook():
+    snapshots = [
+        PerformancePoint(
+            minutes_since_upload=60, views=600, impressions=5000, ctr=0.12, retention_3s=0.22
+        ),
+    ]
+
+    result = PerformanceAnalysisService().analyze(snapshots, {"first_scene_motion": "none"})
+
+    assert result.cause_candidates[0].code == "weak_first_three_seconds"
+
+
+def test_analyze_endpoint_registers_performance_router_low_ctr():
+    client = TestClient(create_app())
+
+    payload = {
+        "snapshots": [
+            {
+                "minutes_since_upload": 360,
+                "views": 130,
+                "impressions": 9000,
+                "ctr": 0.014,
+                "retention_3s": 0.68,
+            }
+        ],
+        "production_facts": {"hook_type": "question"},
+    }
+
+    response = client.post("/api/performance/analyze", json=payload)
+
+    assert response.status_code == 200
+    body = response.json()
+    assert body["cause_candidates"][0]["code"] == "title_thumbnail_mismatch"
