"""
Script generator for creating narration scripts from slide content.

Uses LLM to generate natural-sounding narration text for each slide
based on the slide plan and content.
"""

import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path

from langfuse.openai import OpenAI

from paper2slides.rag.config import APIConfig


# Prompt template for generating narration scripts
NARRATION_SCRIPT_PROMPT = """You are a professional presentation narrator. Your task is to create a natural, engaging narration script for a presentation slide.

## Slide Information

Slide Number: {slide_number} of {total_slides}
Section Type: {section_type}
Title: {title}

Content:
{content}

{speaker_notes}

## Instructions

Generate a narration script that:
1. Sounds natural when spoken aloud (avoid written-only phrases like "as shown below")
2. Explains the key points clearly and concisely
3. Maintains a professional but engaging tone
4. Is appropriate for the section type:
   - For "title" slides: Brief introduction, welcome the audience
   - For "intro/overview" slides: Set context, preview main points
   - For "content" slides: Explain key concepts, provide insights
   - For "conclusion" slides: Summarize, provide takeaways
5. Takes approximately {target_duration} seconds to read at a natural pace (about 150 words per minute)

## Language

Generate the narration in {language}.

## Output Format

Return ONLY the narration script text, without any formatting, markdown, or meta-commentary.
The script should be ready to be spoken directly by a text-to-speech system.
"""

NARRATION_SCRIPT_PROMPT_VI = """Bạn là một người thuyết trình chuyên nghiệp. Nhiệm vụ của bạn là tạo kịch bản thuyết minh tự nhiên, hấp dẫn cho một slide thuyết trình.

## Thông tin Slide

Slide số: {slide_number} trên {total_slides}
Loại phần: {section_type}
Tiêu đề: {title}

Nội dung:
{content}

{speaker_notes}

## Hướng dẫn

Tạo kịch bản thuyết minh:
1. Nghe tự nhiên khi đọc thành tiếng (tránh các cụm từ chỉ dùng trong văn viết như "như hình dưới đây")
2. Giải thích các điểm chính một cách rõ ràng và súc tích
3. Giữ giọng điệu chuyên nghiệp nhưng hấp dẫn
4. Phù hợp với loại phần:
   - Slide "tiêu đề": Giới thiệu ngắn gọn, chào đón khán giả
   - Slide "giới thiệu/tổng quan": Đặt bối cảnh, xem trước các điểm chính
   - Slide "nội dung": Giải thích các khái niệm, cung cấp insights
   - Slide "kết luận": Tóm tắt, đưa ra bài học
5. Mất khoảng {target_duration} giây để đọc với tốc độ tự nhiên (khoảng 120 từ mỗi phút cho tiếng Việt)

## Ngôn ngữ

Tạo kịch bản bằng tiếng Việt.

## Định dạng đầu ra

Chỉ trả về văn bản kịch bản thuyết minh, không có định dạng, markdown hoặc bình luận thêm.
Kịch bản phải sẵn sàng để được đọc trực tiếp bởi hệ thống text-to-speech.
"""


class ScriptGenerator:
    """
    Generates narration scripts for presentation slides using LLM.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_config: Optional[APIConfig] = None,
    ):
        """
        Initialize the script generator.

        Args:
            api_key: OpenAI/OpenRouter API key (defaults to APIConfig)
            base_url: API base URL (defaults to APIConfig)
            model: Model to use for generation (defaults to APIConfig)
            api_config: Optional APIConfig instance to use
        """
        # Use provided api_config or create one from environment
        if api_config is None:
            api_config = APIConfig()

        self.api_key = api_key or api_config.llm_api_key
        self.base_url = base_url or api_config.llm_base_url
        self.model = model or api_config.llm_model

        if not self.api_key:
            raise ValueError("API key not provided and RAG_LLM_API_KEY not set")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def generate_script(
        self,
        slide_data: Dict[str, Any],
        slide_number: int,
        total_slides: int,
        language: str = "en",
        target_duration: int = 30,
    ) -> str:
        """
        Generate a narration script for a single slide.

        Args:
            slide_data: Slide information from the plan
            slide_number: Current slide number (1-indexed)
            total_slides: Total number of slides
            language: Language for narration ("en", "vi", etc.)
            target_duration: Target duration in seconds

        Returns:
            Generated narration script text
        """
        # Extract slide information
        section_type = slide_data.get("section_type", "content")
        title = slide_data.get("title", f"Slide {slide_number}")

        # Build content string from various possible fields
        content_parts = []

        if "description" in slide_data:
            content_parts.append(slide_data["description"])

        if "bullet_points" in slide_data:
            bullets = slide_data["bullet_points"]
            if isinstance(bullets, list):
                content_parts.append("\n".join(f"- {b}" for b in bullets))

        if "key_points" in slide_data:
            points = slide_data["key_points"]
            if isinstance(points, list):
                content_parts.append("\n".join(f"- {p}" for p in points))

        if "content" in slide_data:
            content_parts.append(slide_data["content"])

        content = "\n\n".join(content_parts) if content_parts else "No content provided"

        # Speaker notes if available
        speaker_notes = ""
        if "speaker_notes" in slide_data and slide_data["speaker_notes"]:
            speaker_notes = f"Speaker Notes:\n{slide_data['speaker_notes']}"

        # Choose prompt based on language
        if language.lower() in ["vi", "vietnamese"]:
            prompt_template = NARRATION_SCRIPT_PROMPT_VI
        else:
            prompt_template = NARRATION_SCRIPT_PROMPT

        # Format the prompt
        prompt = prompt_template.format(
            slide_number=slide_number,
            total_slides=total_slides,
            section_type=section_type,
            title=title,
            content=content,
            speaker_notes=speaker_notes,
            target_duration=target_duration,
            language=language,
        )

        # Call the LLM
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional presentation narrator. Generate clear, engaging narration scripts.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1000,
        )

        script = response.choices[0].message.content.strip()
        return script

    async def generate_all_scripts(
        self,
        slides: List[Dict[str, Any]],
        language: str = "en",
        target_duration_per_slide: int = 30,
        progress_callback: Optional[callable] = None,
    ) -> List[str]:
        """
        Generate narration scripts for all slides.

        Args:
            slides: List of slide data dictionaries
            language: Language for narration
            target_duration_per_slide: Target duration per slide in seconds
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            List of narration scripts
        """
        scripts = []
        total_slides = len(slides)

        for i, slide in enumerate(slides):
            script = self.generate_script(
                slide_data=slide,
                slide_number=i + 1,
                total_slides=total_slides,
                language=language,
                target_duration=target_duration_per_slide,
            )
            scripts.append(script)

            if progress_callback:
                progress_callback(i + 1, total_slides)

        return scripts

    def generate_scripts_from_plan(
        self,
        plan_path: Path,
        language: str = "en",
        target_duration_per_slide: int = 30,
    ) -> List[str]:
        """
        Generate scripts from a checkpoint_plan.json file.

        Args:
            plan_path: Path to checkpoint_plan.json
            language: Language for narration
            target_duration_per_slide: Target duration per slide

        Returns:
            List of narration scripts
        """
        with open(plan_path, "r", encoding="utf-8") as f:
            plan_data = json.load(f)

        # Extract slides from plan
        plan = plan_data.get("plan", {})
        slides = plan.get("slides", [])

        if not slides:
            raise ValueError("No slides found in plan")

        scripts = []
        total_slides = len(slides)

        for i, slide in enumerate(slides):
            script = self.generate_script(
                slide_data=slide,
                slide_number=i + 1,
                total_slides=total_slides,
                language=language,
                target_duration=target_duration_per_slide,
            )
            scripts.append(script)

        return scripts


def estimate_speech_duration(text: str, language: str = "en") -> float:
    """
    Estimate the duration of spoken text in seconds.

    Args:
        text: Text to estimate
        language: Language of the text

    Returns:
        Estimated duration in seconds
    """
    # Words per minute varies by language
    # English: ~150 WPM, Vietnamese: ~120 WPM (due to tones)
    wpm = 120 if language.lower() in ["vi", "vietnamese"] else 150

    word_count = len(text.split())
    duration = (word_count / wpm) * 60

    # Add a small buffer for pauses
    return duration * 1.1
