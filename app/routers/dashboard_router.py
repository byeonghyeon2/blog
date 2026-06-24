"""
dashboard_router.py - 대시보드 요약 API

엔드포인트:
    GET /api/dashboard/summary - 전체 글 수 + 상태별 글 수 반환
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.post import Post, PostStatus


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    """
    대시보드 상단에 표시할 요약 정보를 반환합니다.

    모든 PostStatus 열거값을 순회하며 각 상태별 글 수를 계산합니다.
    프론트엔드에서는 status_counts["DRAFT"], ["REVIEWING"], ["PUBLISHED"] 등으로 접근합니다.

    Returns:
        dict: {
            "total": int,                          # 전체 글 수
            "status_counts": { status: count, … } # 상태별 글 수
        }
    """
    total = db.query(Post).count()

    # PostStatus 열거값을 모두 순회하여 상태별 카운트 딕셔너리 생성
    counts = {
        status.value: db.query(Post).filter(Post.status == status).count()
        for status in PostStatus
    }

    return {"total": total, "status_counts": counts}
