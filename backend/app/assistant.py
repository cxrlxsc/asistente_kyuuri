import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .core.config import settings
from .learning import InteractionLog
from .nlu.intent_model import IntentModel
from .nlu.slots import (extract_app, extract_app_name, extract_duration, extract_folder, extract_mode,
                        extract_query, extract_reminder, extract_site, extract_site_query, fix_transcription,
                        is_question, mentions_device, strip_fillers)
from .nlu.text import normalize
from .services.capabilities import (apps_summary, folders_summary, modes_summary, sites_summary,
                                    spoken_summary)
from .services.installed_apps import GOOD_MATCH, MAYBE_MATCH, find
from .services.local_llm import LocalLLM
from .services.modes import ModeRunner, load_modes
from .services.system_executor import SystemExecutor
from .services.timers import TimerService

# Intenciones que no cambian nada en el equipo; el resto exige más confianza y no puede venir de una pregunta
HARMLESS_INTENTS = {"chat", "greet", "tell_time", "timer_status", "confirm_yes", "confirm_no", "capabilities"}
CONFIRMATION_SECONDS = 30

GREETINGS = ["¡Hola! ¿En qué te ayudo?", "Aquí estoy, dime.", "¡Hola! ¿Qué hacemos hoy?"]
GOODBYES = ["Hasta luego.", "Nos vemos, aquí estaré.", "Descansa, hasta pronto."]
HELP_TEXT = ("No pude pensar una respuesta ahora mismo. Puedo abrir o cerrar aplicaciones y carpetas, buscar en internet, "
             "decirte la hora, poner temporizadores, controlar el volumen y la música, y bloquear o apagar el equipo.")


@dataclass
class Reply:
    intent: str
    confidence: float
    text: str
    parameters: dict[str, Any] = field(default_factory=dict)


class Assistant:
    """Punto único que convierte una frase en una acción y una respuesta (lo usan la API y la voz)."""

    def __init__(self):
        self.intents = IntentModel()
        self.executor = SystemExecutor()
        self.llm = LocalLLM()
        self.timers = TimerService()
        self.modes = ModeRunner(self.executor)
        self.log = InteractionLog()
        self.pending: Optional[tuple[str, Callable[[], str], float]] = None  # acción peligrosa esperando un "sí"
        self.simple_actions = {
            "tell_time": self.executor.tell_time,
            "volume_up": self.executor.volume_up,
            "volume_down": self.executor.volume_down,
            "volume_mute": self.executor.volume_mute,
            "media_play_pause": self.executor.media_play_pause,
            "media_next": self.executor.media_next,
            "media_previous": self.executor.media_previous,
            "lock_pc": self.executor.lock_pc,
            "show_desktop": self.executor.show_desktop,
            "cancel_shutdown": self.executor.cancel_shutdown,
            "cancel_timer": self.timers.cancel_all,
            "timer_status": self.timers.status,
        }
        self.needs_confirmation = {
            "shutdown_pc": ("apagar el equipo", self.executor.shutdown_pc),
            "restart_pc": ("reiniciar el equipo", self.executor.restart_pc),
        }

    def decide(self, text: str) -> tuple[str, float]:
        """Qué haría el asistente con la frase, sin ejecutar nada."""
        intent, confidence = self.intents.predict(text)
        if confidence < settings.CONFIDENCE_THRESHOLD:
            intent = "chat"
        elif intent not in HARMLESS_INTENTS and (confidence < settings.ACTION_CONFIDENCE_THRESHOLD or is_question(text)):
            # Equivocarse conversando no hace daño; ejecutar una acción que no pidió sí
            intent = "chat"
        elif intent in ("lock_pc", "shutdown_pc", "restart_pc") and not mentions_device(text):
            intent = "chat"
        return intent, round(confidence, 3)

    def handle(self, text: str, source: str = "texto") -> Reply:
        reply = self._respond(fix_transcription(text.strip()))
        self.log.record(text, reply.intent, reply.confidence, source, reply.text)
        return reply

    def _respond(self, text: str) -> Reply:
        text = strip_fillers(text)
        if not text:
            return Reply("chat", 1.0, "No escuché nada.")

        intent, confidence = self.decide(text)

        if answer := self._resolve_confirmation(intent):
            return Reply(intent, confidence, answer)

        if intent in self.needs_confirmation:
            description, action = self.needs_confirmation[intent]
            self.pending = (description, action, time.time() + CONFIRMATION_SECONDS)
            return Reply(intent, confidence, f"¿Seguro que quieres {description}? Dime sí para confirmar.")

        if intent == "set_timer":
            seconds = extract_duration(text)
            if not seconds:
                return Reply(intent, confidence, "¿De cuánto tiempo? Por ejemplo, un temporizador de cinco minutos.")
            label = extract_reminder(text)
            return Reply(intent, confidence, self.timers.start(seconds, label), {"seconds": seconds, "label": label})

        if intent == "open_folder":
            folder_key = extract_folder(text)
            if not folder_key:
                return Reply(intent, confidence, "¿Qué carpeta? Puedo abrir descargas, documentos, escritorio, imágenes, música o vídeos.")
            return Reply(intent, confidence, self.executor.open_folder(folder_key), {"folder": folder_key})

        if intent == "open_app":
            return self._open_app(text, confidence)

        if intent == "close_app":
            return self._close_app(text, confidence)

        if intent == "capabilities":
            return Reply(intent, confidence, self._describe(text))

        if intent == "search_site":
            site = extract_site(text)
            if site:
                query = extract_site_query(text, site)
                return Reply(intent, confidence, self.executor.search_site(site, query), {"site": site, "query": query})
            intent = "search_web"  # pidió buscar pero no reconocí el sitio: va a Google

        if intent == "search_web":
            query = extract_query(text)
            return Reply(intent, confidence, self.executor.search_web(query), {"query": query})

        if intent in ("activate_mode", "deactivate_mode"):
            mode = extract_mode(text)
            if not mode:
                available = ", ".join(load_modes()) or "ninguno todavía"
                return Reply(intent, confidence, f"¿Qué modo? Tengo configurados: {available}.")
            action = self.modes.activate if intent == "activate_mode" else self.modes.deactivate
            return Reply(intent, confidence, action(mode), {"mode": mode})

        if intent == "play_music":
            return Reply(intent, confidence, self.executor.play_music())

        if intent in self.simple_actions:
            return Reply(intent, confidence, self.simple_actions[intent]())

        if intent == "greet":
            return Reply(intent, confidence, random.choice(GREETINGS))

        if intent == "goodbye":
            return Reply(intent, confidence, random.choice(GOODBYES))

        return Reply("chat", confidence, self.llm.chat(text) or HELP_TEXT)

    def _open_app(self, text: str, confidence: float) -> Reply:
        if app_key := extract_app(text):
            return Reply("open_app", confidence, self.executor.open_application(app_key), {"app_key": app_key})

        # No está en el catálogo: se busca entre los programas instalados en el equipo
        name = extract_app_name(text)
        app, score = find(name)
        if app and score >= GOOD_MATCH:
            return Reply("open_app", confidence, self.executor.open_installed(app), {"installed": app.name})
        if app and score >= MAYBE_MATCH:
            self.pending = (f"abrir {app.name}", lambda: self.executor.open_installed(app), time.time() + CONFIRMATION_SECONDS)
            return Reply("open_app", confidence, f"No tengo {name} en mi lista. ¿Abro {app.name}?", {"suggested": app.name})
        return Reply("open_app", confidence, f"No encontré ningún programa parecido a {name} instalado en el equipo.")

    def _close_app(self, text: str, confidence: float) -> Reply:
        app_key = extract_app(text)
        result = (self.executor.close_application(app_key) if app_key
                  else self.executor.close_running(extract_app_name(text)))
        if result.stubborn_pids:
            pids, display = result.stubborn_pids, result.display_name
            self.pending = (f"cerrar {display} a la fuerza",
                            lambda: self.executor.force_close(pids, display), time.time() + CONFIRMATION_SECONDS)
        return Reply("close_app", confidence, result.message, {"app_key": app_key} if app_key else {})

    def _describe(self, text: str) -> str:
        clean = normalize(text)
        if "modo" in clean:
            return modes_summary()
        if "carpeta" in clean:
            return folders_summary()
        if any(word in clean for word in ("programa", "aplicacion", " app", "abrir")):
            return apps_summary()
        if any(word in clean for word in ("buscar", "sitio", "pagina", "web")):
            return sites_summary()
        return spoken_summary()

    def _resolve_confirmation(self, intent: str) -> Optional[str]:
        """Responde al "sí" o "no" que sigue a una acción peligrosa."""
        if not self.pending:
            return None
        description, action, expires_at = self.pending
        if time.time() > expires_at:
            self.pending = None
            return None
        if intent == "confirm_yes":
            self.pending = None
            return action()
        if intent == "confirm_no":
            self.pending = None
            return f"Listo, no voy a {description}."
        self.pending = None  # cualquier otra cosa cancela la confirmación
        return None
