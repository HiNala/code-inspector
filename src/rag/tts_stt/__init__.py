"""Text-to-Speech and Speech-to-Text functionality."""

from .text_to_speech import (
    read_text_aloud,
    get_available_voices,
    select_voice,
    TTSManager
)
from .speech_to_text import (
    get_user_input,
    test_microphone,
    STTManager
)

__all__ = [
    'read_text_aloud',
    'get_available_voices',
    'select_voice',
    'TTSManager',
    'get_user_input',
    'test_microphone',
    'STTManager'
] 
