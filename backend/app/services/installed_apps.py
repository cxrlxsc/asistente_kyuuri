import difflib
import os
import re
import winreg
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ..nlu.text import normalize

# Accesos directos que no son programas
IGNORE = re.compile(r"uninstall|desinstalar|readme|leeme|website|sitio web|documentation|documentaci|help|ayuda|"
                    r"release notes|changelog|licencia|license|manual", re.IGNORECASE)
GOOD_MATCH = 0.86      # se abre directo
MAYBE_MATCH = 0.62     # se pregunta antes de abrir


@dataclass(frozen=True)
class InstalledApp:
    name: str        # como aparece en el menú inicio
    launch: str      # acceso directo o ejecutable a abrir
    key: str         # nombre normalizado, para comparar


def _start_menu_dirs() -> list[Path]:
    return [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]


def _from_start_menu() -> list[InstalledApp]:
    apps = []
    for folder in _start_menu_dirs():
        if not folder.is_dir():
            continue
        for shortcut in folder.rglob("*.lnk"):
            if IGNORE.search(shortcut.stem):
                continue
            apps.append(InstalledApp(shortcut.stem, str(shortcut), normalize(shortcut.stem)))
    return apps


def _from_registry() -> list[InstalledApp]:
    """Programas que Windows sabe abrir por nombre (App Paths), como chrome.exe o brave.exe."""
    apps = []
    for root, path in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
                       (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")):
        try:
            with winreg.OpenKey(root, path) as key:
                for i in range(winreg.QueryInfoKey(key)[0]):
                    entry = winreg.EnumKey(key, i)
                    if entry.lower().endswith(".exe") and not IGNORE.search(entry):
                        name = entry[:-4]
                        apps.append(InstalledApp(name, entry, normalize(name)))
        except OSError:
            continue
    return apps


@lru_cache(maxsize=1)
def index() -> list[InstalledApp]:
    """Todos los programas instalados que se pueden abrir, sin repetidos."""
    unique: dict[str, InstalledApp] = {}
    for app in _from_start_menu() + _from_registry():
        if app.key and app.key not in unique:
            unique[app.key] = app
    return list(unique.values())


def refresh():
    index.cache_clear()


def find(query: str) -> tuple[Optional[InstalledApp], float]:
    """Busca por parecido: devuelve el programa y qué tan seguro es (0 a 1)."""
    wanted = normalize(query)
    if not wanted:
        return None, 0.0
    best, best_score = None, 0.0
    for app in index():
        if wanted == app.key:
            return app, 1.0
        # Si el nombre pedido aparece completo dentro del nombre real ("brave" en "brave browser")
        if re.search(rf"\b{re.escape(wanted)}\b", app.key):
            score = 0.9 + 0.1 * len(wanted) / len(app.key)
        else:
            score = difflib.SequenceMatcher(None, wanted, app.key).ratio()
        if score > best_score:
            best, best_score = app, score
    return best, round(best_score, 3)
