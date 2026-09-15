from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "TechValley Cloud Instance Monitoring System"
    SECRET_KEY: str = "change-me-to-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    DATABASE_URL: str = "sqlite:///./monitoring.db"

    ANTHROPIC_API_KEY: str = ""

    # Shared short-lived state — values that must outlive a request but not a restart.
    # Empty keeps it in process memory, which is correct for a single worker only.
    REDIS_URL: str = ""
    REDIS_KEY_PREFIX: str = "techvalley:"

    # How long an LLM diagnosis is reused for an unchanged instance; 0 disables the cache
    DIAGNOSIS_CACHE_TTL_SECONDS: int = 1800

    # Business rules
    CPU_WARNING_THRESHOLD: float = 80.0
    LONG_STOPPED_HOURS: int = 48

    # Monthly unit pricing by instance type (USD)
    PRICE_SMALL: float = 50.0
    PRICE_MEDIUM: float = 120.0
    PRICE_LARGE: float = 250.0

    # SLA thresholds (%) by contract plan
    SLA_PREMIUM: float = 99.9
    SLA_STANDARD: float = 99.0
    SLA_BASIC: float = 95.0


settings = Settings()

UNIT_PRICES = {
    "SMALL": settings.PRICE_SMALL,
    "MEDIUM": settings.PRICE_MEDIUM,
    "LARGE": settings.PRICE_LARGE,
}

SLA_THRESHOLDS = {
    "PREMIUM": settings.SLA_PREMIUM,
    "STANDARD": settings.SLA_STANDARD,
    "BASIC": settings.SLA_BASIC,
}
