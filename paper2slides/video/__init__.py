"""
Video generation module for Paper2Slides.

This module provides functionality to convert generated slides into
narrated video presentations using:
- ElevenLabs API for text-to-speech narration
- Replicate Veo 3.1 for AI-animated transitions
- FFmpeg/moviepy for final video composition
"""

from .config import (
    VideoConfig,
    VideoStatus,
    VideoStage,
    StageStatus,
    TransitionStyle,
    VideoResolution,
    VideoProgress,
    VideoOutput,
    get_elevenlabs_api_key,
    get_elevenlabs_voice_id,
    get_elevenlabs_model,
    get_elevenlabs_config,
    get_replicate_api_key,
)
from .state import (
    create_video_state,
    load_video_state,
    save_video_state,
    update_video_progress,
    update_video_stage,
    update_video_status,
    set_video_output,
    mark_video_failed,
    mark_video_cancelled,
    is_video_cancelled,
    get_video_status_summary,
    add_narration_file,
    add_transition_file,
    add_script,
)
from .script_generator import ScriptGenerator, estimate_speech_duration
from .elevenlabs_client import ElevenLabsClient, VoiceInfo, get_available_voices
from .replicate_client import (
    ReplicateVeoClient,
    SimpleTransitionGenerator,
    create_transition_generator,
)
from .video_composer import VideoComposer, VideoMetadata, compose_presentation_video

__all__ = [
    # Config
    "VideoConfig",
    "VideoStatus",
    "VideoStage",
    "StageStatus",
    "TransitionStyle",
    "VideoResolution",
    "VideoProgress",
    "VideoOutput",
    "get_elevenlabs_api_key",
    "get_elevenlabs_voice_id",
    "get_replicate_api_key",
    # State management
    "create_video_state",
    "load_video_state",
    "save_video_state",
    "update_video_progress",
    "update_video_stage",
    "update_video_status",
    "set_video_output",
    "mark_video_failed",
    "mark_video_cancelled",
    "is_video_cancelled",
    "get_video_status_summary",
    "add_narration_file",
    "add_transition_file",
    "add_script",
    # Script generation
    "ScriptGenerator",
    "estimate_speech_duration",
    # ElevenLabs
    "ElevenLabsClient",
    "VoiceInfo",
    "get_available_voices",
    # Replicate/Transitions
    "ReplicateVeoClient",
    "SimpleTransitionGenerator",
    "create_transition_generator",
    # Video composition
    "VideoComposer",
    "VideoMetadata",
    "compose_presentation_video",
]
