from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    APP_NAME: str = "CFS Transport API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # SQLite Database
    DATABASE_URL: str = "sqlite:///./cfs_transport.db"
    DB_ECHO: bool = False
    
    # Security
    SECRET_KEY: str = "cfs-transport-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # CORS - should be comma-separated list of origins in production
    CORS_ORIGINS: str = "*"  # Change to specific origins in production, e.g., "http://localhost:3000,https://app.example.com"
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    
    # OTP Configuration
    OTP_EXPIRY_MINUTES: int = 10
    OTP_LENGTH: int = 4  # For development, using 8805
    
    # API Security
    API_KEY_HEADER: str = "X-API-Key"
    ALLOW_LOCAL_NETWORK_API: bool = True  # Allow API key access from same network
    
    # File uploads
    MAX_FILE_SIZE: int = 5242880
    UPLOAD_DIR: str = "uploads/"
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png,pdf"
    
    # Ensure upload directory exists
    @property
    def upload_path(self):
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        return self.UPLOAD_DIR
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
