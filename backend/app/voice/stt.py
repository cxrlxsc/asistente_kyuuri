import zlib

import numpy as np
import torch
from transformers import pipeline

from ..core import quiet  # noqa: F401  (silencia los avisos de transformers al importarse)
from ..core.config import settings
from ..nlu.text import normalize
from ..services.app_catalog import APPS
from ..services.site_catalog import SITES
from .audio import SAMPLE_RATE

MAX_TOKENS = 96               # un comando de voz de hasta 15 s cabe de sobra
MAX_COMPRESSION_RATIO = 2.4   # mismo criterio que usa Whisper para descartar bucles

# Frases que Whisper "alucina" cuando recibe ruido o silencio
HALLUCINATIONS = {
    "subtitulos realizados por la comunidad de amara org", "gracias por ver el video", "gracias por ver",
    "suscribete", "subtitulos por la comunidad de amara org", "musica", "gracias",
}


class SpeechToText:
    """Whisper corriendo localmente (GPU si hay)."""

    def __init__(self):
        cuda = torch.cuda.is_available()
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=settings.WHISPER_MODEL,
            dtype=torch.float16 if cuda else torch.float32,
            device="cuda" if cuda else "cpu",
        )
        # Vocabulario: el nombre del asistente y los nombres propios de tus apps y sitios,
        # que suelen ser en inglés y sin esta pista Whisper los escribe mal ("vreip" por "Brave")
        self.prompt_ids = self.pipe.tokenizer.get_prompt_ids(vocabulary_hint(), return_tensors="pt").to(self.pipe.device)

    def transcribe(self, audio: np.ndarray) -> str:
        if len(audio) < SAMPLE_RATE * 0.3:
            return ""
        result = self.pipe(
            {"raw": audio, "sampling_rate": SAMPLE_RATE},
            generate_kwargs={"language": "spanish", "task": "transcribe", "prompt_ids": self.prompt_ids,
                             "max_new_tokens": MAX_TOKENS},
        )
        text = result["text"].strip()
        if normalize(text) in HALLUCINATIONS or is_repetitive(text):
            return ""
        return text


def vocabulary_hint() -> str:
    names = [entry.display_name for entry in APPS.values()] + [site.display_name for site in SITES.values()]
    return f"{settings.ASSISTANT_NAME}, abre " + ", ".join(dict.fromkeys(names)) + "."


def is_repetitive(text: str) -> bool:
    """Un texto que se comprime demasiado es un bucle ("¡Hasta la próxima! ¡Hasta la próxima! ..."), no habla real."""
    data = text.encode("utf-8")
    return len(data) > 40 and len(data) / len(zlib.compress(data)) > MAX_COMPRESSION_RATIO
