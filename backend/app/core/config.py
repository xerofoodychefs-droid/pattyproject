import os, pathlib
from typing import List, Optional
from pydantic_settings import BaseSettings

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "patty_project.db"

DEV_FALLBACK_SECRET_KEY: str = "dev_secret_key_patty_project_local_development_only_change_in_production"

DEFAULT_PROD_CORS_ORIGINS: List[str] = [
    "https://order.pattyproject.co.uk",
    "https://admin.pattyproject.co.uk",
    "https://pattyproject.co.uk",
    "https://www.pattyproject.co.uk",
]

DEFAULT_DEV_CORS_ORIGINS: List[str] = [
    "https://order.pattyproject.co.uk",
    "https://admin.pattyproject.co.uk",
    "https://pattyproject.co.uk",
    "https://www.pattyproject.co.uk",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

class Settings(BaseSettings):
    PROJECT_NAME: str = "Patty Project UK"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEV_FALLBACK_SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))  # 15 minutes short-lived access token default
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))  # 7 days persistent refresh window
    
    # Database (Absolute SQLite path for consistent dev database)
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
    
    # Environment & Payment Provider
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development"))
    PAYMENT_PROVIDER: str = os.getenv("PAYMENT_PROVIDER", "square" if os.getenv("ENVIRONMENT") == "production" else "mock")

    # Square Payment Gateway Configuration
    SQUARE_APPLICATION_ID: Optional[str] = os.getenv("SQUARE_APPLICATION_ID")
    SQUARE_LOCATION_ID: Optional[str] = os.getenv("SQUARE_LOCATION_ID")
    SQUARE_ACCESS_TOKEN: Optional[str] = os.getenv("SQUARE_ACCESS_TOKEN")
    SQUARE_ENVIRONMENT: str = os.getenv("SQUARE_ENVIRONMENT", "production" if os.getenv("ENVIRONMENT") == "production" else "sandbox")
    SQUARE_WEBHOOK_SIGNATURE_KEY: Optional[str] = os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY")

    # Google Identity Services (GIS) OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "mock-google-client-id.apps.googleusercontent.com")

    # Resend & Contact Form Configuration
    CONTACT_EMAIL_TO: str = os.getenv("CONTACT_EMAIL_TO", "xerofoodychefs@gmail.com")
    CONTACT_EMAIL_FROM: str = os.getenv("CONTACT_EMAIL_FROM", "Patty Project <website@pattyproject.co.uk>")
    RESEND_API_KEY: Optional[str] = os.getenv("RESEND_API_KEY")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def is_square_sandbox(self) -> bool:
        if self.SQUARE_APPLICATION_ID and self.SQUARE_APPLICATION_ID.startswith("sandbox-"):
            return True
        return self.SQUARE_ENVIRONMENT.lower() in ["sandbox", "development", "testing"]

    @property
    def square_base_url(self) -> str:
        if self.is_square_sandbox:
            return "https://connect.squareupsandbox.com"
        return "https://connect.squareup.com"

    @property
    def cors_origins(self) -> List[str]:
        env_cors = os.getenv("BACKEND_CORS_ORIGINS") or os.getenv("CORS_ORIGINS")
        if env_cors:
            origins = [o.strip() for o in env_cors.split(",") if o.strip()]
            if origins:
                if "https://pattyproject.co.uk" in origins and "https://www.pattyproject.co.uk" not in origins:
                    origins.append("https://www.pattyproject.co.uk")
                if "https://www.pattyproject.co.uk" in origins and "https://pattyproject.co.uk" not in origins:
                    origins.append("https://pattyproject.co.uk")
                return origins
        if self.is_production:
            return DEFAULT_PROD_CORS_ORIGINS
        return DEFAULT_DEV_CORS_ORIGINS

    def validate_production_configuration(self) -> None:
        """Validates critical security configuration when running in production."""
        if self.is_production:
            env_secret = os.getenv("SECRET_KEY", "")
            if not env_secret or env_secret == DEV_FALLBACK_SECRET_KEY or len(env_secret) < 32:
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: "
                    "SECRET_KEY must be provided via environment variable, "
                    "must NOT be the insecure development fallback, "
                    "and must be at least 32 characters long in production."
                )
            
            origins = self.cors_origins
            if not origins or "*" in origins:
                raise RuntimeError(
                    "CRITICAL SECURITY CONFIGURATION ERROR: "
                    "Production CORS configuration must not be empty or contain wildcard '*'."
                )

    class Config:
        case_sensitive = True


settings = Settings()


