import os
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "content"

def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def replace_audio_in_supabase(file_path, linear_id, language):
    """
    Upload an audio file to Supabase storage, replacing any existing file with the same path.
    """
    client = get_supabase_client()
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {file_path}")
        
    # Determine storage path based on language
    if language.lower() == 'english':
        storage_path = f"summaries/{linear_id}.mp3"
    else:
        storage_path = f"summaries/hindi/{linear_id}.mp3"
        
    print(f"Uploading {file_path} to {storage_path} with upsert=True...")
    
    with open(file_path, 'rb') as f:
        # Standard upload with upsert=True
        # Note: If the file already exists, upsert will overwrite it
        response = client.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=f,
            file_options={"cache-control": "3600", "upsert": "true"}
        )
        
    public_url = client.storage.from_(BUCKET_NAME).get_public_url(storage_path)
    print(f"Successfully uploaded/replaced audio. Public URL: {public_url}")
    return public_url

if __name__ == "__main__":
    # Test block (can be run manually)
    # replace_audio_in_supabase("audios/english-final/SUM-104.mp3", "SUM-104", "English")
    pass
