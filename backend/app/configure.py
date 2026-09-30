"""
Configura Kyuuri en este equipo: detecta la GPU, el micrófono, el navegador y el reproductor de música,
y escribe el archivo .env y los modos. Pensado para que alguien que no programa pueda instalarlo.

Uso (desde la carpeta backend):
    python -m app.configure
    python -m app.configure --automatico   sin preguntas, acepta todo lo detectado
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

from .core.config import BACKEND_DIR
from .core.hardware import PROFILES, Profile, detect, ollama_path, recommend, summary

ENV_PATH = BACKEND_DIR / ".env"
MODES_PATH = BACKEND_DIR / "modes.json"
# Reproductores y editores que se buscan en el equipo, en orden de preferencia
MUSIC_CANDIDATES = [("applemusic", "Apple Music"), ("spotify", "Spotify")]
# Dispositivos que Windows inventa y que no son un micrófono de verdad
VIRTUAL_DEVICE = re.compile(r"asignador de sonido|sound mapper|controlador primario|primary sound", re.IGNORECASE)
EDITOR_CANDIDATES = [("vscode", "Visual Studio Code"), ("antigravity", "Antigravity IDE")]


def ask(question: str, default: str, automatic: bool) -> str:
    if automatic:
        print(f"{question} [{default}]")
        return default
    answer = input(f"{question} [{default}]: ").strip()
    return answer or default


def pick_microphone(automatic: bool) -> str:
    """Elige el micrófono probando cuál entrega audio de verdad (hay micrófonos que no dan nada)."""
    from .voice.microphone import Microphone, input_devices
    devices = input_devices()
    if not devices:
        print("  No encontré micrófonos. Conecta uno y vuelve a ejecutar esto.")
        return ""

    print("\nMicrófonos encontrados:")
    working: list[tuple[int, str]] = []
    real_devices = [(i, name) for i, name in devices if not VIRTUAL_DEVICE.search(name)] or devices
    for index, name in real_devices:
        try:
            microphone = Microphone(name)
            microphone.calibrate(0.4)
            working.append((index, name))
            print(f"  [{len(working)}] {name}  (funciona)")
        except Exception:
            print(f"      {name}  (no entrega audio)")
    if not working:
        print("  Ninguno entregó audio. Revisa los permisos de micrófono de Windows.")
        return ""

    chosen = working[0][1]
    if not automatic and len(working) > 1:
        answer = input(f"¿Cuál uso? [1-{len(working)}, Enter para {chosen}]: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(working):
            chosen = working[int(answer) - 1][1]
    print(f"  Micrófono elegido: {chosen}")
    return chosen


def detect_installed(candidates: list[tuple[str, str]]) -> list[tuple[str, str]]:
    from .services.app_catalog import APPS
    from .services.installed_apps import GOOD_MATCH, find
    found = []
    for key, display in candidates:
        entry = APPS.get(key)
        launch = entry.launch if entry else display
        if (Path(launch).exists() if Path(launch).is_absolute() else find(display)[1] >= GOOD_MATCH):
            found.append((key, display))
    return found


def choose_profile(automatic: bool) -> Profile:
    hardware = detect()
    print(f"\nEquipo: {summary(hardware)}")
    suggested = recommend(hardware)
    print(f"Perfil recomendado: {suggested.key} — {suggested.description}")
    if automatic:
        return suggested
    print("Otros perfiles: " + ", ".join(key for key in PROFILES if key != suggested.key))
    answer = input(f"¿Qué perfil uso? [{suggested.key}]: ").strip()
    return PROFILES.get(answer, suggested)


def write_env(values: dict[str, str]):
    lines = ["# Configuración de Kyuuri en este equipo (generada por: python -m app.configure)"]
    for key, value in values.items():
        lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_modes(editors: list[tuple[str, str]], music_app: str):
    """Modos adaptados a lo que hay instalado: no sirve abrir editores que el usuario no tiene."""
    work_steps = [{"app": key} for key, _ in editors] or [{"app": "browser"}]
    modes = {
        "_ayuda": ["Modos: varias acciones de golpe al decir 'ponte en modo trabajo'.",
                   "Pasos: {'app': clave}, {'folder': clave}, {'url': '...'}, {'site': clave, 'query': '...'},",
                   "{'music': true}, {'volume': 'up|down|mute'}, {'wait': segundos}.",
                   "Si agregas un modo, reentrena para que aprenda su nombre: python -m training.train"],
        "trabajo": {"alias": ["trabajo", "programar", "desarrollo", "codigo", "trabajar"],
                    "pasos": work_steps, "cierra": [key for key, _ in editors]},
        "musica": {"alias": ["musica", "concentracion", "escuchar musica"],
                   "pasos": [{"music": True}], "cierra": [music_app] if music_app != "web" else []},
        "descanso": {"alias": ["descanso", "relax", "pausa", "break"],
                     "pasos": [{"site": "youtube", "query": "musica relajante"}, {"volume": "down"}],
                     "cierra": []},
    }
    MODES_PATH.write_text(json.dumps(modes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Configurar Kyuuri en este equipo")
    parser.add_argument("--automatico", action="store_true", help="acepta todo lo detectado, sin preguntas")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 60)
    print(" Configuración de Kyuuri")
    print("=" * 60)

    profile = choose_profile(args.automatico)
    hardware = detect()

    if profile.ollama and not hardware.has_ollama:
        print("\nAviso: no encontré Ollama, que es lo que permite conversar.")
        print("Instálalo desde https://ollama.com y vuelve a ejecutar esto, o quedará solo con comandos.")
        profile = Profile(profile.key, profile.description, profile.whisper, None, profile.piper_voice)

    name = ask("\n¿Cómo quieres llamarlo?", "Kyuuri", args.automatico)
    wake_words = ask("Formas en que puede sonar su nombre (separadas por coma)",
                     ",".join(dict.fromkeys([name.lower(), name.lower().replace("uu", "u")])), args.automatico)

    microphone = pick_microphone(args.automatico)

    from .services.app_catalog import default_browser_key
    browser = default_browser_key()
    print(f"\nNavegador predeterminado: {browser}")

    players = detect_installed(MUSIC_CANDIDATES)
    music_app = players[0][0] if players else "web"
    print(f"Música: {players[0][1] if players else 'YouTube Music en el navegador'}")

    editors = detect_installed(EDITOR_CANDIDATES)
    print(f"Editores para el modo trabajo: {', '.join(display for _, display in editors) or 'ninguno, usará el navegador'}")

    write_env({
        "ASSISTANT_NAME": name,
        "WAKE_WORDS": wake_words,
        "MIC_DEVICE": microphone,
        "WHISPER_MODEL": profile.whisper,
        "PIPER_VOICE": profile.piper_voice,
        "OLLAMA_MODEL": profile.ollama or "",
        "OLLAMA_URL": "http://localhost:11434",
        "MUSIC_APP": music_app,
        "CONFIDENCE_THRESHOLD": "0.6",
        "ACTION_CONFIDENCE_THRESHOLD": "0.8",
        "LOG_INTERACTIONS": "true",
        "API_KEY": "",
    })
    write_modes(editors, music_app)

    print(f"\nListo. Guardé la configuración en {ENV_PATH.name} y los modos en {MODES_PATH.name}.")
    if profile.ollama:
        print(f"Falta descargar el modelo de conversación:  ollama pull {profile.ollama}")
    print(f"Para hablarle:  python -m app.voice")
    print(f"Si algo no funciona:  python -m app.diagnose")


if __name__ == "__main__":
    main()
