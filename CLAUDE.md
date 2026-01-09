# CLAUDE.md - Paper2Slides Project Guide

This file provides context for Claude Code when working on this codebase.

## Code Style Requirements

**IMPORTANT: All imports must be at the top of each file.** Follow this order:
1. Standard library imports
2. Third-party imports
3. Local imports

```python
# Standard library
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Third-party
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from langfuse.openai import OpenAI
from pydantic import BaseModel

# Local imports
from paper2slides.core import run_pipeline, get_base_dir, get_config_dir
from paper2slides.core.state import load_state, save_state, STAGES
from paper2slides.generator.config import GenerationConfig, OutputType, StyleType
from paper2slides.utils import save_json, load_json, setup_logging
```

## Project Overview

Paper2Slides is a document-to-presentation converter that transforms academic papers and general documents into professional slides or posters. It uses a 4-stage RAG-powered pipeline with LLM processing and vision-based image generation.

**Core Flow:** PDF → RAG Indexing → Content Extraction → Layout Planning → Image Generation → Slides/Poster

## Quick Reference

### Running the Application

```bash
# CLI (recommended for development)
uv run python -m paper2slides --input paper.pdf --output slides --style doraemon --length medium --fast

# Web interface
./scripts/start.sh                  # Start both backend + frontend
./scripts/start_backend.sh          # Backend only (port 8001)
./scripts/start_frontend.sh         # Frontend only (port 5173)

# Stop all services
./scripts/stop.sh

# Install dependencies
uv sync

# Add new dependency
uv add <package>

# Add dev dependency
uv add --dev <package>
```

### Key CLI Options

| Option | Values | Description |
|--------|--------|-------------|
| `--input, -i` | path | Input file or directory |
| `--output` | `slides`, `poster` | Output type |
| `--content` | `paper`, `general` | Content type |
| `--style` | `academic`, `doraemon`, custom | Visual style |
| `--length` | `short` (5-8), `medium` (8-12), `long` (12-15) | Slide count |
| `--density` | `sparse`, `medium`, `dense` | Poster density |
| `--fast` | flag | Skip RAG indexing, use vision model directly |
| `--parallel N` | int | Parallel slide generation workers |
| `--from-stage` | `rag`, `summary`, `plan`, `generate` | Force restart from stage |
| `--debug` | flag | Enable debug logging |

## Architecture

### Directory Structure

```
Paper2Slides/
├── paper2slides/                 # Core Python package
│   ├── main.py                   # CLI entry point
│   ├── core/                     # Pipeline orchestration
│   │   ├── pipeline.py           # 4-stage pipeline execution
│   │   ├── state.py              # Checkpoint management
│   │   ├── paths.py              # Path generation helpers
│   │   └── stages/               # Individual stage implementations
│   │       ├── rag_stage.py      # Stage 1: Document parsing + RAG
│   │       ├── summary_stage.py  # Stage 2: Content extraction
│   │       ├── plan_stage.py     # Stage 3: Layout planning
│   │       └── generate_stage.py # Stage 4: Image generation
│   ├── rag/                      # RAG client and queries
│   │   ├── client.py             # LightRAG wrapper
│   │   ├── query.py              # Predefined queries by category
│   │   └── config.py             # RAG configuration
│   ├── raganything/              # Multimodal document processing
│   │   ├── batch_parser.py       # Batch document parsing
│   │   ├── parser.py             # MineU/Docling parsers
│   │   └── modalprocessors.py    # Image/table/equation handlers
│   ├── summary/                  # Content extraction
│   │   ├── paper.py              # Paper structure extraction
│   │   ├── general.py            # General document extraction
│   │   ├── models.py             # Data models (TableInfo, FigureInfo, etc.)
│   │   └── extractors/           # Table/figure extractors
│   ├── generator/                # Content planning + image gen
│   │   ├── content_planner.py    # LLM-based slide planning
│   │   ├── image_generator.py    # Vision model image generation
│   │   └── config.py             # Generation config enums
│   ├── prompts/                  # LLM prompt templates
│   │   ├── content_planning.py   # Slide/poster planning prompts
│   │   ├── image_generation.py   # Image gen prompts + style hints
│   │   └── paper_extraction.py   # Section extraction prompts
│   └── utils/                    # Utilities
│       ├── file_utils.py         # JSON/text file helpers
│       ├── logging.py            # Logging setup
│       └── path_utils.py         # Path normalization
├── api/
│   └── server.py                 # FastAPI backend
├── frontend/                     # React + Vite + TailwindCSS
│   ├── src/
│   │   ├── App.jsx               # Main app component
│   │   └── components/           # UI components
│   └── package.json
├── scripts/                      # Shell scripts
├── outputs/                      # Generated outputs (gitignored)
└── sources/uploads/              # Uploaded files (gitignored)
```

### Pipeline Stages

1. **RAG Stage** (`rag_stage.py`)
   - Fast mode: MineU parser → GPT-4o vision queries
   - Normal mode: MineU parser → LightRAG indexing → category-based queries
   - Output: `checkpoint_rag.json`

2. **Summary Stage** (`summary_stage.py`)
   - Extracts structured content from RAG results
   - Parallel LLM processing for section extraction
   - Extracts tables/figures from markdown
   - Output: `checkpoint_summary.json`, `summary.md`

3. **Plan Stage** (`plan_stage.py`)
   - ContentPlanner generates slide/poster layout via LLM
   - Maps tables and figures to sections
   - Output: `checkpoint_plan.json`

4. **Generate Stage** (`generate_stage.py`)
   - ImageGenerator creates images via Gemini vision model
   - Slides 1-2 sequential (style establishment), 3+ parallel
   - Output: PNG images + `slides.pdf`

### Key Data Models

```python
# paper2slides/summary/models.py
@dataclass
class TableInfo:
    table_id: str           # e.g., "Table 1"
    caption: str
    html_content: str
    line_number: int = 0

@dataclass
class FigureInfo:
    figure_id: str          # e.g., "Figure 1"
    caption: Optional[str]
    image_path: str
    line_number: int = 0

@dataclass
class OriginalElements:
    tables: List[TableInfo]
    figures: List[FigureInfo]
    base_path: str

# paper2slides/generator/config.py
class OutputType(Enum):
    POSTER = "poster"
    SLIDES = "slides"

class StyleType(Enum):
    ACADEMIC = "academic"
    DORAEMON = "doraemon"
    CUSTOM = "custom"
```

### Checkpoint System

Checkpoints enable resumption from any stage:

```
outputs/{project}/{content_type}/{mode}/
├── checkpoint_rag.json           # RAG results + markdown paths
├── checkpoint_summary.json       # Extracted content + tables/figures
├── summary.md                    # Human-readable summary
└── {output}_{style}_{param}/     # e.g., slides_doraemon_medium
    ├── state.json                # Stage status tracking
    ├── checkpoint_plan.json      # Slide/poster layout
    └── {timestamp}/              # Generated outputs
        ├── slide_01.png
        └── slides.pdf
```

## Environment Setup

### Required Environment Variables

Create `.env` in `paper2slides/` directory:

```bash
# LLM API (Required)
RAG_LLM_API_KEY=sk-or-v1-...      # OpenRouter API key
RAG_LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o           # Or openai/gpt-4o-mini

# Image Generation (Required)
IMAGE_GEN_PROVIDER=openrouter     # or "google"
IMAGE_GEN_API_KEY=sk-or-v1-...    # Same as RAG or separate
IMAGE_GEN_BASE_URL=https://openrouter.ai/api/v1
IMAGE_GEN_MODEL=google/gemini-3-pro-image-preview

# For Google provider instead:
# IMAGE_GEN_PROVIDER=google
# GOOGLE_GENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
# IMAGE_GEN_MODEL=models/gemini-1.5-flash

# Observability (Optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://langfuse.example.com
```

### Dependencies

- **uv** - Python package manager (required)
- Python 3.12+ (3.13 supported)
- Node.js 18+ (for frontend)
- Key packages: `lightrag-hku`, `mineru[core]`, `openai`, `langfuse`, `fastapi`

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

## Code Patterns & Conventions

### Async Pipeline

The pipeline uses async/await throughout. **Imports at top of file:**

```python
# At top of file
import asyncio
from paper2slides.core.state import STAGES, load_state, save_state
from paper2slides.core.stages import run_rag_stage, run_summary_stage

# Usage - pipeline updates local state files at each stage
async def run_pipeline(base_dir, config_dir, config, from_stage, ...):
    for stage in STAGES[start_idx:]:
        # Update state before running stage
        state = load_state(config_dir)
        state["stages"][stage] = "running"
        save_state(config_dir, state)

        if stage == "rag":
            await run_rag_stage(base_dir, config)
        elif stage == "summary":
            await run_summary_stage(base_dir, config)
        # ...

        # Update state after stage completes
        state["stages"][stage] = "completed"
        save_state(config_dir, state)
```

### LLM Integration

All LLM calls go through `langfuse.openai.OpenAI` for tracing. **Imports at top of file:**

```python
# At top of file
from langfuse.openai import OpenAI

# Usage
client = OpenAI(api_key=api_key, base_url=base_url)
response = client.chat.completions.create(
    model=model,
    messages=[...],
    response_format={"type": "json_object"},  # For structured output
)
```

### Error Handling

Exponential backoff for API calls:

```python
@retry_with_exponential_backoff
def _call_model(self, prompt, reference_images):
    # API call with automatic retry on failure
```

### State Management

State is tracked in `state.json`. **Imports at top of file:**

```python
# At top of file
from datetime import datetime
from paper2slides.core.state import STAGES, create_state, load_state, save_state

# Usage
STAGES = ["rag", "summary", "plan", "generate"]

def create_state(config):
    return {
        "config": config,
        "created_at": datetime.now().isoformat(),
        "stages": {s: "pending" for s in STAGES},
    }

# Background tasks must update state files
state = load_state(config_dir)
state["stages"]["rag"] = "running"
save_state(config_dir, state)
```

### Path Utilities

Consistent path generation. **Imports at top of file:**

```python
# At top of file
from paper2slides.core.paths import (
    get_base_dir,           # outputs/{project}/{content_type}
    get_mode_dir,           # .../fast or .../normal
    get_config_dir,         # .../slides_doraemon_medium
    get_rag_checkpoint,
    get_summary_checkpoint,
    get_plan_checkpoint,
    get_latest_output_dir,  # Find latest timestamp directory
    get_video_dir,          # .../video/
    get_video_state_path,   # .../video/video_state.json
)
```

### JSON Utilities

Use the provided helpers. **Imports at top of file:**

```python
# At top of file
from paper2slides.utils import save_json, load_json, save_text

# Usage - save_json auto-creates parent dirs, handles unicode
save_json(path, data)
data = load_json(path)  # Returns None if file doesn't exist
```

## Common Tasks

### Adding a New RAG Query

Edit `paper2slides/rag/query.py`. Add new entries to the existing dictionaries:

```python
# In paper2slides/rag/query.py (existing file)

RAG_PAPER_QUERIES = {
    "paper_info": [...],
    "your_new_category": [
        "Your query text here",
        "Another related query",
    ],
}

RAG_QUERY_MODES = {
    "your_new_category": "mix",  # or "hybrid"
}
```

### Modifying Content Planning

Edit `paper2slides/prompts/content_planning.py`:
- `PAPER_SLIDES_PLANNING_PROMPT` - Academic paper → slides
- `PAPER_POSTER_PLANNING_PROMPT` - Academic paper → poster
- `GENERAL_SLIDES_PLANNING_PROMPT` - General document → slides
- `GENERAL_POSTER_PLANNING_PROMPT` - General document → poster

### Adding a New Style

1. Edit `paper2slides/prompts/image_generation.py`. Add new layout dict and update the function:

```python
# In paper2slides/prompts/image_generation.py

SLIDE_LAYOUTS_NEWSTYLE = {...}  # Layout rules per section type

def get_slide_style_hint(style: str, language: str) -> str:
    if style == "newstyle":
        return "Your style description..."
    # ... existing styles
```

2. Update style selection in `image_generator.py`

### Modifying Image Generation

Edit `paper2slides/generator/image_generator.py`:
- `_build_slide_prompt()` - Prompt construction
- `_generate_slides()` - Generation flow (sequential + parallel)
- `_call_model_openrouter()` / `_call_model_google()` - API calls

## API Design: Local Directory as Database

**IMPORTANT: The API uses the local filesystem as the database.** All state is persisted to JSON files in the `outputs/` directory. The API returns immediately and runs processing in background tasks that update local state files.

### Design Principles

1. **Immediate Response**: API endpoints return immediately with a session ID
2. **Background Processing**: Long-running tasks run via `BackgroundTasks`
3. **Local State Files**: All status updates are written to `state.json` in the config directory
4. **Polling for Status**: Frontend polls `/api/status/{session_id}` which reads from local files
5. **No In-Memory State for Status**: Status is always read from disk, not memory

### State Flow

```
POST /api/chat
    ↓ Returns immediately with session_id
    ↓ Starts background task

Background Task:
    ↓ Updates state.json: stages.rag = "running"
    ↓ ... processing ...
    ↓ Updates state.json: stages.rag = "completed"
    ↓ Updates state.json: stages.summary = "running"
    ↓ ... continues for each stage ...

GET /api/status/{session_id}
    ↓ Reads state.json from outputs/{project}/{content_type}/{mode}/{config}/
    ↓ Returns current stages status
```

### Local Directory Structure

```
outputs/{project}/{content_type}/{mode}/{config}/
├── state.json                    # Current pipeline status (THE DATABASE)
│   {
│     "session_id": "uuid",
│     "config": {...},
│     "stages": {
│       "rag": "completed",
│       "summary": "completed",
│       "plan": "completed",
│       "generate": "running"     # or "pending", "completed", "failed", "awaiting_confirmation"
│     },
│     "error": null,
│     "created_at": "...",
│     "updated_at": "..."
│   }
├── checkpoint_plan.json          # Plan data
└── {timestamp}/
    ├── slide_01.png
    ├── slides.pdf
    └── video/                    # Video generation state
        ├── video_state.json      # Video pipeline status
        ├── narration/
        └── transitions/
```

### Background Task Pattern

All API endpoints that start long-running processes must:

1. Validate request and create session directory
2. Return immediately with `session_id`
3. Add background task that updates local state files

```python
@app.post("/api/chat")
async def chat(background_tasks: BackgroundTasks, ...):
    session_id = str(uuid.uuid4())

    # Return immediately
    response = {"session_id": session_id, "status": "started"}

    # Add background task that will update local state files
    background_tasks.add_task(
        run_pipeline_background,
        session_id,
        session_manager,
        # ... other params
    )

    return JSONResponse(content=response)

async def run_pipeline_background(session_id: str, session_manager: SessionManager, ...):
    try:
        # Update state.json at each step
        state = load_state(config_dir)
        state["stages"]["rag"] = "running"
        save_state(config_dir, state)

        # ... do work ...

        state["stages"]["rag"] = "completed"
        save_state(config_dir, state)
    except Exception as e:
        state["stages"]["current_stage"] = "failed"
        state["error"] = str(e)
        save_state(config_dir, state)
    finally:
        await session_manager.end_session(session_id)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Upload files, returns immediately, runs pipeline in background |
| `/api/status/{session_id}` | GET | Reads `state.json` from local directory |
| `/api/result/{session_id}` | GET | Returns output files after completion |
| `/api/plan/{session_id}` | GET | Get plan from `checkpoint_plan.json` |
| `/api/plan/{session_id}` | POST | Update plan in `checkpoint_plan.json` |
| `/api/plan/{session_id}/confirm` | POST | Resume pipeline, runs generate in background |
| `/api/slides/{session_id}/content` | GET | Get structured slide content |
| `/api/slides/{session_id}/regenerate` | POST | Regenerate single slide |
| `/api/cancel/{session_id}` | POST | Mark session for cancellation |
| `/api/video/{session_id}/generate` | POST | Start video generation in background |
| `/api/video/{session_id}/status` | GET | Reads `video_state.json` from local directory |
| `/outputs/{path}` | GET | Serve generated files |

## Testing

Currently no automated test suite. Manual testing:

```bash
# Test CLI
uv run python -m paper2slides --input test.pdf --output slides --fast --debug

# Test API
uv run python scripts/api/test_api.py
```

## Debugging Tips

1. **Enable debug logging:**
   ```bash
   uv run python -m paper2slides --input file.pdf --debug
   ```

2. **Check checkpoints:**
   - Examine `checkpoint_*.json` files for intermediate results
   - Read `summary.md` for human-readable extracted content

3. **Force restart from stage:**
   ```bash
   uv run python -m paper2slides --input file.pdf --from-stage plan
   ```

4. **List existing outputs:**
   ```bash
   uv run python -m paper2slides --list
   ```

5. **Check state file:**
   ```bash
   cat outputs/{project}/paper/fast/slides_doraemon_medium/state.json
   ```

## Important Gotchas

1. **Fast mode vs Normal mode:**
   - Fast mode (`--fast`) embeds images as base64 and queries GPT-4o vision directly
   - Normal mode builds a LightRAG knowledge graph (slower but better for long docs)

2. **Slide generation order:**
   - Slides 1-2 are always generated sequentially to establish visual style
   - Slide 2 becomes the reference image for style consistency
   - Slides 3+ can run in parallel (`--parallel N`)

3. **Checkpoint reuse:**
   - RAG and summary checkpoints are shared across style/length variations
   - Plan checkpoints are style/length-specific
   - Same input file reuses existing checkpoints automatically

4. **Image generation providers:**
   - OpenRouter: Uses `image_url` attachment format
   - Google: Uses `inlineData` format for images
   - Different models have different image generation capabilities

5. **Filename sanitization:**
   - API server sanitizes uploaded filenames (Vietnamese chars, URL encoding)
   - Uses `sanitize_filename()` to prevent "File name too long" errors

6. **Language configuration:**
   - Default language is Vietnamese
   - Set via `--language` or `language` form field in API
   - Affects all generated content (titles, descriptions, slide text)

## Key Files to Know

| File | Purpose |
|------|---------|
| `paper2slides/main.py` | CLI entry point, argument parsing |
| `paper2slides/core/pipeline.py` | Pipeline orchestration |
| `paper2slides/core/state.py` | State management (load_state, save_state) |
| `paper2slides/core/paths.py` | Path generation helpers |
| `paper2slides/core/stages/rag_stage.py` | Document parsing and RAG |
| `paper2slides/core/stages/generate_stage.py` | Image generation |
| `paper2slides/generator/image_generator.py` | Vision model integration |
| `paper2slides/prompts/content_planning.py` | LLM prompts for layout |
| `paper2slides/prompts/image_generation.py` | Image gen prompts + styles |
| `paper2slides/video/__init__.py` | Video generation exports |
| `paper2slides/video/state.py` | Video state management (video_state.json) |
| `api/server.py` | FastAPI backend with background tasks |

## External Dependencies

- **LightRAG** - Graph-based RAG from HKU (knowledge graph + vector retrieval)
- **MineU** - Document parser (PDF → Markdown + images)
- **OpenRouter** - LLM API gateway (GPT-4o, Gemini)
- **Langfuse** - LLM observability/tracing
- **Google Gemini** - Image generation (via OpenRouter or direct)

## Performance Considerations

- **Parallel workers:** Use `--parallel 4` for faster slide generation
- **Fast mode:** ~5x faster than normal mode (skips RAG indexing)
- **Checkpoint reuse:** Re-running same input skips completed stages
- **Image generation:** Rate limits may apply; exponential backoff handles retries

## Contributing

1. **All imports at top of file** - Standard library, third-party, then local imports
2. Follow existing code patterns (async, dataclasses, type hints)
3. Use `save_json`/`load_json` for file I/O
4. **Update local state files** in background tasks (never rely on in-memory state for status)
5. Add checkpoints for any new long-running operations
6. Update prompts in `paper2slides/prompts/` for behavior changes
7. Test with both fast mode and normal mode
8. API endpoints should return immediately and use `BackgroundTasks` for long operations
