import json
from datetime import datetime
from threading import Lock
from typing import Optional

from .core.config import settings


class InteractionLog:
    """Guarda lo que le dices y qué entendió, para después reentrenar con tu forma real de hablar.

    El archivo se queda en tu equipo (backend/data/interactions.jsonl) y se revisa
    con: python -m training.review
    """

    def __init__(self):
        self.path = settings.DATA_DIR / "interactions.jsonl"
        self.lock = Lock()

    def record(self, text: str, intent: str, confidence: float, source: str, reply: Optional[str] = None):
        if not settings.LOG_INTERACTIONS:
            return
        entry = {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "texto": text,
            "intencion": intent,
            "confianza": confidence,
            "origen": source,
            "respuesta": reply,
        }
        try:
            with self.lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            print(f"[Registro] No pude guardar la interacción: {e}")


def load_interactions() -> list[dict]:
    path = settings.DATA_DIR / "interactions.jsonl"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries
