#!/usr/bin/env python3
"""
Script to generate text files for voice generation from JSON files in input folder.
Each text file will contain book title and final_summary content with proper break tags.
Supports splitting summaries into chapters based on h2 (##) or h3 (###) headings.
"""

import json
import os
import glob
import re
from pathlib import Path
# import spacy

# Load the small English model
# try:
#     # nlp = spacy.load("en_core_web_sm")
# except OSError:
#     print("Downloading en_core_web_sm model...")
#     # from spacy.cli import download
#     # download("en_core_web_sm")
#     # nlp = spacy.load("en_core_web_sm")

def clean_filename(filename):
    """Clean filename to be safe for file system."""
    # Remove or replace characters that might cause issues
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()

def clean_title(title):
    """
    Clean book title by removing parentheses content and markdown characters.
    Also handles converting ' — ' or ' - ' to ' by '.
    """
    if not title:
        return ""
    
    # 1. Handle separators: convert "Title — Author" or "Title - Author" to "Title by Author"
    if ' — ' in title:
        parts = title.split(' — ', 1)
        title = f"{parts[0].strip()} by {parts[1].strip()}" if len(parts) == 2 else title
    elif ' - ' in title:
        parts = title.split(' - ', 1)
        title = f"{parts[0].strip()} by {parts[1].strip()}" if len(parts) == 2 else title
    
    # 2. Remove anything between parentheses (inclusive)
    # Using regex to handle multiple pairs and nested-ish cases (non-greedy)
    title = re.sub(r'\([^)]*\)', '', title)
    
    # 3. Remove markdown characters # and *
    title = title.replace('*', '').replace('#', '')
    
    # 4. Clean up extra whitespace that might have been left by removals
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title

def add_breaks_after_punctuation(text, language="English"):
    """
    Add break tags after sentences using spaCy for smart sentence detection.
    
    Uses spaCy's NLP model to detect sentence boundaries, correctly handling
    abbreviations like "Dr.", "Mr.", "D.C.", etc.
    
    Args:
        text: Text content to process
        
    Returns:
        Text with break tags inserted after each sentence
    """
    if not text:
        return ""
    
    # First, protect existing break tags from modification
    # Replace break tags with placeholders
    break_tag_pattern = r'<break\s+time="[^"]*"\s*/>'
    break_tags = []
    
    def replace_break_tag(match):
        break_tags.append(match.group(0))
        return f" __BREAK_TAG_{len(break_tags)-1}__ "
    
    # Pre-process: protect existing tags
    processed_text = re.sub(break_tag_pattern, replace_break_tag, text)
    
    # Restore break tags
    for i, break_tag in enumerate(break_tags):
        processed_text = processed_text.replace(f"__BREAK_TAG_{i}__", break_tag)

    if language.lower() == "hindi":
        # For Hindi, only add breaks after the Hindi full stop '।'
        # We ignore spaCy's sentence segmentation and use a simple regex
        # Note: We append a newline for readability in the voice text file
        output_text = re.sub(r'(।)\s*', r'\1<break time="0.5s" />\n', processed_text)
    else:
        # Process the text with spaCy (Standard English/General Logic)
        doc = nlp(processed_text)
        output_text = ""
        
        # doc.sents automatically yields actual sentences, respecting abbreviations
        for sentence in doc.sents:
            # Convert sentence object back to string
            sent_str = sentence.text.strip()
            
            if not sent_str:
                continue
                
            # Append the sentence plus your break tag
            # Don't add break if the sentence is just a placeholder for an existing break
            if re.match(r'^__BREAK_TAG_\d+__$', sent_str):
                output_text += f"{sent_str}"
            else:
                output_text += f"{sent_str}<break time=\"0.5s\" />\n"
            
    # Final cleanup: remove duplicate consecutive breaks
    output_text = re.sub(r'(<break\s+time="0\.5s"\s*/>\s*)+', r'<break time="0.5s" />\n', output_text)
    
    # Clean up: remove breaks right before existing breaks with different times
    # This might need adjustment depending on exact desired behavior, 
    # but generally we don't want double breaks
    output_text = re.sub(r'<break\s+time="0\.5s"\s*/>\s*(<break\s+time="[^"]*"\s*/>)', r'\1', output_text)
    
    return output_text.strip()

def clean_voice_text(text):
    """
    Clean voice text by removing unnecessary characters and markdown artifacts.
    
    Removes:
    - Markdown separators (***, ---, etc.)
    - Extra whitespace and empty lines at the end
    - Other markdown formatting that shouldn't be spoken
    
    Args:
        text: Raw text content
        
    Returns:
        Cleaned text ready for voice generation
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip markdown separators (***, ---, ===, etc.)
        if stripped in ['***', '---', '===', '___']:
            continue
        
        # Skip lines that are only asterisks, dashes, or equals
        if stripped and all(c in '*=-_' for c in stripped) and len(stripped) >= 3:
            continue
            
        # Global Dictionary Replacements based on review analysis
        # Expand common acronyms 
        line = re.sub(r'\be\.g\.\b', 'for example', line, flags=re.IGNORECASE)
        line = re.sub(r'\bi\.e\.\b', 'that is', line, flags=re.IGNORECASE)
        
        # Remove ALL markdown characters # and * globally from the line so the TTS engine NEVER attempts to pronounce "asterisk"
        line = line.replace('*', '').replace('#', '')
        
        # Keep the line (even if empty, to preserve paragraph breaks)
        cleaned_lines.append(line)
    
    # Join lines back together
    cleaned_text = '\n'.join(cleaned_lines)
    
    # Remove trailing whitespace and empty lines at the end
    cleaned_text = cleaned_text.rstrip()
    
    # Remove any remaining markdown separators at the very end
    while cleaned_text.endswith('\n***') or cleaned_text.endswith('\n---'):
        cleaned_text = cleaned_text[:-4].rstrip()
    
    # Remove standalone *** or --- at the end
    if cleaned_text.endswith('***'):
        cleaned_text = cleaned_text[:-3].rstrip()
    if cleaned_text.endswith('---'):
        cleaned_text = cleaned_text[:-3].rstrip()
    
    # Apply pronunciation improvements (nukta normalization + word substitutions)
    from modules.pronunciation_fixes import apply_all_fixes
    cleaned_text = apply_all_fixes(cleaned_text)

    return cleaned_text

def generate_voice_text_from_json(json_file_path, output_dir="voice_texts1"):
    """
    Generate voice text file from a single JSON file.
    
    Args:
        json_file_path: Path to the JSON file
        output_dir: Directory to save the voice text file
    
    Returns:
        Path to the generated voice text file, or None if failed
    """
    try:
        # Read the JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        title = clean_title(data.get('title', 'Unknown Title'))
        final_summary = data.get('final_summary', '')
        
        # Skip if no content
        if not final_summary.strip():
            print(f"  Skipping {title}: no final_summary content")
            return None
        
        # Create text content for voice generation
        # Add title with break at the beginning
        text_content = [f"{title} <break time=\"1s\" />"]
        
        # Add the final_summary content
        text_content.append(final_summary)
        
        # Join all content
        final_text = "\n".join(text_content)
        
        # Add breaks after punctuation marks
        final_text = add_breaks_after_punctuation(final_text)
        
        # Create output filename
        safe_title = clean_filename(title)
        output_filename = f"{safe_title}_voice.txt"
        output_path = os.path.join(output_dir, output_filename)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_text)
        
        print(f"  Created: {output_filename}")
        return output_path
        
    except Exception as e:
        print(f"Error processing {json_file_path}: {str(e)}")
        return None

def split_summary_into_chapters(final_summary):
    """
    Split summary text into chapters based on h2 (##) or h3 (###) headings.
    
    Args:
        final_summary: The summary text to split
        
    Returns:
        List of tuples: (chapter_title, chapter_content)
    """
    if not final_summary.strip():
        return []
    
    # Split by lines starting with ## or ###
    chapters = []
    lines = final_summary.split('\n')
    
    current_chapter_title = None
    current_chapter_content = []
    
    for line in lines:
        stripped_line = line.strip()
        # Check if line starts with ## (h2) or ### (h3 heading)
        if stripped_line.startswith('###'):
            # Save previous chapter if exists
            if current_chapter_title is not None:
                chapter_text = '\n'.join(current_chapter_content).strip()
                if chapter_text:
                    chapters.append((current_chapter_title, chapter_text))
            
            # Start new chapter
            # Remove ### and clean up the title
            current_chapter_title = stripped_line.replace('###', '').strip()
            current_chapter_content = []
        elif stripped_line.startswith('##') and not stripped_line.startswith('###'):
            # Save previous chapter if exists
            if current_chapter_title is not None:
                chapter_text = '\n'.join(current_chapter_content).strip()
                if chapter_text:
                    chapters.append((current_chapter_title, chapter_text))
            
            # Start new chapter
            # Remove ## and clean up the title
            current_chapter_title = stripped_line.replace('##', '').strip()
            current_chapter_content = []
        else:
            # Add line to current chapter content
            if current_chapter_title is not None:
                current_chapter_content.append(line)
            else:
                # Content before first chapter - we'll include it in the first chapter
                if not chapters and current_chapter_content is not None:
                    current_chapter_content.append(line)
    
    # Save last chapter
    if current_chapter_title is not None:
        chapter_text = '\n'.join(current_chapter_content).strip()
        if chapter_text:
            chapters.append((current_chapter_title, chapter_text))
    
    # If no chapters found (no ## or ### headings), treat entire summary as one chapter
    if not chapters and final_summary.strip():
        chapters.append(("Introduction", final_summary.strip()))
    
    return chapters

def generate_voice_text_chapters_from_json(json_file_path, output_base_dir="voice_texts", **kwargs):
    """
    Generate voice text files split into chapters from a single JSON file.
    Creates a folder for each summary and saves each chapter as a separate file.
    
    Args:
        json_file_path: Path to the JSON file
        output_base_dir: Base directory to save the voice text files
    
    Returns:
        List of paths to generated voice text files, or None if failed
    """
    try:
        # Read the JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Determine title and author based on fields (support nested fields)
        title_field = kwargs.get('title_field', 'title')
        author_field = kwargs.get('author_field', '')

        def get_nested_field(data_obj, field_path):
            if not field_path:
                return ""
            if '.' in field_path:
                parts = field_path.split('.')
                val = data_obj
                for part in parts:
                    if isinstance(val, dict):
                        val = val.get(part, "")
                    else:
                        return ""
                return val
            return data_obj.get(field_path, "")

        # Try to get Hindi title and author if fields provided
        hindi_title = get_nested_field(data, title_field)
        hindi_author = get_nested_field(data, author_field)

        if title_field != 'title' and hindi_title: # If we are looking for a specific (Hindi) title field
            if hindi_author:
                title = f"{hindi_title} - {hindi_author}"
            else:
                title = hindi_title
            # We don't call clean_title on Hindi titles to avoid replacing - with by
        else:
            title = clean_title(data.get('title', 'Unknown Title'))
        
        # Get JSON file ID - use ID from JSON data, fallback to filename stem
        json_id = data.get('id', Path(json_file_path).stem)
        
        # Determine summary content based on field (support nested fields like hindi_translation.summary)
        summary_field = kwargs.get('summary_field', 'final_summary')
        final_summary = get_nested_field(data, summary_field)
        
        # Skip if no content
        if not final_summary or not final_summary.strip():
            print(f"  Skipping {json_id}: no {summary_field} content")
            return None
        
        # Split summary into chapters
        chapters = split_summary_into_chapters(final_summary)
        
        if not chapters:
            print(f"  Skipping {json_id}: no chapters found")
            return None
        
        # Create output directory for this summary using JSON ID
        summary_output_dir = os.path.join(output_base_dir, json_id)
        
        # Clean up existing directory to prevent duplicates (e.g. from filename changes)
        if os.path.exists(summary_output_dir):
            import shutil
            try:
                shutil.rmtree(summary_output_dir)
            except Exception as e:
                print(f"Warning: Could not remove existing directory {summary_output_dir}: {e}")
        
        os.makedirs(summary_output_dir, exist_ok=True)
        
        generated_files = []
        
        # Generate a voice text file for each chapter
        for idx, (chapter_title, chapter_content) in enumerate(chapters, 1):
            # Clean the chapter content to remove unnecessary characters
            cleaned_content = clean_voice_text(chapter_content)
            
            # Clean chapter title of markdown characters
            cleaned_chapter_title = chapter_title.replace('*', '').replace('#', '').strip()

            # Create text content for voice generation
            text_content = []
            
            # Add title with break only for the first chapter
            if idx == 1:
                text_content.append(f"{title} <break time=\"1s\" />")
                # First chapter should not have its heading, only book title and author
            else:
                # Add chapter title with break for all other chapters
                text_content.append(f"{cleaned_chapter_title} <break time=\"1s\" />")
            
            # Add the cleaned chapter content
            text_content.append(cleaned_content)
            
            # Join all content
            final_text = "\n".join(text_content)
            
            # Add breaks after punctuation marks
            final_text = add_breaks_after_punctuation(final_text)
            
            # Final cleanup: remove any trailing separators or extra whitespace
            final_text = final_text.rstrip()
            
            # Create output filename for chapter
            safe_chapter_title = clean_filename(cleaned_chapter_title)
            # Limit chapter title length for filename
            if len(safe_chapter_title) > 50:
                safe_chapter_title = safe_chapter_title[:50]
            
            # Use index and cleaned title for filename
            output_filename = f"chapter_{idx:02d}_{safe_chapter_title}_voice.txt"
            output_path = os.path.join(summary_output_dir, output_filename)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_text)
            
            print(f"    Created chapter {idx}: {output_filename}")
            generated_files.append(output_path)
        
        print(f"  Created {len(generated_files)} chapter files in: {summary_output_dir}")
        return generated_files
        
    except Exception as e:
        print(f"Error processing {json_file_path}: {str(e)}")
        return None

def generate_voice_text_chapters(input_dir="input", output_dir="voice_texts"):
    """
    Generate chapter-based voice text files from JSON files in input folder.
    Each summary is split into chapters and saved in its own folder.
    
    Args:
        input_dir: Directory containing JSON files
        output_dir: Base directory to save voice text files
    
    Returns:
        Dictionary mapping summary names to lists of generated file paths
    """
    # Get all JSON files from input directory
    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    
    # Create base output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Found {len(json_files)} JSON files")
    
    all_generated_files = {}
    for json_file in json_files:
        print(f"\nProcessing: {os.path.basename(json_file)}")
        result = generate_voice_text_chapters_from_json(json_file, output_dir)
        if result:
            # Extract summary name from first file path
            summary_name = os.path.basename(os.path.dirname(result[0]))
            all_generated_files[summary_name] = result
    
    print(f"\n{'='*60}")
    print(f"Voice text files generated in: {output_dir}")
    print(f"Total summaries processed: {len(all_generated_files)}")
    total_files = sum(len(files) for files in all_generated_files.values())
    print(f"Total chapter files created: {total_files}")
    
    return all_generated_files

def generate_voice_text(input_dir="input", output_dir="voice_texts1"):
    """Generate text files for voice generation from JSON files in input folder."""
    
    # Get all JSON files from input directory
    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    
    # Create output directory for voice text files
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Found {len(json_files)} JSON files")
    
    generated_files = []
    for json_file in json_files:
        result = generate_voice_text_from_json(json_file, output_dir)
        if result:
            generated_files.append(result)
    
    print(f"\nVoice text files generated in: {output_dir}")
    print(f"Total files created: {len(generated_files)}")
    return generated_files

if __name__ == "__main__":
    # By default, generate chapter-based files
    generate_voice_text_chapters()
