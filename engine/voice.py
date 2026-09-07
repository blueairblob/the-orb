"""The voice interface (PRD §7 steps 1 and 7 — STT in, TTS out).

A `Voice` implementation is the only thing that changes between this dev
host and a real phone. `engine/loop.py` is written entirely against this
protocol — Android's real on-device STT/TTS becomes a second implementation
during the Phase 2 phone port, with no changes to the loop itself.

This host has no audio hardware at all (confirmed: `/dev/snd` carries only
the software MIDI sequencer/timer, no ALSA playback or capture devices) —
a live mic/speaker loop is physically impossible here, mirroring the §0
spike's "prove logic here, prove hardware on the real device" split. See
`engine/voice_text.py` for the only backend built so far.
"""

from __future__ import annotations

from typing import Protocol


class Voice(Protocol):
    def listen(self) -> str:
        """Blocks until the player has said/typed something, returns the text."""
        ...

    def speak(self, text: str, speaker: str = "guard") -> None:
        """Speaks/prints `text` to the player. `speaker` is 'guard' or 'dm'
        (PRD §12: the DM narrates, the guard only ever speaks his own
        dialogue) — a backend is free to voice them differently."""
        ...
