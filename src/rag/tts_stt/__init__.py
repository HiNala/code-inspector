"""Text-to-Speech and Speech-to-Text functionality."""

from .text_to_speech import read_text_aloud, get_available_voices
from .speech_to_text import transcribe_speech_to_text

__all__ = ['read_text_aloud', 'get_available_voices', 'transcribe_speech_to_text'] 
