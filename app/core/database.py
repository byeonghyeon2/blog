"""
database.py - SQLAlchemy 엔진 및 세션 설정

FastAPI 의존성 주입(Depends)과 함께 사용합니다.
각 API 요청마다 get_db()로 세션을 열고, 요청 처리 후 반드시 닫습니다.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# 전체 앱에서 공유하는 SQLAlchemy 엔진
# pool_pre_ping=True: 연결이 끊어진 경우 재연결을 시도합니다.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# autocommit=False: 명시적 commit/rollback 필요 (의도치 않은 자동 저장 방지)
# autoflush=False:  flush 타이밍을 명시적으로 제어
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """
    모든 ORM 모델이 상속받는 기본 클래스.
    이 클래스를 통해 메타데이터를 관리하고 테이블을 생성합니다.
    """
    pass


def get_db():
    """
    FastAPI 라우터에서 Depends(get_db)로 사용하는 DB 세션 생성기입니다.
    요청 처리 중 세션을 제공하고, 요청이 끝나면 반드시 세션을 닫습니다.
    예외가 발생해도 finally 블록에서 세션이 닫히는 것을 보장합니다.

    Yields:
        Session: 사용 가능한 SQLAlchemy DB 세션
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
