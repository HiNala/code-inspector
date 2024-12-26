"""Speech-to-Text functionality using SpeechRecognition."""

import os
import time
import speech_recognition as sr
from typing import Optional, Dict, Callable
from colorama import Fore, Style
from halo import Halo
from dotenv import load_dotenv
import keyboard
import pocketsphinx
from rich.live import Live
from rich.text import Text
import threading
import queue

# Load environment variables
load_dotenv()

# Constants
DEFAULT_TIMEOUT = int(os.getenv("STT_TIMEOUT", "10"))
DEFAULT_AMBIENT_DURATION = float(os.getenv("AMBIENT_DURATION", "1.0"))
DEFAULT_ENERGY_THRESHOLD = int(os.getenv("ENERGY_THRESHOLD", "4000"))
MAX_RETRIES = 3
RETRY_DELAY = 2

class STTManager:
    def __init__(self):
        """Initialize the STT manager with error handling."""
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            self.offline_engine = None
            self._setup_offline_engine()
            self.streaming = False
            self.stream_queue = queue.Queue()
            
            # Configure recognizer
            with self.microphone as source:
                self.recognizer.energy_threshold = DEFAULT_ENERGY_THRESHOLD
                self.adjust_for_ambient_noise(duration=DEFAULT_AMBIENT_DURATION)
                
        except Exception as e:
            print(f"{Fore.RED}Error initializing STT: {str(e)}{Style.RESET_ALL}")
            print("Please check your microphone connection and permissions.")
            raise
            
    def _setup_offline_engine(self):
        """Set up offline speech recognition engine."""
        try:
            self.offline_engine = pocketsphinx.Pocketsphinx()
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Offline STT engine not available: {str(e)}{Style.RESET_ALL}")
            
    def adjust_for_ambient_noise(self, duration: float = DEFAULT_AMBIENT_DURATION) -> None:
        """Adjust microphone for ambient noise with visual feedback."""
        try:
            with Halo(text='Adjusting for ambient noise...', spinner='dots') as spinner:
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                spinner.succeed('Microphone adjusted successfully')
        except Exception as e:
            print(f"{Fore.RED}Error adjusting microphone: {str(e)}{Style.RESET_ALL}")
            raise
            
    def listen(self, timeout: int = DEFAULT_TIMEOUT, show_progress: bool = True) -> Optional[str]:
        """Listen for speech with progress indicator and error handling."""
        try:
            with self.microphone as source:
                if show_progress:
                    print(f"\n{Fore.CYAN}Listening... (Press 'Esc' to cancel){Style.RESET_ALL}")
                    
                # Start listening with timeout
                start_time = time.time()
                audio = None
                
                with Halo(text='Listening...', spinner='dots') as spinner:
                    while True:
                        try:
                            # Check for Esc key
                            if keyboard.is_pressed('esc'):
                                spinner.fail('Listening cancelled')
                                return None
                                
                            # Update progress
                            elapsed = time.time() - start_time
                            remaining = timeout - elapsed
                            if remaining <= 0:
                                spinner.fail('Listening timeout')
                                return None
                                
                            spinner.text = f'Listening... ({remaining:.1f}s remaining)'
                            
                            # Try to get audio with a short timeout
                            audio = self.recognizer.listen(source, timeout=1)
                            if audio:
                                spinner.succeed('Audio captured successfully')
                                break
                                
                        except sr.WaitTimeoutError:
                            continue
                            
                if not audio:
                    return None
                    
                # Try to recognize speech
                with Halo(text='Processing speech...', spinner='dots') as spinner:
                    for attempt in range(MAX_RETRIES):
                        try:
                            # Try Google Speech Recognition
                            text = self.recognizer.recognize_google(audio)
                            spinner.succeed('Speech processed successfully')
                            return text
                            
                        except sr.RequestError:
                            # Try offline recognition
                            if self.offline_engine:
                                try:
                                    text = self.offline_engine.decode(audio.get_raw_data())
                                    spinner.succeed('Speech processed offline')
                                    return text
                                except Exception:
                                    pass
                                    
                            if attempt < MAX_RETRIES - 1:
                                spinner.text = f'Retrying... ({attempt + 1}/{MAX_RETRIES})'
                                time.sleep(RETRY_DELAY)
                            else:
                                spinner.fail('Speech recognition failed')
                                print(f"{Fore.RED}Error: Could not connect to speech recognition service{Style.RESET_ALL}")
                                return None
                                
                        except sr.UnknownValueError:
                            spinner.fail('Speech not understood')
                            print(f"{Fore.YELLOW}Could not understand audio{Style.RESET_ALL}")
                            return None
                            
        except Exception as e:
            print(f"{Fore.RED}Error during speech recognition: {str(e)}{Style.RESET_ALL}")
            return None
            
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages with error handling."""
        try:
            # This is a placeholder - actual implementation would depend on the
            # speech recognition service being used
            return {
                "en-US": "English (United States)",
                "en-GB": "English (United Kingdom)",
                "es-ES": "Spanish (Spain)",
                "fr-FR": "French (France)",
                "de-DE": "German (Germany)"
            }
        except Exception as e:
            print(f"{Fore.RED}Error getting supported languages: {str(e)}{Style.RESET_ALL}")
            return {}
            
    def cleanup(self):
        """Clean up resources."""
        try:
            if self.offline_engine:
                self.offline_engine.cleanup()
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Error during cleanup: {str(e)}{Style.RESET_ALL}")
            
    def stream_audio(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """Stream audio and transcribe in real-time with rich display."""
        try:
            self.streaming = True
            print(f"\n{Fore.CYAN}Starting audio stream... Press 'Esc' to stop.{Style.RESET_ALL}")
            
            def audio_callback(recognizer, audio):
                """Callback for handling audio data."""
                try:
                    text = recognizer.recognize_google(audio)
                    self.stream_queue.put(("text", text))
                except sr.UnknownValueError:
                    self.stream_queue.put(("error", "Could not understand audio"))
                except sr.RequestError as e:
                    self.stream_queue.put(("error", f"Service error: {e}"))
                except Exception as e:
                    self.stream_queue.put(("error", f"Error: {e}"))

            # Start background listening
            stop_listening = self.recognizer.listen_in_background(
                self.microphone,
                audio_callback,
                phrase_time_limit=5
            )

            # Display streaming transcription
            with Live(refresh_per_second=4) as live:
                live_text = Text()
                while self.streaming:
                    try:
                        if keyboard.is_pressed('esc'):
                            self.streaming = False
                            break

                        try:
                            msg_type, content = self.stream_queue.get_nowait()
                            if msg_type == "text":
                                live_text.append(f"\n{content}")
                                if callback:
                                    callback(content)
                            elif msg_type == "error":
                                live_text.append(f"\n{Fore.YELLOW}{content}{Style.RESET_ALL}")
                        except queue.Empty:
                            pass

                        live.update(live_text)
                        time.sleep(0.1)

                    except Exception as e:
                        print(f"{Fore.RED}Error in streaming loop: {str(e)}{Style.RESET_ALL}")
                        break

            # Stop background listening
            stop_listening(wait_for_stop=False)
            print(f"\n{Fore.GREEN}Streaming stopped.{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.RED}Error in audio streaming: {str(e)}{Style.RESET_ALL}")
        finally:
            self.streaming = False

def test_microphone() -> bool:
    """Test microphone functionality."""
    try:
        manager = STTManager()
        print(f"\n{Fore.CYAN}Testing microphone...{Style.RESET_ALL}")
        print("Please say something...")
        
        text = manager.listen(timeout=5)
        if text:
            print(f"\n{Fore.GREEN}Microphone test successful!{Style.RESET_ALL}")
            print(f"Recognized text: {text}")
            return True
        else:
            print(f"\n{Fore.RED}Microphone test failed{Style.RESET_ALL}")
            return False
            
    except Exception as e:
        print(f"{Fore.RED}Error testing microphone: {str(e)}{Style.RESET_ALL}")
        return False
    finally:
        if 'manager' in locals():
            manager.cleanup() 

def get_user_input(use_voice: bool = True, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Get user input with voice recognition and manual fallback."""
    if use_voice:
        try:
            manager = STTManager()
            print(f"\n{Fore.CYAN}Listening for your query... (Press 'Esc' to type manually){Style.RESET_ALL}")
            
            text = manager.listen(timeout=timeout)
            if text:
                return text
                
            print(f"\n{Fore.YELLOW}Voice input failed. Falling back to manual input.{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}Error with voice input: {str(e)}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Falling back to manual input.{Style.RESET_ALL}")
            
        finally:
            if 'manager' in locals():
                manager.cleanup()
                
    # Manual input fallback
    return input(f"\n{Fore.CYAN}Enter your query: {Style.RESET_ALL}") 

def transcribe_streaming(callback: Optional[Callable[[str], None]] = None) -> None:
    """Stream and transcribe speech dynamically."""
    try:
        manager = STTManager()
        manager.stream_audio(callback)
    except Exception as e:
        print(f"{Fore.RED}Error in streaming transcription: {str(e)}{Style.RESET_ALL}")
    finally:
        if 'manager' in locals():
            manager.cleanup() 