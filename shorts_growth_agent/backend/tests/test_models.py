# 프로젝트 데이터 모델과 리포지토리의 기본 동작을 검증합니다.
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from shorts_agent.db import init_db
from shorts_agent.models import ProjectStatus
from shorts_agent.repositories.project_repository import ProjectRepository


def test_create_project_sets_default_status():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ProjectRepository(session)
        project = repo.create_project(title="테스트 프로젝트", category="일반")

        assert project.id is not None
        assert project.status == ProjectStatus.DRAFT
        assert project.category == "일반"


def test_get_project_returns_saved_project():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ProjectRepository(session)
        created = repo.create_project(title="샘플 제목", category="샘플")
        found = repo.get_project(created.id)

        assert found is not None
        assert found.title == "샘플 제목"


def test_init_db_creates_required_tables():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)

    table_names = set(inspect(engine).get_table_names())

    assert {
        "video_projects",
        "script_harnesses",
        "scene_assets",
        "render_outputs",
        "performance_snapshots",
        "analysis_reports",
        "learning_memories",
    }.issubset(table_names)
