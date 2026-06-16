from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.post import BlogCategory, PostStatus


class PostCreate(BaseModel):
    title: str
    topic_keyword: str
    category: BlogCategory = BlogCategory.IT
    content_text: str | None = None
    content_html: str | None = None
    seo_description: str | None = None
    tags_text: str | None = None


class PostUpdate(BaseModel):
    title: str | None = None
    category: BlogCategory | None = None
    status: PostStatus | None = None
    content_text: str | None = None
    content_html: str | None = None
    seo_description: str | None = None
    tags_text: str | None = None
    tistory_url: str | None = None


class PostOut(BaseModel):
    id: int
    title: str
    topic_keyword: str
    category: BlogCategory
    status: PostStatus
    content_text: str | None = None
    content_html: str | None = None
    seo_description: str | None = None
    tags_text: str | None = None
    tistory_url: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
