"""Text-to-Speech functionality with caching and performance optimizations."""

import os
import json
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv
from elevenlabs import generate, play, set_api_key, voices
from colorama import Fore, Style
from halo import Halo
import threading
import time

# Load environment variables
load_dotenv()

# Constants
CACHE_DIR = Path("cache/tts")
MAX_CACHE_SIZE_MB = int(os.getenv("TTS_CACHE_SIZE", "100"))  # Maximum cache size in MB
MAX_RETRIES = 3
RETRY_DELAY = 2

class TTSManager:
    def __init__(self):
        """Initialize TTS manager with caching."""
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables")
            
        set_api_key(self.api_key)
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_lock = threading.Lock()
        self.cache_info = self._load_cache_info()
        
    def _load_cache_info(self) -> Dict:
        """Load cache information from disk."""
        cache_info_file = self.cache_dir / "cache_info.json"
        if cache_info_file.exists():
            try:
                with open(cache_info_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"{Fore.YELLOW}Warning: Could not load cache info: {str(e)}{Style.RESET_ALL}")
        return {"files": {}, "total_size": 0}
        
    def _save_cache_info(self):
        """Save cache information to disk."""
        try:
            with open(self.cache_dir / "cache_info.json", "w") as f:
                json.dump(self.cache_info, f)
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not save cache info: {str(e)}{Style.RESET_ALL}")
            
    def _get_cache_key(self, text: str, voice: str) -> str:
        """Generate cache key for text and voice combination."""
        return hashlib.md5(f"{text}:{voice}".encode()).hexdigest()
        
    def _manage_cache_size(self):
        """Ensure cache doesn't exceed maximum size."""
        with self.cache_lock:
            while self.cache_info["total_size"] > MAX_CACHE_SIZE_MB * 1024 * 1024:
                # Remove oldest files until under limit
                oldest_file = min(
                    self.cache_info["files"].items(),
                    key=lambda x: x[1]["timestamp"]
                )[0]
                
                try:
                    file_path = self.cache_dir / oldest_file
                    if file_path.exists():
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        self.cache_info["total_size"] -= file_size
                        del self.cache_info["files"][oldest_file]
                except Exception as e:
                    print(f"{Fore.YELLOW}Warning: Error removing cache file: {str(e)}{Style.RESET_ALL}")
                    
            self._save_cache_info()
            
    def generate_speech(self, text: str, voice: str = "Bella") -> bool:
        """Generate speech from text with caching and error handling."""
        try:
            cache_key = self._get_cache_key(text, voice)
            cache_file = self.cache_dir / f"{cache_key}.mp3"
            
            # Check cache first
            with self.cache_lock:
                if cache_file.exists():
                    print(f"{Fore.GREEN}Using cached audio{Style.RESET_ALL}")
                    play(cache_file.read_bytes())
                    return True
                    
            # Generate new audio
            with Halo(text="Generating speech...", spinner="dots") as spinner:
                for attempt in range(MAX_RETRIES):
                    try:
                        audio = generate(text=text, voice=voice)
                        
                        # Save to cache
                        with self.cache_lock:
                            cache_file.write_bytes(audio)
                            file_size = cache_file.stat().st_size
                            self.cache_info["files"][cache_file.name] = {
                                "timestamp": time.time(),
                                "size": file_size
                            }
                            self.cache_info["total_size"] += file_size
                            self._manage_cache_size()
                            
                        # Play audio
                        play(audio)
                        spinner.succeed("Speech generated successfully")
                        return True
                        
                    except Exception as e:
                        if attempt == MAX_RETRIES - 1:
                            spinner.fail(f"Failed to generate speech: {str(e)}")
                            return False
                        print(f"{Fore.YELLOW}Retry {attempt + 1}/{MAX_RETRIES}: {str(e)}{Style.RESET_ALL}")
                        time.sleep(RETRY_DELAY)
                        
        except Exception as e:
            print(f"{Fore.RED}Error generating speech: {str(e)}{Style.RESET_ALL}")
            return False
            
    def get_available_voices(self) -> list:
        """Get list of available voices with error handling."""
        try:
            return [voice.name for voice in voices()]
        except Exception as e:
            print(f"{Fore.RED}Error getting voices: {str(e)}{Style.RESET_ALL}")
            return ["Bella"]  # Return default voice as fallback
            
    def cleanup(self):
        """Clean up resources."""
        try:
            # Save final cache state
            self._save_cache_info()
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Error during cleanup: {str(e)}{Style.RESET_ALL}")
            
def read_text_aloud(text: str, voice: Optional[str] = None) -> bool:
    """Convenience function to read text aloud."""
    try:
        manager = TTSManager()
        return manager.generate_speech(text, voice or "Bella")
    finally:
        if 'manager' in locals():
            manager.cleanup()
            
def select_voice() -> Optional[str]:
    """Select a voice interactively."""
    try:
        manager = TTSManager()
        voices = manager.get_available_voices()
        
        print(f"\n{Fore.CYAN}Available voices:{Style.RESET_ALL}")
        for i, voice in enumerate(voices, 1):
            print(f"{i}. {voice}")
            
        while True:
            try:
                choice = input(f"\n{Fore.GREEN}Select a voice (1-{len(voices)}): {Style.RESET_ALL}")
                index = int(choice) - 1
                if 0 <= index < len(voices):
                    return voices[index]
                print(f"{Fore.RED}Invalid choice. Please try again.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED}Invalid input. Please enter a number.{Style.RESET_ALL}")
                
    except Exception as e:
        print(f"{Fore.RED}Error selecting voice: {str(e)}{Style.RESET_ALL}")
        return None
    finally:
        if 'manager' in locals():
            manager.cleanup() 