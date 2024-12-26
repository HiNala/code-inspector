"""Text-to-Speech and Speech-to-Text functionality for the Code Summary Query System."""

from .text_to_speech import read_text_aloud
from .speech_to_text import transcribe_speech_to_text

__all__ = ['read_text_aloud', 'transcribe_speech_to_text'] 