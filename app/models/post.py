from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PostStatus(StrEnum):
    # 글 작성 흐름을 관리하기 위한 상태값입니다.
    DRAFT = "DRAFT"
    REVIEWING = "REVIEWING"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class PostType(StrEnum):
    # IT 글의 성격에 따라 다른 프롬프트 템플릿을 적용합니다.
    CONCEPT = "CONCEPT"
    TOOL_GUIDE = "TOOL_GUIDE"
    ERROR_FIX = "ERROR_FIX"
    COMPARE = "COMPARE"
    CODE_EXAMPLE = "CODE_EXAMPLE"


class Post(Base):
    # 생성된 블로그 글의 현재 버전을 저장하는 메인 테이블입니다.
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    post_type: Mapped[PostType] = mapped_column(Enum(PostType), default=PostType.CONCEPT)
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=PostStatus.DRAFT)
    outline: Mapped[Optional[str]] = mapped_column(Text)
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    seo_description: Mapped[Optional[str]] = mapped_column(String(300))
    tags_text: Mapped[Optional[str]] = mapped_column(String(500))
    tistory_url: Mapped[Optional[str]] = mapped_column(String(500))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category")
    versions = relationship("PostVersion", cascade="all, delete-orphan")


class PostVersion(Base):
    # AI 생성본과 사용자가 수정한 버전을 이력으로 남기기 위한 테이블입니다.
    __tablename__ = "post_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    change_type: Mapped[str] = mapped_column(String(50), default="MANUAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
