import os
import winreg
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AppEntry:
    display_name: str
    launch: str                     # Ejecutable, URI o ruta completa (las rutas se abren con os.startfile)
    process: Optional[str]          # Proceso a cerrar; None = no se permite cerrar
    aliases: tuple[str, ...]        # Siempre normalizados (sin acentos, minúsculas)


# Lista blanca: SOLO estas aplicaciones se pueden abrir o cerrar.
APPS: dict[str, AppEntry] = {
    "brave": AppEntry("Brave", "brave", "brave.exe", ("brave", "navegador brave", "brave browser")),
    "chrome": AppEntry("Google Chrome", "chrome", "chrome.exe", ("chrome", "google chrome", "navegador chrome")),
    "edge": AppEntry("Microsoft Edge", "msedge", "msedge.exe", ("edge", "microsoft edge")),
    "notepad": AppEntry("Bloc de notas", "notepad", "notepad.exe", ("bloc de notas", "notepad", "block de notas", "notas rapidas")),
    "calc": AppEntry("Calculadora", "calc", "CalculatorApp.exe", ("calculadora", "calc", "calculator")),
    "explorer": AppEntry("Explorador de archivos", "explorer", None,
                         ("explorador", "explorador de archivos", "archivos", "file explorer", "explorer")),
    "vscode": AppEntry("Visual Studio Code", "code", "Code.exe", ("visual studio code", "vscode", "vs code", "code")),
    "spotify": AppEntry("Spotify", "spotify:", "Spotify.exe", ("spotify",)),
    "paint": AppEntry("Paint", "mspaint", "mspaint.exe", ("paint",)),
    "cmd": AppEntry("Símbolo del sistema", "cmd", "cmd.exe",
                    ("cmd", "consola", "terminal", "simbolo del sistema", "command prompt")),
    "discord": AppEntry("Discord", "discord:", "Discord.exe", ("discord",)),
    "whatsapp": AppEntry("WhatsApp", "whatsapp:", "WhatsApp.exe", ("whatsapp", "wasap", "wsp")),
    "word": AppEntry("Word", "winword", "WINWORD.EXE", ("word",)),
    "excel": AppEntry("Excel", "excel", "EXCEL.EXE", ("excel",)),
    "settings": AppEntry("Configuración", "ms-settings:", "SystemSettings.exe",
                         ("configuracion", "ajustes", "settings", "opciones de windows")),
    "taskmgr": AppEntry("Administrador de tareas", "taskmgr", None,
                        ("administrador de tareas", "task manager", "taskmgr")),
    "steam": AppEntry("Steam", "steam", "steam.exe", ("steam",)),
    # Instalados en este equipo
    "antigravity": AppEntry("Antigravity IDE", str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe"),
                            "Antigravity IDE.exe", ("antigravity", "anti gravity", "antigravity ide")),
    "applemusic": AppEntry("Apple Music", "AppleMusic.exe", "AppleMusic.exe", ("apple music", "musica de apple", "itunes")),
    "wt": AppEntry("Windows Terminal", "wt", "WindowsTerminal.exe", ("windows terminal", "terminal de windows")),
    "outlook": AppEntry("Outlook", "olk", "olk.exe", ("outlook", "correo")),
    "onenote": AppEntry("OneNote", "onenote", "onenote.exe", ("onenote", "one note", "notas")),
    "snipping": AppEntry("Recortes", "snippingtool", "SnippingTool.exe", ("recortes", "captura de pantalla", "snipping tool")),
}


# "abre el navegador" no es una app concreta: es el navegador que tengas por defecto o abierto
BROWSER_KEY = "browser"
BROWSER_ALIASES = ("navegador", "browser", "el internet")
BROWSER_KEYS = ("brave", "chrome", "edge", "firefox", "opera")
PROGID_TO_KEY = {"brave": "brave", "chrome": "chrome", "msedge": "edge", "edge": "edge",
                 "firefox": "firefox", "opera": "opera"}


@lru_cache(maxsize=1)
def default_browser_key() -> str:
    """Qué navegador usa Windows para abrir enlaces, para que "abre el navegador" abra el tuyo y no Edge."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"SOFTWARE\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice") as key:
            prog_id = winreg.QueryValueEx(key, "ProgId")[0].lower()
    except OSError:
        return "edge"
    for fragment, app_key in PROGID_TO_KEY.items():
        if fragment in prog_id and app_key in APPS:
            return app_key
    return "edge"


def all_aliases() -> list[tuple[str, str]]:
    """Pares (alias, app_key), del alias más largo al más corto para que gane la coincidencia más específica."""
    pairs = [(alias, key) for key, entry in APPS.items() for alias in entry.aliases]
    pairs += [(alias, BROWSER_KEY) for alias in BROWSER_ALIASES]
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)
