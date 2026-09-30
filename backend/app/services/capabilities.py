"""Lo que el asistente sabe hacer, sacado de los catálogos reales (no de una lista escrita a mano)."""
from ..core.config import settings
from .app_catalog import APPS
from .folder_catalog import FOLDERS, display_name as folder_name
from .installed_apps import index
from .modes import load_modes
from .site_catalog import SITES

SKILLS = [
    "abrir y cerrar programas",
    "abrir carpetas",
    "buscar en Google y en sitios como YouTube o GitHub",
    "poner música",
    "activar modos",
    "decirte la hora y la fecha",
    "poner temporizadores y recordatorios",
    "controlar el volumen y la música",
    "mostrar el escritorio",
    "bloquear, apagar o reiniciar el equipo",
    "conversar de cualquier tema",
]


def spoken_summary() -> str:
    """Respuesta corta para "¿qué sabes hacer?" (se lee en voz alta)."""
    modes = ", ".join(load_modes()) or "ninguno configurado"
    return (f"Puedo {', '.join(SKILLS[:-1])} y {SKILLS[-1]}. "
            f"Mis modos son: {modes}. "
            f"Para abrir programas conozco {len(index())} instalados en este equipo.")


def modes_summary() -> str:
    modes = load_modes()
    if not modes:
        return "No tienes modos configurados todavía."
    parts = []
    for name, mode in modes.items():
        steps = len(mode.get("pasos", []))
        parts.append(f"{name} ({steps} paso{'s' if steps != 1 else ''})")
    return "Tengo estos modos: " + ", ".join(parts) + "."


def apps_summary() -> str:
    favourites = ", ".join(entry.display_name for entry in list(APPS.values())[:8])
    return (f"Tengo {len(APPS)} programas en mi lista rápida, como {favourites}. "
            f"Además busco entre los {len(index())} instalados en el equipo, así que pídeme el que quieras.")


def folders_summary() -> str:
    return "Puedo abrir estas carpetas: " + ", ".join(folder_name(key) for key in FOLDERS) + "."


def sites_summary() -> str:
    return "Puedo buscar en " + ", ".join(site.display_name for site in SITES.values()) + "."


def llm_context() -> str:
    """Contexto que se le da al LLM para que no invente lo que el asistente puede hacer."""
    return (
        f"Esto es lo que {settings.ASSISTANT_NAME} puede hacer cuando el usuario lo pide de forma directa: "
        f"{'; '.join(SKILLS)}. "
        f"Modos configurados: {', '.join(load_modes()) or 'ninguno'}. "
        f"Sitios de búsqueda: {', '.join(site.display_name for site in SITES.values())}. "
        f"Carpetas: {', '.join(folder_name(key) for key in FOLDERS)}."
    )
