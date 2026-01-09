"""
ElevenLabs API client for text-to-speech narration.

Uses the ElevenLabs API to convert narration scripts to speech audio.
"""

import os
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .config import get_elevenlabs_api_key, get_elevenlabs_config, get_elevenlabs_voice_id, get_elevenlabs_model


@dataclass
class VoiceInfo:
    """Information about an ElevenLabs voice."""

    voice_id: str
    name: str
    category: str
    description: str
    preview_url: Optional[str] = None
    labels: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "voice_id": self.voice_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "preview_url": self.preview_url,
            "labels": self.labels or {},
        }


@dataclass
class AudioMetadata:
    """Metadata for generated audio."""

    duration_seconds: float
    file_size_bytes: int
    sample_rate: int
    format: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "sample_rate": self.sample_rate,
            "format": self.format,
        }


class ElevenLabsClient:
    """
    Client for ElevenLabs Text-to-Speech API.
    """

    BASE_URL = "https://api.elevenlabs.io/v1"

    # Available models
    MODELS = {
        "multilingual_v2": "eleven_multilingual_v2",
        "turbo_v2_5": "eleven_turbo_v2_5",
        "turbo_v2": "eleven_turbo_v2",
        "monolingual_v1": "eleven_monolingual_v1",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ):
        """
        Initialize the ElevenLabs client.

        Args:
            api_key: ElevenLabs API key (defaults to config)
            default_voice_id: Default voice ID to use (defaults to config)
            model_id: TTS model to use (defaults to config)
        """
        # Get config from SETTINGS
        config = get_elevenlabs_config()

        self.api_key = api_key or get_elevenlabs_api_key()
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key not provided and ELEVENLABS_API_KEY not set"
            )

        self.default_voice_id = default_voice_id or get_elevenlabs_voice_id()
        self.model_id = model_id or get_elevenlabs_model()

        # Voice settings from config
        self.voice_settings = {
            "stability": config.stability,
            "similarity_boost": config.similarity_boost,
            "style": config.style,
            "use_speaker_boost": config.use_speaker_boost,
        }
        self.speed = config.speed

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }

    async def get_voices(self) -> List[VoiceInfo]:
        """
        Get list of available voices.

        Returns:
            List of VoiceInfo objects
        """
        url = f"{self.BASE_URL}/voices"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"xi-api-key": self.api_key},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to get voices: {error_text}")

                data = await response.json()

        voices = []
        for voice in data.get("voices", []):
            voices.append(
                VoiceInfo(
                    voice_id=voice["voice_id"],
                    name=voice["name"],
                    category=voice.get("category", "unknown"),
                    description=voice.get("description", ""),
                    preview_url=voice.get("preview_url"),
                    labels=voice.get("labels"),
                )
            )

        return voices

    async def get_default_voice_id(self) -> str:
        """
        Get the default voice ID.

        If no default is configured, returns the first available voice.

        Returns:
            Voice ID string
        """
        if self.default_voice_id:
            return self.default_voice_id

        # Get first available voice
        voices = await self.get_voices()
        if not voices:
            raise Exception("No voices available")

        # Prefer a professional/narrative voice if available
        preferred_categories = ["professional", "narrative", "news"]
        for category in preferred_categories:
            for voice in voices:
                if voice.category.lower() == category:
                    return voice.voice_id

        return voices[0].voice_id

    async def generate_speech(
        self,
        text: str,
        output_path: Path,
        voice_id: Optional[str] = None,
        voice_settings: Optional[Dict[str, Any]] = None,
    ) -> AudioMetadata:
        """
        Generate speech from text and save to file.

        Args:
            text: Text to convert to speech
            output_path: Path to save the audio file
            voice_id: Voice ID to use (defaults to default voice)
            voice_settings: Optional voice settings override

        Returns:
            AudioMetadata with information about the generated audio
        """
        # Resolve "default" or empty to actual voice ID
        if not voice_id or voice_id == "default":
            voice_id = await self.get_default_voice_id()
        settings = voice_settings or self.voice_settings

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}"

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": settings,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=self._get_headers(),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to generate speech: {error_text}")

                # Save audio to file
                output_path.parent.mkdir(parents=True, exist_ok=True)
                audio_data = await response.read()

                with open(output_path, "wb") as f:
                    f.write(audio_data)

        # Calculate approximate duration from file size
        # MP3 at 128kbps = 16KB per second
        file_size = output_path.stat().st_size
        approx_duration = file_size / 16000  # rough estimate

        return AudioMetadata(
            duration_seconds=approx_duration,
            file_size_bytes=file_size,
            sample_rate=44100,
            format="mp3",
        )

    async def generate_speech_with_timestamps(
        self,
        text: str,
        output_path: Path,
        voice_id: Optional[str] = None,
    ) -> tuple[AudioMetadata, List[Dict[str, Any]]]:
        """
        Generate speech with word-level timestamps.

        Args:
            text: Text to convert to speech
            output_path: Path to save the audio file
            voice_id: Voice ID to use

        Returns:
            Tuple of (AudioMetadata, list of word timestamps)
        """
        # Resolve "default" or empty to actual voice ID
        if not voice_id or voice_id == "default":
            voice_id = await self.get_default_voice_id()

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}/with-timestamps"

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": self.voice_settings,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "xi-api-key": self.api_key,
                },
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Failed to generate speech with timestamps: {error_text}"
                    )

                data = await response.json()

        # Decode base64 audio and save
        import base64

        audio_base64 = data.get("audio_base64", "")
        audio_data = base64.b64decode(audio_base64)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(audio_data)

        # Extract timestamps
        alignment = data.get("alignment", {})
        word_timestamps = []

        characters = alignment.get("characters", [])
        char_start_times = alignment.get("character_start_times_seconds", [])
        char_end_times = alignment.get("character_end_times_seconds", [])

        # Group characters into words
        current_word = ""
        word_start = 0
        for i, char in enumerate(characters):
            if char == " ":
                if current_word:
                    word_timestamps.append(
                        {
                            "word": current_word,
                            "start": word_start,
                            "end": char_end_times[i - 1] if i > 0 else 0,
                        }
                    )
                current_word = ""
            else:
                if not current_word:
                    word_start = char_start_times[i] if i < len(char_start_times) else 0
                current_word += char

        # Add last word
        if current_word:
            word_timestamps.append(
                {
                    "word": current_word,
                    "start": word_start,
                    "end": char_end_times[-1] if char_end_times else 0,
                }
            )

        file_size = output_path.stat().st_size
        duration = word_timestamps[-1]["end"] if word_timestamps else 0

        metadata = AudioMetadata(
            duration_seconds=duration,
            file_size_bytes=file_size,
            sample_rate=44100,
            format="mp3",
        )

        return metadata, word_timestamps

    async def generate_all_narrations(
        self,
        scripts: List[str],
        output_dir: Path,
        voice_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        max_concurrent: int = 4,
    ) -> List[tuple[Path, AudioMetadata]]:
        """
        Generate narration audio for all scripts in parallel.

        Args:
            scripts: List of narration script texts
            output_dir: Directory to save audio files
            voice_id: Voice ID to use
            progress_callback: Optional callback(current, total) for progress
            max_concurrent: Maximum number of concurrent generations

        Returns:
            List of (file_path, metadata) tuples
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        total = len(scripts)
        completed = [0]  # Use list to allow modification in closure

        async def generate_one(i: int, script: str) -> tuple[int, Path, AudioMetadata]:
            output_path = output_dir / f"slide_{i + 1:02d}.mp3"

            metadata = await self.generate_speech(
                text=script,
                output_path=output_path,
                voice_id=voice_id,
            )

            completed[0] += 1
            if progress_callback:
                progress_callback(completed[0], total)

            return (i, output_path, metadata)

        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_limit(i: int, script: str) -> tuple[int, Path, AudioMetadata]:
            async with semaphore:
                return await generate_one(i, script)

        # Run all narrations in parallel (with concurrency limit)
        tasks = [generate_with_limit(i, script) for i, script in enumerate(scripts)]
        results = await asyncio.gather(*tasks)

        # Sort by index to maintain order and format output
        results.sort(key=lambda x: x[0])
        return [(path, metadata) for _, path, metadata in results]


async def get_available_voices() -> List[Dict[str, Any]]:
    """
    Convenience function to get available voices.

    Returns:
        List of voice dictionaries
    """
    api_key = get_elevenlabs_api_key()
    if not api_key:
        return []

    try:
        client = ElevenLabsClient(api_key=api_key)
        voices = await client.get_voices()
        return [v.to_dict() for v in voices]
    except Exception as e:
        print(f"Error getting voices: {e}")
        return []
