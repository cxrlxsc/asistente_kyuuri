import threading
import time
from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Optional

from ..core.config import settings


@dataclass
class Countdown:
    id: int
    seconds: int
    label: Optional[str]
    ends_at: float
    timer: threading.Timer = field(repr=False)


def spoken_duration(seconds: int) -> str:
    if seconds % 3600 == 0 and seconds >= 3600:
        hours = seconds // 3600
        return "una hora" if hours == 1 else f"{hours} horas"
    if seconds >= 60 and seconds % 60 == 0:
        minutes = seconds // 60
        return "un minuto" if minutes == 1 else f"{minutes} minutos"
    if seconds < 60:
        return "un segundo" if seconds == 1 else f"{seconds} segundos"
    return f"{seconds // 60} minutos y {seconds % 60} segundos"


class TimerService:
    """Temporizadores y recordatorios que avisan por voz cuando se cumplen."""

    def __init__(self):
        self.countdowns: list[Countdown] = []
        self.notify: Callable[[str], None] = lambda message: print(f"[{settings.ASSISTANT_NAME}] {message}")
        self.lock = threading.Lock()
        self.next_id = count(1)

    def start(self, seconds: int, label: Optional[str] = None) -> str:
        countdown_id = next(self.next_id)
        timer = threading.Timer(seconds, self._fire, args=(countdown_id,))
        timer.daemon = True
        with self.lock:
            self.countdowns.append(Countdown(countdown_id, seconds, label, time.time() + seconds, timer))
        timer.start()
        if label:
            return f"Listo, te recuerdo {label} en {spoken_duration(seconds)}."
        return f"Temporizador de {spoken_duration(seconds)} activado."

    def _fire(self, countdown_id: int):
        with self.lock:
            fired = next((c for c in self.countdowns if c.id == countdown_id), None)
            self.countdowns = [c for c in self.countdowns if c.id != countdown_id]
        label = fired.label if fired else None
        self.notify(f"Recordatorio: {label}." if label else "Se acabó el tiempo.")

    def cancel_all(self) -> str:
        with self.lock:
            pending = self.countdowns
            self.countdowns = []
        for countdown in pending:
            countdown.timer.cancel()
        if not pending:
            return "No tienes temporizadores activos."
        return f"Cancelé {len(pending)} temporizador{'es' if len(pending) > 1 else ''}."

    def status(self) -> str:
        with self.lock:
            pending = sorted(self.countdowns, key=lambda c: c.ends_at)
        if not pending:
            return "No tienes temporizadores activos."
        parts = []
        for countdown in pending:
            remaining = max(0, int(countdown.ends_at - time.time()))
            what = countdown.label or "el temporizador"
            parts.append(f"{what} en {spoken_duration(remaining)}")
        return "Te queda " + "; ".join(parts) + "."
