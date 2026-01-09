"""
Video state management for tracking generation progress.

State is stored in video_state.json within the video output directory,
following the same pattern as the existing checkpoint system.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json

from .config import (
    VideoConfig,
    VideoStatus,
    VideoStage,
    StageStatus,
    VideoProgress,
    VideoOutput,
)


def create_video_state(
    session_id: str,
    config: VideoConfig,
    total_slides: int,
) -> Dict[str, Any]:
    """
    Create a new video state dictionary.

    Args:
        session_id: Unique identifier for the video generation session
        config: Video generation configuration
        total_slides: Number of slides to process

    Returns:
        Initial state dictionary
    """
    now = datetime.now().isoformat()

    return {
        "session_id": session_id,
        "created_at": now,
        "updated_at": now,
        "config": config.to_dict(),
        "status": VideoStatus.PENDING.value,
        "progress": VideoProgress(
            current_stage=VideoStage.SCRIPT_GENERATION,
            current_slide=0,
            total_slides=total_slides,
            percentage=0.0,
            message="Initializing video generation...",
        ).to_dict(),
        "stages": {
            VideoStage.SCRIPT_GENERATION.value: StageStatus.PENDING.value,
            VideoStage.NARRATION.value: StageStatus.PENDING.value,
            VideoStage.TRANSITIONS.value: StageStatus.PENDING.value,
            VideoStage.COMPOSITION.value: StageStatus.PENDING.value,
            VideoStage.EXPORT.value: StageStatus.PENDING.value,
        },
        "output": None,
        "error": None,
        # Metadata for intermediate files
        "narration_files": [],  # List of generated audio file paths
        "transition_files": [],  # List of generated transition video paths
        "scripts": [],  # Generated narration scripts per slide
    }


def load_video_state(state_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load video state from JSON file.

    Args:
        state_path: Path to video_state.json

    Returns:
        State dictionary or None if file doesn't exist
    """
    if not state_path.exists():
        return None

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading video state: {e}")
        return None


def save_video_state(state_path: Path, state: Dict[str, Any]) -> bool:
    """
    Save video state to JSON file.

    Args:
        state_path: Path to video_state.json
        state: State dictionary to save

    Returns:
        True if successful, False otherwise
    """
    try:
        # Update timestamp
        state["updated_at"] = datetime.now().isoformat()

        # Ensure parent directory exists
        state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

        return True
    except IOError as e:
        print(f"Error saving video state: {e}")
        return False


def update_video_status(
    state_path: Path,
    status: VideoStatus,
    error: Optional[str] = None,
) -> bool:
    """
    Update the overall video generation status.

    Args:
        state_path: Path to video_state.json
        status: New status
        error: Optional error message if failed

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    state["status"] = status.value
    if error:
        state["error"] = error

    return save_video_state(state_path, state)


def update_video_stage(
    state_path: Path,
    stage: VideoStage,
    stage_status: StageStatus,
    message: Optional[str] = None,
) -> bool:
    """
    Update a specific stage's status.

    Args:
        state_path: Path to video_state.json
        stage: Stage to update
        stage_status: New status for the stage
        message: Optional progress message

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    state["stages"][stage.value] = stage_status.value

    # Update overall status if stage is running
    if stage_status == StageStatus.RUNNING:
        state["status"] = VideoStatus.RUNNING.value
        state["progress"]["current_stage"] = stage.value

    # Update message if provided
    if message:
        state["progress"]["message"] = message

    return save_video_state(state_path, state)


def update_video_progress(
    state_path: Path,
    current_slide: Optional[int] = None,
    percentage: Optional[float] = None,
    message: Optional[str] = None,
) -> bool:
    """
    Update video generation progress.

    Args:
        state_path: Path to video_state.json
        current_slide: Current slide being processed
        percentage: Overall percentage complete
        message: Progress message

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    if current_slide is not None:
        state["progress"]["current_slide"] = current_slide

    if percentage is not None:
        state["progress"]["percentage"] = percentage

    if message is not None:
        state["progress"]["message"] = message

    return save_video_state(state_path, state)


def add_narration_file(state_path: Path, file_path: str) -> bool:
    """
    Add a generated narration file to the state.

    Args:
        state_path: Path to video_state.json
        file_path: Path to the generated audio file

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    state["narration_files"].append(file_path)
    return save_video_state(state_path, state)


def add_transition_file(state_path: Path, file_path: str) -> bool:
    """
    Add a generated transition file to the state.

    Args:
        state_path: Path to video_state.json
        file_path: Path to the generated transition video

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    state["transition_files"].append(file_path)
    return save_video_state(state_path, state)


def add_script(state_path: Path, slide_index: int, script: str) -> bool:
    """
    Add a generated narration script for a slide.

    Args:
        state_path: Path to video_state.json
        slide_index: Index of the slide
        script: Generated narration script

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    # Ensure scripts list is long enough
    while len(state["scripts"]) <= slide_index:
        state["scripts"].append("")

    state["scripts"][slide_index] = script
    return save_video_state(state_path, state)


def set_video_output(
    state_path: Path,
    video_url: str,
    duration_seconds: float,
    file_size_mb: float,
    thumbnail_url: Optional[str] = None,
) -> bool:
    """
    Set the final video output information.

    Args:
        state_path: Path to video_state.json
        video_url: URL/path to the final video
        duration_seconds: Video duration in seconds
        file_size_mb: File size in megabytes
        thumbnail_url: Optional thumbnail URL

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    config = VideoConfig.from_dict(state["config"])
    width, height = config.get_resolution_dimensions()

    state["output"] = VideoOutput(
        video_url=video_url,
        thumbnail_url=thumbnail_url or "",
        duration_seconds=duration_seconds,
        file_size_mb=file_size_mb,
        resolution=f"{width}x{height}",
    ).to_dict()

    state["status"] = VideoStatus.COMPLETED.value

    # Mark all stages as completed
    for stage in VideoStage:
        state["stages"][stage.value] = StageStatus.COMPLETED.value

    state["progress"]["percentage"] = 100.0
    state["progress"]["message"] = "Video generation complete!"

    return save_video_state(state_path, state)


def mark_video_failed(
    state_path: Path,
    error_message: str,
    failed_stage: Optional[VideoStage] = None,
) -> bool:
    """
    Mark video generation as failed.

    Args:
        state_path: Path to video_state.json
        error_message: Error message describing the failure
        failed_stage: Optional stage where failure occurred

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    state["status"] = VideoStatus.FAILED.value
    state["error"] = error_message

    if failed_stage:
        state["stages"][failed_stage.value] = StageStatus.FAILED.value
        state["progress"]["current_stage"] = failed_stage.value

    state["progress"]["message"] = f"Failed: {error_message}"

    return save_video_state(state_path, state)


def mark_video_cancelled(state_path: Path) -> bool:
    """
    Mark video generation as cancelled.

    Args:
        state_path: Path to video_state.json

    Returns:
        True if successful
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    state["status"] = VideoStatus.CANCELLED.value
    state["progress"]["message"] = "Video generation cancelled by user"

    return save_video_state(state_path, state)


def is_video_cancelled(state_path: Path) -> bool:
    """
    Check if video generation has been cancelled.

    Args:
        state_path: Path to video_state.json

    Returns:
        True if cancelled
    """
    state = load_video_state(state_path)
    if state is None:
        return False

    return state.get("status") == VideoStatus.CANCELLED.value


def get_video_status_summary(state_path: Path) -> Optional[Dict[str, Any]]:
    """
    Get a summary of the video generation status for API response.

    Args:
        state_path: Path to video_state.json

    Returns:
        Summary dictionary suitable for API response
    """
    state = load_video_state(state_path)
    if state is None:
        return None

    return {
        "session_id": state.get("session_id"),
        "status": state.get("status"),
        "progress": state.get("progress"),
        "stages": state.get("stages"),
        "output": state.get("output"),
        "error": state.get("error"),
        "updated_at": state.get("updated_at"),
    }
