import re
import unicodedata
from collections import deque
from threading import Lock, Thread
from typing import Optional

import httpx

from ..core.config import settings

def build_system_prompt() -> str:
    from .capabilities import llm_context
    return SYSTEM_PROMPT + "\n\n" + llm_context()


SYSTEM_PROMPT = f"""Eres {settings.ASSISTANT_NAME}, un asistente de voz personal que corre localmente en la computadora del usuario.

Cómo respondes:
- Siempre en español, cálido y directo, en una a tres frases cortas.
- Tus respuestas se leen en voz alta: nada de markdown, listas, emojis ni código.
- Si la pregunta parte de algo falso, corrígelo con amabilidad.

Límites que nunca rompes:
- En esta conversación NO puedes ejecutar acciones: no abres apps, no pones música, no buscas en internet, no cambias el volumen. Solo si el usuario te pide hacer algo así, di que no reconociste el comando y sugiere decirlo más directo, por ejemplo "abre Spotify". A las preguntas y comentarios normales respóndeles con normalidad.
- Solo recuerdas lo dicho en esta conversación. No inventes cosas que hayas hecho antes por el usuario.
- No tienes internet ni datos en tiempo real (clima, noticias, precios). Menciónalo solo si te piden ese tipo de datos.
- Si no estás seguro de un dato, dilo en vez de inventarlo."""
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def clean_for_speech(text: str) -> str:
    """Quita emojis y símbolos que la voz no puede leer y que el modelo a veces agrega pese al prompt."""
    text = "".join(c for c in text if unicodedata.category(c) not in ("So", "Cs")
                   and c != "️" and not "\U0001F3FB" <= c <= "\U0001F3FF")  # tonos de piel
    return re.sub(r"[ \t]+", " ", text).strip()


class LocalLLM:
    """Conversación libre con un LLM abierto servido por Ollama (sin salir de tu equipo)."""

    def __init__(self, max_turns: int = 6):
        self.history: deque[dict] = deque(maxlen=max_turns * 2)
        self.lock = Lock()
        # Cargar el modelo desde ya para que la primera pregunta no espere el arranque en frío
        if settings.chat_enabled:
            Thread(target=self._warm_up, daemon=True).start()

    def _warm_up(self):
        try:
            httpx.post(f"{settings.OLLAMA_URL}/api/generate",
                       json={"model": settings.OLLAMA_MODEL, "keep_alive": "30m",
                             "options": {"num_ctx": settings.LLM_CONTEXT}}, timeout=300)
        except httpx.HTTPError as e:
            print(f"[LLM] Ollama no disponible, la conversación libre estará desactivada: {e}")

    def chat(self, text: str) -> Optional[str]:
        if not settings.chat_enabled:
            return None
        with self.lock:
            messages = [{"role": "system", "content": build_system_prompt()}, *self.history, {"role": "user", "content": text}]
            try:
                response = httpx.post(
                    f"{settings.OLLAMA_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": messages,
                        "stream": False,
                        "think": False,
                        "keep_alive": "30m",
                        # Sin fijar el contexto, Ollama usa el máximo del modelo (32k), infla la memoria
                        # y termina corriendo en el procesador. Una charla de voz no necesita tanto.
                        "options": {"temperature": 0.7, "num_ctx": settings.LLM_CONTEXT},
                    },
                    timeout=120,
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[LLM] Ollama no disponible: {e}")
                return None

            reply = clean_for_speech(THINK_BLOCK.sub("", response.json()["message"]["content"]))
            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": reply})
            return reply
