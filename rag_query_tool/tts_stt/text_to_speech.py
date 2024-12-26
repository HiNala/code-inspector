"""Text-to-Speech functionality using ElevenLabs with pyttsx3 fallback."""

import os
import time
import hashlib
import pickle
from pathlib import Path
from typing import Optional, Dict, Union
from elevenlabs import generate, play, set_api_key, voices
import pyttsx3
from colorama import Fore, Style
from halo import Halo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "elevenlabs").lower()
MAX_RETRIES = 3
CACHE_SIZE = int(os.getenv("TTS_CACHE_SIZE", "100"))  # Number of responses to cache
CACHE_DIR = Path("cache/tts")

# Create cache directory if it doesn't exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Initialize ElevenLabs if API key is available
if ELEVENLABS_API_KEY and TTS_PROVIDER == "elevenlabs":
    set_api_key(ELEVENLABS_API_KEY)

# Initialize pyttsx3 engine
try:
    fallback_engine = pyttsx3.init()
    fallback_engine.setProperty('rate', 150)
except Exception as e:
    print(f"{Fore.YELLOW}Warning: Could not initialize fallback TTS engine: {str(e)}{Style.RESET_ALL}")
    fallback_engine = None

class TTSCache:
    """Cache for TTS audio data."""
    
    def __init__(self, cache_dir: Path, max_size: int = 100):
        self.cache_dir = cache_dir
        self.max_size = max_size
        self.cache_index_file = cache_dir / "cache_index.pkl"
        self.cache_index = self._load_cache_index()
    
    def _load_cache_index(self) -> Dict[str, Dict]:
        """Load the cache index from disk."""
        if self.cache_index_file.exists():
            try:
                with open(self.cache_index_file, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_cache_index(self) -> None:
        """Save the cache index to disk."""
        with open(self.cache_index_file, 'wb') as f:
            pickle.dump(self.cache_index, f)
    
    def _get_cache_key(self, text: str, voice: str) -> str:
        """Generate a cache key from text and voice."""
        return hashlib.md5(f"{text}:{voice}".encode()).hexdigest()
    
    def get(self, text: str, voice: str) -> Optional[bytes]:
        """Retrieve audio data from cache."""
        cache_key = self._get_cache_key(text, voice)
        if cache_key in self.cache_index:
            cache_file = self.cache_dir / f"{cache_key}.bin"
            if cache_file.exists():
                try:
                    with open(cache_file, 'rb') as f:
                        return f.read()
                except Exception:
                    # Remove invalid cache entry
                    self._remove_cache_entry(cache_key)
        return None
    
    def put(self, text: str, voice: str, audio_data: bytes) -> None:
        """Store audio data in cache."""
        # Check cache size and remove oldest entries if needed
        while len(self.cache_index) >= self.max_size:
            oldest_key = min(self.cache_index.items(), key=lambda x: x[1]['timestamp'])[0]
            self._remove_cache_entry(oldest_key)
        
        cache_key = self._get_cache_key(text, voice)
        cache_file = self.cache_dir / f"{cache_key}.bin"
        
        try:
            with open(cache_file, 'wb') as f:
                f.write(audio_data)
            
            self.cache_index[cache_key] = {
                'timestamp': time.time(),
                'text': text,
                'voice': voice
            }
            self._save_cache_index()
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Failed to cache audio: {str(e)}{Style.RESET_ALL}")
    
    def _remove_cache_entry(self, cache_key: str) -> None:
        """Remove a cache entry and its data."""
        if cache_key in self.cache_index:
            cache_file = self.cache_dir / f"{cache_key}.bin"
            try:
                if cache_file.exists():
                    cache_file.unlink()
                del self.cache_index[cache_key]
                self._save_cache_index()
            except Exception:
                pass

# Initialize cache
tts_cache = TTSCache(CACHE_DIR, CACHE_SIZE)

def get_available_voices() -> list:
    """Get list of available voices based on the current TTS provider."""
    try:
        if TTS_PROVIDER == "elevenlabs" and ELEVENLABS_API_KEY:
            return [voice.name for voice in voices()]
        elif fallback_engine:
            return [voice.name for voice in fallback_engine.getProperty('voices')]
        return []
    except Exception as e:
        print(f"{Fore.YELLOW}Warning: Could not fetch available voices: {str(e)}{Style.RESET_ALL}")
        return []

def read_text_aloud(text: str, voice: str = "Bella", retry_count: int = 0) -> bool:
    """
    Convert text to speech and play audio using available TTS provider.
    
    Args:
        text (str): The text to convert to speech
        voice (str): The voice to use (default: "Bella" for ElevenLabs)
        retry_count (int): Number of retries attempted
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Check cache first
    cached_audio = tts_cache.get(text, voice)
    if cached_audio:
        print(f"{Fore.CYAN}Using cached audio...{Style.RESET_ALL}")
        play(cached_audio)
        return True
    
    # Use ElevenLabs if available and configured
    if TTS_PROVIDER == "elevenlabs" and ELEVENLABS_API_KEY:
        try:
            with Halo(text='Generating audio with ElevenLabs...', spinner='dots') as spinner:
                # Generate audio
                audio = generate(text=text, voice=voice)
                spinner.succeed("Audio generated successfully")
                
                # Cache the audio
                tts_cache.put(text, voice, audio)
                
                # Play audio
                print(f"\n{Fore.CYAN}Playing response...{Style.RESET_ALL}")
                play(audio)
                return True
                
        except Exception as e:
            error_msg = str(e).lower()
            if retry_count < MAX_RETRIES and ("network" in error_msg or "timeout" in error_msg):
                print(f"{Fore.YELLOW}Network error, retrying... ({retry_count + 1}/{MAX_RETRIES}){Style.RESET_ALL}")
                time.sleep(2)
                return read_text_aloud(text, voice, retry_count + 1)
            elif "api key" in error_msg:
                print(f"{Fore.RED}Error: Invalid or missing ElevenLabs API key{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Error using ElevenLabs: {str(e)}{Style.RESET_ALL}")
            
            # Try fallback if available
            if fallback_engine:
                print(f"{Fore.YELLOW}Falling back to local TTS engine...{Style.RESET_ALL}")
                return _use_fallback_tts(text)
            return False
    
    # Use fallback TTS if ElevenLabs is not available
    elif fallback_engine:
        return _use_fallback_tts(text)
    
    else:
        print(f"{Fore.RED}Error: No TTS provider available. Please configure ElevenLabs API key or ensure pyttsx3 is working.{Style.RESET_ALL}")
        return False

def _use_fallback_tts(text: str) -> bool:
    """Use pyttsx3 as fallback TTS engine."""
    try:
        with Halo(text='Generating audio with local TTS...', spinner='dots') as spinner:
            fallback_engine.say(text)
            spinner.succeed("Using local TTS engine")
            fallback_engine.runAndWait()
            return True
    except Exception as e:
        print(f"{Fore.RED}Error using fallback TTS: {str(e)}{Style.RESET_ALL}")
        return False 