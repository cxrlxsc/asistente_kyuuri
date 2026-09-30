import re

import numpy as np
import sounddevice as sd
from huggingface_hub import hf_hub_download
from piper import PiperVoice

from ..core.config import settings

MARKDOWN = re.compile(r"[*_#`>~]")


def _voice_path() -> str:
    """Descarga la voz de Piper la primera vez (p. ej. es_MX-claude-high -> es/es_MX/claude/high/...)."""
    lang, name, quality = settings.PIPER_VOICE.split("-")
    folder = f"{lang.split('_')[0]}/{lang}/{name}/{quality}"
    for extension in (".onnx.json", ".onnx"):
        path = hf_hub_download("rhasspy/piper-voices", f"{folder}/{settings.PIPER_VOICE}{extension}",
                               local_dir=settings.PIPER_DIR)
    return path


class TextToSpeech:
    """Voz neuronal offline con Piper."""

    def __init__(self):
        self.voice = PiperVoice.load(_voice_path())
        self.sample_rate = self.voice.config.sample_rate

    def synthesize(self, text: str) -> np.ndarray:
        text = MARKDOWN.sub("", text)
        chunks = [chunk.audio_float_array for chunk in self.voice.synthesize(text)]
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)

    def say(self, text: str):
        audio = self.synthesize(text)
        if len(audio):
            sd.play(audio, self.sample_rate)
            sd.wait()
