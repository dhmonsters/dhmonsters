// 키워드와 카테고리 기반 소재 발굴 화면이다.
import { useEffect, useState } from "react";

import { fetchTrendCandidates } from "../api/client";
import { SectionCustomizer } from "../components/SectionCustomizer";
import type { TrendAnalysis, TrendCandidate, TrendCategory } from "../types";

export const TREND_CATEGORIES: TrendCategory[] = [
  { id: "", label: "전체" },
  { id: "20", label: "게임" },
  { id: "25", label: "뉴스" },
  { id: "24", label: "엔터·블로그" },
  { id: "26", label: "쇼핑·생활" },
];

export function getTrendCategory(categoryId: string): TrendCategory {
  return TREND_CATEGORIES.find((category) => category.id === categoryId) ?? TREND_CATEGORIES[0];
}

export function KeywordStep({
  customization,
  onCustomizationChange,
  onTrendInspect,
  onTrendPicked,
  selectedTrend,
  trendAnalysis,
}: {
  customization: string;
  onCustomizationChange: (value: string) => void;
  onTrendInspect: (trend: TrendCandidate) => Promise<void> | void;
  onTrendPicked: (trend: TrendCandidate, category: TrendCategory) => Promise<void> | void;
  selectedTrend: TrendCandidate | null;
  trendAnalysis: TrendAnalysis | null;
}) {
  const [categoryId, setCategoryId] = useState("20");
  const [keyword, setKeyword] = useState("");
  const [items, setItems] = useState<TrendCandidate[]>([]);
  const [source, setSource] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const search = async () => {
    setIsLoading(true);
    setError("");
    try {
      const response = await fetchTrendCandidates({
        region: "KR",
        category_id: categoryId,
        keyword: keyword.trim(),
      });
      setItems(response.items);
      setSource(response.source === "youtube" ? "YouTube 실데이터" : "한국 샘플 데이터");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "검색에 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void search();
  }, []);

  return (
    <section className="step-panel" aria-label="키워드 단계">
      <div className="step-heading">
        <p className="eyebrow">한국 트렌드 후보</p>
        <h1>인기 영상에서 만들 소재를 고릅니다</h1>
      </div>

      <SectionCustomizer
        title="후보 검색 설정"
        value={customization}
        onChange={onCustomizationChange}
        placeholder="예: 한국 게임 이슈, 과한 논란 제외, 쿠팡 파트너스 연결 가능 소재"
      />

      <form
        className="trend-search"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        <label className="field">
          <span>카테고리</span>
          <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
            {TREND_CATEGORIES.map((category) => (
              <option key={category.id || "all"} value={category.id}>
                {category.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>키워드</span>
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="비워두면 카테고리 기준"
          />
        </label>
        <button type="submit" className="primary-button" disabled={isLoading} aria-busy={isLoading}>
          후보 검색
        </button>
      </form>

      {source && <p className="source-badge">{source}</p>}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}

      <div className="trend-list" aria-label="트렌드 후보 목록">
        {items.map((item) => {
          const category = getTrendCategory(item.category_id);
          return (
            <article className="trend-card" key={item.video_id}>
              <div>
                <p className="trend-meta">
                  {category.label} · {item.channel_title}
                </p>
                <h2>{item.title}</h2>
                <p className="trend-score">
                  조회수 {item.view_count.toLocaleString()} · 상승 점수{" "}
                  {Math.round(item.score).toLocaleString()}
                </p>
                <div className="keyword-row">
                  {item.keyword_candidates.slice(0, 4).map((candidate) => (
                    <span key={candidate}>{candidate}</span>
                  ))}
                </div>
              </div>
              <div className="button-row">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void onTrendInspect(item)}
                >
                  상세 분석
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void onTrendPicked(item, category)}
                >
                  이 후보로 대본 만들기
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {selectedTrend && <p className="selected-trend">선택됨: {selectedTrend.title}</p>}
      {trendAnalysis && (
        <aside className="analysis-panel" aria-label="후보 상세 분석">
          <div className="step-heading">
            <p className="eyebrow">후보 상세 분석</p>
            <h2>{trendAnalysis.title}</h2>
          </div>
          <p>{trendAnalysis.summary}</p>
          <dl className="analysis-grid">
            <div>
              <dt>주의도</dt>
              <dd>{trendAnalysis.risk_level}</dd>
            </div>
            <div>
              <dt>대본 씨앗</dt>
              <dd>{trendAnalysis.script_seed}</dd>
            </div>
            <div>
              <dt>추천 길이</dt>
              <dd>{trendAnalysis.recommended_harness.target_seconds}초</dd>
            </div>
          </dl>
          <h3>제작 각도</h3>
          <ul>
            {trendAnalysis.production_angles.map((angle) => (
              <li key={angle}>{angle}</li>
            ))}
          </ul>
          <h3>주의 메모</h3>
          <ul>
            {trendAnalysis.risk_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </aside>
      )}
    </section>
  );
}
