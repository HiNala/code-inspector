"""Hotkey management for voice interface."""

import keyboard
from typing import Optional, Callable
from colorama import Fore, Style
from .text_to_speech import read_text_aloud, select_voice
from .speech_to_text import get_user_input, transcribe_streaming

class HotkeyManager:
    def __init__(self):
        """Initialize hotkey manager."""
        self.last_response = None
        self.voice_id = None
        self.streaming = False
        self._setup_hotkeys()
        
    def _setup_hotkeys(self):
        """Set up hotkey bindings."""
        # Voice input (Ctrl+B)
        keyboard.add_hotkey('ctrl+b', self._handle_voice_input)
        
        # Read last response (Ctrl+N)
        keyboard.add_hotkey('ctrl+n', self._read_last_response)
        
        # Toggle streaming (Ctrl+S)
        keyboard.add_hotkey('ctrl+s', self._toggle_streaming)
        
        # Change voice (Ctrl+V)
        keyboard.add_hotkey('ctrl+v', self._change_voice)
        
        # Pause/Resume TTS (Ctrl+P)
        keyboard.add_hotkey('ctrl+p', self._toggle_tts)
        
        print(f"\n{Fore.CYAN}Hotkeys enabled:{Style.RESET_ALL}")
        print("  Ctrl+B: Voice input")
        print("  Ctrl+N: Read last response")
        print("  Ctrl+S: Toggle streaming")
        print("  Ctrl+V: Change voice")
        print("  Ctrl+P: Pause/Resume TTS")
        
    def _handle_voice_input(self):
        """Handle voice input hotkey."""
        text = get_user_input(use_voice=True)
        if text and not text.isspace():
            print(f"\n{Fore.GREEN}Voice input: {text}{Style.RESET_ALL}")
            if self.callback:
                self.callback(text)
                
    def _read_last_response(self):
        """Read the last response aloud."""
        if self.last_response:
            read_text_aloud(self.last_response, self.voice_id)
        else:
            print(f"{Fore.YELLOW}No response to read.{Style.RESET_ALL}")
            
    def _toggle_streaming(self):
        """Toggle streaming transcription."""
        if not self.streaming:
            self.streaming = True
            transcribe_streaming(callback=self.callback)
        else:
            self.streaming = False
            
    def _change_voice(self):
        """Change TTS voice."""
        self.voice_id = select_voice()
        
    def _toggle_tts(self):
        """Toggle TTS pause/resume."""
        # This is a placeholder - actual implementation would depend on
        # the TTS engine's capabilities
        print(f"{Fore.YELLOW}TTS pause/resume not implemented.{Style.RESET_ALL}")
        
    def set_callback(self, callback: Callable[[str], None]):
        """Set callback for handling voice input."""
        self.callback = callback
        
    def set_last_response(self, response: str):
        """Set the last response for reading aloud."""
        self.last_response = response
        
    def cleanup(self):
        """Clean up resources."""
        keyboard.unhook_all()
        
def setup_voice_interface(callback: Optional[Callable[[str], None]] = None) -> HotkeyManager:
    """Set up voice interface with hotkeys."""
    manager = HotkeyManager()
    if callback:
        manager.set_callback(callback)
    return manager 