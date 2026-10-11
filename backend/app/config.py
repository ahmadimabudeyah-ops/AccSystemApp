"""Central configuration — env-driven, JOD/Amman defaults."""
import os
from datetime import timedelta

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:  # pragma: no cover
    pass


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-12345")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-12345")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://accounting:accounting123@localhost:5432/accounting_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_reset_on_return": "rollback"}
    JSON_AS_ASCII = False
    JWT_TOKEN_LOCATION = ["headers"]
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "JOD")
    DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Amman")
    BCRYPT_LOG_ROUNDS = int(os.getenv("BCRYPT_LOG_ROUNDS", "12"))
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600")))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", "2592000")))
    LOGIN_RATELIMIT = os.getenv("LOGIN_RATELIMIT", "10 per minute")
    PASSWORD_MIN_LENGTH = 8


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    BCRYPT_LOG_ROUNDS = 4


def get_config(name: str | None = None):
    name = name or os.getenv("FLASK_ENV", "development")
    if name == "production":
        for key in ("SECRET_KEY", "JWT_SECRET_KEY"):
            if os.getenv(key, "").startswith("dev-") or len(os.getenv(key, "")) < 32:
                raise RuntimeError(f"{key} must be a strong value (>=32 chars) in production")
        return ProductionConfig
    if name == "testing":
        return TestingConfig
    return DevelopmentConfig
