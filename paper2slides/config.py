import base64
import os
from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LangfuseConfig(BaseSettings):
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(extra="allow")


class ElevenLabsConfig(BaseSettings):
    """Configuration for ElevenLabs text-to-speech service.

    Environment variables:
        ELEVENLABS_API_KEY: API key for ElevenLabs
        ELEVENLABS_DEFAULT_MODEL: Default TTS model (default: eleven_multilingual_v2)
        ELEVENLABS_DEFAULT_VOICE_ID: Default voice ID
        ELEVENLABS_OUTPUT_DIR: Directory for audio files (default: data/audio)
    """

    api_key: str = ""
    default_model: str = "eleven_turbo_v2_5"
    default_voice_id: str = "XBDAUT8ybuJTTCoOLSUj"  # Bella - multilingual female
    output_dir: str = "data/audio"

    # Voice settings
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    speed: float = 1.1

    model_config = SettingsConfigDict(extra="allow")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "paper2slides/.env"),  # Check both locations
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Langfuse
    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)

    # ElevenLabs TTS - read directly from environment
    elevenlabs: ElevenLabsConfig = Field(default_factory=ElevenLabsConfig)

    # Direct environment variable mappings for API keys
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = Field(default="", alias="ELEVENLABS_VOICE_ID")

    # Replicate API key for video transitions
    replicate_key: str = Field(default="", alias="REPLICATE_KEY")


def _load_settings() -> Settings:
    """Load settings and populate nested configs from environment."""
    settings = Settings()

    # Populate ElevenLabs config from direct env vars if available
    if settings.elevenlabs_api_key:
        settings.elevenlabs.api_key = settings.elevenlabs_api_key
    if settings.elevenlabs_voice_id:
        settings.elevenlabs.default_voice_id = settings.elevenlabs_voice_id

    # Also try direct os.getenv as fallback
    if not settings.elevenlabs.api_key:
        settings.elevenlabs.api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not settings.replicate_key:
        settings.replicate_key = os.getenv("REPLICATE_KEY", "") or os.getenv("REPLICATE_API_KEY", "")

    return settings


SETTINGS = _load_settings()

# Export the setting
os.environ["LANGFUSE_PUBLIC_KEY"] = SETTINGS.langfuse.public_key
os.environ["LANGFUSE_SECRET_KEY"] = SETTINGS.langfuse.secret_key
os.environ["LANGFUSE_HOST"] = SETTINGS.langfuse.host
