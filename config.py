"""
Configuration management for Relab Chatbot
Loads settings from environment variables
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    
    # Database Configuration
    database_url: str = "sqlite:///./chatbot.db"
    database_auth_token: Optional[str] = None
    
    # Application Configuration
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # Testing & Whitelisting
    test_mode_enabled: bool = False
    allowed_test_users: str = ""  # Comma-separated identifiers
    
    # Business Rules
    high_value_threshold: int = 5000  # MAD
    max_bot_messages: int = 10  # Max messages before suggesting human
    
    # n8n Workflow Configuration
    use_n8n_workflow: bool = False
    n8n_webhook_url: Optional[str] = None
    
    # Rate Limiting
    max_requests_per_minute: int = 60
    
    # Meta Compatibility Mode
    # When True: Returns HTTP 200 even on errors (prevents Meta webhook retries)
    # When False: Returns proper HTTP status codes (4xx/5xx) for debugging
    meta_compat_mode: bool = True  # Default True for production safety
    
    # Google Sheets Configuration (optional)
    google_sheets_credentials_file: Optional[str] = None
    google_sheets_credentials_json: Optional[str] = None
    google_sheets_inventory_url: Optional[str] = None
    
    # Knowledge Base
    knowledge_base_dir: str = "knowledge/"
    
    # Instagram Configuration
    instagram_verify_token: Optional[str] = None
    instagram_access_token: Optional[str] = None
    
    # WhatsApp Configuration (Meta Cloud API)
    whatsapp_verify_token: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    
    # Admin Notifications
    admin_whatsapp_number: Optional[str] = "+2127031502030"
    
    # Messenger Configuration
    messenger_verify_token: Optional[str] = None
    messenger_access_token: Optional[str] = None
    
    # Email Configuration
    email_webhook_token: Optional[str] = "relab-secure-token"
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
