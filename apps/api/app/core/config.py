from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"), env_ignore_empty=True, extra="ignore"
    )

    app_name: str = "星云智家售后服务智能体"
    environment: str = "development"
    api_prefix: str = "/api/ai/v1"
    legacy_api_prefix: str = "/api/v1"
    enable_legacy_api: bool = True
    secret_key: str = "change-me-before-production-at-least-32-bytes"
    jwt_issuer: str = "nebula-business-service"
    jwt_audience: str = "nebula-platform"
    access_token_minutes: int = 480
    database_url: str = "sqlite:///./aftersales.db"
    redis_url: str = "redis://localhost:6379/0"
    job_data_dir: str = "./data/jobs"
    job_lease_seconds: int = 120
    cors_origins: str = "http://localhost:5173"
    demo_mode: bool = True
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    business_service_url: str = ""
    business_service_enabled: bool = False
    business_service_timeout_seconds: float = 5.0
    business_service_token: str = ""

    llm_provider: str = "mock"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    embedding_provider: str = "hash"
    model_cache_dir: str = str(PROJECT_ROOT / ".model-cache")
    retrieval_top_k: int = 6
    evidence_threshold: float = 0.16
    cross_encoder_enabled: bool = False
    cross_encoder_model: str = "BAAI/bge-reranker-base"

    lightrag_base_url: str = ""
    lightrag_api_key: str = ""
    openviking_base_url: str = ""
    openviking_api_key: str = ""
    openviking_root_uri: str = "viking://resources/aftersales"
    external_retrieval_timeout_seconds: float = 30.0
    mem0_base_url: str = ""
    mem0_api_key: str = ""

    langfuse_enabled: bool = False
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_runtime(self) -> None:
        if not self.is_production:
            return
        errors: list[str] = []
        if self.secret_key == "change-me-before-production-at-least-32-bytes":
            errors.append("生产环境必须设置 SECRET_KEY")
        if self.demo_mode:
            errors.append("生产环境必须关闭 DEMO_MODE")
        if self.database_url.startswith("sqlite"):
            errors.append("生产环境必须使用 PostgreSQL")
        if self.bootstrap_admin_password and len(self.bootstrap_admin_password) < 12:
            errors.append("BOOTSTRAP_ADMIN_PASSWORD 至少需要 12 个字符")
        if errors:
            raise RuntimeError("；".join(errors))


@lru_cache
def get_settings() -> Settings:
    value = Settings()
    value.validate_runtime()
    return value


settings = get_settings()
