"""
Video composer for combining slides, transitions, and narration audio.

Uses moviepy and FFmpeg to compose the final presentation video.
"""

import os
import re
import sys
import asyncio
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Callable, Tuple
from dataclasses import dataclass

from .config import VideoConfig, VideoResolution


try:
    from proglog import ProgressBarLogger as ProglogLogger
    HAS_PROGLOG = True
except ImportError:
    HAS_PROGLOG = False
    ProglogLogger = object  # Fallback for inheritance


class CustomProgressLogger(ProglogLogger if HAS_PROGLOG else object):
    """Custom logger to capture FFmpeg progress and report to callback.

    Inherits from proglog.ProgressBarLogger to work with moviepy 2.x.
    """

    def __init__(
        self,
        callback: Optional[Callable[[str, float], None]] = None,
        base_progress: float = 70,
        progress_range: float = 30,
    ):
        if HAS_PROGLOG:
            super().__init__()
        self.custom_callback = callback
        self.base_progress = base_progress
        self.progress_range = progress_range
        self.last_progress = 0

    def bars_callback(self, bar, attr, value, old_value=None):
        """Called by proglog/moviepy during encoding with progress updates."""
        if self.custom_callback and attr == "index" and bar in self.bars:
            total = self.bars[bar].get("total", 1)
            if total > 0:
                percentage = (value / total) * self.progress_range + self.base_progress
                # Only update if progress changed significantly
                if percentage - self.last_progress >= 1:
                    self.last_progress = percentage
                    self.custom_callback("Encoding video", min(percentage, 99))


# Detect moviepy version
def _get_moviepy_version():
    """Detect which moviepy version is installed."""
    try:
        from moviepy import ImageClip
        return 2
    except ImportError:
        try:
            from moviepy.editor import ImageClip
            return 1
        except ImportError:
            raise ImportError("moviepy is required for video composition")


@dataclass
class VideoMetadata:
    """Metadata for the final composed video."""

    duration_seconds: float
    file_size_mb: float
    resolution: str
    fps: int
    num_slides: int
    has_audio: bool

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "duration_seconds": self.duration_seconds,
            "file_size_mb": self.file_size_mb,
            "resolution": self.resolution,
            "fps": self.fps,
            "num_slides": self.num_slides,
            "has_audio": self.has_audio,
        }


class VideoComposer:
    """
    Composes final video from slides, transitions, and audio narration.
    """

    def __init__(self, config: VideoConfig):
        """
        Initialize the video composer.

        Args:
            config: Video configuration settings
        """
        self.config = config
        self.width, self.height = config.get_resolution_dimensions()
        self._moviepy_version = _get_moviepy_version()

    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Get the duration of an audio file in seconds.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds
        """
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(str(audio_path))
            return len(audio) / 1000.0
        except Exception as e:
            print(f"Warning: Could not get audio duration: {e}")
            return self.config.min_slide_duration

    def _resize_image_to_video(self, image_path: Path, output_path: Path) -> None:
        """
        Resize an image to match video dimensions.

        Args:
            image_path: Path to input image
            output_path: Path to save resized image
        """
        try:
            from PIL import Image

            img = Image.open(image_path)

            # Resize to target dimensions, maintaining aspect ratio with padding
            img_ratio = img.width / img.height
            target_ratio = self.width / self.height

            if img_ratio > target_ratio:
                # Image is wider, fit to width
                new_width = self.width
                new_height = int(self.width / img_ratio)
            else:
                # Image is taller, fit to height
                new_height = self.height
                new_width = int(self.height * img_ratio)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Create new image with target dimensions (black background)
            final = Image.new("RGB", (self.width, self.height), (0, 0, 0))

            # Paste resized image centered
            x = (self.width - new_width) // 2
            y = (self.height - new_height) // 2
            final.paste(img, (x, y))

            output_path.parent.mkdir(parents=True, exist_ok=True)
            final.save(output_path, "PNG")

        except ImportError:
            raise ImportError("Pillow is required for image processing")

    def _compose_simple_sync(
        self,
        slides: List[Path],
        audio_files: List[Path],
        output_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> VideoMetadata:
        """Synchronous implementation of simple video composition."""
        if self._moviepy_version == 2:
            from moviepy import (
                ImageClip,
                AudioFileClip,
                concatenate_videoclips,
            )
        else:
            from moviepy.editor import (
                ImageClip,
                AudioFileClip,
                concatenate_videoclips,
            )

        if len(slides) != len(audio_files):
            raise ValueError(
                f"Number of slides ({len(slides)}) must match audio files ({len(audio_files)})"
            )

        if progress_callback:
            progress_callback("Preparing slides", 0)

        clips = []
        total_slides = len(slides)

        for i, (slide_path, audio_path) in enumerate(zip(slides, audio_files)):
            # Get audio duration
            audio_duration = self._get_audio_duration(audio_path)
            duration = max(audio_duration, self.config.min_slide_duration)

            # Create image clip
            image_clip = ImageClip(str(slide_path))

            # Set duration (different API for v1 vs v2)
            if self._moviepy_version == 2:
                image_clip = image_clip.with_duration(duration)
            else:
                image_clip = image_clip.set_duration(duration)

            # Resize if needed
            if image_clip.size != (self.width, self.height):
                if self._moviepy_version == 2:
                    image_clip = image_clip.resized((self.width, self.height))
                else:
                    image_clip = image_clip.resize((self.width, self.height))

            # Add audio
            audio_clip = AudioFileClip(str(audio_path))
            if self._moviepy_version == 2:
                image_clip = image_clip.with_audio(audio_clip)
            else:
                image_clip = image_clip.set_audio(audio_clip)

            clips.append(image_clip)

            if progress_callback:
                progress_callback("Preparing slides", (i + 1) / total_slides * 50)

        if progress_callback:
            progress_callback("Composing video", 50)

        # Concatenate all clips
        final_video = concatenate_videoclips(clips, method="compose")

        if progress_callback:
            progress_callback("Encoding video", 60)

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup progress logger for encoding
        custom_logger = None
        if progress_callback and HAS_PROGLOG:
            custom_logger = CustomProgressLogger(
                callback=progress_callback,
                base_progress=60,
                progress_range=40,  # 60% to 100%
            )

        # Use faster encoding settings with progress tracking
        # ffmpeg_params for additional speed optimization
        ffmpeg_params = [
            "-crf", "28",  # Lower quality but faster (default is 23)
            "-tune", "stillimage",  # Optimize for slideshow content
        ]

        final_video.write_videofile(
            str(output_path),
            fps=self.config.fps,
            codec=self.config.video_codec,
            audio_codec=self.config.audio_codec,
            preset="ultrafast",  # Fastest encoding
            threads=0,  # Use all available CPU threads
            logger=custom_logger if custom_logger else None,
            write_logfile=False,
            ffmpeg_params=ffmpeg_params,
        )

        total_duration = final_video.duration

        # Clean up
        final_video.close()
        for clip in clips:
            clip.close()

        if progress_callback:
            progress_callback("Complete", 100)

        # Get file info
        file_size = output_path.stat().st_size / (1024 * 1024)  # MB

        return VideoMetadata(
            duration_seconds=total_duration,
            file_size_mb=round(file_size, 2),
            resolution=f"{self.width}x{self.height}",
            fps=self.config.fps,
            num_slides=len(slides),
            has_audio=True,
        )

    def _compose_with_transitions_sync(
        self,
        slides: List[Path],
        audio_files: List[Path],
        transitions: List[Path],
        output_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> VideoMetadata:
        """Synchronous implementation of video composition with transitions."""
        if self._moviepy_version == 2:
            from moviepy import (
                ImageClip,
                AudioFileClip,
                VideoFileClip,
                concatenate_videoclips,
            )
        else:
            from moviepy.editor import (
                ImageClip,
                AudioFileClip,
                VideoFileClip,
                concatenate_videoclips,
            )

        if len(slides) != len(audio_files):
            raise ValueError("Number of slides must match audio files")

        if len(transitions) != len(slides) - 1:
            raise ValueError(
                f"Expected {len(slides) - 1} transitions, got {len(transitions)}"
            )

        if progress_callback:
            progress_callback("Loading media", 0)

        clips = []
        total_items = len(slides) + len(transitions)

        for i, (slide_path, audio_path) in enumerate(zip(slides, audio_files)):
            # Get audio duration
            audio_duration = self._get_audio_duration(audio_path)
            duration = max(audio_duration, self.config.min_slide_duration)

            # Create slide clip with audio
            slide_clip = ImageClip(str(slide_path))

            if self._moviepy_version == 2:
                slide_clip = slide_clip.with_duration(duration)
            else:
                slide_clip = slide_clip.set_duration(duration)

            if slide_clip.size != (self.width, self.height):
                if self._moviepy_version == 2:
                    slide_clip = slide_clip.resized((self.width, self.height))
                else:
                    slide_clip = slide_clip.resize((self.width, self.height))

            audio_clip = AudioFileClip(str(audio_path))
            if self._moviepy_version == 2:
                slide_clip = slide_clip.with_audio(audio_clip)
            else:
                slide_clip = slide_clip.set_audio(audio_clip)

            clips.append(slide_clip)

            if progress_callback:
                progress = (i * 2 + 1) / total_items * 60
                progress_callback("Loading slides", progress)

            # Add transition after this slide (except for last slide)
            if i < len(transitions):
                transition_clip = VideoFileClip(str(transitions[i]))

                # Resize transition if needed
                if transition_clip.size != (self.width, self.height):
                    if self._moviepy_version == 2:
                        transition_clip = transition_clip.resized((self.width, self.height))
                    else:
                        transition_clip = transition_clip.resize((self.width, self.height))

                clips.append(transition_clip)

                if progress_callback:
                    progress = (i * 2 + 2) / total_items * 60
                    progress_callback("Loading transitions", progress)

        if progress_callback:
            progress_callback("Composing video", 60)

        # Concatenate all clips
        final_video = concatenate_videoclips(clips, method="compose")

        if progress_callback:
            progress_callback("Encoding video", 70)

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup progress logger for encoding
        custom_logger = None
        if progress_callback and HAS_PROGLOG:
            custom_logger = CustomProgressLogger(
                callback=progress_callback,
                base_progress=70,
                progress_range=30,  # 70% to 100%
            )

        # Use faster encoding settings with progress tracking
        # ffmpeg_params for additional speed optimization
        ffmpeg_params = [
            "-crf", "28",  # Lower quality but faster (default is 23)
            "-tune", "stillimage",  # Optimize for slideshow content
        ]

        final_video.write_videofile(
            str(output_path),
            fps=self.config.fps,
            codec=self.config.video_codec,
            audio_codec=self.config.audio_codec,
            preset="ultrafast",  # Fastest encoding
            threads=0,  # Use all available CPU threads
            logger=custom_logger if custom_logger else None,
            write_logfile=False,
            ffmpeg_params=ffmpeg_params,
        )

        total_duration = final_video.duration

        # Clean up
        final_video.close()
        for clip in clips:
            clip.close()

        if progress_callback:
            progress_callback("Complete", 100)

        file_size = output_path.stat().st_size / (1024 * 1024)

        return VideoMetadata(
            duration_seconds=total_duration,
            file_size_mb=round(file_size, 2),
            resolution=f"{self.width}x{self.height}",
            fps=self.config.fps,
            num_slides=len(slides),
            has_audio=True,
        )

    async def compose_simple(
        self,
        slides: List[Path],
        audio_files: List[Path],
        output_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> VideoMetadata:
        """
        Compose a simple video with slides and audio (no AI transitions).

        Each slide is shown for the duration of its narration audio.

        Args:
            slides: List of slide image paths (in order)
            audio_files: List of audio files (one per slide)
            output_path: Path to save the final video
            progress_callback: Optional callback(stage, percentage)

        Returns:
            VideoMetadata with information about the composed video
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool,
                self._compose_simple_sync,
                slides,
                audio_files,
                output_path,
                progress_callback,
            )

    async def compose_with_transitions(
        self,
        slides: List[Path],
        audio_files: List[Path],
        transitions: List[Path],
        output_path: Path,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> VideoMetadata:
        """
        Compose video with slides, audio, and AI-generated transitions.

        Video structure:
        [slide1 + audio1] -> [transition1] -> [slide2 + audio2] -> [transition2] -> ...

        Args:
            slides: List of slide image paths
            audio_files: List of audio files (one per slide)
            transitions: List of transition video paths (N-1 for N slides)
            output_path: Path to save final video
            progress_callback: Optional callback(stage, percentage)

        Returns:
            VideoMetadata
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(
                pool,
                self._compose_with_transitions_sync,
                slides,
                audio_files,
                transitions,
                output_path,
                progress_callback,
            )

    async def generate_thumbnail(
        self,
        video_path: Path,
        output_path: Path,
        timestamp: float = 0.0,
    ) -> Path:
        """
        Generate a thumbnail from a video.

        Args:
            video_path: Path to the video file
            output_path: Path to save the thumbnail
            timestamp: Time in seconds to capture thumbnail

        Returns:
            Path to the generated thumbnail
        """
        if self._moviepy_version == 2:
            from moviepy import VideoFileClip
        else:
            from moviepy.editor import VideoFileClip

        output_path.parent.mkdir(parents=True, exist_ok=True)

        clip = VideoFileClip(str(video_path))

        # Use first frame if timestamp is 0 or beyond duration
        if timestamp >= clip.duration:
            timestamp = 0

        frame = clip.get_frame(timestamp)
        clip.close()

        # Save as image
        try:
            from PIL import Image
            import numpy as np

            img = Image.fromarray(np.uint8(frame))
            img.save(output_path, "JPEG", quality=85)

        except ImportError:
            # Fallback using moviepy's save_frame
            clip = VideoFileClip(str(video_path))
            clip.save_frame(str(output_path), t=timestamp)
            clip.close()

        return output_path


async def compose_presentation_video(
    slides: List[Path],
    audio_files: List[Path],
    transitions: Optional[List[Path]],
    output_path: Path,
    config: VideoConfig,
    progress_callback: Optional[Callable[[str, float], None]] = None,
) -> VideoMetadata:
    """
    High-level function to compose a presentation video.

    Args:
        slides: List of slide image paths
        audio_files: List of narration audio files
        transitions: Optional list of transition videos
        output_path: Path to save final video
        config: Video configuration
        progress_callback: Progress callback

    Returns:
        VideoMetadata
    """
    composer = VideoComposer(config)

    if transitions and len(transitions) == len(slides) - 1:
        return await composer.compose_with_transitions(
            slides=slides,
            audio_files=audio_files,
            transitions=transitions,
            output_path=output_path,
            progress_callback=progress_callback,
        )
    else:
        return await composer.compose_simple(
            slides=slides,
            audio_files=audio_files,
            output_path=output_path,
            progress_callback=progress_callback,
        )
