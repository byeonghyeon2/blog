# Tistory IT Blog Writer

Tistory에 복사해서 발행하기 좋은 IT 기술 블로그 글을 생성하고 검수하는 개인용 MVP 도구입니다.

## 주요 방향

- 블로그 주제: IT 기술
- 발행 방식: 자동 발행 없이 Tistory에 직접 복사
- 글 스타일: 짧고 명확한 설명, 번호형 목차, 실무 중심 문체
- 기술 스택: HTML/CSS/JavaScript/jQuery, FastAPI, MySQL

## 실행 준비

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

기본 설정은 로컬 SQLite를 사용합니다. 별도 설정 없이도 화면과 저장 기능을 먼저 확인할 수 있습니다.

```env
DATABASE_URL=sqlite:///./work/blog_writer.db
OPENAI_API_KEY=
```

## MySQL 저장 설정

글 저장 시 MySQL에 저장하려면 `.env`의 `DATABASE_URL`을 실제 계정 정보로 바꾸고, MySQL에 `blog_writer` 데이터베이스를 미리 생성해야 합니다.

```sql
CREATE DATABASE blog_writer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

예시:

```env
DATABASE_URL=mysql+pymysql://root:실제비밀번호@localhost:3306/blog_writer?charset=utf8mb4
```

별도 사용자를 만들고 싶다면 MySQL에서 아래처럼 계정을 생성할 수 있습니다.

```sql
CREATE USER 'blog_writer'@'localhost' IDENTIFIED BY '원하는비밀번호';
GRANT ALL PRIVILEGES ON blog_writer.* TO 'blog_writer'@'localhost';
FLUSH PRIVILEGES;
```

그 경우 `.env`는 아래처럼 설정합니다.

```env
DATABASE_URL=mysql+pymysql://blog_writer:원하는비밀번호@localhost:3306/blog_writer?charset=utf8mb4
```

`.env`를 수정한 뒤에는 FastAPI 서버를 재시작해야 변경된 DB 설정이 적용됩니다.

## 실행

```powershell
uvicorn app.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000`으로 접속합니다.

## 현재 MVP 기능

- 키워드 기반 제목, 목차, 본문, SEO 생성
- devbeg 스타일 규칙 기반 프롬프트
- 글 저장, 목록 조회, 상세 수정
- 검수 체크리스트
- Tistory 복사용 텍스트/HTML 복사
- OpenAI API 키가 없을 때도 동작하는 샘플 생성 fallback
