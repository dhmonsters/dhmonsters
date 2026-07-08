// 상단의 작은 제작 단계 표시 컴포넌트다.
import type { StepId } from "../types";

const STEPS: Array<{ id: StepId; label: string }> = [
  { id: "keyword", label: "키워드" },
  { id: "script", label: "대본" },
  { id: "voice", label: "음성/자막" },
  { id: "editor", label: "편집" },
  { id: "export", label: "출력" },
];

export function TopStepNav({
  currentStep,
  onStepChange,
}: {
  currentStep: StepId;
  onStepChange: (step: StepId) => void;
}) {
  return (
    <nav className="top-step-nav" aria-label="쇼츠 제작 단계">
      {STEPS.map((step) => (
        <button
          key={step.id}
          type="button"
          aria-current={currentStep === step.id ? "step" : undefined}
          onClick={() => onStepChange(step.id)}
        >
          {step.label}
        </button>
      ))}
    </nav>
  );
}
