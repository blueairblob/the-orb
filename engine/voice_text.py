"""Text-mode `Voice` backend: `input()`/`print()` standing in for STT/TTS.

The only voice backend that makes sense on this dev host (see
`engine/voice.py` for why). Type a line, read the reply.
"""

from __future__ import annotations


class TextVoice:
    def __init__(self, prompt: str = "> ") -> None:
        self._prompt = prompt

    def listen(self) -> str:
        return input(self._prompt)

    def speak(self, text: str) -> None:
        print(f"Guard: {text}")
