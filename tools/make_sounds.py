"""Generate the TheCore startup sounds.

Run once to (re)create the WAV files in ``assets/``:

    python tools/make_sounds.py

The sounds are synthesised, so they are small and there is nothing to license.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def _write(name: str, samples: list[float]) -> Path:
    path = ASSETS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for value in samples:
        clamped = max(-1.0, min(1.0, value))
        frames += struct.pack("<h", int(clamped * 32767))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(bytes(frames))
    print(f"wrote {path} ({path.stat().st_size} bytes)")
    return path


def _envelope(index: int, total: int, attack: float = 0.08, release: float = 0.4) -> float:
    """A soft attack / long release envelope."""
    position = index / max(1, total)
    if position < attack:
        return position / attack
    if position > 1.0 - release:
        return max(0.0, (1.0 - position) / release)
    return 1.0


def _soft_clip(value: float) -> float:
    """Gentle saturation, so the tone never sounds harsh."""
    return math.tanh(value * 1.6) / math.tanh(1.6)


def loading_sound() -> list[float]:
    """A slow, warm rising swell — the system coming to life."""
    duration = 1.6
    total = int(SAMPLE_RATE * duration)
    samples: list[float] = []
    for index in range(total):
        t = index / SAMPLE_RATE
        position = index / total

        # The pitch rises from A2 to A3 and settles.
        start_hz = 110.0
        end_hz = 220.0
        freq = start_hz + (end_hz - start_hz) * min(1.0, position * 1.35)
        phase = 2.0 * math.pi * freq * t

        # A soft fifth above, and a shimmer that fades in.
        body = math.sin(phase)
        fifth = 0.32 * math.sin(phase * 1.5)
        shimmer = 0.16 * math.sin(phase * 2.0) * position

        # A slow tremolo that stops towards the end.
        tremolo = 0.82 + 0.18 * math.sin(2.0 * math.pi * 3.2 * t) * (1.0 - position)

        value = (body + fifth + shimmer) * tremolo
        value *= _envelope(index, total, attack=0.12, release=0.45)
        samples.append(_soft_clip(value * 0.55))
    return samples


def ready_sound() -> list[float]:
    """Two short notes — the system is up."""
    notes = [(880.0, 0.10), (1318.5, 0.30)]
    samples: list[float] = []
    for freq, length in notes:
        count = int(SAMPLE_RATE * length)
        for index in range(count):
            t = index / SAMPLE_RATE
            value = math.sin(2.0 * math.pi * freq * t)
            value += 0.25 * math.sin(2.0 * math.pi * freq * 2.0 * t)
            value *= _envelope(index, count, attack=0.01, release=0.7)
            samples.append(_soft_clip(value * 0.5))
        # A short gap between the notes.
        samples.extend([0.0] * int(SAMPLE_RATE * 0.04))
    return samples


def main() -> None:
    _write("loading.wav", loading_sound())
    _write("ready.wav", ready_sound())


if __name__ == "__main__":
    main()
