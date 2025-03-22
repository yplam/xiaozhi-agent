"""
Configuration settings for the application.
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# WebSocket server configuration
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", "8000"))
WS_PROTOCOL_VERSION = 1

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

# HTTP proxy configuration (optional)
PROXY_URL = os.getenv("PROXY_URL")
PROXY_ENABLED = bool(PROXY_URL)

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
OPUS_FRAME_DURATION_MS = 60

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Authentication settings
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "your-secret-key-change-this")

# Other settings
DEFAULT_TIMEOUT = 10  # seconds 