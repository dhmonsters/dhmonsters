// 쇼츠 제작 프로젝트 상태 전이와 초기 상태를 관리합니다.
import type { SectionCustomization, StepId, TrendCandidate } from "../types";

export type ScriptPlan = {
  keyword: string;
  scenes: Array<{ index: number; subtitle: string }>;
};

export type ProjectState = {
  currentStep: StepId;
  project: { id: number; title: string } | null;
  scriptPlan: ScriptPlan | null;
  selectedTrend: TrendCandidate | null;
  customization: SectionCustomization;
};

export type ProjectAction =
  | { type: "projectCreated"; project: { id: number; title: string } }
  | { type: "planGenerated"; plan: ScriptPlan }
  | { type: "stepChanged"; step: StepId }
  | { type: "trendSelected"; trend: TrendCandidate }
  | { type: "customizationChanged"; section: StepId; value: string };

export function createInitialProjectState(): ProjectState {
  return {
    currentStep: "keyword",
    project: null,
    scriptPlan: null,
    selectedTrend: null,
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
  if (action.type === "customizationChanged") {
    return {
      ...state,
      customization: { ...state.customization, [action.section]: action.value },
    };
  }
  return state;
}
