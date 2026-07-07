# 하네스 기본값을 제공하는 API 라우터입니다.
from fastapi import APIRouter


router = APIRouter()


@router.get("/harnesses/default")
def get_default_harness():
    return {
        "name": "정보+후킹형",
        "mode": "basic",
        "system_prompt": "빠르고 정확한 한국어 쇼츠 작가로서 첫 3초 후킹과 명확한 정보 전달을 우선한다.",
        "output_schema": {
            "scene": "number",
            "subtitle": "string",
            "voice_text": "string",
            "image_prompt": "string",
            "source_type": "string",
            "motion_type": "string",
            "sound_effect": "string",
        },
        "forbidden_terms": ["무조건", "100%", "확정"],
    }
