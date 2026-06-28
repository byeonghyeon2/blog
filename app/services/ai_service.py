"""
ai_service.py - OpenAI 기반 블로그 글 생성 서비스

주요 기능:
    - OpenAI Responses API 호출 (generate_text)
    - 카테고리별 프롬프트 생성 (title / content / seo)
    - API 키 없는 개발 환경용 fallback 응답 (fallback_response)
"""

import re
from dataclasses import dataclass
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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

NAVER_BLOG_RULES = """
- 네이버 블로그에 바로 복사해서 붙여넣기 좋은 일반 텍스트로 작성
- 검색될 만한 핵심 표현은 제목, 첫 문단, 중간 소제목에 자연스럽게 한 번씩만 배치
- 긴 줄글보다 짧은 문단, 사진 삽입 위치, 간단한 코멘트, 정보 목록을 섞어서 작성
- 문단은 2~4문장 정도로 짧게 끊고, 모바일에서 읽기 좋게 여백을 둔 느낌으로 구성
- 과도한 키워드 반복, 광고 문구, 이모지 남발, 억지 후기체는 피하기
- 마지막에는 태그 후보를 본문과 분리해서 적기 좋은 단어 중심으로 구성
""".strip()

MEMO_REWRITE_RULES = """
- 사용자 작성 메모는 원문이 아니라 글감과 의도 파악용 자료로만 사용
- 사용자가 쓴 문장을 그대로 복사하거나 문단 순서를 그대로 따라가지 말 것
- 메모의 말투, 감정, 관점은 유지하되 표현은 블로그 독자가 이해하기 쉬운 단어로 다시 작성
- 애매한 표현, 줄임말, 혼잣말은 자연스러운 설명 문장으로 풀어쓰기
- 핵심 팁은 살리고 중복되거나 거친 표현은 덜어내기
- 사용자가 쓴 표현 중 꼭 필요한 표현만 일부 살리고, 전체 문장은 새로 구성
""".strip()

CATEGORY_LABELS: dict[BlogCategory, str] = {
    BlogCategory.IT:        "IT / 기술",
    BlogCategory.FINANCE:   "금융 / 재테크",
    BlogCategory.FOOD:      "맛집 / 음식",
    BlogCategory.TRAVEL:    "여행 / 장소",
    BlogCategory.LIFESTYLE: "생활 / 리뷰",
}

CATEGORY_FORMAT_RULES: dict[BlogCategory, str] = {
    BlogCategory.IT: """
- 문제 상황 또는 사용 계기를 짧게 설명
- [사진/화면 1 삽입] 뒤에 화면에서 봐야 할 포인트를 한두 문장으로 설명
- 설정 방법, 주의점, 체크리스트를 목록으로 정리
- 코드가 필요하면 아주 짧게 넣고 바로 아래에 쉬운 설명 추가
""".strip(),
    BlogCategory.FINANCE: """
- 핵심 내용을 먼저 요약하고, 조건/장점/리스크를 분리
- 숫자나 조건은 목록으로 정리해서 오해를 줄이기
- 투자 권유처럼 쓰지 말고 판단 기준과 주의점 중심으로 작성
""".strip(),
    BlogCategory.FOOD: """
- 사진 위주 맛집 글처럼 구성: 사진 위치 표시 → 짧은 코멘트 → 정보 목록
- 맛, 분위기, 웨이팅, 가격대, 추천 메뉴, 재방문 의사를 분리해서 작성
- 말투는 과장 없이 담백하게, 직접 다녀온 사람이 알려주는 느낌으로 작성
- 참고 스타일은 담백한 개인 맛집 기록 느낌만 반영하고 문장이나 표현은 따라 쓰지 않기
""".strip(),
    BlogCategory.TRAVEL: """
- 동선, 시간대, 비용, 준비물, 주의점을 목록으로 정리
- 사진 위치마다 그 장면에서 독자가 알아야 할 팁을 짧게 덧붙이기
- 감상은 담백하게 쓰고 실제 이동/방문에 도움이 되는 정보 중심으로 작성
""".strip(),
    BlogCategory.LIFESTYLE: """
- 사용 계기, 실제 사용감, 장점, 아쉬운 점, 추천 대상을 분리
- 사진 위치마다 어떤 부분을 보면 되는지 짧은 코멘트 추가
- 협찬 느낌보다 개인 기록과 실사용 후기처럼 담백하게 작성
""".strip(),
}


REFERENCE_BLOG_STYLE_RULES: dict[BlogCategory, str] = {
    BlogCategory.FOOD: """
- 참고한 네이버 맛집 블로그들의 공통 구성을 반영하되, 특정 블로그의 문장/표현/별명/고정 멘트는 따라 쓰지 말 것
- 제목은 지역명 + 상호명 또는 메뉴명 + 핵심 장점이 자연스럽게 들어가게 작성
- 첫 문단은 방문 계기나 기대감, 주변 일정, 지인 추천, 우연히 들른 상황처럼 개인적인 맥락으로 시작
- 초반에 상호명, 주소, 영업시간, 휴무, 전화/예약, 주차, 웨이팅, 대표 메뉴, 방문일 중 확인 가능한 정보를 짧은 정보 블록처럼 정리
- 본문 흐름은 외관/가는 길/주차 → 매장 분위기/좌석 → 메뉴판/주문 메뉴 → 기본찬/세팅 → 음식별 맛과 양 → 이용 팁 → 총평 순서를 기본으로 사용
- 사진이 있으면 사진 순서에 맞춰 [사진 N 삽입: 외관], [사진 N 삽입: 메뉴판], [사진 N 삽입: 대표 메뉴]처럼 실제 네이버 글에 붙여 넣기 쉬운 위치를 촘촘히 배치
- 맛 평가는 '맛있다'만 반복하지 말고 식감, 온도, 간, 재료, 양, 조합, 재방문 의사를 구체적으로 적기
- 주차, 웨이팅, 예약, 혼밥/데이트/가족 모임 가능 여부, 아이 동반, 포장 여부 같은 실사용 정보를 빠뜨리지 않기
- 마지막에는 이런 사람에게 추천, 아쉬운 점 한 줄, 재방문 의사, 태그 후보를 분리해 정리
- 말투는 담백하게 쓰되 너무 홍보글처럼 과장하지 말고, 직접 다녀온 사람이 알려주는 기록처럼 쓰기
""".strip(),
    BlogCategory.TRAVEL: """
- 참고한 네이버 여행/장소 블로그들의 공통 구성을 반영하되, 특정 블로그의 문장/표현/고정 멘트는 따라 쓰지 말 것
- 제목은 지역명 + 장소명 + 계절/코스/핵심 장점이 자연스럽게 들어가게 작성
- 첫 문단은 방문 시점, 계절감, 왜 이 장소를 골랐는지, 당일치기/1박2일/코스 여부를 짧게 설명
- 초반에 위치, 주차, 입장료, 운영시간, 소요시간, 방문일, 반려동물/아이 동반, 예약 여부 중 확인 가능한 정보를 기본 정보 블록처럼 정리
- 본문 흐름은 이동/주차 → 입구/첫인상 → 주요 동선 → 포토존/볼거리 → 주변 코스/먹거리 → 소요시간/주의점 → 추천 대상 순서를 기본으로 사용
- 사진이 있으면 장소의 흐름에 맞춰 [사진 N 삽입: 입구], [사진 N 삽입: 대표 풍경], [사진 N 삽입: 포토존]처럼 독자가 따라가기 쉬운 위치를 배치
- 계절형 장소는 개화 상황, 날씨, 그늘, 혼잡도, 방문 시간대, 준비물처럼 실제 방문 전 필요한 정보를 우선 작성
- 코스형 글은 1번, 2번, 3번처럼 동선이 보이게 쓰되 각 구간마다 짧은 감상과 실용 팁을 함께 넣기
- 마지막에는 추천 방문 시간, 같이 묶기 좋은 코스, 아쉬운 점/주의점, 태그 후보를 분리해 정리
- 말투는 정보 전달 중심으로 담백하게 쓰고, 풍경 묘사는 길게 늘이지 말고 사진 코멘트와 실사용 팁 위주로 작성
""".strip(),
}


def reference_blog_style_rules(category: BlogCategory) -> str:
    rules = REFERENCE_BLOG_STYLE_RULES.get(category)
    if not rules:
        return ""

    return f"""

참고 블로그 기반 구성 규칙:
{rules}
""".rstrip()


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


def generate_text(prompt: str, reference_image_data_urls: list[str] | str | None = None) -> str:
    """
    기존 호출부 호환을 위해 텍스트만 반환합니다.
    토큰 사용량까지 필요한 곳에서는 generate_text_with_usage를 사용합니다.
    """
    return generate_text_with_usage(prompt, reference_image_data_urls).text


def normalize_image_urls(reference_image_data_urls: list[str] | str | None = None) -> list[str]:
    if not reference_image_data_urls:
        return []
    if isinstance(reference_image_data_urls, str):
        return [reference_image_data_urls]
    return [url for url in reference_image_data_urls if url]


def generate_text_with_usage(prompt: str, reference_image_data_urls: list[str] | str | None = None) -> GeneratedText:
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
    image_urls = normalize_image_urls(reference_image_data_urls)
    user_content: str | list[dict[str, object]]
    if image_urls:
        user_content = [{"type": "text", "text": prompt}]
        user_content.extend(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                },
            }
            for image_url in image_urls
        )
    else:
        user_content = prompt

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": "너는 네이버 블로그 글을 작성하는 한국어 블로거다."},
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

def reference_image_instruction(image_count: int = 0) -> str:
    """
    사용자가 올린 참고 이미지를 어떻게 활용할지 프롬프트에 추가합니다.
    이미지 내용과 사용자가 적은 메모를 함께 해석하되, 말투는 사용자 메모를 우선하도록 제한합니다.
    """
    if image_count <= 0:
        return ""

    return f"""

참고 방식:
- 첨부된 참고 이미지 {image_count}장을 각각 분석해서 글의 소재로 활용
- 사용자가 작성 메모에서 사진 이야기를 했다면 이미지에서 확인되는 내용을 자연스럽게 보강
- 이미지 속 텍스트나 정보가 불확실하면 단정하지 말고 "사진상으로는", "보기에는"처럼 조심스럽게 표현
- 본문에는 적절한 위치마다 [사진 1 삽입: 사진 내용에 맞는 짧은 설명] 형식의 줄을 넣기
- 여러 장이면 사진 번호 순서대로 배치하되, 내용 흐름에 맞게 위치를 조정
- 사진 삽입 줄 바로 아래에는 1~2문장 정도의 짧은 코멘트를 작성
- 최종 말투와 강조점은 사용자 작성 메모에서 파악하되, 문장은 그대로 가져오지 말고 새로 다듬어 작성
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


def title_prompt(keyword: str, category: BlogCategory, image_count: int = 0) -> str:
    """
    사용자의 작성 메모와 카테고리를 기반으로 제목 후보 5개를 요청하는 프롬프트를 생성합니다.

    Args:
        keyword:   사용자가 입력한 작성 메모
        category: 카테고리

    Returns:
        완성된 프롬프트 문자열
    """
    return f"""
아래 조건에 맞춰 네이버 블로그 제목 후보 5개를 작성해줘.

사용자 작성 메모:
{keyword}

카테고리: {CATEGORY_LABELS[category]}
카테고리 작성 방향: {category_instruction(category)}
{reference_image_instruction(image_count)}
{reference_blog_style_rules(category)}

말투 규칙:
{STYLE_RULES}

메모 재작성 규칙:
{MEMO_REWRITE_RULES}

조건:
- 네이버 블로그 검색에서 자연스럽게 보일 만한 제목으로 작성
- 사용자가 쓴 메모에서 핵심 주제, 의도, 감정, 말투를 먼저 파악
- 메모가 줄글이어도 그 안에서 검색될 만한 핵심어를 뽑아 제목에 반영
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
    image_count: int = 0,
) -> str:
    """
    제목과 사용자 작성 메모를 기반으로 실제 블로그 본문을 요청하는 프롬프트를 생성합니다.

    Args:
        title:         블로그 제목
        keyword:       사용자가 입력한 작성 메모
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
아래 조건에 맞춰 네이버 블로그 본문을 작성해줘.

제목: {title}
사용자 작성 메모:
{keyword}

카테고리: {CATEGORY_LABELS[category]}
카테고리 작성 방향: {category_instruction(category)}
목표 길이: 약 {target_length}자
{reference_image_instruction(image_count)}

말투 규칙:
{STYLE_RULES}

네이버 블로그 작성 규칙:
{NAVER_BLOG_RULES}

메모 재작성 규칙:
{MEMO_REWRITE_RULES}

카테고리별 구성 규칙:
{CATEGORY_FORMAT_RULES[category]}
{reference_blog_style_rules(category)}

추가 조건:
- 사용자가 쓴 메모를 단순 키워드가 아니라 초안 재료로 보고 핵심 주장, 경험, 팁, 감정을 분석
- 사용자가 알리고 싶어 하는 팁이나 강조점은 빠뜨리지 말고 본문에 자연스럽게 반영
- 사용자의 말투가 캐주얼하면 캐주얼하게, 담백하면 담백하게 맞춰 쓰되 원문 문장은 그대로 사용하지 말 것
- 부족한 배경 설명은 일반적으로 알려진 정보와 문맥을 바탕으로 보완하되, 최신 사실이나 불확실한 정보는 단정하지 말 것
- 사용자가 사진을 언급했거나 참고 이미지가 있으면 이미지에서 확인되는 내용도 본문에 자연스럽게 추가
- 별도 목차를 만들지 말 것
- 정해진 양식이나 고정 안내문을 넣지 말 것
- 전체를 긴 줄글로 쓰지 말고, 사진 위치 표시와 짧은 코멘트, 목록형 정보 전달을 섞어서 작성
- 독자가 바로 이해하기 어려운 단어는 쉬운 표현으로 바꾸고, 필요한 배경 설명을 짧게 덧붙일 것
- 필요한 경우에만 번호를 사용하고, 번호 형식을 억지로 맞추지 말 것
- {code_rule}
- 네이버 블로그에 그대로 붙여넣기 좋은 일반 텍스트로 작성
""".strip()


def seo_prompt(title: str, keyword: str, content_text: str) -> str:
    """
    완성된 본문을 기반으로 SEO 설명과 네이버 블로그 태그를 요청하는 프롬프트를 생성합니다.
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
사용자 작성 메모:
{keyword[:1000]}

본문:
{content_text[:3000]}

출력 형식:
SEO 설명: ...
태그: 태그1, 태그2, 태그3, 태그4, 태그5
""".strip()


def fetch_url_text(url: str, limit: int = 6000) -> str:
    """
    URL 기반 카드뉴스 생성에 사용할 페이지 본문을 가볍게 추출합니다.
    외부 사이트 구조가 제각각이라 완벽한 크롤러가 아니라, AI 입력용 요약 재료를 만드는 용도입니다.
    """
    if not url:
        return ""

    try:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; BlogWriter/1.0)",
            },
        )
        with urlopen(request, timeout=8) as response:
            content_type = response.headers.get("content-type", "")
            charset = "utf-8"
            match = re.search(r"charset=([\w-]+)", content_type, re.I)
            if match:
                charset = match.group(1)
            raw_html = response.read(300000)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return ""

    html = raw_html.decode(charset, errors="ignore")
    html = re.sub(r"(?is)<(script|style|noscript|svg).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit]


def instagram_cards_prompt(
    source_type: str,
    source_url: str | None,
    source_text: str,
    fetched_text: str,
    card_count: int,
    category: BlogCategory | None,
    purpose: str,
    style_note: str,
) -> str:
    """
    블로그 글, URL, 정보성 메모를 인스타 카드뉴스 원고로 바꾸는 프롬프트를 만듭니다.
    출력 형식을 고정해두면 프론트에서 카드별로 안정적으로 미리보기를 만들 수 있습니다.
    """
    safe_card_count = min(max(card_count or 6, 3), 10)
    category_text = CATEGORY_LABELS.get(category, "주제 제한 없음") if category else "주제 제한 없음"
    source_label = {
        "URL": "URL",
        "BLOG": "블로그 글",
        "TEXT": "정보성 글",
    }.get((source_type or "TEXT").upper(), "정보성 글")

    return f"""
아래 자료를 바탕으로 인스타 카드뉴스 원고를 작성해줘.

자료 유형: {source_label}
카테고리: {category_text}
목적: {purpose}
카드 수: {safe_card_count}장
원본 URL: {source_url or "없음"}

사용자가 입력한 자료:
{source_text[:7000]}

URL에서 추출한 참고 자료:
{fetched_text[:6000]}

참고 스타일 메모:
{style_note[:1000] or "아직 없음"}

말투 규칙:
{STYLE_RULES}

작성 규칙:
- 인스타 카드뉴스처럼 한 장에 하나의 메시지만 담기
- 첫 카드는 훅이 되는 제목, 마지막 카드는 저장/공유/댓글을 유도하는 정리 카드로 작성
- 카드별 본문은 2~4줄 안에서 짧게 작성
- 어려운 내용은 "쉽게 얘기하면", "예를 들어" 같은 표현으로 풀기
- 원본 내용을 그대로 복붙하지 말고 핵심만 재구성
- 과장된 광고 문구, 논문식 문체, 너무 딱딱한 표현 금지
- 이미지 설명은 실제 이미지 생성이 아니라 디자이너가 참고할 수 있는 장면 설명으로 작성

출력 형식은 반드시 아래 형식만 사용:
[카드 1]
제목: ...
본문: ...
이미지: ...

[카드 2]
제목: ...
본문: ...
이미지: ...

해시태그: #태그1 #태그2 #태그3 #태그4 #태그5
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
        extract_prompt_block(prompt, "사용자 작성 메모")
        or extract_prompt_value(prompt, "사용자 작성 메모")
        or extract_prompt_value(prompt, "작성 메모")
        or extract_prompt_value(prompt, "키워드")
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

[사진 1 삽입: 핵심 장면이나 첫인상을 보여주는 사진]

쉽게 얘기하면, 처음 보는 사람도 바로 이해할 수 있게 핵심만 먼저 잡아주는 글입니다.

알아두면 좋은 점
- 먼저 확인해야 할 포인트를 짧게 정리합니다.
- 실제로 겪을 수 있는 상황을 기준으로 설명합니다.
- 과하게 좋게만 쓰기보다 아쉬운 점도 담백하게 적습니다.

정리하면, {keyword}는 단순히 정보만 나열하기보다 직접 보는 사람이 바로 판단할 수 있게 구성하는 것이 좋습니다."""


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


def extract_prompt_block(prompt: str, key: str) -> str:
    """
    프롬프트에서 "키:\n여러 줄 값" 형태의 블록 값을 추출합니다.
    사용자 작성 메모처럼 줄글 입력을 fallback 응답에 반영하기 위해 사용합니다.
    """
    match = re.search(
        rf"^{re.escape(key)}:\s*\n(.+?)(?:\n\n[가-힣A-Za-z /]+:|\Z)",
        prompt,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""
