"""
FastAPI server for Paper2Slides
"""

import asyncio
import base64
import json
import logging
import re
import sys
import unicodedata
import urllib.parse
import uuid
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from langfuse import observe
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Add parent directory to path to import paper2slides modules
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import paper2slides functions
from paper2slides.core import (
    detect_start_stage,
    get_base_dir,
    get_config_dir,
    get_config_name,
    get_plan_checkpoint,
    run_pipeline,
    continue_pipeline_from_generate,
    is_awaiting_confirmation,
)
from paper2slides.core.state import STAGES, create_state, load_state, save_state
from paper2slides.utils import setup_logging
from paper2slides.utils.path_utils import get_project_name

# Configuration - use project root directories
UPLOAD_DIR = PROJECT_ROOT / "sources" / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def sanitize_filename(filename: str, max_bytes: int = 200) -> str:
    """
    Sanitize a filename for safe filesystem storage.

    Handles:
    1. URL-decode percent-encoded characters (e.g., %C6%B0 → ư)
    2. Normalize unicode to NFC (composed form)
    3. Remove/replace dangerous filesystem characters
    4. Truncate to max_bytes while preserving extension
    5. Fall back to UUID if filename is still problematic

    Args:
        filename: The original filename (may be percent-encoded)
        max_bytes: Maximum length in bytes for the filename

    Returns:
        A safe filename that can be stored on the filesystem
    """
    if not filename:
        return str(uuid.uuid4()) + ".bin"

    # URL-decode the filename (handles %C6%B0 → ư, %20 → space, etc.)
    decoded = urllib.parse.unquote(filename)

    # Normalize unicode to NFC (composed form) for consistent handling
    decoded = unicodedata.normalize("NFC", decoded)

    # Replace dangerous filesystem characters with underscore
    decoded = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", decoded)

    # Remove leading/trailing whitespace and dots
    decoded = decoded.strip().strip(".")

    if not decoded:
        return str(uuid.uuid4()) + ".bin"

    # Separate extension from name
    if "." in decoded:
        name, ext = decoded.rsplit(".", 1)
        ext = "." + ext[:10]  # Limit extension length to 10 chars
    else:
        name, ext = decoded, ""

    # Encode to bytes to check actual length
    name_bytes = name.encode("utf-8")
    ext_bytes = ext.encode("utf-8")

    # Calculate max name length (reserve space for extension)
    max_name_bytes = max_bytes - len(ext_bytes)

    # Truncate name if too long (careful with multi-byte UTF-8 chars)
    if len(name_bytes) > max_name_bytes:
        truncated = name_bytes[:max_name_bytes]
        # Decode back, handling potential partial multi-byte characters
        while truncated:
            try:
                name = truncated.decode("utf-8")
                break
            except UnicodeDecodeError:
                truncated = truncated[:-1]
        else:
            # Fallback to UUID if decoding fails completely
            name = str(uuid.uuid4())

    result = name + ext

    # Final safety check
    if not result or len(result.encode("utf-8")) > 255:
        result = str(uuid.uuid4()) + ext

    return result


app = FastAPI(title="Paper2Slides API", version="1.0.0")

# Configure logging for paper2slides
setup_logging(level=logging.INFO)


# Global state for tracking running sessions
class SessionManager:
    def __init__(self):
        self.running_session = None
        self.cancelled_sessions = set()  # Track cancelled session IDs
        self.lock = asyncio.Lock()

    async def start_session(self, session_id: str) -> bool:
        """Try to start a new session. Returns False if another session is already running"""
        async with self.lock:
            if self.running_session is not None:
                return False
            self.running_session = session_id
            # Remove from cancelled set when starting (for regeneration cases)
            self.cancelled_sessions.discard(session_id)
            return True

    async def end_session(self, session_id: str):
        """End a session"""
        async with self.lock:
            if self.running_session == session_id:
                self.running_session = None
            # Keep cancelled flag for a bit, clean up later if needed

    async def cancel_session(self, session_id: str) -> bool:
        """Cancel a running session. Returns True if session was running"""
        async with self.lock:
            if self.running_session == session_id:
                self.cancelled_sessions.add(session_id)
                logger.info(f"Session {session_id[:8]} marked for cancellation")
                return True
            return False

    def is_cancelled(self, session_id: str) -> bool:
        """Check if a session has been cancelled"""
        return session_id in self.cancelled_sessions

    def get_running_session(self) -> Optional[str]:
        """Get the currently running session ID"""
        return self.running_session


session_manager = SessionManager()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],  # Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving generated files
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
# Mount uploads directory for serving uploaded source files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


class ChatResponse(BaseModel):
    message: str
    slides: Optional[List[dict]] = None
    ppt_url: Optional[str] = None
    poster_url: Optional[str] = None
    session_id: Optional[str] = None
    uploaded_files: Optional[List[dict]] = None


@app.get("/")
async def root():
    return {"message": "Paper2Slides API Server", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/session/running")
async def get_running_session():
    """Check if there is a session currently running"""
    running_session = session_manager.get_running_session()
    return {
        "has_running_session": running_session is not None,
        "running_session_id": running_session[:8] if running_session else None,
    }


@app.post("/api/cancel/{session_id}")
async def cancel_session(session_id: str):
    """Cancel a running session"""
    try:
        cancelled = await session_manager.cancel_session(session_id)
        if cancelled:
            return {
                "message": f"Session {session_id[:8]} cancellation requested",
                "cancelled": True,
            }
        else:
            return {
                "message": f"Session {session_id[:8]} is not running",
                "cancelled": False,
            }
    except Exception as e:
        logger.error(f"Error cancelling session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    background_tasks: BackgroundTasks,
    message: str = Form(""),
    content: str = Form("paper"),  # 'paper' or 'general'
    output_type: str = Form("slides"),  # 'slides' or 'poster'
    style: str = Form("doraemon"),  # 'academic', 'doraemon', or custom description
    length: Optional[str] = Form(None),  # 'short', 'medium', 'long' (for slides)
    density: Optional[str] = Form(None),  # 'sparse', 'medium', 'dense' (for poster)
    fast_mode: Optional[str] = Form(
        None
    ),  # 'true' or 'false' - fast mode for paper content
    language: str = Form("vietnamese"),  # 'vietnamese' or 'english'
    session_id: Optional[str] = Form(None),  # Existing session ID to reuse files
    files: List[UploadFile] = File([]),
):
    """
    Main chat endpoint that receives files and instructions

    Args:
        message: User's text message
        content: 'paper' or 'general'
        output_type: 'slides' or 'poster'
        style: 'academic', 'doraemon', or custom description
        length: 'short', 'medium', 'long' (for slides)
        density: 'sparse', 'medium', 'dense' (for poster)
        fast_mode: 'true' or 'false' - fast mode for paper content (no RAG indexing)
        language: 'vietnamese' or 'english' - language for generation
        session_id: Optional existing session ID to reuse files (for regeneration)
        files: List of uploaded files (PDF, MD, etc.)

    Returns:
        Response with session ID - actual generation happens in background
    """
    try:
        # Check if another session is already running
        running_session = session_manager.get_running_session()

        # Check if reusing existing session
        reusing_session = False
        if session_id and not files:
            # Reuse existing session
            session_dir = UPLOAD_DIR / session_id
            if session_dir.exists():
                reusing_session = True
                print(f"Reusing existing session: {session_id[:8]}")

                # Check if this is a different session from the running one
                if running_session and running_session != session_id:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Another session is already running. Please wait for it to complete. Running session: {running_session[:8]}",
                    )
            else:
                raise HTTPException(
                    status_code=404, detail=f"Session {session_id} not found"
                )
        else:
            # Generate new session ID
            if running_session:
                raise HTTPException(
                    status_code=409,
                    detail=f"Another session is already running. Please wait for it to complete. Running session: {running_session[:8]}",
                )

            session_id = str(uuid.uuid4())
            session_dir = UPLOAD_DIR / session_id
            session_dir.mkdir(exist_ok=True)

        # Save uploaded files or load existing files
        saved_files = []
        if reusing_session:
            # Load existing files from session directory
            for file_path in session_dir.iterdir():
                if file_path.is_file():
                    saved_files.append(
                        {
                            "filename": file_path.name,
                            "path": str(file_path),
                            "size": file_path.stat().st_size,
                        }
                    )
            print(f"Loaded {len(saved_files)} existing file(s) from session")
        else:
            # Save newly uploaded files
            for file in files:
                if file.filename:
                    # Sanitize filename to prevent "File name too long" errors
                    # (Vietnamese UTF-8 chars get percent-encoded in HTTP headers,
                    # expanding each char from 2-3 bytes to 6-9 bytes)
                    safe_filename = sanitize_filename(file.filename)
                    file_path = session_dir / safe_filename
                    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
                    with open(file_path, "wb") as buffer:
                        while chunk := file.file.read(CHUNK_SIZE):
                            buffer.write(chunk)
                    saved_files.append(
                        {
                            "filename": safe_filename,  # Use safe filename for filesystem
                            "original_filename": urllib.parse.unquote(file.filename),  # Keep original for display
                            "path": str(file_path),
                            "size": file_path.stat().st_size,
                        }
                    )
                    print(f"Saved file: {file_path}")

        # Parse fast_mode from string to boolean
        fast_mode_bool = fast_mode and fast_mode.lower() == "true"

        # Log received request
        print(f"\n{'=' * 60}")
        print(f"New Request (Session: {session_id[:8]})")
        print(f"Files: {len(saved_files)} file(s)")
        for f in saved_files:
            display_name = f.get("original_filename", f["filename"])
            print(f"  - {display_name} ({f['size']} bytes)")
        print(f"Config: {output_type} | {style} | {content} | {language}")
        if length:
            print(f"  Length: {length}")
        if density:
            print(f"  Density: {density}")
        if content == "paper" and fast_mode_bool:
            print(f"  Fast Mode: enabled")
        print(f"{'=' * 60}\n")

        # Prepare initial response with session_id and uploaded files
        response_data = {
            "message": f"Processing {len(saved_files)} file(s)...",
            "session_id": session_id,
            "uploaded_files": [
                {
                    # Use original filename for display, safe filename for URL
                    "name": f.get("original_filename", f["filename"]),
                    "size": f["size"],
                    "url": f"/uploads/{session_id}/{f['filename']}",
                }
                for f in saved_files
            ],
            "slides": [],
            "ppt_url": None,
            "poster_url": None,
        }

        # Start the pipeline in background
        background_tasks.add_task(
            run_pipeline_background,
            session_id,
            message,
            saved_files,
            content,
            output_type,
            style,
            length,
            density,
            fast_mode_bool,
            language,
            session_manager,  # Pass session manager to check for cancellation
        )

        # Return immediately so frontend can start polling
        return JSONResponse(content=response_data)

    except HTTPException:
        raise  # Re-raise HTTPException with original status code (e.g., 409)
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


async def generate_slides_with_pipeline(
    session_id: str,
    message: str,
    files: List[dict],
    content: str,
    output_type: str,
    style: str,
    length: Optional[str] = None,
    density: Optional[str] = None,
    fast_mode: bool = False,
    language: str = "vietnamese",
    session_manager: SessionManager = None,
) -> dict:
    """
    Run the actual Paper2Slides pipeline

    Args:
        session_id: Unique session ID for this upload
        message: User message
        files: List of saved file info
        content: 'paper' or 'general'
        output_type: 'slides' or 'poster'
        style: 'academic', 'doraemon', or custom description
        length: 'short', 'medium', 'long' (for slides)
        density: 'sparse', 'medium', 'dense' (for poster)
        fast_mode: Fast mode for paper content (no RAG indexing)
        language: 'vietnamese' or 'english' - language for generation

    Returns:
        Dictionary with slides info and output paths
    """
    # Find PDF files (support multiple PDFs in one session)
    pdf_files = [f for f in files if f["filename"].lower().endswith(".pdf")]
    if not pdf_files:
        raise ValueError("No PDF file found in uploaded files")

    # Parse style and message
    # Priority: message > style parameter
    PREDEFINED_STYLES = {"academic", "doraemon"}

    if message and message.strip():
        # If user provided message, use it as custom style description
        style_type = "custom"
        custom_style = message.strip()
    elif style.lower() in PREDEFINED_STYLES:
        # Use predefined style
        style_type = style.lower()
        custom_style = None
    else:
        # Use style parameter as custom description
        style_type = "custom"
        custom_style = style

    # Handle multiple PDFs: all paths in a list
    pdf_paths = [f["path"] for f in pdf_files]

    # Determine paths (using session-based directory for multiple PDFs)
    if len(pdf_paths) > 1:
        # Multiple PDFs: use session_id as the identifier
        project_name = f"session_{session_id[:8]}"
        # Use session directory as input_path for multiple files
        input_path = str(Path(pdf_paths[0]).parent)
        print(f"Processing {len(pdf_paths)} PDFs as a single project")
    else:
        # Single PDF: use pdf name
        project_name = get_project_name(pdf_paths[0])
        # Use the single PDF path as input_path
        input_path = pdf_paths[0]

    # Build config matching main.py format
    config = {
        "input_path": input_path,  # Required by RAG stage
        "pdf_paths": pdf_paths,  # Support multiple PDFs
        "content_type": content,
        "output_type": output_type,
        "style": style_type,
        "custom_style": custom_style,
        "slides_length": length or "medium",
        "poster_density": density or "medium",
        "fast_mode": fast_mode
        if content == "paper"
        else False,  # Fast mode only for paper content
        "language": language,
    }

    base_dir = get_base_dir(str(OUTPUT_DIR), project_name, content)
    config_dir = get_config_dir(base_dir, config)

    print(f"\nPipeline Configuration:")
    print(f"  Project: {project_name}")
    print(f"  PDFs: {len(pdf_paths)}")
    for i, path in enumerate(pdf_paths, 1):
        print(f"    [{i}] {Path(path).name}")
    if message and message.strip():
        print(f"  Message: {message}")
    print(f"  Output: {base_dir}")
    print(f"  Config: {config_dir.name}")

    # Detect start stage first
    from_stage = detect_start_stage(base_dir, config_dir, config)
    print(f"Starting from stage: {from_stage}")

    initial_state = create_state(config)

    # Add session_id to state for tracking
    initial_state["session_id"] = session_id

    # Mark stages before from_stage as completed (they are being reused)
    start_idx = STAGES.index(from_stage)
    for i in range(start_idx):
        initial_state["stages"][STAGES[i]] = "completed"

    save_state(config_dir, initial_state)
    print(f"  Initial state saved (starting from {from_stage})")

    # Run the pipeline (base_dir already handles document grouping)
    # Pass session_manager to enable cancellation checks
    # pause_after_plan=True pauses after plan stage for user confirmation
    await run_pipeline(
        base_dir, config_dir, config, from_stage, session_id, session_manager,
        pause_after_plan=True
    )

    # Find generated output
    output_files = []
    if config_dir.exists():
        # Find latest timestamped directory
        timestamp_dirs = sorted(
            [d for d in config_dir.iterdir() if d.is_dir()], reverse=True
        )
        if timestamp_dirs:
            latest_output = timestamp_dirs[0]
            # Collect generated files
            for file_path in latest_output.iterdir():
                if file_path.is_file():
                    output_files.append(
                        {
                            "filename": file_path.name,
                            "path": str(file_path),
                            "relative_path": str(file_path.relative_to(OUTPUT_DIR)),
                        }
                    )

    return {
        "output_dir": str(config_dir),
        "output_files": output_files,
        "num_files": len(output_files),
    }


def _update_state_on_error(
    session_id: str,
    error_msg: str,
    files: List[dict],
    content: str,
    output_type: str,
    style: str,
    length: Optional[str],
    density: Optional[str],
    fast_mode: bool,
):
    """Update state.json when background pipeline fails"""

    # Find PDF files
    pdf_files = [f for f in files if f["filename"].lower().endswith(".pdf")]
    if not pdf_files:
        return

    pdf_paths = [f["path"] for f in pdf_files]
    if len(pdf_paths) > 1:
        project_name = f"session_{session_id[:8]}"
    else:
        project_name = get_project_name(pdf_paths[0])

    # Determine which stage failed by checking state file
    base_dir = get_base_dir(str(OUTPUT_DIR), project_name, content)

    # Build config to find config_dir
    PREDEFINED_STYLES = {"academic", "doraemon"}
    style_type = style.lower() if style.lower() in PREDEFINED_STYLES else "custom"

    config = {
        "output_type": output_type,
        "style": style_type,
        "slides_length": length or "medium",
        "poster_density": density or "medium",
        "fast_mode": fast_mode if content == "paper" else False,
    }

    config_dir = get_config_dir(base_dir, config)

    # Load and update state
    state = load_state(config_dir)
    if state:
        # Find the running stage and mark it as failed
        for stage_name, stage_status in state.get("stages", {}).items():
            if stage_status == "running":
                state["stages"][stage_name] = "failed"
                break
        state["error"] = error_msg
        save_state(config_dir, state)
        logger.info(f"Updated state.json with error for session {session_id[:8]}")


@observe(name="run_pipeline_background")
async def run_pipeline_background(
    session_id: str,
    message: str,
    files: List[dict],
    content: str,
    output_type: str,
    style: str,
    length: Optional[str],
    density: Optional[str],
    fast_mode: bool = False,
    language: str = "vietnamese",
    session_manager: SessionManager = None,
):
    """
    Run pipeline in background and store results
    """
    try:
        # Try to start the session
        can_start = await session_manager.start_session(session_id)
        if not can_start:
            logger.error(
                f"Cannot start session {session_id[:8]} - another session is already running"
            )
            # Store error in state
            if not hasattr(app.state, "results"):
                app.state.results = {}
            app.state.results[session_id] = {
                "error": "Another session is already running"
            }
            return

        logger.info(f"Starting background pipeline for session {session_id[:8]}")
        result = await generate_slides_with_pipeline(
            session_id,
            message,
            files,
            content,
            output_type,
            style,
            length,
            density,
            fast_mode,
            language,
            session_manager,
        )

        # Check if cancelled after completion
        if session_manager and session_manager.is_cancelled(session_id):
            logger.info(f"Session {session_id[:8]} was cancelled")
            raise Exception("Generation cancelled by user")

        logger.info(f"Background pipeline completed for session {session_id[:8]}")

        # Store result in a simple cache (in production, use Redis or database)
        if not hasattr(app.state, "results"):
            app.state.results = {}
        app.state.results[session_id] = result

    except Exception as e:
        logger.error(
            f"Background pipeline failed for session {session_id[:8]}: {e}",
            exc_info=True,
        )
        # Store error in state
        if not hasattr(app.state, "results"):
            app.state.results = {}
        app.state.results[session_id] = {"error": str(e)}

        # Also update the state.json file to reflect the failure
        try:
            _update_state_on_error(
                session_id,
                str(e),
                files,
                content,
                output_type,
                style,
                length,
                density,
                fast_mode,
            )
        except Exception as state_err:
            logger.error(f"Failed to update state file: {state_err}")
    finally:
        # Always end the session when done (success or failure)
        await session_manager.end_session(session_id)
        logger.info(f"Session {session_id[:8]} ended")


@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    """Get processing status for a session"""
    try:
        # Find the output directory for this session
        session_dir = UPLOAD_DIR / session_id
        if not session_dir.exists():
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

        # Get PDF files from session
        pdf_files = list(session_dir.glob("*.pdf"))
        if not pdf_files:
            return {"session_id": session_id, "status": "no_files", "stages": {}}

        # Determine project name and paths
        if len(pdf_files) > 1:
            project_name = f"session_{session_id[:8]}"
        else:
            project_name = get_project_name(str(pdf_files[0]))

        # Check both paper and general content types
        state_data = None
        most_recent_time = None

        for content_type in ["paper", "general"]:
            base_dir = Path(get_base_dir(str(OUTPUT_DIR), project_name, content_type))
            if base_dir.exists():
                # Look for all state.json files in config directories
                for state_file_path in base_dir.rglob("state.json"):
                    if state_file_path.is_file():
                        try:
                            with open(state_file_path, "r") as f:
                                current_state = json.load(f)

                            # First priority: exact match by session_id
                            if current_state.get("session_id") == session_id:
                                state_data = current_state
                                logger.debug(
                                    f"Found exact session match: {state_file_path}"
                                )
                                break

                            # Second priority: most recently updated (fallback for old state files)
                            updated_at = current_state.get(
                                "updated_at"
                            ) or current_state.get("created_at")
                            if updated_at:
                                if (
                                    most_recent_time is None
                                    or updated_at > most_recent_time
                                ):
                                    most_recent_time = updated_at
                                    # Only use as fallback if no exact match found
                                    if (
                                        state_data is None
                                        or state_data.get("session_id") != session_id
                                    ):
                                        state_data = current_state
                        except Exception as e:
                            logger.warning(
                                f"Error reading state file {state_file_path}: {e}"
                            )
                            continue

                # If found exact match, stop searching
                if state_data and state_data.get("session_id") == session_id:
                    break

        if not state_data:
            return {
                "session_id": session_id,
                "status": "pending",
                "stages": {
                    "rag": "pending",
                    "summary": "pending",
                    "plan": "pending",
                    "generate": "pending",
                },
            }

        # Determine overall status
        stages = state_data.get("stages", {})
        if any(status == "failed" for status in stages.values()):
            overall_status = "failed"
        elif stages.get("generate") == "awaiting_confirmation":
            overall_status = "awaiting_confirmation"
        elif all(status == "completed" for status in stages.values()):
            overall_status = "completed"
        elif any(status == "running" for status in stages.values()):
            overall_status = "running"
        else:
            overall_status = "pending"

        return {
            "session_id": session_id,
            "status": overall_status,
            "stages": stages,
            "error": state_data.get("error"),
            "updated_at": state_data.get("updated_at"),
        }

    except Exception as e:
        logger.error(
            f"Error getting status for session {session_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    """Get the final result for a completed session"""
    try:
        # Check if result is in cache
        if hasattr(app.state, "results") and session_id in app.state.results:
            result = app.state.results[session_id]

            if "error" in result:
                raise HTTPException(status_code=500, detail=result["error"])

            # Prepare response with output files
            output_files = result.get("output_files", [])

            # Find PDF file in output
            pdf_file = next(
                (f for f in output_files if f["filename"].endswith(".pdf")), None
            )
            # Find image files and sort by filename to ensure correct order
            image_files = sorted(
                [
                    f
                    for f in output_files
                    if f["filename"].endswith((".png", ".jpg", ".jpeg", ".webp"))
                ],
                key=lambda x: x["filename"]
            )

            # Get output_type from state
            session_dir = UPLOAD_DIR / session_id
            pdf_files = list(session_dir.glob("*.pdf"))
            if len(pdf_files) > 1:
                project_name = f"session_{session_id[:8]}"
            else:
                project_name = get_project_name(str(pdf_files[0]))

            output_type = "slides"  # default
            for content_type in ["paper", "general"]:
                base_dir = Path(
                    get_base_dir(str(OUTPUT_DIR), project_name, content_type)
                )
                if base_dir.exists():
                    for state_file_path in base_dir.rglob("state.json"):
                        if state_file_path.is_file():
                            try:
                                with open(state_file_path, "r") as f:
                                    state_data = json.load(f)
                                    output_type = state_data.get("config", {}).get(
                                        "output_type", "slides"
                                    )
                                    break
                            except:
                                pass
                    if output_type != "slides":
                        break

            response_data = {
                "session_id": session_id,
                "slides": [
                    {
                        "title": f"Slide {i + 1}",
                        "image_url": f"/outputs/{img['relative_path']}",
                    }
                    for i, img in enumerate(image_files)
                ],
            }

            # Add download links
            if pdf_file:
                if output_type == "slides":
                    response_data["ppt_url"] = f"/outputs/{pdf_file['relative_path']}"
                elif output_type == "poster":
                    response_data["poster_url"] = (
                        f"/outputs/{pdf_file['relative_path']}"
                    )
            elif image_files and output_type == "poster":
                # If no PDF but has images, use first image as poster
                response_data["poster_url"] = (
                    f"/outputs/{image_files[0]['relative_path']}"
                )

            return JSONResponse(content=response_data)

        # If not in cache, return not ready
        return JSONResponse(
            status_code=202,
            content={"message": "Result not ready yet", "session_id": session_id},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting result for session {session_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


def extract_slide_content(session_id: str) -> dict:
    """
    Extract structured slide content from checkpoint files.

    Args:
        session_id: The session ID to extract content for

    Returns:
        Dictionary with slides array containing structured content

    Raises:
        HTTPException: If session not found, not completed, or missing data
    """
    # Find the session directory
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Get PDF files from session
    pdf_files = list(session_dir.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(
            status_code=400, detail=f"No PDF files found in session {session_id}"
        )

    # Determine project name
    if len(pdf_files) > 1:
        project_name = f"session_{session_id[:8]}"
    else:
        project_name = get_project_name(str(pdf_files[0]))

    # Find the checkpoint files by searching both content types
    checkpoint_plan_path = None
    config_dir = None
    timestamp_dir = None

    for content_type in ["paper", "general"]:
        base_dir = Path(get_base_dir(str(OUTPUT_DIR), project_name, content_type))
        if base_dir.exists():
            # Look for checkpoint_plan.json files
            for plan_file in base_dir.rglob("checkpoint_plan.json"):
                if plan_file.is_file():
                    # Check if this is the right session by loading state.json
                    state_file = plan_file.parent / "state.json"
                    if state_file.exists():
                        try:
                            with open(state_file, "r") as f:
                                state_data = json.load(f)
                            if state_data.get("session_id") == session_id:
                                checkpoint_plan_path = plan_file
                                config_dir = plan_file.parent
                                # Find the timestamp directory (where images are)
                                for d in config_dir.iterdir():
                                    if d.is_dir() and not d.name.startswith(
                                        "checkpoint"
                                    ):
                                        timestamp_dir = d
                                        break
                                break
                        except Exception as e:
                            logger.warning(f"Error reading state file: {e}")
                            continue

            if checkpoint_plan_path:
                break

    if not checkpoint_plan_path or not checkpoint_plan_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Checkpoint plan not found for session {session_id}. Generation may not be complete.",
        )

    # Load checkpoint_plan.json
    try:
        with open(checkpoint_plan_path, "r") as f:
            plan_data = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reading checkpoint plan: {str(e)}"
        )

    # Extract sections from nested "plan" object
    plan = plan_data.get("plan", {})
    sections = plan.get("sections", [])
    tables_index = plan_data.get("tables_index", {})
    figures_index = plan_data.get("figures_index", {})
    output_type = plan.get("output_type", "slides")

    # Find generated images in timestamp directory
    image_files = []
    if timestamp_dir and timestamp_dir.exists():
        # Sort image files by name (slide_01.png, slide_02.png, etc.)
        image_files = sorted(
            [
                f
                for f in timestamp_dir.iterdir()
                if f.is_file()
                and f.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]
            ]
        )

    # Build structured response
    slides = []
    for i, section in enumerate(sections):
        slide_num = i + 1

        # Get corresponding image if available
        image_url = None
        if i < len(image_files):
            image_file = image_files[i]
            relative_path = image_file.relative_to(OUTPUT_DIR)
            image_url = f"/outputs/{relative_path}"

        # Resolve table references
        tables = []
        for table_ref in section.get("tables", []):
            table_id = table_ref.get("table_id")
            if table_id in tables_index:
                table_info = tables_index[table_id]
                tables.append(
                    {
                        "id": table_info.get("id"),
                        "caption": table_info.get("caption"),
                        "html": table_info.get("html"),
                        "extract": table_ref.get("extract", ""),
                        "focus": table_ref.get("focus", ""),
                    }
                )

        # Resolve figure references
        figures = []
        for figure_ref in section.get("figures", []):
            figure_id = figure_ref.get("figure_id")
            if figure_id in figures_index:
                figure_info = figures_index[figure_id]
                figures.append(
                    {
                        "id": figure_info.get("id"),
                        "caption": figure_info.get("caption"),
                        "focus": figure_ref.get("focus", ""),
                    }
                )

        # Build slide object
        slide = {
            "slide_number": slide_num,
            "section_id": section.get("id"),
            "title": section.get("title"),
            "section_type": section.get("type"),
            "content": section.get("content"),
            "image_url": image_url,
            "tables": tables,
            "figures": figures,
        }

        slides.append(slide)

    return {
        "session_id": session_id,
        "output_type": output_type,
        "total_slides": len(slides),
        "slides": slides,
    }


@app.get("/api/slides/{session_id}/content")
async def get_slide_content(session_id: str):
    """
    Get structured slide content for a completed session.

    Returns detailed content for each slide including:
    - Slide number and title
    - Text content for narration
    - Image URL for the slide
    - Referenced tables and figures with metadata

    This endpoint is designed for programmatic access and video generation workflows.

    Args:
        session_id: The session ID to retrieve content for

    Returns:
        JSON with array of slide objects containing structured content
    """
    try:
        return extract_slide_content(session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error extracting slide content for session {session_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


# Helper function to find config_dir for a session
def find_session_config_dir(session_id: str) -> tuple:
    """Find the config directory for a given session.

    Returns:
        Tuple of (config_dir, base_dir, content_type) or raises HTTPException
    """
    session_dir = UPLOAD_DIR / session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    pdf_files = list(session_dir.glob("*.pdf"))
    if not pdf_files:
        raise HTTPException(status_code=400, detail=f"No PDF files found in session {session_id}")

    if len(pdf_files) > 1:
        project_name = f"session_{session_id[:8]}"
    else:
        project_name = get_project_name(str(pdf_files[0]))

    # Search for the state file with matching session_id
    for content_type in ["paper", "general"]:
        base_dir = Path(get_base_dir(str(OUTPUT_DIR), project_name, content_type))
        if base_dir.exists():
            for state_file in base_dir.rglob("state.json"):
                if state_file.is_file():
                    try:
                        with open(state_file, "r") as f:
                            state_data = json.load(f)
                        if state_data.get("session_id") == session_id:
                            config_dir = state_file.parent
                            return config_dir, base_dir, content_type
                    except Exception:
                        continue

    raise HTTPException(
        status_code=404,
        detail=f"No configuration found for session {session_id}"
    )


@app.get("/api/plan/{session_id}")
async def get_plan(session_id: str):
    """
    Get the content plan for a session.

    Returns the plan data including sections, tables, and figures.
    This endpoint is used to display the outline for editing.
    """
    try:
        config_dir, base_dir, content_type = find_session_config_dir(session_id)

        # Load the plan checkpoint
        plan_checkpoint = config_dir / "checkpoint_plan.json"
        if not plan_checkpoint.exists():
            raise HTTPException(
                status_code=404,
                detail="Plan not yet generated. Wait for plan stage to complete."
            )

        with open(plan_checkpoint, "r") as f:
            plan_data = json.load(f)

        # Load state to check status
        state = load_state(config_dir)
        is_editable = state and state.get("stages", {}).get("generate") == "awaiting_confirmation"

        return {
            "session_id": session_id,
            "plan": plan_data.get("plan", {}),
            "tables_index": plan_data.get("tables_index", {}),
            "figures_index": plan_data.get("figures_index", {}),
            "origin": plan_data.get("origin", {}),
            "content_type": plan_data.get("content_type", content_type),
            "is_editable": is_editable,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan/{session_id}")
async def update_plan(session_id: str, request: dict):
    """
    Update the content plan for a session.

    Accepts modified sections and saves them to the checkpoint.
    Only works when the pipeline is awaiting confirmation.
    """
    try:
        config_dir, base_dir, content_type = find_session_config_dir(session_id)

        # Check if plan is editable
        state = load_state(config_dir)
        if not state or state.get("stages", {}).get("generate") != "awaiting_confirmation":
            raise HTTPException(
                status_code=400,
                detail="Plan cannot be edited at this stage. It's only editable after plan stage completes."
            )

        # Load current plan
        plan_checkpoint = config_dir / "checkpoint_plan.json"
        if not plan_checkpoint.exists():
            raise HTTPException(status_code=404, detail="Plan not found")

        with open(plan_checkpoint, "r") as f:
            plan_data = json.load(f)

        # Update sections if provided
        if "sections" in request:
            plan_data["plan"]["sections"] = request["sections"]

        # Save updated plan
        with open(plan_checkpoint, "w") as f:
            json.dump(plan_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Updated plan for session {session_id}")

        return {
            "success": True,
            "message": "Plan updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating plan for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/plan/{session_id}/confirm")
async def confirm_plan(session_id: str, background_tasks: BackgroundTasks):
    """
    Confirm the plan and continue to generate stage.

    This endpoint resumes the pipeline from the generate stage.
    """
    try:
        config_dir, base_dir, content_type = find_session_config_dir(session_id)

        # Check if awaiting confirmation
        state = load_state(config_dir)
        if not state or state.get("stages", {}).get("generate") != "awaiting_confirmation":
            raise HTTPException(
                status_code=400,
                detail="Pipeline is not awaiting confirmation"
            )

        # Check if another session is running
        running_session = session_manager.get_running_session()
        if running_session and running_session != session_id:
            raise HTTPException(
                status_code=409,
                detail=f"Another session is already running: {running_session[:8]}"
            )

        # Get config from state
        config = state.get("config", {})

        # Start the generate stage in background
        background_tasks.add_task(
            run_generate_background,
            session_id,
            base_dir,
            config_dir,
            config,
            session_manager,
        )

        return {
            "success": True,
            "message": "Generation started",
            "session_id": session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming plan for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def run_generate_background(
    session_id: str,
    base_dir: Path,
    config_dir: Path,
    config: dict,
    session_manager: SessionManager,
):
    """Run the generate stage in background after plan confirmation."""
    try:
        can_start = await session_manager.start_session(session_id)
        if not can_start:
            logger.error(f"Cannot start generate for session {session_id[:8]} - another session is running")
            return

        logger.info(f"Continuing pipeline (generate stage) for session {session_id[:8]}")

        await continue_pipeline_from_generate(
            base_dir, config_dir, config, session_id, session_manager
        )

        # Store result in cache
        output_files = []
        if config_dir.exists():
            timestamp_dirs = sorted(
                [d for d in config_dir.iterdir() if d.is_dir()], reverse=True
            )
            if timestamp_dirs:
                latest_output = timestamp_dirs[0]
                for file_path in latest_output.iterdir():
                    if file_path.is_file():
                        output_files.append({
                            "filename": file_path.name,
                            "path": str(file_path),
                            "relative_path": str(file_path.relative_to(OUTPUT_DIR)),
                        })

        if not hasattr(app.state, "results"):
            app.state.results = {}
        app.state.results[session_id] = {
            "output_dir": str(config_dir),
            "output_files": output_files,
            "num_files": len(output_files),
        }

        logger.info(f"Generate stage completed for session {session_id[:8]}")

    except Exception as e:
        logger.error(f"Generate stage failed for session {session_id[:8]}: {e}", exc_info=True)

        if not hasattr(app.state, "results"):
            app.state.results = {}
        app.state.results[session_id] = {"error": str(e)}

        # Update state
        state = load_state(config_dir)
        if state:
            state["stages"]["generate"] = "failed"
            state["error"] = str(e)
            save_state(config_dir, state)
    finally:
        await session_manager.end_session(session_id)


@app.post("/api/slides/{session_id}/regenerate")
async def regenerate_slide(
    session_id: str,
    slide_index: int = Form(...),
    prompt: Optional[str] = Form(None),
    reference_image: Optional[UploadFile] = File(None),
):
    """
    Regenerate a single slide with optional custom prompt and reference image.

    Args:
        session_id: The session ID
        slide_index: 0-based index of the slide to regenerate
        prompt: Optional custom prompt for regeneration
        reference_image: Optional reference image file for style guidance
    """
    try:
        config_dir, base_dir, content_type = find_session_config_dir(session_id)

        # Load plan checkpoint
        plan_checkpoint = config_dir / "checkpoint_plan.json"
        if not plan_checkpoint.exists():
            raise HTTPException(status_code=404, detail="Plan not found")

        with open(plan_checkpoint, "r") as f:
            plan_data = json.load(f)

        # Load summary checkpoint for GenerationInput
        from paper2slides.core.paths import get_summary_checkpoint
        state = load_state(config_dir)
        config = state.get("config", {})

        summary_checkpoint = get_summary_checkpoint(base_dir, config)
        if not summary_checkpoint.exists():
            raise HTTPException(status_code=404, detail="Summary checkpoint not found")

        with open(summary_checkpoint, "r") as f:
            summary_data = json.load(f)

        # Reconstruct ContentPlan
        from paper2slides.generator.content_planner import ContentPlan, Section, TableRef, FigureRef
        from paper2slides.generator.config import GenerationInput, GenerationConfig, OutputType, StyleType
        from paper2slides.summary.models import OriginalElements, TableInfo, FigureInfo

        plan_raw = plan_data.get("plan", {})
        sections = []
        for s in plan_raw.get("sections", []):
            tables = [TableRef(**t) for t in s.get("tables", [])]
            figures = [FigureRef(**f) for f in s.get("figures", [])]
            sections.append(Section(
                id=s.get("id"),
                title=s.get("title"),
                section_type=s.get("type", "content"),
                content=s.get("content", ""),
                tables=tables,
                figures=figures,
            ))

        # Build tables_index and figures_index
        tables_index = {}
        for tid, tinfo in plan_data.get("tables_index", {}).items():
            tables_index[tid] = TableInfo(
                table_id=tinfo.get("id"),
                caption=tinfo.get("caption", ""),
                html_content=tinfo.get("html", ""),
            )

        figures_index = {}
        for fid, finfo in plan_data.get("figures_index", {}).items():
            figures_index[fid] = FigureInfo(
                figure_id=finfo.get("id"),
                caption=finfo.get("caption"),
                image_path=finfo.get("image_path", ""),
            )

        plan = ContentPlan(
            output_type=plan_raw.get("output_type", "slides"),
            sections=sections,
            tables_index=tables_index,
            figures_index=figures_index,
            metadata=plan_raw.get("metadata", {}),
        )

        # Reconstruct OriginalElements
        origin_data = plan_data.get("origin", {})
        origin_tables = [
            TableInfo(
                table_id=t.get("id", t.get("table_id", "")),
                caption=t.get("caption", ""),
                html_content=t.get("html", t.get("html_content", "")),
            )
            for t in origin_data.get("tables", [])
        ]
        origin_figures = [
            FigureInfo(
                figure_id=f.get("id", f.get("figure_id", "")),
                caption=f.get("caption"),
                image_path=f.get("image_path", ""),
            )
            for f in origin_data.get("figures", [])
        ]
        origin = OriginalElements(
            tables=origin_tables,
            figures=origin_figures,
            base_path=origin_data.get("base_path", str(base_dir)),
        )

        # Build GenerationConfig
        style_value = config.get("style", "academic")
        try:
            style_type = StyleType(style_value)
        except ValueError:
            style_type = StyleType.CUSTOM

        gen_config = GenerationConfig(
            output_type=OutputType(config.get("output_type", "slides")),
            style=style_type,
            custom_style=config.get("custom_style"),
            slides_length=config.get("slides_length", "medium"),
            poster_density=config.get("poster_density", "medium"),
            language=config.get("language", "vietnamese"),
        )

        # Reconstruct content from summary checkpoint
        from paper2slides.summary.paper import PaperContent
        from paper2slides.summary.general import GeneralContent

        content_type = summary_data.get("content_type", "paper")
        content_data = summary_data.get("content", {})

        if content_type == "paper":
            content = PaperContent(
                paper_info=content_data.get("paper_info", ""),
                figures=content_data.get("figures", ""),
                tables=content_data.get("tables", ""),
                equations=content_data.get("equations", ""),
                motivation=content_data.get("motivation", ""),
                solution=content_data.get("solution", ""),
                results=content_data.get("results", ""),
                contributions=content_data.get("contributions", ""),
                raw_rag_results=content_data.get("raw_rag_results", {}),
            )
        else:
            content = GeneralContent(
                content=content_data.get("content", ""),
                raw_rag_results=content_data.get("raw_rag_results", []),
            )

        gen_input = GenerationInput(config=gen_config, content=content, origin=origin)

        # Process reference image if provided
        reference_image_base64 = None
        reference_image_mime = "image/png"
        if reference_image:
            image_data = await reference_image.read()
            reference_image_base64 = base64.b64encode(image_data).decode("utf-8")
            reference_image_mime = reference_image.content_type or "image/png"

        # Find style reference image (slide 2) and old slide from existing outputs
        style_ref_image_data = None
        old_slide_image_data = None
        timestamp_dirs = sorted(
            [d for d in config_dir.iterdir() if d.is_dir()], reverse=True
        )
        if timestamp_dirs:
            latest_output = timestamp_dirs[0]
            # Style reference from slide 2
            slide_2_path = latest_output / "slide_02.png"
            if slide_2_path.exists():
                with open(slide_2_path, "rb") as f:
                    style_ref_image_data = f.read()

            # Find the OLD version of the current slide being regenerated
            for ext in ['.png', '.jpg', '.jpeg']:
                old_slide_path = latest_output / f"slide_{slide_index + 1:02d}{ext}"
                if old_slide_path.exists():
                    with open(old_slide_path, "rb") as f:
                        old_slide_image_data = f.read()
                    break

        # Create ImageGenerator and regenerate
        from paper2slides.generator.image_generator import ImageGenerator

        generator = ImageGenerator()
        result = generator.regenerate_single_slide(
            plan=plan,
            gen_input=gen_input,
            section_index=slide_index,
            custom_prompt=prompt,
            reference_image_base64=reference_image_base64,
            reference_image_mime=reference_image_mime,
            style_ref_image_data=style_ref_image_data,
            old_slide_image_data=old_slide_image_data,
        )

        # Save the regenerated image
        if timestamp_dirs:
            output_dir = timestamp_dirs[0]
        else:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = config_dir / timestamp
            output_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename
        ext = ".png" if "png" in result.mime_type else ".jpg"
        slide_filename = f"slide_{slide_index + 1:02d}{ext}"
        slide_path = output_dir / slide_filename

        # Delete any existing versions of this slide with different extensions
        slide_prefix = f"slide_{slide_index + 1:02d}"
        for old_file in output_dir.glob(f"{slide_prefix}.*"):
            if old_file.suffix.lower() in ['.png', '.jpg', '.jpeg'] and old_file != slide_path:
                old_file.unlink()
                logger.info(f"Deleted old slide file: {old_file.name}")

        with open(slide_path, "wb") as f:
            f.write(result.image_data)

        logger.info(f"Regenerated slide {slide_index + 1} for session {session_id[:8]}")

        # Regenerate PDF with all current slides
        from PIL import Image as PILImage

        slide_files = sorted([
            f for f in output_dir.iterdir()
            if f.is_file() and f.suffix.lower() in ['.png', '.jpg', '.jpeg']
            and f.name.startswith('slide_')
        ])

        if slide_files:
            images = []
            for slide_file in slide_files:
                img = PILImage.open(slide_file)
                images.append(img)

            pdf_path = output_dir / "slides.pdf"
            # Convert to RGB and save
            rgb_images = []
            for img in images:
                if img.mode == 'RGBA':
                    rgb_img = PILImage.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3])
                    rgb_images.append(rgb_img)
                else:
                    rgb_images.append(img.convert('RGB'))

            if rgb_images:
                rgb_images[0].save(pdf_path, save_all=True, append_images=rgb_images[1:])
                logger.info(f"Regenerated PDF after slide {slide_index + 1} update")

        # Return the URL
        relative_path = slide_path.relative_to(OUTPUT_DIR)
        return {
            "success": True,
            "slide_index": slide_index,
            "image_url": f"/outputs/{relative_path}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating slide for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download/{filepath:path}")
async def download_file(filepath: str):
    """Download generated file (supports subdirectories)"""
    file_path = OUTPUT_DIR / filepath

    # Security check: ensure file is within OUTPUT_DIR
    try:
        file_path = file_path.resolve()
        OUTPUT_DIR.resolve()
        if not str(file_path).startswith(str(OUTPUT_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


if __name__ == "__main__":
    import sys

    import uvicorn

    # Allow port to be specified via command line argument
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001

    print("Starting Paper2Slides API server...")
    print(f"Upload directory: {UPLOAD_DIR.absolute()}")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"Server running on http://0.0.0.0:{port}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        timeout_keep_alive=300,
        limit_concurrency=10,
        limit_max_requests=1000,
    )
