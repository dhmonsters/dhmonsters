# API 입출력을 위한 pydantic 스키마를 제공합니다.
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    category: str
    selected_keyword: str | None = None


class ProjectRead(BaseModel):
    id: int
    title: str
    category: str
    selected_keyword: str | None
    status: str

    model_config = {"from_attributes": True}
