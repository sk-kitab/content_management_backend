# backend/services/voice_service.py
import json
import tempfile
from pathlib import Path
from source.config import settings

from modules.generate_voice_text import generate_voice_text_chapters_from_json

def generate_voice_text(linear_id: str, language: str, title: str, final_summary: str) -> bool:
    voice_texts_dir = (
        settings.voice_texts_dir if language.lower() == "english"
        else "hindi_texts"
    )
    payload = {"id": linear_id, "title": title, "final_summary": final_summary}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f, ensure_ascii=False)
        tmp_path = f.name

    try:
        result = generate_voice_text_chapters_from_json(
            tmp_path, voice_texts_dir,
            summary_field="final_summary",
            title_field="title",
            author_field="",
        )
        return bool(result)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
