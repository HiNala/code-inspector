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
import shutil

# Load environment variables
load_dotenv()

# Constants
MAX_CACHE_SIZE_MB = 500  # Maximum TTS cache size in MB
CACHE_DIR = Path("cache/tts")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class TTSManager:
    def __init__(self, provider: str = "elevenlabs", voice_id: Optional[str] = None):
        self.provider = provider
        self.voice_id = voice_id
        self.cache = {}
        self.load_cache()
        
        if provider == "elevenlabs":
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                raise ValueError("ElevenLabs API key not found in environment variables")
            set_api_key(api_key)
        elif provider == "local":
            self.engine = pyttsx3.init()
            
    def load_cache(self):
        """Load the TTS cache and manage its size."""
        cache_file = CACHE_DIR / "cache_index.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    self.cache = pickle.load(f)
            except Exception as e:
                print(f"{Fore.YELLOW}Warning: Could not load TTS cache: {str(e)}{Style.RESET_ALL}")
                self.cache = {}
                
        # Check cache size and clean if necessary
        self._manage_cache_size()
        
    def save_cache(self):
        """Save the cache index."""
        try:
            cache_file = CACHE_DIR / "cache_index.pkl"
            with open(cache_file, "wb") as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not save TTS cache: {str(e)}{Style.RESET_ALL}")
            
    def _manage_cache_size(self):
        """Ensure cache doesn't exceed MAX_CACHE_SIZE_MB."""
        total_size = 0
        cache_files = []
        
        # Get all audio files with their sizes and timestamps
        for file in CACHE_DIR.glob("*.mp3"):
            if file.name == "cache_index.pkl":
                continue
            stats = file.stat()
            total_size += stats.st_size
            cache_files.append((file, stats.st_mtime))
            
        # Convert to MB
        total_size_mb = total_size / (1024 * 1024)
        
        # If cache exceeds limit, remove oldest files
        if total_size_mb > MAX_CACHE_SIZE_MB:
            print(f"{Fore.YELLOW}Cache size ({total_size_mb:.1f}MB) exceeds limit ({MAX_CACHE_SIZE_MB}MB). Cleaning...{Style.RESET_ALL}")
            cache_files.sort(key=lambda x: x[1])  # Sort by modification time
            
            for file, _ in cache_files:
                if total_size_mb <= MAX_CACHE_SIZE_MB:
                    break
                    
                file_size = file.stat().st_size / (1024 * 1024)
                file.unlink()
                total_size_mb -= file_size
                
                # Remove from cache index
                cache_key = file.stem
                if cache_key in self.cache:
                    del self.cache[cache_key]
                    
            print(f"{Fore.GREEN}Cache cleaned. New size: {total_size_mb:.1f}MB{Style.RESET_ALL}")
            self.save_cache()
            
    def generate_speech(self, text: str, voice_id: Optional[str] = None) -> Optional[str]:
        """Generate speech from text with caching and error handling."""
        try:
            # Generate cache key
            text_hash = hashlib.md5(text.encode()).hexdigest()
            voice = voice_id or self.voice_id or "default"
            cache_key = f"{text_hash}_{voice}_{self.provider}"
            
            # Check cache
            if cache_key in self.cache:
                cache_path = CACHE_DIR / f"{cache_key}.mp3"
                if cache_path.exists():
                    return str(cache_path)
                    
            # Generate new audio
            with Halo(text="Generating speech...", spinner="dots") as spinner:
                if self.provider == "elevenlabs":
                    try:
                        audio = generate(
                            text=text,
                            voice=voice_id or self.voice_id,
                            model="eleven_monolingual_v1"
                        )
                    except Exception as e:
                        spinner.fail(f"ElevenLabs API error: {str(e)}")
                        # Fallback to local TTS
                        print(f"{Fore.YELLOW}Falling back to local TTS...{Style.RESET_ALL}")
                        self.provider = "local"
                        self.engine = pyttsx3.init()
                        return self.generate_speech(text)
                        
                elif self.provider == "local":
                    self.engine.save_to_file(text, str(CACHE_DIR / f"{cache_key}.mp3"))
                    self.engine.runAndWait()
                    
                spinner.succeed("Speech generated successfully")
                
            # Save to cache
            output_path = CACHE_DIR / f"{cache_key}.mp3"
            if self.provider == "elevenlabs":
                with open(output_path, "wb") as f:
                    f.write(audio)
                    
            self.cache[cache_key] = str(output_path)
            self.save_cache()
            self._manage_cache_size()
            
            return str(output_path)
            
        except Exception as e:
            print(f"{Fore.RED}Error generating speech: {str(e)}{Style.RESET_ALL}")
            return None
            
    def cleanup(self):
        """Clean up resources."""
        if self.provider == "local" and hasattr(self, 'engine'):
            self.engine.stop()
            
def get_available_voices() -> Dict[str, str]:
    """Get available voices with error handling."""
    try:
        voice_list = voices()
        return {voice.name: voice.voice_id for voice in voice_list}
    except Exception as e:
        print(f"{Fore.YELLOW}Could not fetch ElevenLabs voices: {str(e)}{Style.RESET_ALL}")
        print("Using local TTS voices instead...")
        engine = pyttsx3.init()
        return {voice.name: voice.id for voice in engine.getProperty('voices')}
        
def read_text_aloud(text: str, voice_id: Optional[str] = None) -> bool:
    """Read text aloud with error handling and fallback."""
    try:
        tts = TTSManager(provider="elevenlabs", voice_id=voice_id)
        audio_path = tts.generate_speech(text)
        
        if audio_path:
            if os.path.exists(audio_path):
                play(audio_path)
                return True
                
        return False
        
    except Exception as e:
        print(f"{Fore.RED}Error reading text: {str(e)}{Style.RESET_ALL}")
        return False
    finally:
        if 'tts' in locals():
            tts.cleanup() 