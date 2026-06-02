import os
import logging
from typing import Optional
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
from pathlib import Path
import json

# ============================================================================
# Client Initialization
# ============================================================================

voice_settings = VoiceSettings(
    stability=0.8,
    similarity_boost=0.51,
    speed=0.96,
    style=.17 
    # maybe other style/emotion settings depending on voice
)

def _load_elevenlabs_client() -> ElevenLabs:
    """Initialize and return ElevenLabs client using API key from environment."""
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set in environment.")
    return ElevenLabs(api_key=api_key)

def _get_voice_name_from_id(voice_id: str) -> Optional[str]:
    """
    Get voice name from voice ID using the voice mapping file.
    
    Args:
        voice_id: ElevenLabs voice ID
        
    Returns:
        Voice name if found, None otherwise
    """
    try:
        # Try to load voice mapping file - check multiple possible locations
        current_file = Path(__file__)
        possible_paths = [
            current_file.parent / "voice_name_to_id_mapping.json",  # Same directory
            current_file.parent.parent / "voice_name_to_id_mapping.json",  # Parent directory
            Path("modules") / "voice_name_to_id_mapping.json",  # Relative to cwd
        ]
        
        mapping_file = None
        for path in possible_paths:
            if path.exists():
                mapping_file = path
                break
        
        if mapping_file and mapping_file.exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                voice_id_to_name = mapping_data.get("voice_id_to_name", {})
                return voice_id_to_name.get(voice_id)
    except Exception as e:
        logging.warning(f"Could not load voice mapping: {e}")
    return None


def select_model_by_voice(voice_id: str, default_model: str = "eleven_multilingual_v2", language: str = "English") -> str:
    """
    Select the appropriate model based on voice name or language.
    
    If language is "Hindi", use "eleven_v3".
    For "Anchor v1" and "Coach v1" voices in English, use "eleven_v3".
    For all other voices, use "eleven_multilingual_v2" (or provided default).
    
    Args:
        voice_id: ElevenLabs voice ID
        default_model: Default model to use if voice doesn't match special cases
        language: Language of the text (default: "English")
        
    Returns:
        Model ID string
    """
    # Force eleven_v3 for Hindi summaries regardless of voice
    if language.lower() == "hindi":
        logging.info(f"Using eleven_v3 model for Hindi summary")
        return "eleven_v3"

    voice_name = _get_voice_name_from_id(voice_id)
    
    if voice_name:
        # Normalize voice name for comparison (case-insensitive, handle variations)
        normalized_name = voice_name.lower().replace("-", " ").replace("_", " ")
        
        # Check if it's Anchor v1 or Coach v1
        if "anchor" in normalized_name and "v1" in normalized_name:
            return "eleven_v3"
        elif "coach" in normalized_name and "v1" in normalized_name:
            return "eleven_v3"
    
    # Default to multilingual model for all other voices
    return default_model


def generate_tts(
    text: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
    override_model_selection: bool = False,
    language: str = "English",
) -> bytes:
    """
    Generate TTS using ElevenLabs.
    
    Args:
        text: Input text
        voice_id: ElevenLabs voice ID
        model_id: ElevenLabs model ID (default: "eleven_multilingual_v2")
            Note: This will be overridden based on voice name or language unless override_model_selection=True:
            - Language is "Hindi" -> "eleven_v3"
            - "Anchor v1" and "Coach v1" -> "eleven_v3"
            - All others -> "eleven_multilingual_v2"
        override_model_selection: If True, use provided model_id without voice-based override (default: False)
        language: Language of the text (default: "English")
    
    Returns:
        Raw audio bytes
    """
    client = _load_elevenlabs_client()
    
    # Select model based on voice name or language (unless override is requested)
    if not override_model_selection:
        selected_model = select_model_by_voice(voice_id, default_model=model_id, language=language)
        if selected_model != model_id:
            logging.info(f"Model overridden: {model_id} -> {selected_model} (based on voice or language)")
        model_id = selected_model
    else:
        logging.info(f"Using provided model: {model_id} (override_model_selection=True)")

    # Remove break tags if using eleven_v3 model (Anchor v1 and Coach v1)
    if model_id == "eleven_v3":
        import re
        # Remove all break tag variations
        text = re.sub(r'<break\s+time=["\'][^"\']*["\']\s*/>', '', text)
        text = re.sub(r'<break\s+time=["\'][^"\']*["\']\s*></break>', '', text)
        text = re.sub(r'</break>', '', text)
        text = re.sub(r'<break\s+time=["\'][^"\']*["\']\s*>', '', text)
        logging.info("Removed break tags for eleven_v3 model")

    # Generate TTS audio
    # eleven_v3 model doesn't support voice_settings parameter
    if model_id == "eleven_v3":
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
        )
    else:
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
    
    # Convert generator to bytes if needed
    if hasattr(audio_generator, '__iter__') and not isinstance(audio_generator, (bytes, str)):
        audio_bytes = b''.join(audio_generator)
    else:
        audio_bytes = audio_generator
            
    return audio_bytes

# Keep old name for compatibility if needed, but we will update the caller.
generate_tts_with_hindi_dictionary = generate_tts

__all__ = ["generate_tts", "generate_tts_with_hindi_dictionary", "select_model_by_voice"]
