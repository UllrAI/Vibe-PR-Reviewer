
import os
from logging.config import dictConfig

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self):
        self.GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
        self.GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
        
        # Webhook
        self.GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "ullrai")

        # Optional with defaults
        self.AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "gemini-1.5-pro-latest")
        self.MAX_PROMPT_LENGTH: int = int(os.getenv("MAX_PROMPT_LENGTH", "200000"))
        self.INCLUDE_FILE_CONTEXT: bool = os.getenv("INCLUDE_FILE_CONTEXT", "true").lower() == "true"
        self.CONTEXT_MAX_LINES: int = int(os.getenv("CONTEXT_MAX_LINES", "400"))
        self.CONTEXT_SURROUNDING_LINES: int = int(os.getenv("CONTEXT_SURROUNDING_LINES", "50"))
        self.MAX_FILES_PER_REVIEW: int = int(os.getenv("MAX_FILES_PER_REVIEW", "50"))
        self.OUTPUT_LANGUAGE: str = os.getenv("OUTPUT_LANGUAGE", "english")
        self.MAX_RETRY_ATTEMPTS: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
        self.RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "2.0"))
        self.REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "60"))
        
        # Server
        self.PORT: int = int(os.getenv("PORT", "8080"))
        self.HOST: str = os.getenv("HOST", "0.0.0.0")
        
        # Logging
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def validate_settings(self):
        if not self.GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN environment variable not set.")
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable not set.")



settings = Settings()

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(asctime)s - %(name)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "pr_review_bot": {"handlers": ["default"], "level": settings.LOG_LEVEL, "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
}

def setup_logging():
    settings.validate_settings()
    dictConfig(LOGGING_CONFIG)

