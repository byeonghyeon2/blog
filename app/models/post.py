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


class BlogCategory(StrEnum):
    # 블로그 글의 주제 카테고리입니다.
    IT = "IT"
    FINANCE = "FINANCE"
    FOOD = "FOOD"
    TRAVEL = "TRAVEL"
    LIFESTYLE = "LIFESTYLE"


class Post(Base):
    # 생성된 블로그 글의 현재 버전을 저장하는 메인 테이블입니다.
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_keyword: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[BlogCategory] = mapped_column(Enum(BlogCategory), default=BlogCategory.IT)
    status: Mapped[PostStatus] = mapped_column(Enum(PostStatus), default=PostStatus.DRAFT)
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    seo_description: Mapped[Optional[str]] = mapped_column(String(300))
    tags_text: Mapped[Optional[str]] = mapped_column(String(500))
    tistory_url: Mapped[Optional[str]] = mapped_column(String(500))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
