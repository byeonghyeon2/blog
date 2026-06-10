"""
post_router.py - 블로그 글(Post) CRUD API 엔드포인트

엔드포인트:
    GET    /api/posts              - 글 목록 (상태/키워드 필터 지원)
    POST   /api/posts              - 글 생성
    GET    /api/posts/{id}         - 글 단일 조회
    PUT    /api/posts/{id}         - 글 수정
    DELETE /api/posts/{id}         - 글 삭제
    GET    /api/posts/{id}/versions - 글 버전 이력 조회
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.post import Post, PostVersion
from app.schemas.post_schema import PostCreate, PostOut, PostUpdate
from app.services.html_service import text_to_tistory_html


router = APIRouter(prefix="/api/posts", tags=["posts"])


def create_post_version(db: Session, post: Post, change_type: str) -> None:
    """
    현재 글 상태를 버전 이력(post_versions 테이블)에 저장합니다.
    수정 전에 호출하면 변경 전 스냅숏을 보존할 수 있습니다.

    Args:
        db:          SQLAlchemy DB 세션
        post:        버전을 저장할 Post ORM 객체
        change_type: 변경 유형 코드 (CREATE / UPDATE / MANUAL)
    """
    version_count = (
        db.query(PostVersion)
        .filter(PostVersion.post_id == post.id)
        .count()
    )
    db.add(
        PostVersion(
            post_id=post.id,
            version_no=version_count + 1,
            title=post.title,
            content_text=post.content_text,
            content_html=post.content_html,
            change_type=change_type,
        )
    )


@router.get("", response_model=list[PostOut])
def list_posts(
    status: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
):
    """
    저장된 글 목록을 최신순으로 반환합니다.
    status 파라미터로 특정 상태만, keyword로 제목/키워드 포함 검색이 가능합니다.

    Args:
        status:  필터링할 상태 코드 (DRAFT, REVIEWING, READY, PUBLISHED, ARCHIVED)
        keyword: title 또는 topic_keyword에서 부분 일치 검색할 문자열
    """
    query = db.query(Post)

    if status:
        query = query.filter(Post.status == status)

    if keyword:
        # 제목 또는 키워드 중 하나라도 포함되면 결과에 포함합니다.
        query = query.filter(
            Post.title.contains(keyword)
            | Post.topic_keyword.contains(keyword)
        )

    return query.order_by(Post.created_at.desc()).all()


@router.post("", response_model=PostOut)
def create_post(request: PostCreate, db: Session = Depends(get_db)):
    """
    새 글을 DB에 저장합니다.
    content_html이 요청에 없으면 content_text를 자동으로 HTML로 변환합니다.
    저장 후 초기 버전 이력(CREATE)을 생성합니다.
    """
    # content_html이 제공되지 않은 경우 텍스트로부터 자동 변환
    content_html = request.content_html or text_to_tistory_html(
        request.content_text or ""
    )

    post = Post(
        **request.model_dump(exclude={"content_html"}),
        content_html=content_html,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # 최초 생성 버전 이력 저장
    create_post_version(db, post, "CREATE")
    db.commit()

    return post


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    """
    단일 글 정보를 조회합니다.
    존재하지 않는 ID이면 404를 반환합니다.

    Args:
        post_id: 조회할 글의 PK
    """
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.put("/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    request: PostUpdate,
    db: Session = Depends(get_db),
):
    """
    기존 글을 수정합니다.
    수정 전 현재 상태를 버전 이력(UPDATE)으로 먼저 저장합니다.
    content_text가 변경되고 content_html이 별도로 제공되지 않으면
    content_html도 자동으로 재변환합니다.

    Args:
        post_id: 수정할 글의 PK
        request: 변경할 필드만 포함하는 부분 업데이트 스키마
    """
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # 변경 전 스냅숏 저장
    create_post_version(db, post, "UPDATE")

    # 요청에 포함된 필드만 업데이트 (exclude_unset=True)
    data = request.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(post, key, value)

    # content_text만 변경된 경우 HTML을 자동 재생성
    if "content_text" in data and "content_html" not in data:
        post.content_html = text_to_tistory_html(post.content_text or "")

    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    """
    글을 DB에서 삭제합니다.
    연결된 PostVersion 레코드는 cascade 설정에 의해 함께 삭제됩니다.
    존재하지 않는 ID이면 404를 반환합니다.

    Args:
        post_id: 삭제할 글의 PK
    """
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    db.delete(post)
    db.commit()
    return {"deleted": True}


@router.get("/{post_id}/versions")
def list_post_versions(post_id: int, db: Session = Depends(get_db)):
    """
    특정 글의 버전 이력을 최신순으로 반환합니다.
    AI 생성본(CREATE)과 사용자 수정본(UPDATE)을 모두 포함합니다.

    Args:
        post_id: 이력을 조회할 글의 PK
    """
    return (
        db.query(PostVersion)
        .filter(PostVersion.post_id == post_id)
        .order_by(PostVersion.version_no.desc())
        .all()
    )
