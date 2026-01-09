"""
Replicate API client for AI-animated video transitions using Veo 3.1.

Uses Replicate's hosted Google Veo 3.1 model to generate smooth
AI-animated transitions between consecutive slides.
"""

import os
import asyncio
import aiohttp
import base64
from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass

from .config import get_replicate_api_key


@dataclass
class TransitionMetadata:
    """Metadata for a generated transition."""

    duration_seconds: float
    file_size_bytes: int
    from_slide: int
    to_slide: int
    model: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "duration_seconds": self.duration_seconds,
            "file_size_bytes": self.file_size_bytes,
            "from_slide": self.from_slide,
            "to_slide": self.to_slide,
            "model": self.model,
        }


class ReplicateVeoClient:
    """
    Client for Replicate's Veo 3.1 video generation API.

    Veo 3.1 supports first-frame + last-frame to video generation,
    which is perfect for creating smooth transitions between slides.
    """

    # Replicate API endpoints
    BASE_URL = "https://api.replicate.com/v1"

    # Model identifier for Veo 3.1
    VEO_MODEL = "google/veo-3.1"

    # Alternative models if Veo is unavailable
    FALLBACK_MODELS = [
        "stability-ai/stable-video-diffusion",
        "minimax/video-01",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the Replicate client.

        Args:
            api_key: Replicate API key (defaults to env var)
            model: Model to use (defaults to Veo 3.1)
        """
        self.api_key = api_key or get_replicate_api_key()
        if not self.api_key:
            raise ValueError(
                "Replicate API key not provided and REPLICATE_API_KEY not set"
            )

        self.model = model or self.VEO_MODEL

    def _get_headers(self) -> dict:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _image_to_data_uri(self, image_path: Path, target_size: tuple = (1280, 720)) -> str:
        """
        Convert an image file to a data URI, resizing if needed.

        Args:
            image_path: Path to the image file
            target_size: Target dimensions (width, height) for Veo API

        Returns:
            Data URI string
        """
        try:
            from PIL import Image
            import io

            # Open and resize image to Veo-compatible dimensions
            with Image.open(image_path) as img:
                # Convert to RGB if necessary (remove alpha channel)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

                # Resize to target dimensions
                if img.size != target_size:
                    img = img.resize(target_size, Image.Resampling.LANCZOS)

                # Save to bytes as JPEG for smaller size
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=90)
                data = buffer.getvalue()

            mime_type = "image/jpeg"
        except ImportError:
            # Fallback if PIL not available
            with open(image_path, "rb") as f:
                data = f.read()

            ext = image_path.suffix.lower()
            mime_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }
            mime_type = mime_types.get(ext, "image/png")

        base64_data = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_type};base64,{base64_data}"

    # Veo API only accepts these duration values
    VALID_DURATIONS = [4, 6, 8]

    async def generate_transition(
        self,
        first_frame: Path,
        last_frame: Path,
        output_path: Path,
        prompt: str = "Smooth cinematic transition, professional presentation style",
        duration: float = 4.0,
        aspect_ratio: str = "16:9",
    ) -> TransitionMetadata:
        """
        Generate an AI-animated transition between two frames.

        Args:
            first_frame: Path to the starting image (slide N)
            last_frame: Path to the ending image (slide N+1)
            output_path: Path to save the transition video
            prompt: Text prompt to guide the transition style
            duration: Duration of transition in seconds (must be 4, 6, or 8)
            aspect_ratio: Aspect ratio of the output video

        Returns:
            TransitionMetadata with information about the generated transition
        """
        # Validate duration - Veo only accepts 4, 6, or 8 seconds
        valid_duration = min(self.VALID_DURATIONS, key=lambda x: abs(x - duration))
        if valid_duration != duration:
            print(f"Note: Duration {duration}s adjusted to {valid_duration}s (Veo requires 4, 6, or 8)")

        # Convert images to data URIs
        # Veo expects 1280x720 for 16:9 aspect ratio
        first_frame_uri = self._image_to_data_uri(first_frame)
        last_frame_uri = self._image_to_data_uri(last_frame)

        # Build the prediction request
        # Note: Veo uses "image" for first frame, not "first_frame"
        prediction_input = {
            "prompt": prompt,
            "image": first_frame_uri,  # Start image
            "last_frame": last_frame_uri,  # End image for interpolation
            "duration": valid_duration,
            "aspect_ratio": aspect_ratio,
            "generate_audio": False,  # We have our own narration
        }

        # Create prediction
        create_url = f"{self.BASE_URL}/predictions"

        async with aiohttp.ClientSession() as session:
            # Start the prediction
            async with session.post(
                create_url,
                json={
                    "version": self.model,
                    "input": prediction_input,
                },
                headers=self._get_headers(),
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise Exception(f"Failed to create prediction: {error_text}")

                prediction = await response.json()

            prediction_id = prediction["id"]
            get_url = f"{self.BASE_URL}/predictions/{prediction_id}"

            # Poll for completion
            max_attempts = 120  # 10 minutes with 5-second intervals
            for attempt in range(max_attempts):
                async with session.get(
                    get_url,
                    headers=self._get_headers(),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to get prediction: {error_text}")

                    prediction = await response.json()

                status = prediction["status"]

                if status == "succeeded":
                    # Download the output video
                    output_url = prediction["output"]
                    if isinstance(output_url, list):
                        output_url = output_url[0]

                    await self._download_video(session, output_url, output_path)

                    file_size = output_path.stat().st_size

                    return TransitionMetadata(
                        duration_seconds=duration,
                        file_size_bytes=file_size,
                        from_slide=0,  # Will be set by caller
                        to_slide=0,
                        model=self.model,
                    )

                elif status == "failed":
                    error = prediction.get("error", "Unknown error")
                    raise Exception(f"Prediction failed: {error}")

                elif status == "canceled":
                    raise Exception("Prediction was canceled")

                # Still processing, wait and retry
                await asyncio.sleep(5)

            raise Exception("Prediction timed out after 10 minutes")

    async def _download_video(
        self,
        session: aiohttp.ClientSession,
        url: str,
        output_path: Path,
    ) -> None:
        """
        Download a video from URL and save to file.

        Args:
            session: aiohttp session
            url: URL to download from
            output_path: Path to save the video
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Failed to download video: {response.status}")

            with open(output_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)

    async def generate_all_transitions(
        self,
        slides: List[Path],
        output_dir: Path,
        prompt: str = "Smooth cinematic transition, professional presentation style",
        duration: float = 4.0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        max_concurrent: int = 4,
    ) -> List[tuple[Path, TransitionMetadata]]:
        """
        Generate transitions between all consecutive slides in parallel.

        For N slides, generates N-1 transition segments.

        Args:
            slides: List of slide image paths (in order)
            output_dir: Directory to save transition videos
            prompt: Text prompt for transition style
            duration: Duration per transition in seconds
            progress_callback: Optional callback(current, total) for progress
            max_concurrent: Maximum number of concurrent transitions to generate

        Returns:
            List of (file_path, metadata) tuples
        """
        if len(slides) < 2:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        total_transitions = len(slides) - 1
        completed = [0]  # Use list to allow modification in closure

        async def generate_one(i: int) -> tuple[Path, TransitionMetadata]:
            output_path = output_dir / f"transition_{i + 1:02d}.mp4"

            metadata = await self.generate_transition(
                first_frame=slides[i],
                last_frame=slides[i + 1],
                output_path=output_path,
                prompt=prompt,
                duration=duration,
            )

            # Update slide indices
            metadata.from_slide = i + 1
            metadata.to_slide = i + 2

            completed[0] += 1
            if progress_callback:
                progress_callback(completed[0], total_transitions)

            return (output_path, metadata)

        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_with_limit(i: int) -> tuple[Path, TransitionMetadata]:
            async with semaphore:
                return await generate_one(i)

        # Run all transitions in parallel (with concurrency limit)
        tasks = [generate_with_limit(i) for i in range(total_transitions)]
        results = await asyncio.gather(*tasks)

        # Sort results by transition index to maintain order
        return list(results)


class SimpleTransitionGenerator:
    """
    Fallback transition generator using simple fade effects.

    Used when Replicate/Veo is not available or for testing.
    Requires moviepy.
    """

    def __init__(self, fps: int = 30):
        """
        Initialize the simple transition generator.

        Args:
            fps: Frames per second for transitions
        """
        self.fps = fps

    async def generate_fade_transition(
        self,
        first_frame: Path,
        last_frame: Path,
        output_path: Path,
        duration: float = 1.0,
    ) -> TransitionMetadata:
        """
        Generate a simple fade transition between two frames.

        Args:
            first_frame: Path to starting image
            last_frame: Path to ending image
            output_path: Path to save transition video
            duration: Duration in seconds

        Returns:
            TransitionMetadata
        """
        # Run the blocking video generation in a thread pool
        import concurrent.futures

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            metadata = await loop.run_in_executor(
                pool,
                self._generate_fade_transition_sync,
                first_frame,
                last_frame,
                output_path,
                duration,
            )
        return metadata

    def _generate_fade_transition_sync(
        self,
        first_frame: Path,
        last_frame: Path,
        output_path: Path,
        duration: float,
    ) -> TransitionMetadata:
        """Synchronous implementation of fade transition generation."""
        try:
            # moviepy 2.x uses different import structure
            from moviepy import ImageClip, CompositeVideoClip, vfx
            moviepy_v2 = True
        except ImportError:
            try:
                # Fallback for moviepy 1.x
                from moviepy.editor import ImageClip, CompositeVideoClip
                moviepy_v2 = False
            except ImportError:
                raise ImportError("moviepy is required for simple transitions")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create clips from images
        clip1 = ImageClip(str(first_frame))
        clip2 = ImageClip(str(last_frame))

        # moviepy 2.x uses with_duration instead of set_duration
        if moviepy_v2:
            clip1 = clip1.with_duration(duration)
            clip2 = clip2.with_duration(duration)
            # Create crossfade effect using vfx
            clip2 = clip2.with_effects([vfx.CrossFadeIn(duration)])
        else:
            clip1 = clip1.set_duration(duration)
            clip2 = clip2.set_duration(duration)
            clip2 = clip2.crossfadein(duration)

        # Composite the clips
        final = CompositeVideoClip([clip1, clip2])

        # Write output
        final.write_videofile(
            str(output_path),
            fps=self.fps,
            codec="libx264",
            audio=False,
            logger=None,  # Suppress moviepy output
        )

        # Clean up
        clip1.close()
        clip2.close()
        final.close()

        file_size = output_path.stat().st_size

        return TransitionMetadata(
            duration_seconds=duration,
            file_size_bytes=file_size,
            from_slide=0,
            to_slide=0,
            model="simple_fade",
        )

    async def generate_all_transitions(
        self,
        slides: List[Path],
        output_dir: Path,
        prompt: str = "Smooth transition",  # Ignored, for API compatibility
        duration: float = 1.0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[tuple[Path, TransitionMetadata]]:
        """
        Generate fade transitions between all slides.

        Args:
            slides: List of slide image paths
            output_dir: Directory to save transitions
            prompt: Ignored (for API compatibility with ReplicateVeoClient)
            duration: Duration per transition
            progress_callback: Progress callback

        Returns:
            List of (path, metadata) tuples
        """
        if len(slides) < 2:
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        results = []
        total = len(slides) - 1

        for i in range(total):
            output_path = output_dir / f"transition_{i + 1:02d}.mp4"

            metadata = await self.generate_fade_transition(
                first_frame=slides[i],
                last_frame=slides[i + 1],
                output_path=output_path,
                duration=duration,
            )

            metadata.from_slide = i + 1
            metadata.to_slide = i + 2

            results.append((output_path, metadata))

            if progress_callback:
                progress_callback(i + 1, total)

        return results


async def create_transition_generator(
    use_ai: bool = True,
    api_key: Optional[str] = None,
) -> ReplicateVeoClient | SimpleTransitionGenerator:
    """
    Factory function to create a transition generator.

    Args:
        use_ai: Whether to use AI transitions (Veo 3.1)
        api_key: Optional Replicate API key

    Returns:
        Transition generator instance
    """
    if use_ai:
        key = api_key or get_replicate_api_key()
        if key:
            return ReplicateVeoClient(api_key=key)
        else:
            print("Warning: No Replicate API key, falling back to simple transitions")

    return SimpleTransitionGenerator()
