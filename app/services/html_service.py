"""
html_service.py - 텍스트 → 네이버 블로그용 HTML 변환 서비스

블로그 본문 텍스트를 네이버 블로그 에디터에 붙여넣기 적합한 단순 HTML로 변환합니다.

변환 규칙:
    - 코드 블록(```…```)    → <pre><code>…</code></pre>
    - 숫자점 시작 줄 (1. …) → <h2>…</h2> (대목차)
    - 숫자괄호/하이픈 (1) / 1-1.) → <p>…</p> (소목차/설명)
    - 일반 문단              → <p>…</p> (줄바꿈은 <br>로 처리)
"""

import html
import re


def text_to_tistory_html(text: str) -> str:
    """
    일반 텍스트 본문을 네이버 블로그 에디터에 붙여넣기 쉬운 단순 HTML로 변환합니다.

    처리 순서:
        1. HTML 특수문자 이스케이프 (XSS 방지)
        2. 코드 블록(```) 치환 → <pre><code>
        3. 빈 줄 기준으로 문단 분리
        4. 각 문단의 첫 줄 패턴으로 태그 결정

    Args:
        text: 변환할 원본 텍스트 (None이나 빈 문자열도 허용)

    Returns:
        네이버 블로그 에디터에 붙여넣기 적합한 HTML 문자열
    """
    if not text:
        return ""

    # 1단계: HTML 특수문자를 안전하게 이스케이프
    escaped = html.escape(text)

    # 2단계: 코드 블록(```...```) → <pre><code>...</code></pre> 치환
    #        DOTALL 플래그로 코드 블록 내 줄바꿈도 포함
    escaped = re.sub(
        r"```(.*?)```",
        r"<pre><code>\1</code></pre>",
        escaped,
        flags=re.DOTALL,
    )

    paragraphs = []

    # 3단계: 빈 줄 기준으로 문단을 나누어 각각 태그 적용
    for block in escaped.split("\n\n"):
        line = block.strip()
        if not line:
            continue

        # 이미 <pre><code> 블록으로 변환된 경우 그대로 사용
        if line.startswith("<pre><code>"):
            paragraphs.append(line)

        # 대목차: "1. 텍스트" 형태 → <h2>
        elif re.match(r"^\d+\.\s", line):
            paragraphs.append(f"<h2>{line}</h2>")

        # 소목차: "1) 텍스트" 또는 "1-1. 텍스트" 형태 → <p>
        elif re.match(r"^\d+\)\s", line) or re.match(r"^\d+-\d+\.\s", line):
            paragraphs.append(f"<p>{line}</p>")

        # 일반 문단: 단락 내 줄바꿈은 <br>로 변환
        else:
            paragraphs.append(f"<p>{line.replace(chr(10), '<br>')}</p>")

    return "\n".join(paragraphs)
