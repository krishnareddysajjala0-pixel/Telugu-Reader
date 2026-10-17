import os
import hashlib
import re
from gtts import gTTS
from typing import Optional

if os.environ.get("VERCEL"):
    AUDIO_DIR = "/tmp/audio"
else:
    AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audio")

def clean_text_for_speech(text: str) -> str:
    """Removes markdown symbols, URLs, asterisks, brackets, and rogue font artifacts for natural TTS reading."""
    if not text:
        return ""
    # Remove markdown links [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove bold/italic markers
    text = re.sub(r'[*_~`#>]', ' ', text)
    # Remove bullet markers at line start
    text = re.sub(r'^\s*[-+*]\s+', '', text, flags=re.MULTILINE)
    # Remove numbered lists at line start
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove rogue Latin extended characters often found in legacy Telugu PDF font encodings
    # but keep Telugu Unicode (\u0C00-\u0C7F), English alphanumerics, and standard punctuation
    text = re.sub(r'[^\u0C00-\u0C7Fa-zA-Z0-9\s.,!?:;₹\-—()/\n]', ' ', text)
    # Replace multiple spaces/newlines with single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def generate_telugu_audio(text: str, lang: str = "te") -> Optional[str]:
    """
    Synthesizes Telugu audio for given text using gTTS and returns relative URL path.
    Cached by MD5 hash of text to avoid re-generating.
    """
    cleaned = clean_text_for_speech(text)
    if not cleaned:
        return None
    
    # Limit max text length for single audio generation to ~2000 chars for good audio quality
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000] + "..."
        
    os.makedirs(AUDIO_DIR, exist_ok=True)
    hash_name = hashlib.md5((cleaned + "_" + lang).encode("utf-8")).hexdigest()
    filename = f"{hash_name}.mp3"
    filepath = os.path.join(AUDIO_DIR, filename)
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return f"/audio/{filename}"
    
    try:
        tts = gTTS(text=cleaned, lang=lang, slow=False)
        tts.save(filepath)
        return f"/audio/{filename}"
    except Exception as e:
        print(f"Error in TTS generation: {e}")
        return None
