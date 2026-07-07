# 프로젝트 생성/조회 기능을 담당하는 리포지토리입니다.
from sqlalchemy.orm import Session

from shorts_agent.models import VideoProject


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_project(
        self, title: str, category: str, selected_keyword: str | None = None
    ) -> VideoProject:
        project = VideoProject(
            title=title, category=category, selected_keyword=selected_keyword
        )
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def get_project(self, project_id: int) -> VideoProject | None:
        return self.session.get(VideoProject, project_id)
