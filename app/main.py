"""
main.py - FastAPI 애플리케이션 엔트리포인트

앱 초기화, 미들웨어 설정, 라우터 등록, 정적 파일 서빙을 담당합니다.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.core.database import Base, engine
from app.routers import ai_router, dashboard_router, post_router


# ── DB 테이블 자동 생성 ──────────────────────────────────────────────────
# 앱 시작 시 SQLAlchemy 모델을 기반으로 테이블이 없으면 자동 생성합니다.
# 운영 환경에서는 Alembic 같은 마이그레이션 도구 사용을 권장합니다.
Base.metadata.create_all(bind=engine)


def ensure_generation_log_token_columns() -> None:
    """
    기존 로컬 DB에 generation_logs 테이블이 이미 있는 경우,
    create_all만으로는 새 컬럼이 추가되지 않습니다.
    MVP 단계에서는 간단한 자동 보정으로 토큰 사용량 컬럼을 추가합니다.
    """
    inspector = inspect(engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("generation_logs")
    }
    required_columns = {
        "prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
        "total_tokens": "INTEGER",
    }

    with engine.begin() as connection:
        for name, column_type in required_columns.items():
            if name not in columns:
                connection.execute(
                    text(f"ALTER TABLE generation_logs ADD COLUMN {name} {column_type}")
                )


ensure_generation_log_token_columns()

app = FastAPI(title="Naver Blog Writer")

# ── CORS 미들웨어 설정 ──────────────────────────────────────────────────
# 프론트엔드 정적 파일과 API가 같은 서버에서 제공되므로 기본적으로 열려있어도 무방합니다.
# 필요 시 allow_origins를 특정 도메인으로 제한하세요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ──────────────────────────────────────────────────────────
app.include_router(post_router.router)
app.include_router(ai_router.router)
app.include_router(dashboard_router.router)

# ── 정적 파일 서빙 ───────────────────────────────────────────────────────
# /api 경로는 라우터가 먼저 처리하므로 충돌하지 않습니다.
# html=True: 경로 요청 시 index.html을 자동으로 반환합니다.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
