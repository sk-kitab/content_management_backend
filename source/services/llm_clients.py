import os
import time
from typing import Optional

try:
    # Load environment variables from a .env file if present
    from dotenv import load_dotenv  # type: ignore
    # Prefer project root .env (two levels up from this file: services/ -> source/ -> backend/)
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
    _root_env = os.path.join(_project_root, ".env")
    if os.path.exists(_root_env):
        load_dotenv(_root_env)
    else:
        # Fallback: load default .env from current working directory
        load_dotenv()
except Exception:
    # dotenv is optional; continue if unavailable
    pass


def summary_response_gemini(instructions: str, user_prompt: str, max_retries: int = 3) -> Optional[str]:
    """
    Generate content via Google Gemini models using env var GOOGLE_GENAI_API_KEY.
    Falls back to GOOGLE_GENAI_API_KEY1 if primary key fails.
    Includes retry logic with exponential backoff.
    Returns text or None if unavailable/misconfigured.

    Args:
        instructions: System instructions for the model
        user_prompt: User prompt/content
        max_retries: Maximum number of retry attempts per API key (default: 3)
    """
    # Get primary and fallback API keys
    primary_key = (
        os.getenv("GOOGLE_GENAI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_APIKEY")
    )

    fallback_key = os.getenv("GOOGLE_GENAI_API_KEY1")

    # Collect all available keys
    api_keys = []
    if primary_key:
        api_keys.append(("primary", primary_key))
    if fallback_key:
        api_keys.append(("fallback", fallback_key))

    if not api_keys:
        print("Warning: Google/Gemini API key not set; skipping Gemini call.")
        return None

    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        print(f"Warning: google-genai not available ({e}); skipping Gemini call.")
        return None

    # Try each API key with retries
    for key_idx, (key_type, api_key) in enumerate(api_keys):
        for attempt in range(max_retries):
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=instructions,
                        max_output_tokens=65536,
                        temperature=0.1,
                    ),
                )
                result = getattr(response, "text", None) or None
                if result:
                    if attempt > 0 or key_idx > 0:
                        status = f"on {key_type} key"
                        if attempt > 0:
                            status += f" (attempt {attempt + 1})"
                        if key_idx > 0:
                            status += " [using fallback key]"
                        print(f"✅ Gemini API call succeeded {status}")
                    return result
                else:
                    print(f"Warning: Gemini API returned empty response on {key_type} key (attempt {attempt + 1})")
            except Exception as e:
                error_msg = str(e)
                is_last_attempt = (attempt == max_retries - 1)
                is_last_key = (key_idx == len(api_keys) - 1)

                if is_last_attempt and is_last_key:
                    # Final attempt on last key - print error and return None
                    print(f"❌ Error during Gemini call with {key_type} key (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    print("All API keys exhausted. Returning None.")
                    return None
                elif is_last_attempt:
                    # Last attempt on this key, but more keys available
                    print(f"⚠️ Error during Gemini call with {key_type} key (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    print(f"Switching to next API key...")
                    break  # Break inner loop to try next key
                else:
                    # Not last attempt - retry with backoff
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, etc.
                    print(f"⚠️ Error during Gemini call with {key_type} key (attempt {attempt + 1}/{max_retries}): {error_msg}")
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

    # If we get here, all keys and retries were exhausted
    print("❌ All Gemini API keys and retries exhausted. Returning None.")
    return None


def summary_response_openai(instructions: str, user_prompt: str) -> Optional[str]:
    """
    Generate content via OpenAI Responses API using env var OPENAI_API_KEY.
    Returns text or None if unavailable/misconfigured.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY not set; skipping OpenAI call.")
        return None
    try:
        from openai import OpenAI
    except Exception as e:
        print(f"Warning: openai package not available ({e}); skipping OpenAI call.")
        return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-4.1",
            input=user_prompt,
            instructions=instructions,
        )
        # New SDK exposes convenience:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return output_text
        # Fallback: concatenate text from response content parts if present
        try:
            parts = []
            for item in response.output or []:  # type: ignore[attr-defined]
                if getattr(item, "type", "") == "output_text":
                    parts.append(getattr(item, "text", ""))
            return "\n".join(parts) if parts else None
        except Exception:
            return None
    except Exception as e:
        print(f"Error during OpenAI call: {e}")
        return None


