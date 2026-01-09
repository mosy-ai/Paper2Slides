"""
Configuration dataclasses and enums for video generation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import os


class VideoStatus(str, Enum):
    """Overall video generation status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoStage(str, Enum):
    """Individual stages of video generation."""

    SCRIPT_GENERATION = "script_generation"
    NARRATION = "narration"
    TRANSITIONS = "transitions"
    COMPOSITION = "composition"
    EXPORT = "export"


class StageStatus(str, Enum):
    """Status for individual stages."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TransitionStyle(str, Enum):
    """Style of transitions between slides."""

    AI_ANIMATED = "ai_animated"  # Use Veo 3.1 for AI transitions
    FADE = "fade"  # Simple fade transition
    SLIDE = "slide"  # Slide transition
    NONE = "none"  # No transition, direct cut


class VideoResolution(str, Enum):
    """Video output resolution."""

    HD_720P = "720p"
    FHD_1080P = "1080p"
    QHD_1440P = "1440p"


@dataclass
class VideoConfig:
    """Configuration for video generation."""

    # Voice settings
    voice_id: str = "default"
    voice_model: str = "eleven_multilingual_v2"

    # Transition settings
    transition_style: TransitionStyle = TransitionStyle.AI_ANIMATED
    transition_duration: float = 3.0  # seconds per transition

    # Slide settings
    slide_duration: str = "auto"  # "auto" = based on narration, or fixed seconds
    min_slide_duration: float = 5.0  # minimum seconds per slide

    # Video settings
    resolution: VideoResolution = VideoResolution.HD_720P  # 720p is faster to encode
    fps: int = 24  # 24fps is sufficient for presentations
    video_codec: str = "libx264"
    audio_codec: str = "aac"

    # Language
    language: str = "en"

    # Transition prompts
    transition_prompt: str = (
        "Smooth cinematic transition, professional presentation style, "
        "subtle camera movement"
    )

    def to_dict(self) -> dict:
        """Convert config to dictionary for JSON serialization."""
        return {
            "voice_id": self.voice_id,
            "voice_model": self.voice_model,
            "transition_style": self.transition_style.value,
            "transition_duration": self.transition_duration,
            "slide_duration": self.slide_duration,
            "min_slide_duration": self.min_slide_duration,
            "resolution": self.resolution.value,
            "fps": self.fps,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "language": self.language,
            "transition_prompt": self.transition_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VideoConfig":
        """Create config from dictionary."""
        return cls(
            voice_id=data.get("voice_id", "default"),
            voice_model=data.get("voice_model", "eleven_multilingual_v2"),
            transition_style=TransitionStyle(
                data.get("transition_style", "ai_animated")
            ),
            transition_duration=data.get("transition_duration", 3.0),
            slide_duration=data.get("slide_duration", "auto"),
            min_slide_duration=data.get("min_slide_duration", 5.0),
            resolution=VideoResolution(data.get("resolution", "1080p")),
            fps=data.get("fps", 30),
            video_codec=data.get("video_codec", "libx264"),
            audio_codec=data.get("audio_codec", "aac"),
            language=data.get("language", "en"),
            transition_prompt=data.get(
                "transition_prompt",
                "Smooth cinematic transition, professional presentation style",
            ),
        )

    def get_resolution_dimensions(self) -> tuple[int, int]:
        """Get width and height for the configured resolution."""
        resolutions = {
            VideoResolution.HD_720P: (1280, 720),
            VideoResolution.FHD_1080P: (1920, 1080),
            VideoResolution.QHD_1440P: (2560, 1440),
        }
        return resolutions.get(self.resolution, (1920, 1080))


@dataclass
class VideoProgress:
    """Progress tracking for video generation."""

    current_stage: VideoStage = VideoStage.SCRIPT_GENERATION
    current_slide: int = 0
    total_slides: int = 0
    percentage: float = 0.0
    message: str = ""

    def to_dict(self) -> dict:
        """Convert progress to dictionary."""
        return {
            "current_stage": self.current_stage.value,
            "current_slide": self.current_slide,
            "total_slides": self.total_slides,
            "percentage": self.percentage,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VideoProgress":
        """Create progress from dictionary."""
        return cls(
            current_stage=VideoStage(
                data.get("current_stage", "script_generation")
            ),
            current_slide=data.get("current_slide", 0),
            total_slides=data.get("total_slides", 0),
            percentage=data.get("percentage", 0.0),
            message=data.get("message", ""),
        )


@dataclass
class VideoOutput:
    """Output information for completed video."""

    video_url: str = ""
    thumbnail_url: str = ""
    duration_seconds: float = 0.0
    file_size_mb: float = 0.0
    resolution: str = "1920x1080"

    def to_dict(self) -> dict:
        """Convert output to dictionary."""
        return {
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "file_size_mb": self.file_size_mb,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VideoOutput":
        """Create output from dictionary."""
        return cls(
            video_url=data.get("video_url", ""),
            thumbnail_url=data.get("thumbnail_url", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            file_size_mb=data.get("file_size_mb", 0.0),
            resolution=data.get("resolution", "1920x1080"),
        )


def get_elevenlabs_config():
    """Get the full ElevenLabs configuration from SETTINGS."""
    from paper2slides.config import SETTINGS
    return SETTINGS.elevenlabs


def get_elevenlabs_api_key() -> Optional[str]:
    """Get ElevenLabs API key from SETTINGS or environment."""
    from paper2slides.config import SETTINGS
    return SETTINGS.elevenlabs.api_key or os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_KEY")


def get_elevenlabs_voice_id() -> Optional[str]:
    """Get default ElevenLabs voice ID from SETTINGS or environment."""
    from paper2slides.config import SETTINGS
    return SETTINGS.elevenlabs.default_voice_id or os.getenv("ELEVENLABS_VOICE_ID")


def get_elevenlabs_model() -> str:
    """Get default ElevenLabs model from SETTINGS."""
    from paper2slides.config import SETTINGS
    return SETTINGS.elevenlabs.default_model


def get_replicate_api_key() -> Optional[str]:
    """Get Replicate API key from SETTINGS or environment."""
    from paper2slides.config import SETTINGS
    return SETTINGS.replicate_key or os.getenv("REPLICATE_API_KEY") or os.getenv("REPLICATE_KEY")
