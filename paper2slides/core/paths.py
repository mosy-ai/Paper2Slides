"""
Path generation functions for checkpoints and outputs
"""
from pathlib import Path
from datetime import datetime
from typing import Dict


def get_base_dir(output_dir: str, project_name: str, content_type: str) -> Path:
    """Get base directory for project."""
    return Path(output_dir) / project_name / content_type


def get_mode_dir(base_dir: Path, config: Dict) -> Path:
    """Get mode-specific directory (fast or normal)."""
    fast_mode = config.get("fast_mode", False)
    mode = "fast" if fast_mode else "normal"
    return base_dir / mode


def get_config_name(config: Dict) -> str:
    """Generate config directory name: {output}_{style}_{param}."""
    output_type = config.get("output_type", "slides")
    style = config.get("style", "academic")
    
    if output_type == "poster":
        param = config.get("poster_density", "medium")
    else:
        param = config.get("slides_length", "medium")
    
    # Handle custom style. Use hash suffix
    if style == "custom":
        custom = config.get("custom_style", "")
        # Use first 16 chars of custom style
        suffix = custom[:16].replace(" ", "_").replace("/", "_") if custom else "custom"
        style = f"custom_{suffix}"
    
    return f"{output_type}_{style}_{param}"


def get_config_dir(base_dir: Path, config: Dict) -> Path:
    """Get config-specific directory for plan and output."""
    mode_dir = get_mode_dir(base_dir, config)
    return mode_dir / get_config_name(config)


def get_rag_checkpoint(base_dir: Path, config: Dict) -> Path:
    """Get path to RAG checkpoint file."""
    mode_dir = get_mode_dir(base_dir, config)
    return mode_dir / "checkpoint_rag.json"


def get_summary_checkpoint(base_dir: Path, config: Dict) -> Path:
    """Get path to summary checkpoint file."""
    mode_dir = get_mode_dir(base_dir, config)
    return mode_dir / "checkpoint_summary.json"


def get_summary_md(base_dir: Path, config: Dict) -> Path:
    """Get path to summary markdown file."""
    mode_dir = get_mode_dir(base_dir, config)
    return mode_dir / "summary.md"


def get_plan_checkpoint(config_dir: Path) -> Path:
    """Get path to plan checkpoint file."""
    return config_dir / "checkpoint_plan.json"


def get_output_dir(config_dir: Path) -> Path:
    """Get output directory with timestamp to preserve history."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return config_dir / timestamp


def get_latest_output_dir(config_dir: Path) -> Path | None:
    """Get the most recent timestamped output directory."""
    if not config_dir.exists():
        return None

    # Find all timestamp directories (format: YYYYMMDD_HHMMSS)
    timestamp_dirs = [
        d for d in config_dir.iterdir()
        if d.is_dir() and len(d.name) == 15 and d.name[8] == "_"
    ]

    if not timestamp_dirs:
        return None

    # Sort by name (which sorts by timestamp) and return latest
    return sorted(timestamp_dirs, reverse=True)[0]


# ============================================================================
# Video Generation Paths
# ============================================================================


def get_video_dir(output_dir: Path) -> Path:
    """
    Get the video generation directory within an output directory.

    Args:
        output_dir: The timestamped output directory containing slides

    Returns:
        Path to the video/ subdirectory
    """
    return output_dir / "video"


def get_video_state_path(video_dir: Path) -> Path:
    """
    Get the path to video_state.json.

    Args:
        video_dir: The video directory

    Returns:
        Path to video_state.json
    """
    return video_dir / "video_state.json"


def get_video_narration_dir(video_dir: Path) -> Path:
    """
    Get the directory for narration audio files.

    Args:
        video_dir: The video directory

    Returns:
        Path to narration/ subdirectory
    """
    return video_dir / "narration"


def get_video_transitions_dir(video_dir: Path) -> Path:
    """
    Get the directory for transition video segments.

    Args:
        video_dir: The video directory

    Returns:
        Path to transitions/ subdirectory
    """
    return video_dir / "transitions"


def get_video_final_dir(video_dir: Path) -> Path:
    """
    Get the directory for final composed video.

    Args:
        video_dir: The video directory

    Returns:
        Path to final/ subdirectory
    """
    return video_dir / "final"


def get_narration_file_path(video_dir: Path, slide_index: int) -> Path:
    """
    Get the path for a slide's narration audio file.

    Args:
        video_dir: The video directory
        slide_index: Index of the slide (0-based)

    Returns:
        Path to the narration audio file
    """
    narration_dir = get_video_narration_dir(video_dir)
    return narration_dir / f"slide_{slide_index + 1:02d}.mp3"


def get_transition_file_path(video_dir: Path, transition_index: int) -> Path:
    """
    Get the path for a transition video segment.

    Args:
        video_dir: The video directory
        transition_index: Index of the transition (0-based)

    Returns:
        Path to the transition video file
    """
    transitions_dir = get_video_transitions_dir(video_dir)
    return transitions_dir / f"transition_{transition_index + 1:02d}.mp4"


def get_final_video_path(video_dir: Path) -> Path:
    """
    Get the path for the final composed video.

    Args:
        video_dir: The video directory

    Returns:
        Path to the final video file
    """
    final_dir = get_video_final_dir(video_dir)
    return final_dir / "presentation.mp4"


def get_video_thumbnail_path(video_dir: Path) -> Path:
    """
    Get the path for the video thumbnail.

    Args:
        video_dir: The video directory

    Returns:
        Path to the thumbnail image
    """
    final_dir = get_video_final_dir(video_dir)
    return final_dir / "thumbnail.jpg"


def setup_video_directories(video_dir: Path) -> None:
    """
    Create all necessary video generation directories.

    Args:
        video_dir: The video directory to set up
    """
    get_video_narration_dir(video_dir).mkdir(parents=True, exist_ok=True)
    get_video_transitions_dir(video_dir).mkdir(parents=True, exist_ok=True)
    get_video_final_dir(video_dir).mkdir(parents=True, exist_ok=True)
