# Paper2Slides - Architecture & Flow Documentation

This document provides comprehensive low-level details of the Paper2Slides processing pipeline.

## Table of Contents

1. [System Overview](#system-overview)
2. [Entry Points](#entry-points)
3. [4-Stage Processing Pipeline](#4-stage-processing-pipeline)
4. [Module Architecture](#module-architecture)
5. [Data Flow](#data-flow)
6. [Configuration](#configuration)
7. [External Services](#external-services)
8. [Checkpoint System](#checkpoint-system)
9. [Error Handling](#error-handling)

---

## System Overview

Paper2Slides converts academic papers and general documents into presentation slides or posters using a 4-stage pipeline:

```
PDF/Document → RAG Indexing → Content Extraction → Layout Planning → Image Generation → Slides/Poster
```

**Key Features:**
- Two processing modes: Fast (vision-based) and Normal (RAG-based)
- Parallel slide generation with style consistency
- Checkpoint-based resumption
- Multi-document support
- Customizable styles (academic, doraemon, custom)

---

## Entry Points

### CLI Entry Point

**File:** `paper2slides/__main__.py` → `paper2slides/main.py`

```python
# Command Line Arguments
--input, -i     # Input file or directory (required)
--content       # "paper" or "general" (default: paper)
--output        # "slides" or "poster" (default: poster)
--style         # "academic", "doraemon", or custom description
--length        # "short", "medium", "long" for slides
--density       # "sparse", "medium", "dense" for posters
--fast          # Fast mode (parse only, no RAG indexing)
--parallel N    # Parallel generation with N workers
--from-stage    # Force restart from stage (rag/summary/plan/generate)
--debug         # Enable debug logging
--list          # List all outputs
```

**Execution Flow in `main()`:**

```
1. Parse CLI arguments
2. Setup logging (debug level if --debug)
3. Normalize input path to absolute
4. Parse style → (style_type, custom_description)
5. Build configuration dictionary:
   {
     input_path, output_type, style, length/density,
     fast_mode, parallel_workers, debug
   }
6. Determine project name from input filename
7. Build directory structure paths
8. Detect start stage (checkpoint detection)
9. Execute: asyncio.run(run_pipeline(config))
```

### API Entry Point

**File:** `api/server.py`

FastAPI application providing:
- Document upload endpoints
- Job tracking via SessionManager
- Output serving
- Progress monitoring

---

## 4-Stage Processing Pipeline

**Orchestrator:** `paper2slides/core/pipeline.py`

### Stage 1: RAG (Document Indexing & Querying)

**File:** `paper2slides/core/stages/rag_stage.py`

#### Fast Mode (`--fast` flag)

Uses direct vision model querying without RAG indexing.

```
1. BatchParser (MineU) converts PDF → Markdown + Images
2. _replace_images_with_base64() embeds images in markdown
3. For each query category:
   a. Build content: [markdown_text, embedded_images, query]
   b. Call GPT-4o vision model with images
   c. Store response in results dictionary
4. Save checkpoint_rag.json
```

#### Normal Mode (default)

Uses LightRAG for knowledge graph-based retrieval.

```
1. Initialize RAGClient with LightRAG backend
2. Index files recursively:
   a. Parse documents to markdown (MineU/Docling)
   b. Build knowledge graph
   c. Create vector embeddings
3. Execute category-organized queries:
   - paper_info: "hybrid" mode
   - figures, tables, equations: "mix" mode (local + global)
   - motivation, solution, results, contributions: "mix" mode
4. Save checkpoint_rag.json
```

**Predefined RAG Queries** (from `paper2slides/rag/query.py`):

| Category | Query Purpose |
|----------|---------------|
| `paper_info` | Title, authors, affiliations |
| `figures` | Architecture/framework diagrams |
| `tables` | Performance, ablation studies, datasets |
| `equations` | Core formulations |
| `motivation` | Problem statement, research gap |
| `solution` | Method overview, components, algorithm |
| `results` | Datasets, metrics, comparisons |
| `contributions` | Novelty, limitations, future work |

**Output:** `checkpoint_rag.json`
```json
{
  "rag_results": {
    "paper_info": "...",
    "figures": "...",
    "tables": "...",
    ...
  },
  "markdown_paths": ["doc1.md", "doc2.md"],
  "mode": "fast" | "normal"
}
```

---

### Stage 2: Summary (Content Extraction)

**File:** `paper2slides/core/stages/summary_stage.py`

```
1. Load checkpoint_rag.json
2. Extract paper metadata directly from markdown
3. For Papers - extract_paper():
   a. merge_answers() combines RAG results per section
   b. Parallel LLM processing (5 concurrent) for section extraction
   c. Sections: paper_info, motivation, solution, results, contributions
   d. Supplement solution with figures/equations
   e. Supplement results with tables
   Output: PaperContent dataclass

4. For General - extract_general():
   a. Merge all RAG results
   Output: GeneralContent dataclass

5. Figure & Table Extraction - extract_tables_and_figures():
   a. Parse HTML tables from markdown
   b. Extract image paths from markdown
   c. Handle multi-doc prefixing (Doc1_, Doc2_)
   Output: OriginalElements (tables + figures)

6. Save human-readable summary.md
7. Save checkpoint_summary.json
```

**Output:** `checkpoint_summary.json`
```json
{
  "content": {
    "title": "...",
    "authors": "...",
    "abstract": "...",
    "motivation": "...",
    "solution": "...",
    "results": "...",
    "contributions": "..."
  },
  "origin": {
    "tables": [...],
    "figures": [...]
  },
  "content_type": "paper" | "general"
}
```

---

### Stage 3: Planning (Content Layout Generation)

**File:** `paper2slides/core/stages/plan_stage.py`

```
1. Load checkpoint_summary.json
2. Reconstruct PaperContent/GeneralContent objects
3. Reconstruct OriginalElements with table/figure references
4. Build GenerationConfig:
   - output_type: POSTER | SLIDES
   - style: ACADEMIC | DORAEMON | CUSTOM
   - length: SHORT (5-8) | MEDIUM (8-12) | LONG (12-15)
   - density: SPARSE | MEDIUM | DENSE
   - language: vietnamese (default)

5. Initialize ContentPlanner:
   - OpenAI client with LLM API credentials
   - Model: from environment (default: gpt-4o)
   - Max tokens: RAG_LLM_MAX_TOKENS (default: 16000)

6. Call planner.plan(gen_input):
   - Uses prompts from paper2slides/prompts/content_planning.py
   - For Slides: PAPER_SLIDES_PLANNING_PROMPT
     * Distributes content across N slides
     * Generates titles, detailed content per slide
     * Maps tables/figures to slides
     * Preserves formulas in LaTeX
     * Minimum 150-200 words per slide
   - For Posters: PAPER_POSTER_PLANNING_PROMPT
     * Single poster with optimized density
     * Strategic figure/table placement

7. Save checkpoint_plan.json
```

**Output:** `checkpoint_plan.json`
```json
{
  "plan": {
    "sections": [
      {
        "id": "slide_01",
        "title": "...",
        "content": "...",
        "tables": [{"id": "table_1", "extract": "...", "focus": "..."}],
        "figures": [{"id": "figure_1", "focus": "..."}],
        "section_type": "title" | "content" | "conclusion"
      },
      ...
    ]
  },
  "origin": {...},
  "content_type": "paper" | "general"
}
```

---

### Stage 4: Generation (Image Creation)

**File:** `paper2slides/core/stages/generate_stage.py`

```
1. Load checkpoint_plan.json and checkpoint_summary.json
2. Reconstruct ContentPlan and content objects

3. Initialize ImageGenerator:
   Providers:
   - OpenRouter (default):
     * API: IMAGE_GEN_API_KEY
     * Base URL: https://openrouter.ai/api/v1
     * Model: google/gemini-3-pro-image-preview
   - Google:
     * Official Gemini API
     * Base URL: https://generativelanguage.googleapis.com/v1beta
     * Model: models/gemini-1.5-flash

4. For Posters:
   a. Generate single poster image
   b. Use FORMAT_POSTER template
   c. Apply style hints
   d. Save poster image

5. For Slides:
   a. Sequential Generation (Slides 1-2):
      * Slide 1: Generate without reference
      * Slide 2: Generate + save as visual style reference

   b. Parallel Generation (Slides 3+):
      * ThreadPoolExecutor with --parallel N workers
      * Each slide generated with reference image
      * Reference ensures style consistency

6. Prompt Construction:
   - Section content
   - Layout rules (SLIDE_LAYOUTS_ACADEMIC/DORAEMON/DEFAULT)
   - Style hints
   - Reference images (base64 encoded)
   - Consistency hints
   - Language specification

7. Custom Style Processing (if style="custom"):
   - LLM extracts: style_name, color_tone, special_elements, decorations
   - Validates and applies custom style hints

8. Image Saving:
   - Callback saves each image immediately
   - Formats: PNG, JPG, WebP (based on mime_type)
   - Final PDF generation (concatenates all slides)
```

**Output:**
```
{output_dir}/{timestamp}/
├── slide_01.png
├── slide_02.png
├── slide_03.png
├── ...
└── slides.pdf
```

---

## Module Architecture

### Core Module (`paper2slides/core/`)

| File | Responsibility |
|------|----------------|
| `pipeline.py` | Async orchestrator, runs 4-stage pipeline |
| `state.py` | Checkpoint state management |
| `paths.py` | Path generation for checkpoints/outputs |
| `stages/rag_stage.py` | Document parsing and RAG querying |
| `stages/summary_stage.py` | Content extraction from RAG |
| `stages/plan_stage.py` | Content layout planning |
| `stages/generate_stage.py` | Image generation and PDF |

### RAG Module (`paper2slides/rag/`)

| File | Responsibility |
|------|----------------|
| `client.py` | RAGClient wrapper around LightRAG |
| `config.py` | RAG configuration (API, storage, parser) |
| `query.py` | Predefined queries, result types |

### RAG-Anything Module (`paper2slides/raganything/`)

| File | Responsibility |
|------|----------------|
| `raganything.py` | Multimodal document processing |
| `batch_parser.py` | Batch processing with parallel parsing |
| `batch.py` | Batch mixing utilities |
| `parser.py` | MineU and Docling wrappers |
| `processor.py` | Processor mixing for content types |
| `modalprocessors.py` | Image, table, equation processors |
| `query.py` | Query execution and retrieval |

### Summary Module (`paper2slides/summary/`)

| File | Responsibility |
|------|----------------|
| `paper.py` | Paper content extraction |
| `general.py` | General document extraction |
| `models.py` | Data models (PaperContent, etc.) |
| `extractors/figure_extractor.py` | Figure extraction |
| `extractors/table_extractor.py` | Table extraction |
| `extractors/table_cleaner.py` | Table content cleaning |

### Generator Module (`paper2slides/generator/`)

| File | Responsibility |
|------|----------------|
| `content_planner.py` | ContentPlanner LLM interface |
| `image_generator.py` | ImageGenerator for vision calls |
| `config.py` | Configuration enums and types |

### Prompts Module (`paper2slides/prompts/`)

| File | Responsibility |
|------|----------------|
| `content_planning.py` | Slide/poster planning prompts |
| `image_generation.py` | Image generation prompts |
| `paper_extraction.py` | Paper section extraction prompts |

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           INPUT (PDF/Document)                           │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STAGE 1: RAG                                     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ Parser          │ → │ RAGClient/       │ → │ checkpoint_rag.json │  │
│  │ (MineU/Docling) │    │ Vision Query    │    │ - rag_results       │  │
│  │ PDF → Markdown  │    │ Index + Query   │    │ - markdown_paths    │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STAGE 2: SUMMARY                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ Load RAG        │ → │ Extract Content │ → │ checkpoint_summary   │  │
│  │ Checkpoint      │    │ + Tables/Figs   │    │ .json               │  │
│  │                 │    │ Parallel LLM    │    │ - content           │  │
│  └─────────────────┘    └─────────────────┘    │ - origin            │  │
│                                                 └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STAGE 3: PLANNING                                │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ Load Summary    │ → │ ContentPlanner  │ → │ checkpoint_plan.json│  │
│  │ Checkpoint      │    │ LLM Planning    │    │ - plan (sections)   │  │
│  │                 │    │ Layout JSON     │    │ - origin            │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STAGE 4: GENERATION                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ Load Plan       │ → │ ImageGenerator  │ → │ Output Images       │  │
│  │ Checkpoint      │    │ - Seq (1-2)     │    │ - slide_XX.png      │  │
│  │                 │    │ - Parallel (3+) │    │ - slides.pdf        │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         OUTPUT (Slides/Poster)                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### Environment Variables

#### LLM & RAG API
```bash
RAG_LLM_API_KEY=...          # OpenAI/OpenRouter API key (required)
RAG_LLM_BASE_URL=...         # Custom LLM endpoint (optional)
LLM_MODEL=openai/gpt-4o      # Model identifier (default)
RAG_LLM_MAX_TOKENS=16000     # Max tokens for LLM calls
```

#### Embedding
```bash
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIM=3072
```

#### Image Generation
```bash
IMAGE_GEN_PROVIDER=openrouter        # or "google"
IMAGE_GEN_API_KEY=...
IMAGE_GEN_BASE_URL=https://openrouter.ai/api/v1
IMAGE_GEN_MODEL=google/gemini-3-pro-image-preview
GOOGLE_GENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
IMAGE_GEN_RESPONSE_MIME_TYPE=text/plain
```

#### RAG Storage
```bash
RAG_STORAGE_DIR=...          # Graph and vector index storage
RAG_OUTPUT_DIR=...           # Parsed markdown output
```

#### Parser
```bash
PARSER=mineru                # or "docling"
PARSE_METHOD=auto            # or "ocr", "txt"
```

#### Observability (Optional)
```bash
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=...
```

### Directory Structure

```
outputs/
└── {project_name}/
    └── {content_type}/          # paper/ or general/
        ├── fast/                # Fast mode checkpoints
        │   ├── checkpoint_rag.json
        │   ├── checkpoint_summary.json
        │   ├── summary.md
        │   └── {output}_{style}_{param}/
        │       ├── state.json
        │       ├── checkpoint_plan.json
        │       └── {timestamp}/
        │           ├── slide_01.png
        │           ├── slide_02.png
        │           └── slides.pdf
        │
        └── normal/              # Normal mode checkpoints
            ├── checkpoint_rag.json
            ├── checkpoint_summary.json
            ├── summary.md
            ├── rag_output/      # Parsed markdown + images
            ├── rag_storage/     # LightRAG indices
            └── {output}_{style}_{param}/
                └── {timestamp}/
```

### Configuration Objects

#### GenerationConfig
```python
class GenerationConfig:
    output_type: OutputType    # POSTER | SLIDES
    poster_density: PosterDensity  # SPARSE | MEDIUM | DENSE
    slides_length: SlidesLength    # SHORT (5-8) | MEDIUM (8-12) | LONG (12-15)
    style: StyleType           # ACADEMIC | DORAEMON | CUSTOM
    custom_style: Optional[str]
    language: str = "vietnamese"
```

#### RAGConfig
```python
class RAGConfig:
    api: APIConfig             # Keys, models, base URLs
    storage: StorageConfig     # Storage paths
    parser: ParserConfig       # Parser type, method
```

---

## External Services

### LLM Services

**OpenAI (via OpenRouter or direct):**
- Model: GPT-4o (default)
- Used for:
  - RAG querying (fast mode with vision)
  - Section content extraction
  - Content planning
  - Custom style processing
- Wrapped via `langfuse.openai.OpenAI` for tracing

### Vision/Image Generation

**Google Gemini (via OpenRouter or Google API):**
- Model: `google/gemini-3-pro-image-preview` or `models/gemini-1.5-flash`
- Purpose: Generate slide/poster images from text prompts
- Supports inline images (Google) or image_url attachments (OpenRouter)

### Embedding & RAG

**OpenAI Embeddings:**
- Model: `text-embedding-3-large`
- Dimension: 3072
- Used by LightRAG for vector storage

**LightRAG:**
- Knowledge graph construction
- Hybrid querying (local, global, mix modes)
- Vector database + graph retrieval

### Document Parsing

**MineU Parser (default):**
- PDF/Office → Markdown + Images
- OCR for scanned documents
- Spatial relationship preservation

**Docling (alternative):**
- Alternative parser
- Similar markdown output

---

## Checkpoint System

### How Checkpoints Work

Each stage saves its output to a checkpoint file:

```
Stage 1 (RAG)     → checkpoint_rag.json
Stage 2 (Summary) → checkpoint_summary.json
Stage 3 (Plan)    → checkpoint_plan.json
Stage 4 (Generate)→ Images + PDF (no checkpoint)
```

### Automatic Resume

`detect_start_stage()` determines where to resume:

```python
def detect_start_stage(paths):
    if not exists(checkpoint_rag.json):
        return "rag"
    if not exists(checkpoint_summary.json):
        return "summary"
    if not exists(checkpoint_plan.json):
        return "plan"
    return "generate"
```

### Force Restart

Override with `--from-stage`:
```bash
python -m paper2slides --input paper.pdf --from-stage rag
```

### State Tracking

`state.json` tracks stage status:
```json
{
  "stages": {
    "rag": "completed",
    "summary": "completed",
    "plan": "running",
    "generate": "pending"
  },
  "current_stage": "plan",
  "error": null
}
```

---

## Error Handling

### Retry Mechanism

Image generation uses exponential backoff:

```python
@retry_with_exponential_backoff(max_retries=10)
async def generate_image(prompt, ...):
    ...
```

### Filename Sanitization

Handles problematic filenames:
- URL decoding
- Unicode normalization (NFC)
- Dangerous character removal
- Safe truncation
- UUID fallback

### Batch Processing Results

```python
class BatchResult:
    successful: List[str]
    failed: List[Tuple[str, str]]  # (filename, error)
    success_rate: float
    processing_time: float
```

### State Recovery

On failure:
1. Stage marked as "failed" in state.json
2. Error message stored
3. Pipeline halts
4. User can retry or restart from specific stage

---

## Example Processing Flows

### Fast Mode: PDF → Slides

```bash
python -m paper2slides --input paper.pdf --output slides --fast
```

```
1. main.py: Parse args, build config
   config = {input_path, output_type="slides", fast_mode=True, style="doraemon"}

2. rag_stage.py (FAST):
   - BatchParser: paper.pdf → markdown + images
   - Embed images as base64
   - GPT-4o vision: query each category
   - Save checkpoint_rag.json

3. summary_stage.py:
   - Load checkpoint
   - Parallel LLM extraction
   - Extract tables/figures
   - Save checkpoint_summary.json

4. plan_stage.py:
   - ContentPlanner generates 5-8 slides
   - Save checkpoint_plan.json

5. generate_stage.py:
   - Slide 1: generate (no reference)
   - Slide 2: generate + save reference
   - Slides 3-8: parallel generation
   - Create slides.pdf
```

### Normal Mode with Parallel Generation

```bash
python -m paper2slides --input paper.pdf --length medium --parallel 4
```

```
1. rag_stage.py (NORMAL):
   - RAGClient initialization
   - Index documents to knowledge graph
   - Batch query by category
   - Save checkpoint

2. [Same summary and plan stages]

3. generate_stage.py (PARALLEL):
   - Slide 1-2: Sequential
   - Slides 3-12: ThreadPoolExecutor(max_workers=4)
   - Each worker: prompt → vision model → image
   - Immediate save via callback
   - Final PDF creation
```

### Resuming from Checkpoint

```bash
# First run (fails at stage 2)
python -m paper2slides --input paper.pdf

# Re-run (auto-resumes from summary)
python -m paper2slides --input paper.pdf
# Detects checkpoint_rag.json exists, starts from "summary"
```

---

## Advanced Features

### Parallel Processing

- **Document Parsing:** BatchParser with configurable workers
- **Slide Generation:**
  - First 2 slides: Sequential (style establishment)
  - Remaining slides: Parallel with reference image
  - Configurable via `--parallel N`

### Multi-Document Support

- Process multiple files/directories
- Shared RAG index
- Tables/figures prefixed: Doc1_, Doc2_

### Multi-Modal Content

- RAG-Anything: Image, table, equation processing
- Vision model integration
- Reference image system for consistency
- LLM-driven custom style application

### Style Consistency

Two-phase approach:
1. Generate slides 1-2 sequentially
2. Slide 2 becomes reference for remaining slides
3. Reference ensures: color palette, fonts, chart styles
