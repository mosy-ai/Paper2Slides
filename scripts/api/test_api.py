#!/usr/bin/env python3
"""
Test script for Paper2Slides API

This script tests the complete workflow:
1. Upload PDF to generate slides
2. Poll for status until completion
3. Retrieve generated results
4. Get structured slide content for video generation

Usage:
    python test_api.py
"""

import json
import time
from pathlib import Path

import requests

# Configuration
API_BASE = "http://localhost:8152"
PDF_PATH = "/home/aiden/folder-em-linh-xin-dung-xoa/Paper2Slides/data/Present-Simple-YEnglishtube.pdf"

# Generation settings
CONFIG = {
    "content": "general",  # 'paper' or 'general'
    "output_type": "slides",  # 'slides' or 'poster'
    "style": "academic",  # 'academic', 'doraemon', or custom description
    "length": "medium",  # 'short', 'medium', 'long' (for slides)
    "language": "vietnamese",  # 'vietnamese' or 'english'
    "fast_mode": "false",  # 'true' or 'false'
}


# ANSI color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(text):
    """Print a header with formatting."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_info(text):
    """Print info message."""
    print(f"{Colors.OKBLUE}ℹ {text}{Colors.ENDC}")


def print_success(text):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_stage(stage_name, status):
    """Print stage status with color coding."""
    status_icons = {
        "pending": f"{Colors.WARNING}⏸{Colors.ENDC}",
        "running": f"{Colors.OKCYAN}▶{Colors.ENDC}",
        "completed": f"{Colors.OKGREEN}✓{Colors.ENDC}",
        "failed": f"{Colors.FAIL}✗{Colors.ENDC}",
    }
    icon = status_icons.get(status, "?")
    print(f"  {icon} {stage_name.upper()}: {status}")


def upload_pdf(pdf_path):
    """Upload PDF and start generation."""
    print_header("STEP 1: Upload PDF and Start Generation")

    if not Path(pdf_path).exists():
        print_error(f"PDF file not found: {pdf_path}")
        return None

    print_info(f"Uploading: {Path(pdf_path).name}")
    print_info(f"Configuration:")
    for key, value in CONFIG.items():
        print(f"  - {key}: {value}")

    try:
        with open(pdf_path, "rb") as f:
            response = requests.post(
                f"{API_BASE}/api/chat",
                data=CONFIG,
                files={"files": f},
                timeout=600,
            )

        response.raise_for_status()
        result = response.json()

        session_id = result.get("session_id")
        if not session_id:
            print_error("No session_id in response")
            return None

        print_success(f"Upload successful! Session ID: {session_id[:8]}...")
        print_info(f"Message: {result.get('message')}")

        return session_id

    except requests.exceptions.RequestException as e:
        print_error(f"Upload failed: {e}")
        return None


def poll_status(session_id, poll_interval=5, max_wait=1800):
    """Poll for generation status until completion."""
    print_header("STEP 2: Monitor Generation Progress")

    start_time = time.time()
    last_stages = {}

    while True:
        try:
            response = requests.get(f"{API_BASE}/api/status/{session_id}", timeout=10)
            response.raise_for_status()
            status_data = response.json()

            overall_status = status_data.get("status")
            stages = status_data.get("stages", {})

            # Print stages only if they changed
            if stages != last_stages:
                print(f"\n{Colors.BOLD}Status: {overall_status.upper()}{Colors.ENDC}")
                for stage_name in ["rag", "summary", "plan", "generate"]:
                    stage_status = stages.get(stage_name, "pending")
                    print_stage(stage_name, stage_status)
                last_stages = stages.copy()

            # Check if completed or failed
            if overall_status == "completed":
                elapsed = time.time() - start_time
                print_success(f"\nGeneration completed in {elapsed:.1f} seconds!")
                return True

            elif overall_status == "failed":
                error = status_data.get("error", "Unknown error")
                print_error(f"\nGeneration failed: {error}")
                return False

            # Check timeout
            if time.time() - start_time > max_wait:
                print_error(f"\nTimeout after {max_wait} seconds")
                return False

            # Wait before next poll
            time.sleep(poll_interval)

        except requests.exceptions.RequestException as e:
            print_error(f"Status check failed: {e}")
            time.sleep(poll_interval)


def get_results(session_id):
    """Get generated results."""
    print_header("STEP 3: Retrieve Generated Results")

    try:
        response = requests.get(f"{API_BASE}/api/result/{session_id}", timeout=30)
        response.raise_for_status()
        result = response.json()

        slides = result.get("slides", [])
        ppt_url = result.get("ppt_url")

        print_success(f"Found {len(slides)} generated slides")

        if ppt_url:
            print_info(f"PDF available at: {API_BASE}{ppt_url}")

        # Show slide previews
        print(f"\n{Colors.BOLD}Slide Previews:{Colors.ENDC}")
        for i, slide in enumerate(slides[:3], 1):  # Show first 3
            print(f"  {i}. {slide.get('title', 'Untitled')}")
            print(f"     Image: {slide.get('image_url', 'N/A')}")

        if len(slides) > 3:
            print(f"  ... and {len(slides) - 3} more slides")

        return result

    except requests.exceptions.RequestException as e:
        print_error(f"Failed to get results: {e}")
        return None


def get_slide_content(session_id, save_to_file=True):
    """Get structured slide content (for video generation)."""
    print_header("STEP 4: Get Structured Slide Content")

    try:
        response = requests.get(
            f"{API_BASE}/api/slides/{session_id}/content", timeout=30
        )
        response.raise_for_status()
        content = response.json()

        total_slides = content.get("total_slides", 0)
        output_type = content.get("output_type", "unknown")
        slides = content.get("slides", [])

        print_success(f"Retrieved content for {total_slides} {output_type}")

        # Display detailed slide information
        print(f"\n{Colors.BOLD}Detailed Slide Content:{Colors.ENDC}\n")

        for slide in slides:
            slide_num = slide.get("slide_number")
            title = slide.get("title", "Untitled")
            section_type = slide.get("section_type", "")
            content_text = slide.get("content", "")
            image_url = slide.get("image_url", "")
            tables = slide.get("tables", [])
            figures = slide.get("figures", [])

            # Print slide header
            print(
                f"{Colors.OKCYAN}{Colors.BOLD}Slide {slide_num}: {title}{Colors.ENDC}"
            )
            print(f"  Type: {section_type}")
            print(f"  Image: {API_BASE}{image_url}" if image_url else "  Image: N/A")

            # Print content (truncated)
            if content_text:
                preview = (
                    content_text[:200] + "..."
                    if len(content_text) > 200
                    else content_text
                )
                print(f"  Content: {preview}")

            # Print tables
            if tables:
                print(f"  Tables: {len(tables)} table(s)")
                for table in tables:
                    print(
                        f"    - {table.get('id')}: {table.get('caption', 'No caption')}"
                    )

            # Print figures
            if figures:
                print(f"  Figures: {len(figures)} figure(s)")
                for figure in figures:
                    print(
                        f"    - {figure.get('id')}: {figure.get('caption', 'No caption')}"
                    )

            print()  # Blank line between slides

        # Save to file
        if save_to_file:
            output_file = f"slide_content_{session_id[:8]}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            print_success(f"Saved full content to: {output_file}")

        return content

    except requests.exceptions.RequestException as e:
        print_error(f"Failed to get slide content: {e}")
        if hasattr(e, "response") and e.response is not None:
            print_error(f"Response: {e.response.text}")
        return None


def main():
    """Main test workflow."""
    print_header("Paper2Slides API Test")
    print_info(f"API Base URL: {API_BASE}")
    print_info(f"PDF File: {PDF_PATH}")

    # Step 1: Upload PDF
    session_id = upload_pdf(PDF_PATH)
    if not session_id:
        print_error("Test failed at upload stage")
        return

    # Step 2: Poll for completion
    success = poll_status(session_id)
    if not success:
        print_error("Test failed at generation stage")
        return

    # Step 3: Get results
    results = get_results(session_id)
    if not results:
        print_error("Test failed at results retrieval stage")
        return

    # Step 4: Get slide content
    content = get_slide_content(session_id)
    if not content:
        print_error("Test failed at content extraction stage")
        return

    # Success!
    print_header("TEST COMPLETED SUCCESSFULLY")
    print_success("All API endpoints working correctly!")
    print_info(f"Session ID: {session_id}")
    print_info(f"Total slides generated: {content.get('total_slides', 0)}")
    print_info("You can now use the slide content for video generation")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nTest interrupted by user")
    except Exception as e:
        print_error(f"\n\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
