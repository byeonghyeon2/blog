"""
ai_router.py - AI 글 생성 관련 API 엔드포인트

엔드포인트:
    POST /api/ai/title        - 제목 후보 생성
    POST /api/ai/content      - 본문 생성
    POST /api/ai/seo          - SEO 설명 및 태그 생성
    POST /api/ai/html-convert - 텍스트 → 네이버 블로그용 HTML 변환
"""

from fastapi import APIRouter, Depends, HTTPException
from openai import APIConnectionError, OpenAIError, RateLimitError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.generation_log import GenerationLog
from app.schemas.ai_schema import (
    AiResponse,
    ContentRequest,
    InstagramCardRequest,
    SeoRequest,
    TitleRequest,
)
from app.services.ai_service import (
    GeneratedText,
    content_prompt,
    fetch_url_text,
    generate_text_with_usage,
    instagram_cards_prompt,
    seo_prompt,
    title_prompt,
)
from app.services.html_service import text_to_tistory_html


router = APIRouter(prefix="/api/ai", tags=["ai"])


def request_image_urls(
    reference_image_data_url: str | None = None,
    reference_image_data_urls: list[str] | None = None,
) -> list[str]:
    urls = list(reference_image_data_urls or [])
    if reference_image_data_url and reference_image_data_url not in urls:
        urls.insert(0, reference_image_data_url)
    return urls


def run_ai_generation(prompt: str, reference_image_data_urls: list[str] | None = None) -> GeneratedText:
    """
    OpenAI 호출을 실행하고, 사용자가 이해할 수 있는 오류 메시지로 변환합니다.
    결제/쿼터/네트워크 문제를 500 대신 명확한 API 오류로 내려주기 위한 래퍼입니다.
    """
    try:
        return generate_text_with_usage(prompt, reference_image_data_urls)
    except RateLimitError as exc:
        raise HTTPException(
            status_code=402,
            detail="OpenAI API 사용량 또는 결제 한도가 부족합니다. OpenAI 결제/크레딧 설정을 확인해주세요.",
        ) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="OpenAI API 서버에 연결하지 못했습니다. 네트워크 또는 방화벽 설정을 확인해주세요.",
        ) from exc
    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI API 호출 중 오류가 발생했습니다: {exc}",
        ) from exc


def save_generation_log(
    db: Session,
    generation_type: str,
    prompt: str,
    response: GeneratedText,
) -> None:
    """
    AI 호출 결과(프롬프트 + 응답)를 generation_logs 테이블에 저장합니다.
    나중에 프롬프트 품질 개선이나 비용 분석에 활용할 수 있습니다.

    Args:
        db:              SQLAlchemy DB 세션
        generation_type: 생성 유형 코드 (TITLE / CONTENT / SEO)
        prompt:          OpenAI에 전달한 프롬프트 원문
        response:        OpenAI가 반환한 응답 원문
    """
    db.add(
        GenerationLog(
            generation_type=generation_type,
            prompt=prompt,
            response=response.text,
            model_name=settings.openai_model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
        )
    )
    db.commit()


@router.post("/title", response_model=AiResponse)
def generate_title(request: TitleRequest, db: Session = Depends(get_db)):
    """
    키워드와 글 유형을 기반으로 블로그 제목 후보 5개를 생성합니다.
    생성 결과와 프롬프트는 이력으로 저장됩니다.
    """
    image_urls = request_image_urls(request.reference_image_data_url, request.reference_image_data_urls)
    prompt = title_prompt(request.keyword, request.category, len(image_urls), request.reference_image_notes)
    generated = run_ai_generation(prompt, image_urls)
    save_generation_log(db, "TITLE", prompt, generated)
    return AiResponse(result=generated.text)


@router.post("/content", response_model=AiResponse)
def generate_content(request: ContentRequest, db: Session = Depends(get_db)):
    """
    제목과 주제/키워드를 기준으로 실제 블로그 본문을 생성합니다.
    예제 코드 포함 여부와 목표 글자 수를 파라미터로 받습니다.
    생성 결과와 프롬프트는 이력으로 저장됩니다.
    """
    prompt = content_prompt(
        request.title,
        request.keyword,
        request.category,
        request.include_code,
        request.target_length,
        len(request_image_urls(request.reference_image_data_url, request.reference_image_data_urls)),
        request.reference_image_notes,
    )
    generated = run_ai_generation(
        prompt,
        request_image_urls(request.reference_image_data_url, request.reference_image_data_urls),
    )
    save_generation_log(db, "CONTENT", prompt, generated)
    return AiResponse(result=generated.text)


@router.post("/seo", response_model=AiResponse)
def generate_seo(request: SeoRequest, db: Session = Depends(get_db)):
    """
    생성된 본문을 기준으로 SEO 설명(100자 이내)과 네이버 블로그 태그를 생성합니다.
    생성 결과와 프롬프트는 이력으로 저장됩니다.
    """
    prompt = seo_prompt(request.title, request.keyword, request.content_text)
    generated = run_ai_generation(prompt)
    save_generation_log(db, "SEO", prompt, generated)
    return AiResponse(result=generated.text)


@router.post("/instagram-cards", response_model=AiResponse)
def generate_instagram_cards(request: InstagramCardRequest, db: Session = Depends(get_db)):
    """
    URL, 블로그 글, 정보성 글을 인스타 카드뉴스 원고로 변환합니다.
    URL 본문 추출은 보조 재료로만 사용하고, 실패해도 사용자가 입력한 텍스트가 있으면 계속 진행합니다.
    """
    source_url = (request.source_url or "").strip()
    source_text = (request.source_text or "").strip()
    fetched_text = fetch_url_text(source_url) if source_url else ""

    if not source_text and not fetched_text and not source_url:
        raise HTTPException(status_code=400, detail="URL 또는 카드뉴스로 만들 내용을 입력해 주세요.")

    prompt = instagram_cards_prompt(
        request.source_type,
        source_url,
        source_text,
        fetched_text,
        request.card_count,
        request.category,
        request.purpose,
        request.style_note,
    )
    generated = run_ai_generation(prompt)
    save_generation_log(db, "INSTAGRAM_CARDS", prompt, generated)
    return AiResponse(result=generated.text)


@router.post("/html-convert", response_model=AiResponse)
def convert_html(request: SeoRequest):
    """
    본문 텍스트를 네이버 블로그 에디터에 붙여넣기 적합한 HTML 구조로 변환합니다.
    AI 호출 없이 서버 내 변환 로직만 사용하므로 DB 저장은 하지 않습니다.

    Note:
        SeoRequest를 재사용하지만 실제로는 content_text 필드만 사용합니다.
        추후 전용 스키마로 분리하는 것을 권장합니다.
    """
    return AiResponse(result=text_to_tistory_html(request.content_text))
