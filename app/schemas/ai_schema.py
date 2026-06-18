from pydantic import BaseModel, Field
from typing import Optional

from app.models.post import BlogCategory


class TitleRequest(BaseModel):
    keyword: str
    category: BlogCategory
    reference_image_data_url: Optional[str] = None
    reference_image_data_urls: list[str] = Field(default_factory=list)


class ContentRequest(BaseModel):
    title: str
    keyword: str
    category: BlogCategory
    include_code: bool = False
    target_length: int = 2500
    reference_image_data_url: Optional[str] = None
    reference_image_data_urls: list[str] = Field(default_factory=list)


class SeoRequest(BaseModel):
    title: str
    keyword: str
    content_text: str


class AiResponse(BaseModel):
    result: str
