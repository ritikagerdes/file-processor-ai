"""
Application configuration management with environment variable support.
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings with validation and type checking."""
    
    # AWS Configuration
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    aws_s3_bucket: str
    aws_rds_endpoint: str
    aws_rds_database: str
    aws_rds_username: str
    aws_rds_password: str
    
    # Security Configuration
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    encryption_key: str
    
    # OpenAI Configuration
    openai_api_key: str
    embedding_model: str = "text-embedding-ada-002"
    chat_model: str = "gpt-4"
    
    # Application Configuration
    app_name: str = "Secure File Chatbot"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    max_file_size_mb: int = 100
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Client Configuration
    allowed_ips: str = "127.0.0.1"
    client_timeout: int = 300
    max_concurrent_uploads: int = 5
    
    # Database Configuration
    database_url: str
    
    @validator('allowed_ips')
    def parse_allowed_ips(cls, v: str) -> List[str]:
        """Parse comma-separated IP addresses and CIDR blocks."""
        return [ip.strip() for ip in v.split(',') if ip.strip()]
    
    @validator('encryption_key')
    def validate_encryption_key(cls, v: str) -> str:
        """Validate encryption key length."""
        if len(v) != 32:
            raise ValueError("Encryption key must be exactly 32 bytes")
        return v
    
    @validator('max_file_size_mb')
    def validate_max_file_size(cls, v: int) -> int:
        """Validate maximum file size."""
        if v <= 0 or v > 1000:
            raise ValueError("Max file size must be between 1 and 1000 MB")
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()