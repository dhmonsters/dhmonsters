// 쇼츠 제작 프로젝트 상태 전이와 초기 상태를 관리합니다.
import type { HarnessSettings, SectionCustomization, StepId, TrendAnalysis, TrendCandidate } from "../types";

export type ScriptPlan = {
  keyword: string;
  scenes: Array<{ index: number; subtitle: string; source_type?: string; motion_type?: string }>;
};

export type ProjectState = {
  currentStep: StepId;
  project: { id: number; title: string } | null;
  scriptPlan: ScriptPlan | null;
  selectedTrend: TrendCandidate | null;
  trendAnalysis: TrendAnalysis | null;
  harness: HarnessSettings;
  customization: SectionCustomization;
};

export type ProjectAction =
  | { type: "projectCreated"; project: { id: number; title: string } }
  | { type: "planGenerated"; plan: ScriptPlan }
  | { type: "stepChanged"; step: StepId }
  | { type: "trendSelected"; trend: TrendCandidate }
  | { type: "trendAnalyzed"; analysis: TrendAnalysis }
  | { type: "harnessChanged"; harness: Partial<HarnessSettings> }
  | { type: "sceneSubtitleChanged"; index: number; subtitle: string }
  | { type: "sceneRegenerated"; index: number }
  | { type: "sceneMoved"; index: number; direction: "up" | "down" }
  | { type: "customizationChanged"; section: StepId; value: string };

export function createInitialProjectState(): ProjectState {
  return {
    currentStep: "keyword",
    project: null,
    scriptPlan: null,
    selectedTrend: null,
    trendAnalysis: null,
    harness: {
      name: "기본 하네스",
      tone: "명료",
      hook_strength: "강함",
      target_seconds: 45,
      forbidden_terms: ["100%", "무조건", "충격"],
      custom_prompt: "",
    },
    customization: {
      keyword: "한국 인기 영상 기준, 너무 자극적인 소재는 제외",
      script: "강한 훅, 짧은 문장, 45초 안쪽",
      voice: "밝고 빠른 톤, 자막은 하단 중앙",
      editor: "9:16 화면, 큰 자막, 장면 전환은 빠르게",
      export: "업로드 전 제목과 첫 3초를 다시 점검",
    },
  };
}

export function reduceProjectState(state: ProjectState, action: ProjectAction): ProjectState {
  if (action.type === "projectCreated") {
    return { ...state, project: action.project, currentStep: "script" };
  }
  if (action.type === "planGenerated") {
    return { ...state, scriptPlan: action.plan, currentStep: "script" };
  }
  if (action.type === "stepChanged") {
    return { ...state, currentStep: action.step };
  }
  if (action.type === "trendSelected") {
    return { ...state, selectedTrend: action.trend };
  }
  if (action.type === "trendAnalyzed") {
    return {
      ...state,
      trendAnalysis: action.analysis,
      harness: {
        ...state.harness,
        tone: action.analysis.recommended_harness.tone,
        hook_strength: action.analysis.recommended_harness.hook_strength,
        target_seconds: action.analysis.recommended_harness.target_seconds,
        forbidden_terms: action.analysis.recommended_harness.forbidden_terms,
      },
    };
  }
  if (action.type === "harnessChanged") {
    return { ...state, harness: { ...state.harness, ...action.harness } };
  }
  if (action.type === "sceneSubtitleChanged") {
    return {
      ...state,
      scriptPlan: state.scriptPlan
        ? {
            ...state.scriptPlan,
            scenes: state.scriptPlan.scenes.map((scene) =>
              scene.index === action.index ? { ...scene, subtitle: action.subtitle } : scene,
            ),
          }
        : state.scriptPlan,
    };
  }
  if (action.type === "sceneRegenerated") {
    return {
      ...state,
      scriptPlan: state.scriptPlan
        ? {
            ...state.scriptPlan,
            scenes: state.scriptPlan.scenes.map((scene) =>
              scene.index === action.index
                ? { ...scene, subtitle: `${scene.subtitle} 다시 생성` }
                : scene,
            ),
          }
        : state.scriptPlan,
    };
  }
  if (action.type === "sceneMoved") {
    if (!state.scriptPlan) return state;
    const from = state.scriptPlan.scenes.findIndex((scene) => scene.index === action.index);
    const to = action.direction === "up" ? from - 1 : from + 1;
    if (from < 0 || to < 0 || to >= state.scriptPlan.scenes.length) return state;
    const scenes = [...state.scriptPlan.scenes];
    [scenes[from], scenes[to]] = [scenes[to], scenes[from]];
    return {
      ...state,
      scriptPlan: {
        ...state.scriptPlan,
        scenes: scenes.map((scene, index) => ({ ...scene, index: index + 1 })),
      },
    };
  }
  if (action.type === "customizationChanged") {
    return {
      ...state,
      customization: { ...state.customization, [action.section]: action.value },
    };
  }
  return state;
}
