import json
import time
from pathlib import Path
from typing import Optional

from ..core.config import settings

MODES_PATH = settings.BACKEND_DIR / "modes.json"


def load_modes() -> dict[str, dict]:
    """Los modos definidos en modes.json (las claves que empiezan con _ son comentarios)."""
    if not MODES_PATH.exists():
        return {}
    try:
        data = json.loads(MODES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[Modos] {MODES_PATH.name} tiene un error de formato: {e}")
        return {}
    return {name: mode for name, mode in data.items() if not name.startswith("_")}


def mode_aliases() -> list[tuple[str, str]]:
    pairs = [(alias, name) for name, mode in load_modes().items() for alias in mode.get("alias", [name])]
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)


def mode_names() -> list[str]:
    return sorted({alias for alias, _ in mode_aliases()})


class ModeRunner:
    """Ejecuta los pasos de un modo, uno por uno, usando las mismas acciones seguras del asistente."""

    def __init__(self, executor):
        self.executor = executor

    def activate(self, name: str) -> str:
        mode = load_modes().get(name)
        if mode is None:
            return f"No tengo configurado el modo {name}."
        done, failed = [], []
        for step in mode.get("pasos", []):
            result = self._run(step)
            (done if result else failed).append(step)
        message = f"Modo {name} activado."
        if failed:
            message += f" No pude con {len(failed)} paso{'s' if len(failed) > 1 else ''}."
        return message

    def deactivate(self, name: str) -> str:
        mode = load_modes().get(name)
        if mode is None:
            return f"No tengo configurado el modo {name}."
        closing = mode.get("cierra", [])
        for app_key in closing:
            self.executor.close_application(app_key)
        if not closing:
            return f"Salí del modo {name}."
        return f"Cerré lo del modo {name}."

    def _run(self, step: dict) -> bool:
        try:
            if app_key := step.get("app"):
                self.executor.open_application(app_key)
            elif folder_key := step.get("folder"):
                self.executor.open_folder(folder_key)
            elif url := step.get("url"):
                self.executor.open_url(url)
            elif site := step.get("site"):
                self.executor.search_site(site, step.get("query", ""))
            elif step.get("music"):
                self.executor.play_music()
            elif volume := step.get("volume"):
                {"up": self.executor.volume_up, "down": self.executor.volume_down,
                 "mute": self.executor.volume_mute}[volume]()
            elif seconds := step.get("wait"):
                time.sleep(min(float(seconds), 10))
            else:
                print(f"[Modos] Paso desconocido: {step}")
                return False
            return True
        except (KeyError, OSError, ValueError) as e:
            print(f"[Modos] Falló el paso {step}: {e}")
            return False
