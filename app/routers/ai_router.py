"""
ai_router.py - AI 글 생성 관련 API 엔드포인트

엔드포인트:
    POST /api/ai/title        - 제목 후보 생성
    POST /api/ai/outline      - 목차 생성
    POST /api/ai/content      - 본문 생성
    POST /api/ai/seo          - SEO 설명 및 태그 생성
    POST /api/ai/html-convert - 텍스트 → Tistory HTML 변환
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.generation_log import GenerationLog
from app.schemas.ai_schema import (
    AiResponse,
    ContentRequest,
    OutlineRequest,
    SeoRequest,
    TitleRequest,
)
from app.services.ai_service import (
    content_prompt,
    generate_text,
    outline_prompt,
    seo_prompt,
    title_prompt,
)
from app.services.html_service import text_to_tistory_html


router = APIRouter(prefix="/api/ai", tags=["ai"])


def save_generation_log(
    db: Session,
    generation_type: str,
    prompt: str,
    response: str,
) -> None:
    """
    AI 호출 결과(프롬프트 + 응답)를 generation_logs 테이블에 저장합니다.
    나중에 프롬프트 품질 개선이나 비용 분석에 활용할 수 있습니다.

    Args:
        db:              SQLAlchemy DB 세션
        generation_type: 생성 유형 코드 (TITLE / OUTLINE / CONTENT / SEO)
        prompt:          OpenAI에 전달한 프롬프트 원문
        response:        OpenAI가 반환한 응답 원문
    """
    db.add(
        GenerationLog(
            generation_type=generation_type,
            prompt=prompt,
            response=response,
        )
    )
    db.commit()


@router.post("/title", response_model=AiResponse)
def generate_title(request: TitleRequest, db: Session = Depends(get_db)):
    """
    키워드와 글 유형을 기반으로 블로그 제목 후보 5개를 생성합니다.
    생성 결과와 프롬프트는 이력으로 저장됩니다.
    """
    prompt = title_prompt(request.keyword, request.post_type)
    result = generate_text(prompt)
    save_generation_log(db, "TITLE", prompt, result)
    return AiResponse(result=result)


@router.post("/outline", response_model=AiResponse)
def generate_outline(request: OutlineRequest, db: Session = Depends(get_db)):
    """
    선택한 제목과 키워드를 기준으로 번호형 목차를 생성합니다.
    생성 결과와 프롬프트는 이력으로 저장됩니다.
    """
    prompt = outline_prompt(request.title, request.keyword, request.post_type)
    result = generate_text(prompt)
    save_generation_log(db, "OUTLINE", prompt, result)
    return AiResponse(result=result)


@router.post("/content", response_model=AiResponse)
def generate_content(request: ContentRequest, db: Session = Depends(get_db)):
    """
    목차를 기준으로 실제 블로그 본문을 생성합니다.
    예제 코드 포함 여부와 목표 글자 수를 파라미터로 받습니다.
    생성 결과와 프롬프트는 이력으로 저장됩니다.
    """
    prompt = content_prompt(
        request.title,
        request.keyword,
        request.post_type,
        request.outline,
        request.include_code,
        request.target_length,
    )
    result = generate_text(prompt)
    save_generation_log(db, "CONTENT", prompt, result)
    return AiResponse(result=result)


@router.post("/seo", response_model=AiResponse)
def generate_seo(request: SeoRequest, db: Session = Depends(get_db)):
    """
    생성된 본문을 기준으로 SEO 설명(100자 이내)과 Tistory 태그를 생성합니다.
    생성 결과와 프롬프트는 이력으로 저장됩니다.
    """
    prompt = seo_prompt(request.title, request.keyword, request.content_text)
    result = generate_text(prompt)
    save_generation_log(db, "SEO", prompt, result)
    return AiResponse(result=result)


@router.post("/html-convert", response_model=AiResponse)
def convert_html(request: SeoRequest):
    """
    본문 텍스트를 Tistory 에디터에 붙여넣기 적합한 HTML 구조로 변환합니다.
    AI 호출 없이 서버 내 변환 로직만 사용하므로 DB 저장은 하지 않습니다.

    Note:
        SeoRequest를 재사용하지만 실제로는 content_text 필드만 사용합니다.
        추후 전용 스키마로 분리하는 것을 권장합니다.
    """
    return AiResponse(result=text_to_tistory_html(request.content_text))
