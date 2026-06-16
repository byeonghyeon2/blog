"""
ai_service.py - OpenAI 기반 블로그 글 생성 서비스

주요 기능:
    - OpenAI Responses API 호출 (generate_text)
    - 카테고리별 프롬프트 생성 (title / content / seo)
    - API 키 없는 개발 환경용 fallback 응답 (fallback_response)
"""

import re
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import settings
from app.models.post import BlogCategory


# ───────────────────────────────────────────
# 상수 정의
# ───────────────────────────────────────────

# 모든 프롬프트에 공통으로 적용되는 말투 규칙
STYLE_RULES = """
- 설명은 짧고 명확하게 작성
- "쉽게 얘기하면", "예를 들어" 같은 표현 사용
- 실제 상황에서 어떻게 쓰이는지 중심으로 설명
- 과장된 문구, 광고성 문구, 논문식 문체 금지
- 문장은 너무 길게 늘이지 말고 블로그 글처럼 자연스럽게 작성
""".strip()

CATEGORY_LABELS: dict[BlogCategory, str] = {
    BlogCategory.IT:        "IT / 기술",
    BlogCategory.FINANCE:   "금융 / 재테크",
    BlogCategory.FOOD:      "맛집 / 음식",
    BlogCategory.TRAVEL:    "여행 / 장소",
    BlogCategory.LIFESTYLE: "생활 / 리뷰",
}


# ───────────────────────────────────────────
# 핵심 생성 함수
# ───────────────────────────────────────────

@dataclass
class GeneratedText:
    """
    OpenAI 응답 텍스트와 사용 토큰 수를 함께 전달하기 위한 값 객체입니다.
    """

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


def estimate_tokens(text: str) -> int:
    """
    API 키가 없거나 usage 값이 없는 경우를 위한 대략적인 토큰 추정치입니다.
    한국어는 글자 수와 토큰 수가 정확히 일치하지 않으므로 참고용으로만 사용합니다.
    """
    return max(1, len(text or "") // 2)


def generate_text(prompt: str, reference_image_data_url: str | None = None) -> str:
    """
    기존 호출부 호환을 위해 텍스트만 반환합니다.
    토큰 사용량까지 필요한 곳에서는 generate_text_with_usage를 사용합니다.
    """
    return generate_text_with_usage(prompt, reference_image_data_url).text


def generate_text_with_usage(prompt: str, reference_image_data_url: str | None = None) -> GeneratedText:
    """
    OpenAI Responses API를 호출하여 텍스트를 생성합니다.
    API 키가 설정되어 있지 않으면 fallback_response를 반환합니다.

    Args:
        prompt: OpenAI에 전달할 프롬프트 문자열

    Returns:
        생성된 텍스트 (앞뒤 공백 제거됨)

    Raises:
        openai.OpenAIError: API 호출 자체 실패 시 (키 오류, 네트워크 등)
    """
    if not settings.openai_api_key:
        # 개발/테스트 환경: API 키 없이도 화면 동작 확인이 가능하도록 샘플 응답 반환
        text = fallback_response(prompt)
        prompt_tokens = estimate_tokens(prompt)
        completion_tokens = estimate_tokens(text)
        return GeneratedText(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    client = OpenAI(api_key=settings.openai_api_key)
    user_content: str | list[dict[str, object]]
    if reference_image_data_url:
        user_content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": reference_image_data_url,
                },
            },
        ]
    else:
        user_content = prompt

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "너는 티스토리 블로그 글을 작성하는 한국어 블로거다."},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
    )
    result_text = response.choices[0].message.content.strip()
    usage = response.usage
    return GeneratedText(
        text=result_text,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
    )


# ───────────────────────────────────────────
# 프롬프트 생성 함수
# ───────────────────────────────────────────

def reference_image_instruction(has_reference_image: bool) -> str:
    """
    사용자가 올린 참고 이미지를 어떻게 활용할지 프롬프트에 추가합니다.
    이미지의 레이아웃/정보 배치만 참고하고 문체는 기존 스타일을 유지하도록 제한합니다.
    """
    if not has_reference_image:
        return ""

    return f"""

참고 방식:
- 첨부된 참고 이미지는 글의 화면 구성, 정보 배치, 섹션 흐름만 참고
- 이미지 안의 문장, 말투, 표현, 사례를 그대로 따라 쓰지 말 것
- 참고 이미지의 디자인 요소를 설명하지 말고, 글의 자연스러운 흐름에만 반영
- 최종 말투는 반드시 아래 말투 규칙을 우선 적용
""".rstrip()


def category_instruction(category: BlogCategory) -> str:
    """
    선택한 카테고리에 따라 글에서 중점적으로 다룰 관점을 제공합니다.
    특정 양식을 강제하지 않고, 주제에 맞는 설명 방향만 잡습니다.
    """
    instructions = {
        BlogCategory.IT: "IT / 기술: 개념, 사용 이유, 실제 적용 상황, 주의할 점을 중심으로 작성",
        BlogCategory.FINANCE: "금융 / 재테크: 개념, 조건, 장단점, 리스크를 균형 있게 설명하고 투자 권유처럼 쓰지 않기",
        BlogCategory.FOOD: "맛집 / 음식: 위치, 분위기, 메뉴, 가격대, 실제 방문자가 궁금해할 포인트 중심으로 작성",
        BlogCategory.TRAVEL: "여행 / 장소: 동선, 비용, 준비물, 주의점, 실제 여행자가 겪을 상황 중심으로 작성",
        BlogCategory.LIFESTYLE: "생활 / 리뷰: 사용 계기, 장단점, 추천 대상, 아쉬운 점을 솔직하게 작성",
    }
    return instructions[category]


def title_prompt(keyword: str, category: BlogCategory, has_reference_image: bool = False) -> str:
    """
    주제/키워드와 카테고리를 기반으로 제목 후보 5개를 요청하는 프롬프트를 생성합니다.

    Args:
        keyword:   사용자가 입력한 핵심 키워드
        category: 카테고리

    Returns:
        완성된 프롬프트 문자열
    """
    return f"""
아래 조건에 맞춰 티스토리 블로그 제목 후보 5개를 작성해줘.

주제/키워드: {keyword}
카테고리: {CATEGORY_LABELS[category]}
카테고리 작성 방향: {category_instruction(category)}
{reference_image_instruction(has_reference_image)}

말투 규칙:
{STYLE_RULES}

조건:
- 제목만 번호 목록으로 작성
- 독자가 검색할 만한 자연스러운 표현 사용
- 과장된 제목 금지
""".strip()


def content_prompt(
    title: str,
    keyword: str,
    category: BlogCategory,
    include_code: bool,
    target_length: int,
    has_reference_image: bool = False,
) -> str:
    """
    제목과 주제/키워드를 기반으로 실제 블로그 본문을 요청하는 프롬프트를 생성합니다.

    Args:
        title:         블로그 제목
        keyword:       핵심 키워드
        category:      카테고리
        include_code:  예제 코드 포함 여부
        target_length: 목표 글자 수 (기본 2500자)

    Returns:
        완성된 프롬프트 문자열
    """
    # 예제 코드 포함 여부에 따라 추가 지시사항 선택
    code_rule = (
        "카테고리가 IT / 기술일 때만 필요한 경우 예제 코드를 포함"
        if include_code
        else "코드는 포함하지 말고 일반 독자가 읽기 쉬운 설명으로 작성"
    )

    return f"""
아래 조건에 맞춰 티스토리 블로그 본문을 작성해줘.

제목: {title}
주제/키워드: {keyword}
카테고리: {CATEGORY_LABELS[category]}
카테고리 작성 방향: {category_instruction(category)}
목표 길이: 약 {target_length}자
{reference_image_instruction(has_reference_image)}

말투 규칙:
{STYLE_RULES}

추가 조건:
- 별도 목차를 만들지 말 것
- 정해진 양식이나 고정 안내문을 넣지 말 것
- 주제에 맞게 자연스러운 문단 흐름으로 작성
- 필요한 경우에만 번호를 사용하고, 번호 형식을 억지로 맞추지 말 것
- {code_rule}
- 티스토리에 그대로 붙여넣기 좋은 일반 텍스트로 작성
""".strip()


def seo_prompt(title: str, keyword: str, content_text: str) -> str:
    """
    완성된 본문을 기반으로 SEO 설명과 Tistory 태그를 요청하는 프롬프트를 생성합니다.
    본문은 너무 길 수 있으므로 앞 3000자만 전달합니다.

    Args:
        title:        블로그 제목
        keyword:      핵심 키워드
        content_text: 본문 텍스트 (최대 3000자까지만 사용)

    Returns:
        완성된 프롬프트 문자열
    """
    return f"""
아래 블로그 글의 SEO 설명과 태그를 작성해줘.

제목: {title}
핵심 키워드: {keyword}
본문:
{content_text[:3000]}

출력 형식:
SEO 설명: ...
태그: 태그1, 태그2, 태그3, 태그4, 태그5
""".strip()


# ───────────────────────────────────────────
# Fallback 응답 (API 키 없는 개발 환경용)
# ───────────────────────────────────────────

def fallback_response(prompt: str) -> str:
    """
    OpenAI API 키가 없을 때 화면/저장 흐름을 테스트할 수 있는 샘플 응답을 반환합니다.
    프롬프트 내용을 분석하여 제목 / SEO / 본문 중 적절한 샘플을 선택합니다.

    Args:
        prompt: 어떤 종류의 응답이 필요한지 판단하기 위한 프롬프트 원문

    Returns:
        해당 유형의 샘플 텍스트
    """
    keyword = (
        extract_prompt_value(prompt, "키워드")
        or extract_prompt_value(prompt, "핵심 키워드")
        or "FastAPI"
    )
    title = (
        extract_prompt_value(prompt, "제목")
        or f"{keyword} 기본 구조와 실무 사용 방법"
    )

    # 제목 후보 응답
    if "제목 후보" in prompt:
        return "\n".join([
            f"1. {keyword} 기본 개념과 실무 사용 방법",
            f"2. {keyword}를 사용할 때 알아두면 좋은 내용",
            f"3. {keyword} 구조와 동작 방식 정리",
            f"4. {keyword} 예제와 코드 설명",
            f"5. {keyword} 개발 시 자주 사용하는 패턴",
        ])

    # SEO 응답
    if "SEO 설명" in prompt:
        return f"SEO 설명: {keyword}에 대해 쉽게 정리한 블로그 글입니다.\n태그: {keyword}, 블로그, 정보, 후기, 정리"

    # 기본 본문 응답
    return f"""{keyword}에 대해 정리해보겠습니다.

쉽게 얘기하면, 이 주제는 처음 볼 때 어렵게 느껴질 수 있지만 핵심만 잡으면 생각보다 단순합니다.

예를 들어 실제로 사용할 상황을 먼저 떠올리면 이해가 훨씬 쉽습니다. 무엇을 알아야 하는지, 어떤 점을 조심해야 하는지, 내가 직접 적용할 때 어떤 기준으로 판단하면 되는지를 중심으로 보면 됩니다.

정리하면 {keyword}는 단순히 정보만 보는 것보다 내 상황에 맞게 해석하는 것이 중요합니다. 필요한 부분부터 확인하고, 실제로 써볼 수 있는 방식으로 접근하면 더 자연스럽게 이해할 수 있습니다."""


def extract_prompt_value(prompt: str, key: str) -> str:
    """
    프롬프트 텍스트에서 "키: 값" 패턴으로 작성된 값을 추출합니다.
    fallback_response에서 키워드/제목을 동적으로 반영하기 위해 사용합니다.

    Args:
        prompt: 검색 대상 프롬프트 문자열
        key:    추출할 키 이름 (예: "키워드", "제목")

    Returns:
        추출된 값 문자열 (없으면 빈 문자열)
    """
    match = re.search(
        rf"^{re.escape(key)}:\s*(.+)$",
        prompt,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else ""
