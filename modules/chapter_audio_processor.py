#!/usr/bin/env python3
"""
Module for processing chapter audio files:
1. Generate audio for each chapter using text_to_speech_v2
2. Combine chapter audio files into final audio using ffmpeg
"""

import subprocess
import re
from pathlib import Path
from typing import List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from modules.text_to_speech_v2 import generate_tts_with_hindi_dictionary, select_model_by_voice
from pydub import AudioSegment, effects
import io

# Default voice ID - can be configured
DEFAULT_VOICE_ID = "NaKPQmdr7mMxXuXrNeFC"


def _extract_chapter_number(filename: str) -> int:
    """
    Extract chapter number from filename.
    Expected format: chapter_01_title_voice.txt or chapter_1_title_voice.txt
    
    Args:
        filename: Chapter filename
        
    Returns:
        Chapter number as integer, or 0 if not found
    """
    match = re.search(r'chapter_(\d+)', filename)
    if match:
        return int(match.group(1))
    return 0


def _sort_chapter_files(chapter_files: List[Path]) -> List[Path]:
    """
    Sort chapter files by chapter number.
    
    Args:
        chapter_files: List of chapter file paths
        
    Returns:
        Sorted list of chapter files
    """
    return sorted(chapter_files, key=lambda f: _extract_chapter_number(f.name))


def generate_chapter_audios(
    json_id: str,
    voice_texts_dir: str = "voice_texts",
    pre_audio_dir: str = "audios/english_pre_audio",
    voice_id: str = DEFAULT_VOICE_ID,
    model_id: str = "eleven_multilingual_v2",
    use_llm: bool = True,
    language: str = "English",
    override_model_selection: bool = False,
) -> List[Path]:
    """
    Generate audio files for each chapter using text_to_speech_v2.
    Skips chapters that already have audio files.
    
    Args:
        json_id: JSON file ID (used for folder naming)
        voice_texts_dir: Base directory containing voice text files
        pre_audio_dir: Directory to save chapter audio files
        voice_id: ElevenLabs voice ID
        model_id: ElevenLabs model ID
        use_llm: Whether to use LLM for script improvements
        language: Language of the text
        
    Returns:
        List of paths to chapter audio files (existing and newly generated)
    """
    voice_texts_path = Path(voice_texts_dir) / json_id
    pre_audio_path = Path(pre_audio_dir) / json_id
    
    # Create pre_audio directory if it doesn't exist
    pre_audio_path.mkdir(parents=True, exist_ok=True)
    
    if not voice_texts_path.exists():
        logging.error(f"Voice text directory not found: {voice_texts_path}")
        return []
    
    # Find all chapter voice text files
    chapter_files = list(voice_texts_path.glob("chapter_*_voice.txt"))
    
    if not chapter_files:
        logging.warning(f"No chapter files found in {voice_texts_path}")
        return []
    
    # Sort chapter files by chapter number
    chapter_files = _sort_chapter_files(chapter_files)
    
    generated_audio_files = []
    
    for chapter_file in chapter_files:
        # Determine output audio file path
        audio_filename = chapter_file.stem + ".mp3"
        audio_path = pre_audio_path / audio_filename
        
        # Skip if audio already exists
        if audio_path.exists():
            logging.info(f"⏭️  Skipping {chapter_file.name}: audio already exists")
            generated_audio_files.append(audio_path)
            continue
        
        try:
            # Read chapter text
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter_text = f.read()
            
            if not chapter_text.strip():
                logging.warning(f"Empty chapter file: {chapter_file}")
                continue
            
            # Generate audio
            logging.info(f"Generating audio for {chapter_file.name}...")
            audio_bytes = generate_tts_with_hindi_dictionary(
                text=chapter_text,
                voice_id=voice_id,
                model_id=model_id,
                language=language,
                override_model_selection=override_model_selection,
            )
            
            # Save audio file
            with open(audio_path, 'wb') as f:
                f.write(audio_bytes)
            
            logging.info(f"✅ Generated audio: {audio_path}")
            generated_audio_files.append(audio_path)
            
        except Exception as e:
            logging.error(f"Error generating audio for {chapter_file.name}: {e}")
            continue
    
    return generated_audio_files

def combine_audios_v2(audios):
    segments = []
    
    # Convert bytes to AudioSegment objects
    for audio_bytes in audios:
        # Create AudioSegment from bytes (ElevenLabs typically returns MP3)
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        # Normalize each segment
        audio_segment = effects.normalize(audio_segment)
        segments.append(audio_segment)

    combined = segments[0]
    pause_ms=750
    crossfade_ms=0
        
    # Add pause and remaining segments with crossfade
    pause = AudioSegment.silent(duration=pause_ms)

    for segment in segments[1:]:
        combined = combined.append(pause).append(segment, crossfade=crossfade_ms)

    # Final normalization
    combined = effects.normalize(combined)
    # Create an in-memory buffer
    audio_buffer = io.BytesIO()

    # Export AudioSegment to buffer as MP3
    combined.export(audio_buffer, format="mp3", bitrate="128k")

    # Reset buffer position to beginning
    audio_buffer.seek(0)

    # Get the bytes data
    audio_bytes = audio_buffer.getvalue()
    return audio_bytes


def combine_chapter_audios(
    json_id: str,
    pre_audio_dir: str = "audios/english_pre_audio",
    audios_dir: str = "audios/english-final",
    voice_id: str = DEFAULT_VOICE_ID,
    model_id: str = "eleven_multilingual_v2",
    language: str = "English",
) -> Optional[Path]:
    """
    Combine chapter audio files into a single final audio file.
    Uses combine_audios_v2 for eleven_v3 model, otherwise uses ffmpeg.
    
    Args:
        json_id: JSON file ID (used for folder naming)
        pre_audio_dir: Directory containing chapter audio files
        audios_dir: Directory to save final combined audio
        voice_id: ElevenLabs voice ID
        model_id: ElevenLabs model ID
        language: Language of the text
        
    Returns:
        Path to final combined audio file, or None if failed
    """
    pre_audio_path = Path(pre_audio_dir) / json_id
    audios_path = Path(audios_dir)
    
    # Create audios directory if it doesn't exist
    audios_path.mkdir(parents=True, exist_ok=True)
    
    if not pre_audio_path.exists():
        logging.error(f"Pre-audio directory not found: {pre_audio_path}")
        return None
    
    # Find all chapter audio files
    chapter_audio_files = list(pre_audio_path.glob("chapter_*.mp3"))
    
    if not chapter_audio_files:
        logging.error(f"No chapter audio files found in {pre_audio_path}")
        return None
    
    # Sort chapter audio files by chapter number
    chapter_audio_files = _sort_chapter_files(chapter_audio_files)
    
    # Determine the actual model used
    actual_model = select_model_by_voice(voice_id, default_model=model_id, language=language)
    
    # If using eleven_v3, use combine_audios_v2 (pydub)
    if actual_model == "eleven_v3":
        logging.info("Using combine_audios_v2 (pydub) for eleven_v3 model")
        try:
            # Read all audio files into bytes
            audio_bytes_list = []
            for audio_file in chapter_audio_files:
                with open(audio_file, 'rb') as f:
                    audio_bytes_list.append(f.read())
            
            # Combine audios
            combined_bytes = combine_audios_v2(audio_bytes_list)
            
            # Save final audio
            final_audio_path = audios_path / f"{json_id}.mp3"
            with open(final_audio_path, 'wb') as f:
                f.write(combined_bytes)
                
            logging.info(f"✅ Combined audio files to: {final_audio_path}")
            return final_audio_path
            
        except Exception as e:
            logging.error(f"Error combining audio files with pydub: {e}")
            return None

    if len(chapter_audio_files) == 1:
        # If only one chapter, just copy it
        source_file = chapter_audio_files[0]
        final_audio_path = audios_path / f"{json_id}.mp3"
        
        try:
            import shutil
            shutil.copy2(source_file, final_audio_path)
            logging.info(f"✅ Copied single chapter audio to: {final_audio_path}")
            return final_audio_path
        except Exception as e:
            logging.error(f"Error copying audio file: {e}")
            return None
    
    # Use ffmpeg to concatenate multiple audio files
    # Create a temporary file list for ffmpeg concat demuxer
    concat_list_path = pre_audio_path / "concat_list.txt"
    
    try:
        # Write file list for ffmpeg concat demuxer
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for audio_file in chapter_audio_files:
                # Use absolute path
                abs_path = str(audio_file.resolve())
                
                # For ffmpeg concat demuxer format:
                # When using single quotes, escape single quotes by ending the quote,
                # adding an escaped single quote, and starting a new quote: '\''
                # So 'path/with'quote' becomes 'path/with'\''quote'
                # In Python string: replace ' with '\''
                escaped_path = abs_path.replace("'", "'\\''")
                
                # Write in format: file '/path/to/file'
                # The -safe 0 flag allows absolute paths and special characters
                f.write(f"file '{escaped_path}'\n")
        
        # Final output path
        final_audio_path = audios_path / f"{json_id}.mp3"
        
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, 
                         check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logging.error("ffmpeg not found. Please install ffmpeg to combine audio files.")
            return None
        
        # Run ffmpeg concat command
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_list_path),
            '-c', 'copy',  # Copy codec (faster, no re-encoding)
            '-y',  # Overwrite output file if exists
            str(final_audio_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        logging.info(f"✅ Combined audio files to: {final_audio_path}")
        
        # Clean up temporary concat list file
        try:
            concat_list_path.unlink()
        except Exception:
            pass
        
        return final_audio_path
        
    except subprocess.CalledProcessError as e:
        logging.error(f"ffmpeg error: {e.stderr}")
        return None
    except Exception as e:
        logging.error(f"Error combining audio files: {e}")
        return None
    finally:
        # Clean up temporary concat list file if it exists
        if concat_list_path.exists():
            try:
                concat_list_path.unlink()
            except Exception:
                pass


def process_chapters_to_final_audio(
    json_id: str,
    voice_texts_dir: str = "voice_texts",
    pre_audio_dir: str = "audios/english_pre_audio",
    audios_dir: str = "audios/english-final",
    voice_id: str = DEFAULT_VOICE_ID,
    model_id: str = "eleven_multilingual_v2",
    use_llm: bool = True,
    language: str = "English",
    override_model_selection: bool = False,
) -> Optional[Path]:
    """
    Complete workflow: Generate chapter audios and combine into final audio.
    
    Args:
        json_id: JSON file ID (used for folder naming)
        voice_texts_dir: Base directory containing voice text files
        pre_audio_dir: Directory to save chapter audio files
        audios_dir: Directory to save final combined audio
        voice_id: ElevenLabs voice ID
        model_id: ElevenLabs model ID
        use_llm: Whether to use LLM for script improvements
        language: Language of the text
        
    Returns:
        Path to final combined audio file, or None if failed
    """
    # Step 1: Generate chapter audios
    chapter_audios = generate_chapter_audios(
        json_id=json_id,
        voice_texts_dir=voice_texts_dir,
        pre_audio_dir=pre_audio_dir,
        voice_id=voice_id,
        model_id=model_id,
        use_llm=use_llm,
        language=language,
        override_model_selection=override_model_selection,
    )
    
    if not chapter_audios:
        logging.error(f"No chapter audios generated for {json_id}")
        return None
    
    # Step 2: Combine chapter audios
    final_audio = combine_chapter_audios(
        json_id=json_id,
        pre_audio_dir=pre_audio_dir,
        audios_dir=audios_dir,
        voice_id=voice_id,
        model_id=model_id,
        language=language,
    )
    
    return final_audio


    return final_audio


def generate_single_chapter_audio(
    json_id: str,
    chapter_filename: str,
    voice_texts_dir: str = "voice_texts",
    pre_audio_dir: str = "audios/english_pre_audio",
    voice_id: str = DEFAULT_VOICE_ID,
    model_id: str = "eleven_multilingual_v2",
    use_llm: bool = True,
    language: str = "English",
    override_model_selection: bool = False,
) -> bool:
    """
    Generate audio for a single chapter.
    
    Args:
        json_id: JSON file ID
        chapter_filename: Name of the chapter audio file (e.g. chapter_01_....mp3)
        voice_texts_dir: Base directory containing voice text files
        pre_audio_dir: Directory to save chapter audio files
        voice_id: ElevenLabs voice ID
        model_id: ElevenLabs model ID
        use_llm: Whether to use LLM for script improvements
        language: Language of the text
        override_model_selection: Whether to override model selection logic
        
    Returns:
        True if successful, False otherwise
    """
    try:
        voice_texts_path = Path(voice_texts_dir) / json_id
        pre_audio_path = Path(pre_audio_dir) / json_id
        
        # Ensure directories exist
        pre_audio_path.mkdir(parents=True, exist_ok=True)
        
        # Construct text filename from audio filename
        # Audio: chapter_01_Title.mp3 -> Text: chapter_01_Title_voice.txt
        # Or if the audio filename is just the stem of the text filename
        # Let's assume the audio filename is derived from the text filename
        
        # Actually, in generate_chapter_audios:
        # audio_filename = chapter_file.stem + ".mp3"
        # So text_filename = audio_filename.replace(".mp3", "_voice.txt") ? 
        # No, chapter_file.stem is "chapter_01_Title_voice"
        # So audio_filename is "chapter_01_Title_voice.mp3"
        
        # So to get text filename from audio filename:
        # text_filename = audio_filename.replace(".mp3", ".txt")
        
        text_filename = chapter_filename.replace(".mp3", ".txt")
        text_path = voice_texts_path / text_filename
        
        if not text_path.exists():
            logging.error(f"Text file not found: {text_path}")
            return False
            
        # Read chapter text
        with open(text_path, 'r', encoding='utf-8') as f:
            chapter_text = f.read()
        
        if not chapter_text.strip():
            logging.warning(f"Empty chapter file: {text_path}")
            return False
        
        # Generate audio
        logging.info(f"Generating audio for {chapter_filename}...")
        audio_bytes = generate_tts_with_hindi_dictionary(
            text=chapter_text,
            voice_id=voice_id,
            model_id=model_id,
            language=language,
            override_model_selection=override_model_selection,
        )
        
        # Save audio file
        audio_path = pre_audio_path / chapter_filename
        with open(audio_path, 'wb') as f:
            f.write(audio_bytes)
        
        logging.info(f"✅ Generated audio: {audio_path}")
        return True
        
    except Exception as e:
        logging.error(f"Error generating single chapter audio: {e}")
        return False


__all__ = [
    "generate_chapter_audios",
    "combine_chapter_audios",
    "process_chapters_to_final_audio",
    "generate_single_chapter_audio",
]

