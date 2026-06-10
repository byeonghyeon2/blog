"""
category_router.py - 카테고리 관리 API

엔드포인트:
    GET  /api/categories - 카테고리 목록 조회 (정렬 순서 → 이름 순)
    POST /api/categories - 새 카테고리 등록
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.category import Category
from app.schemas.post_schema import CategoryCreate, CategoryOut


router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    """
    등록된 카테고리 목록을 sort_order → name 순으로 반환합니다.
    글 생성 화면의 카테고리 선택 드롭다운에서 사용합니다.
    """
    return (
        db.query(Category)
        .order_by(Category.sort_order, Category.name)
        .all()
    )


@router.post("", response_model=CategoryOut)
def create_category(request: CategoryCreate, db: Session = Depends(get_db)):
    """
    새 Tistory 카테고리 후보를 등록합니다.
    sort_order로 표시 순서를 제어할 수 있습니다.

    Args:
        request: 카테고리 이름, 설명, 정렬 순서를 담은 스키마
    """
    category = Category(
        name=request.name,
        description=request.description,
        sort_order=request.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
