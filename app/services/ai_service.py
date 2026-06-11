"""
ai_service.py - OpenAI 기반 블로그 글 생성 서비스

주요 기능:
    - OpenAI Responses API 호출 (generate_text)
    - 글 유형별 프롬프트 생성 (title / outline / content / seo)
    - API 키 없는 개발 환경용 fallback 응답 (fallback_response)
"""

import re

from openai import OpenAI

from app.core.config import settings
from app.models.post import PostType


# ───────────────────────────────────────────
# 상수 정의
# ───────────────────────────────────────────

# 모든 프롬프트에 공통으로 적용되는 글쓰기 스타일 규칙
STYLE_RULES = """
- 설명은 짧고 명확하게 작성
- 번호형 목차 사용
- 큰 목차는 1. 2. 3. 형식
- 하위 항목은 1), 1-1. 형식
- "쉽게 얘기하면", "예를 들어" 같은 표현 사용
- 실무에서 어떻게 쓰는지 중심으로 설명
- 과장된 문구, 광고성 문구, 논문식 문체 금지
- 코드가 있으면 코드 설명을 번호로 풀어서 작성
""".strip()

# PostType 열거값 → 한글 표시명 매핑
POST_TYPE_LABELS: dict[PostType, str] = {
    PostType.CONCEPT:      "개념 설명형",
    PostType.TOOL_GUIDE:   "툴 사용법형",
    PostType.ERROR_FIX:    "에러 해결형",
    PostType.COMPARE:      "비교 분석형",
    PostType.CODE_EXAMPLE: "예제 코드형",
}


# ───────────────────────────────────────────
# 핵심 생성 함수
# ───────────────────────────────────────────

def generate_text(prompt: str, reference_image_data_url: str | None = None) -> str:
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
        return fallback_response(prompt)

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
            {"role": "system", "content": "너는 티스토리 IT 블로그 글을 작성하는 한국어 기술 블로거다."},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


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
- 참고 이미지의 디자인 요소를 설명하지 말고, 블로그 글 구조에만 반영
- 최종 말투와 작성 습관은 반드시 아래 문체 규칙을 우선 적용
""".rstrip()


def title_prompt(keyword: str, post_type: PostType, has_reference_image: bool = False) -> str:
    """
    키워드와 글 유형을 기반으로 제목 후보 5개를 요청하는 프롬프트를 생성합니다.

    Args:
        keyword:   사용자가 입력한 핵심 키워드
        post_type: 글 유형 (개념설명 / 툴가이드 / 에러해결 / 비교분석 / 예제코드)

    Returns:
        완성된 프롬프트 문자열
    """
    return f"""
아래 조건에 맞춰 티스토리 IT 블로그 제목 후보 5개를 작성해줘.

키워드: {keyword}
글 유형: {POST_TYPE_LABELS[post_type]}
{reference_image_instruction(has_reference_image)}

문체 규칙:
{STYLE_RULES}

조건:
- 제목만 번호 목록으로 작성
- 실무 개발자가 검색할 만한 표현 사용
- 과장된 제목 금지
""".strip()


def outline_prompt(title: str, keyword: str, post_type: PostType, has_reference_image: bool = False) -> str:
    """
    선택된 제목으로 번호형 목차를 요청하는 프롬프트를 생성합니다.

    Args:
        title:     사용자가 선택한 블로그 제목
        keyword:   핵심 키워드
        post_type: 글 유형

    Returns:
        완성된 프롬프트 문자열
    """
    return f"""
아래 제목의 티스토리 IT 블로그 목차를 작성해줘.

제목: {title}
키워드: {keyword}
글 유형: {POST_TYPE_LABELS[post_type]}
{reference_image_instruction(has_reference_image)}

문체 규칙:
{STYLE_RULES}

조건:
- 큰 목차는 1. 2. 3. 형식
- 필요한 경우 하위 항목은 1), 1-1. 형식
- 개념 설명, 실무 사용 이유, 예시, 정리 흐름으로 구성
""".strip()


def content_prompt(
    title: str,
    keyword: str,
    post_type: PostType,
    outline: str,
    include_code: bool,
    target_length: int,
    has_reference_image: bool = False,
) -> str:
    """
    목차를 기반으로 실제 블로그 본문을 요청하는 프롬프트를 생성합니다.

    Args:
        title:         블로그 제목
        keyword:       핵심 키워드
        post_type:     글 유형
        outline:       AI가 생성한 번호형 목차
        include_code:  예제 코드 포함 여부
        target_length: 목표 글자 수 (기본 2500자)

    Returns:
        완성된 프롬프트 문자열
    """
    # 예제 코드 포함 여부에 따라 추가 지시사항 선택
    code_rule = (
        "예제 코드를 포함하고 코드 설명을 번호로 풀어서 작성"
        if include_code
        else "코드는 꼭 필요할 때만 짧게 포함"
    )

    return f"""
아래 조건에 맞춰 티스토리 IT 블로그 본문을 작성해줘.

제목: {title}
키워드: {keyword}
글 유형: {POST_TYPE_LABELS[post_type]}
목표 길이: 약 {target_length}자
{reference_image_instruction(has_reference_image)}

목차:
{outline}

문체 규칙:
{STYLE_RULES}

추가 조건:
- 시작 안내문은 아래 3줄을 그대로 사용
※ 실제 프로젝트를 진행하며 얻은 지식을 정리한 내용입니다.
※ 이론적인 내용보단 실무에서 사용하는 방식 위주로 작성하였습니다.
※ 잘못된 내용이 있다면 댓글로 지적 부탁드리겠습니다.
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
    프롬프트 내용을 분석하여 제목 / 목차 / SEO / 본문 중 적절한 샘플을 선택합니다.

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

    # 목차 응답
    if "목차" in prompt:
        return "\n".join([
            f"1. {keyword}란?",
            f"2. {keyword}를 사용하는 이유",
            f"3. {keyword} 기본 구조",
            f"4. {keyword} 사용 예시",
            "5. 정리",
        ])

    # SEO 응답
    if "SEO 설명" in prompt:
        return (
            f"SEO 설명: {keyword}의 기본 개념과 실무 사용 방법을 정리한 글입니다.\n"
            f"태그: {keyword}, IT, 개발, 실무정리, 웹개발"
        )

    # 기본 본문 응답
    return f"""※ 실제 프로젝트를 진행하며 얻은 지식을 정리한 내용입니다.
※ 이론적인 내용보단 실무에서 사용하는 방식 위주로 작성하였습니다.
※ 잘못된 내용이 있다면 댓글로 지적 부탁드리겠습니다.

1. {keyword}란?

1) {keyword}는 개발 과정에서 특정 문제를 해결하거나 기능을 구현할 때 사용하는 기술입니다.
2) 쉽게 얘기하면, 반복해서 작성해야 하는 작업을 정리된 방식으로 처리하도록 도와주는 도구라고 볼 수 있습니다.
3) 실무에서는 코드 구조를 단순하게 만들고 유지보수를 편하게 하기 위해 사용하는 경우가 많습니다.

2. {keyword}를 사용하는 이유

1) 작업 흐름을 정리하기 좋습니다.
1-1. 기능별 역할을 나눠서 작성할 수 있습니다.
1-2. 예를 들어 화면, 서버, DB 처리 로직을 분리하면 수정할 때 확인해야 할 범위가 줄어듭니다.

2) 실무 적용이 쉽습니다.
2-1. 기본 개념만 이해하면 기존 프로젝트에도 단계적으로 적용할 수 있습니다.
2-2. 문제가 발생했을 때 원인을 추적하기도 비교적 편합니다.

3. 실무에서 사용하는 방식

1) 먼저 {keyword}가 필요한 상황인지 확인합니다.
2) 그 다음 작은 예제 코드로 동작 방식을 확인합니다.
3) 마지막으로 실제 프로젝트 구조에 맞게 적용합니다.

4. 정리

1) {keyword}는 개념만 보는 것보다 직접 적용해보는 것이 중요합니다.
2) 처음에는 작은 기능부터 테스트하는 방식이 좋습니다.
3) 이후 프로젝트 구조에 맞춰 조금씩 확장하면 됩니다."""


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
