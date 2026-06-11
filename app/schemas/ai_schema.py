from pydantic import BaseModel
from typing import Optional

from app.models.post import PostType


class TitleRequest(BaseModel):
    keyword: str
    post_type: PostType
    reference_image_data_url: Optional[str] = None


class OutlineRequest(BaseModel):
    title: str
    keyword: str
    post_type: PostType
    reference_image_data_url: Optional[str] = None


class ContentRequest(BaseModel):
    title: str
    keyword: str
    post_type: PostType
    outline: str
    include_code: bool = False
    target_length: int = 2500
    reference_image_data_url: Optional[str] = None


class SeoRequest(BaseModel):
    title: str
    keyword: str
    content_text: str


class AiResponse(BaseModel):
    result: str
