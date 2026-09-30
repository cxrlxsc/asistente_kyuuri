import queue
from collections import deque
from contextlib import contextmanager
from typing import Callable, Iterator, Optional

import numpy as np
import sounddevice as sd

from .audio import SAMPLE_RATE

BLOCK_SECONDS = 0.03
PRE_ROLL_SECONDS = 0.3      # audio que se guarda antes de detectar voz para no cortar la primera sílaba
END_SILENCE_SECONDS = 0.8   # silencio que marca el fin de la frase
MAX_SECONDS = 15
MIN_THRESHOLD = 0.008
NO_AUDIO_TIMEOUT = 3        # segundos sin recibir bloques = micrófono ocupado o desconectado


def input_devices() -> list[tuple[int, str]]:
    """Micrófonos de la API de audio por defecto (la única que acepta grabar a 16 kHz directamente)."""
    return [(i, d["name"]) for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0 and d["hostapi"] == sd.default.hostapi]


def find_device(name: str) -> Optional[int]:
    if not name:
        return None
    for index, device_name in input_devices():
        if name.lower() in device_name.lower():
            return index
    print(f"[Micrófono] No encontré '{name}', uso el micrófono predeterminado de Windows.")
    return None


class Microphone:
    """Graba frases completas usando detección de voz por energía."""

    def __init__(self, device_name: str = ""):
        self.device = find_device(device_name)
        self.name = sd.query_devices(self.device, kind="input")["name"]
        self.block_size = int(SAMPLE_RATE * BLOCK_SECONDS)
        self.threshold = MIN_THRESHOLD

    @contextmanager
    def _stream(self) -> Iterator[Callable[[], np.ndarray]]:
        """Abre el micrófono y entrega una función que devuelve el siguiente bloque de audio."""
        blocks: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata, frames, time, status):
            blocks.put(indata[:, 0].copy())

        def next_block() -> np.ndarray:
            try:
                return blocks.get(timeout=NO_AUDIO_TIMEOUT)
            except queue.Empty:
                raise RuntimeError(
                    f"El micrófono '{self.name}' no está enviando audio. Puede estar ocupado por otra aplicación; "
                    "elige otro con MIC_DEVICE en .env (lista: python -m app.voice --microfonos)."
                ) from None

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=self.device,
                            blocksize=self.block_size, callback=callback):
            yield next_block

    def calibrate(self, seconds: float = 1.0):
        with self._stream() as next_block:
            noise = np.concatenate([next_block() for _ in range(int(seconds / BLOCK_SECONDS))])
        noise_rms = float(np.sqrt(np.mean(noise ** 2)))
        self.threshold = max(MIN_THRESHOLD, noise_rms * 3)

    def listen(self) -> np.ndarray:
        pre_roll = deque(maxlen=int(PRE_ROLL_SECONDS / BLOCK_SECONDS))
        recorded: list[np.ndarray] = []
        silent_blocks = 0
        end_blocks = int(END_SILENCE_SECONDS / BLOCK_SECONDS)
        max_blocks = int(MAX_SECONDS / BLOCK_SECONDS)

        with self._stream() as next_block:
            while True:
                block = next_block()
                loud = float(np.sqrt(np.mean(block ** 2))) > self.threshold
                if not recorded:
                    pre_roll.append(block)
                    if loud:
                        recorded.extend(pre_roll)
                    continue
                recorded.append(block)
                silent_blocks = 0 if loud else silent_blocks + 1
                if silent_blocks >= end_blocks or len(recorded) >= max_blocks:
                    break
        return np.concatenate(recorded)
