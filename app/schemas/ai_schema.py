from pydantic import BaseModel

from app.models.post import PostType


class TitleRequest(BaseModel):
    keyword: str
    post_type: PostType


class OutlineRequest(BaseModel):
    title: str
    keyword: str
    post_type: PostType


class ContentRequest(BaseModel):
    title: str
    keyword: str
    post_type: PostType
    outline: str
    include_code: bool = False
    target_length: int = 2500


class SeoRequest(BaseModel):
    title: str
    keyword: str
    content_text: str


class AiResponse(BaseModel):
    result: str
