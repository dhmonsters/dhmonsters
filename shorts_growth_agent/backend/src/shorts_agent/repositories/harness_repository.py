# Shorts용 하네스 기본값을 생성하고 읽는 저장소입니다.
from sqlalchemy.orm import Session

from shorts_agent.models import ScriptHarness


class HarnessRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_default_harness(self) -> ScriptHarness:
        harness = ScriptHarness(
            name="정보+후킹형",
            mode="basic",
            system_prompt="빠르고 정확한 한국어 쇼츠 작가로서 첫 3초 후킹과 명확한 정보 전달을 우선한다.",
            output_schema={
                "scene": "number",
                "subtitle": "string",
                "voice_text": "string",
                "image_prompt": "string",
                "source_type": "string",
                "motion_type": "string",
                "sound_effect": "string",
            },
            forbidden_terms=["무조건", "100%", "확정"],
        )
        self.session.add(harness)
        self.session.commit()
        self.session.refresh(harness)
        return harness
