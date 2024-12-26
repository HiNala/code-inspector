"""Speech-to-Text functionality using SpeechRecognition."""

import os
import speech_recognition as sr
from colorama import Fore, Style
from halo import Halo
import keyboard
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
STT_TIMEOUT = int(os.getenv("STT_TIMEOUT", "10"))  # Default 10 seconds
AMBIENT_DURATION = float(os.getenv("AMBIENT_DURATION", "1.0"))  # Default 1 second
ENERGY_THRESHOLD = int(os.getenv("ENERGY_THRESHOLD", "4000"))  # Default 4000

def check_microphone() -> tuple[bool, str]:
    """
    Check if a working microphone is available.
    
    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        mic_list = sr.Microphone.list_microphone_names()
        if not mic_list:
            return False, "No microphones found"
        
        # Try to initialize microphone
        with sr.Microphone() as source:
            return True, f"Found microphone: {source.device_index}"
            
    except Exception as e:
        return False, f"Error checking microphone: {str(e)}"

def transcribe_speech_to_text(timeout: int = STT_TIMEOUT) -> str:
    """
    Transcribe audio input to text using SpeechRecognition.
    
    Args:
        timeout (int): Maximum time to listen for speech in seconds
        
    Returns:
        str: The transcribed text or empty string if failed
    """
    # Check microphone first
    mic_ok, mic_msg = check_microphone()
    if not mic_ok:
        print(f"{Fore.RED}Microphone error: {mic_msg}{Style.RESET_ALL}")
        return ""
    
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD  # Adjust sensitivity
    
    try:
        with sr.Microphone() as source:
            # Adjust for ambient noise
            print(f"\n{Fore.CYAN}Adjusting for ambient noise...{Style.RESET_ALL}")
            recognizer.adjust_for_ambient_noise(source, duration=AMBIENT_DURATION)
            
            with Halo(text='Listening... Press Enter when done or Esc to cancel', spinner='dots') as spinner:
                try:
                    # Start listening
                    spinner.text = 'Listening... (Speak now)'
                    audio = recognizer.listen(source, timeout=timeout)
                    
                    # Wait for user to press Enter or Esc
                    while True:
                        if keyboard.is_pressed('enter'):
                            break
                        if keyboard.is_pressed('esc'):
                            print(f"\n{Fore.YELLOW}Transcription cancelled.{Style.RESET_ALL}")
                            return ""
                        time.sleep(0.1)
                    
                    # Try multiple recognition services
                    spinner.text = 'Transcribing...'
                    
                    # Try Google Speech Recognition first
                    try:
                        text = recognizer.recognize_google(audio)
                        spinner.succeed(f"Transcribed: {text}")
                        return text
                    except sr.RequestError:
                        # If Google fails, try Sphinx (offline)
                        try:
                            text = recognizer.recognize_sphinx(audio)
                            spinner.succeed(f"Transcribed (offline): {text}")
                            return text
                        except Exception as e:
                            spinner.fail(f"All recognition services failed")
                            return ""
                    
                except sr.WaitTimeoutError:
                    spinner.fail("Listening timed out. No speech detected.")
                    return ""
                except sr.UnknownValueError:
                    spinner.fail("Could not understand the audio. Please try again.")
                    return ""
                    
    except Exception as e:
        error_msg = str(e).lower()
        if "no default input device available" in error_msg:
            print(f"{Fore.RED}Error: No microphone found. Please check your microphone settings.{Style.RESET_ALL}")
        elif "access denied" in error_msg:
            print(f"{Fore.RED}Error: Microphone access denied. Please check your permissions.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Error during transcription: {str(e)}{Style.RESET_ALL}")
        return "" 