"""
dashboard_router.py - 대시보드 요약 API

엔드포인트:
    GET /api/dashboard/summary - 전체 글 수 + 상태별 글 수 반환
    GET /api/dashboard/token-usage - 이번 달 AI 토큰/예상 비용 사용량 반환
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.generation_log import GenerationLog
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


@router.get("/token-usage")
def token_usage(db: Session = Depends(get_db)):
    """
    현재 앱에서 이번 달에 발생한 AI 생성 토큰/예상 비용 사용량을 반환합니다.
    OpenAI 계정 전체 사용량이 아니라 generation_logs와 설정된 보정값 기준입니다.
    """
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    used_tokens = (
        db.query(func.coalesce(func.sum(GenerationLog.total_tokens), 0))
        .filter(GenerationLog.created_at >= month_start)
        .scalar()
    )
    app_cost = (
        db.query(func.coalesce(func.sum(GenerationLog.estimated_cost_usd), 0.0))
        .filter(GenerationLog.created_at >= month_start)
        .scalar()
    )
    used_cost = float(app_cost or 0.0) + settings.openai_initial_spend_usd
    budget = settings.openai_monthly_budget_usd
    remaining = max(budget - used_cost, 0)
    usage_percent = round((used_cost / budget) * 100, 2) if budget else 0

    return {
        "used_tokens": int(used_tokens or 0),
        "used_cost_usd": round(used_cost, 4),
        "app_cost_usd": round(float(app_cost or 0.0), 4),
        "initial_spend_usd": settings.openai_initial_spend_usd,
        "budget_usd": budget,
        "remaining_usd": round(remaining, 4),
        "usage_percent": min(usage_percent, 100),
        "period": month_start.strftime("%Y-%m"),
    }
