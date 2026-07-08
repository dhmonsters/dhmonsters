// 쇼츠 제작 프로젝트 상태 전이와 초기 상태를 관리합니다.
import type { StepId } from "../types";

export type ScriptPlan = {
  keyword: string;
  scenes: Array<{ index: number; subtitle: string }>;
};

export type ProjectState = {
  currentStep: StepId;
  project: { id: number; title: string } | null;
  scriptPlan: ScriptPlan | null;
};

export type ProjectAction =
  | { type: "projectCreated"; project: { id: number; title: string } }
  | { type: "planGenerated"; plan: ScriptPlan }
  | { type: "stepChanged"; step: StepId };

export function createInitialProjectState(): ProjectState {
  return { currentStep: "keyword", project: null, scriptPlan: null };
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
  return state;
}
