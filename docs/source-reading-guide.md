# 소스 분석 순서

이 프로젝트는 화면에서 입력한 값을 FastAPI로 보내고, AI 생성 결과를 다시 화면에 표시한 뒤 MySQL에 저장하는 구조입니다.

## 1. 화면 구조 먼저 보기

1. `frontend/index.html`
   - 글 목록 화면과 글 작성 화면의 HTML 구조를 확인합니다.
   - 작성 화면은 `글 생성 조건` 영역과 `생성 결과 / 최종 미리보기` 영역으로 나뉩니다.

2. `frontend/assets/css/style.css`
   - `create-stack`: 글 작성 화면 전체 배치입니다.
   - `create-top-row`: 좌측 생성 조건, 우측 생성 결과를 같은 줄에 배치합니다.
   - `panel--input`: 좌측 상단 생성 조건 입력 영역입니다.
   - `panel--editor`: 우측 상단 생성 결과 편집 영역입니다.
   - `preview-panel`, `post-preview`: 하단 전체 폭에서 실제 블로그 글처럼 보이게 만드는 미리보기 영역입니다.

## 2. 프론트 동작 흐름 보기

1. `frontend/assets/js/app.js`
   - `generateSelected()`: 생성하기 버튼을 눌렀을 때 실행되는 시작점입니다.
   - `generateTitle()`, `generateOutline()`, `generateContent()`, `generateSeo()`: 생성 항목별 API 호출 함수입니다.
   - `updatePostPreview()`: 제목, 목차, 본문, SEO 값을 모아 최종 미리보기를 갱신합니다.
   - `savePost()`: 현재 작성한 글을 MySQL에 저장하도록 백엔드 API를 호출합니다.

## 3. AI API 흐름 보기

1. `app/routers/ai_router.py`
   - `/api/ai/title`, `/api/ai/outline`, `/api/ai/content`, `/api/ai/seo` 요청을 받습니다.
   - OpenAI 오류를 사용자가 이해할 수 있는 메시지로 바꿔줍니다.

2. `app/services/ai_service.py`
   - 사용자 스타일 규칙과 프롬프트를 관리합니다.
   - 참고 이미지가 있으면 OpenAI 요청에 함께 전달합니다.

3. `app/schemas/ai_schema.py`
   - 프론트에서 백엔드로 보내는 AI 요청 데이터 구조입니다.

## 4. 글 저장 흐름 보기

1. `app/routers/post_router.py`
   - 글 생성, 수정, 삭제, 목록 조회 API를 담당합니다.

2. `app/models/post.py`
   - MySQL에 저장되는 글 테이블 구조입니다.

3. `app/core/database.py`
   - MySQL 연결과 테이블 생성 흐름을 확인합니다.

## 5. 설정 파일 보기

1. `app/core/config.py`
   - `.env` 값을 읽어 DB와 OpenAI 설정으로 사용합니다.

2. `.env`
   - 실제 MySQL 계정과 OpenAI API 키를 넣는 로컬 설정 파일입니다.
   - 이 파일은 Git에 올리지 않습니다.
