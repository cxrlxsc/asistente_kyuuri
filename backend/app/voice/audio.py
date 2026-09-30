import io

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000  # Whisper trabaja a 16 kHz mono


def to_whisper_format(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Convierte cualquier audio a mono float32 a 16 kHz."""
    audio = audio.astype(np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sample_rate != SAMPLE_RATE:
        duration = len(audio) / sample_rate
        target = np.linspace(0, duration, int(duration * SAMPLE_RATE), endpoint=False)
        audio = np.interp(target, np.arange(len(audio)) / sample_rate, audio).astype(np.float32)
    return audio


def decode_file(data: bytes) -> np.ndarray:
    audio, sample_rate = sf.read(io.BytesIO(data), dtype="float32")
    return to_whisper_format(audio, sample_rate)


def encode_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV")
    return buffer.getvalue()
