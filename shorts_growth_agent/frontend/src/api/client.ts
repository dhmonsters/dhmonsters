// 백엔드 API 호출을 담당하는 클라이언트 유틸입니다.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

export async function createProject(payload: {
  title: string;
  category: string;
  selected_keyword?: string;
}) {
  const response = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("프로젝트 생성에 실패했습니다.");
  return response.json();
}

export async function generatePlan(projectId: number) {
  const response = await fetch(`${API_BASE}/projects/${projectId}/generate-plan`, {
    method: "POST",
  });
  if (!response.ok) throw new Error("대본 계획 생성에 실패했습니다.");
  return response.json();
}
