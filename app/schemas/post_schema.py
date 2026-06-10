from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.post import PostStatus, PostType


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CategoryCreate(BaseModel):
    name: str
    description: str | None = None
    sort_order: int = 0


class PostCreate(BaseModel):
    title: str
    topic_keyword: str
    post_type: PostType = PostType.CONCEPT
    category_id: int | None = None
    outline: str | None = None
    content_text: str | None = None
    content_html: str | None = None
    seo_description: str | None = None
    tags_text: str | None = None


class PostUpdate(BaseModel):
    title: str | None = None
    category_id: int | None = None
    status: PostStatus | None = None
    outline: str | None = None
    content_text: str | None = None
    content_html: str | None = None
    seo_description: str | None = None
    tags_text: str | None = None
    tistory_url: str | None = None


class PostOut(BaseModel):
    id: int
    category_id: int | None = None
    title: str
    topic_keyword: str
    post_type: PostType
    status: PostStatus
    outline: str | None = None
    content_text: str | None = None
    content_html: str | None = None
    seo_description: str | None = None
    tags_text: str | None = None
    tistory_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
