"""
config.py - 애플리케이션 설정 관리

pydantic-settings를 사용하여 .env 파일과 환경변수에서 설정을 읽습니다.
설정값은 settings 싱글턴 객체를 통해 전체 앱에서 공유합니다.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    앱 전역 설정 클래스.
    .env 파일 또는 OS 환경변수에서 자동으로 값을 읽습니다.
    환경변수 이름은 필드명과 동일합니다 (대소문자 무시).

    Attributes:
        app_name:       애플리케이션 표시 이름
        database_url:   SQLAlchemy 연결 문자열 (SQLite 기본값)
        openai_api_key: OpenAI API 키 (없으면 fallback 모드로 동작)
        openai_model:   사용할 OpenAI 모델 ID
        openai_monthly_budget_usd: 화면에 표시할 월간 OpenAI 예산
        openai_initial_spend_usd: 앱 외부에서 이미 사용한 금액 보정값
    """

    app_name:       str = "Naver Blog Writer"
    database_url:   str = "sqlite:///./work/blog_writer.db"
    openai_api_key: str = ""
    openai_model:   str = "gpt-4.1-mini"
    openai_monthly_budget_usd: float = 10.0
    openai_initial_spend_usd: float = 0.02
    openai_input_price_per_1m_tokens: float = 0.75
    openai_output_price_per_1m_tokens: float = 4.50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )


# 전체 앱에서 공유하는 설정 싱글턴 인스턴스
settings = Settings()
