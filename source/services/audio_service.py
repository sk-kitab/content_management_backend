# backend/services/audio_service.py
from source.config import settings

from modules.chapter_audio_processor import process_chapters_to_final_audio
from modules.supabase_utils import replace_audio_in_supabase

def generate_audio(linear_id: str, language: str, voice_id: str | None) -> str | None:
    lang = language.lower()
    if lang == "english":
        voice_texts_dir = settings.voice_texts_dir
        pre_audio_dir = f"{settings.audios_root}/english_pre_audio"
        audios_dir = f"{settings.audios_root}/english-final"
    else:
        voice_texts_dir = "hindi_texts"
        pre_audio_dir = f"{settings.audios_root}/hindi_pre_audio"
        audios_dir = f"{settings.audios_root}/hindi-final"

    result = process_chapters_to_final_audio(
        json_id=linear_id,
        voice_texts_dir=voice_texts_dir,
        pre_audio_dir=pre_audio_dir,
        audios_dir=audios_dir,
        voice_id=voice_id or "",
        use_llm=(lang == "english"),
        language=language.capitalize(),
    )
    if not result:
        return None

    public_url = replace_audio_in_supabase(str(result), linear_id, language)
    return public_url
