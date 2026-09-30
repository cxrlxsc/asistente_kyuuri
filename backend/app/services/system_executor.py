import ctypes
import os
import platform
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus

from ..core.config import settings
from .app_catalog import APPS, BROWSER_KEY, BROWSER_KEYS, default_browser_key
from .folder_catalog import display_name, folder_path
from .installed_apps import InstalledApp
from .processes import (find_open_program, force_kill, media_players_running, pids_of, request_close,
                        wait_until_closed)
from .site_catalog import SITES, search_url


@dataclass
class CloseResult:
    """Qué pasó al cerrar: si quedaron procesos vivos, el asistente puede ofrecer forzarlo."""
    message: str
    stubborn_pids: list[int]
    display_name: str = ""

DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Teclas multimedia virtuales de Windows
VK_VOLUME_MUTE, VK_VOLUME_DOWN, VK_VOLUME_UP = 0xAD, 0xAE, 0xAF
VK_MEDIA_NEXT, VK_MEDIA_PREVIOUS, VK_MEDIA_PLAY_PAUSE = 0xB0, 0xB1, 0xB3
VK_LWIN = 0x5B
KEYEVENTF_KEYUP = 0x2
SHUTDOWN_DELAY = 30        # segundos de margen para arrepentirse
MUSIC_WAIT_SECONDS = 25    # cuánto se espera a que Apple Music abra su ventana
MUSIC_START_DELAY = 4      # margen extra para que cargue la biblioteca antes del play
MUSIC_PLAY_ATTEMPTS = 3    # la primera tecla de play a veces se pierde

IS_WINDOWS = platform.system() == "Windows"
NOT_SUPPORTED = "El sistema operativo no es Windows. Esta acción no está soportada."


def _press_key(vk: int, times: int = 1):
    for _ in range(times):
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


class SystemExecutor:
    def open_application(self, app_key: str) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        if app_key == BROWSER_KEY:
            app_key = default_browser_key()
        entry = APPS[app_key]
        try:
            # `launch` sale siempre de la lista blanca, nunca del texto del usuario.
            if os.path.isabs(entry.launch):
                if not os.path.exists(entry.launch):
                    return f"No encontré {entry.display_name} instalado en este equipo."
                os.startfile(entry.launch)
            else:
                # El "" vacío es el título de la ventana que espera `start`.
                subprocess.Popen(["cmd", "/c", "start", "", entry.launch], creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Abriendo {entry.display_name}."
        except OSError as e:
            return f"Hubo un error al intentar abrir {entry.display_name}: {e}"

    def close_application(self, app_key: str) -> CloseResult:
        if not IS_WINDOWS:
            return CloseResult(NOT_SUPPORTED, [])
        if app_key == BROWSER_KEY:
            return self._close_browser()
        entry = APPS[app_key]
        if entry.process is None:
            return CloseResult(f"Por seguridad no cierro {entry.display_name}.", [])
        return self._close(entry.display_name, pids_of(entry.process))

    def _close_browser(self) -> CloseResult:
        """"Cierra el navegador": el que esté abierto, empezando por el predeterminado."""
        order = [default_browser_key()] + [key for key in BROWSER_KEYS if key != default_browser_key()]
        for key in order:
            entry = APPS.get(key)
            if entry and entry.process and pids_of(entry.process):
                return self._close(entry.display_name, pids_of(entry.process))
        return CloseResult("No veo ningún navegador abierto.", [])

    def close_running(self, name: str) -> CloseResult:
        """Cierra cualquier programa abierto que coincida con el nombre, aunque no esté en el catálogo."""
        if not IS_WINDOWS:
            return CloseResult(NOT_SUPPORTED, [])
        match = find_open_program(name)
        if match is None:
            return CloseResult(f"No veo {name} abierto.", [])
        display_name, pids = match
        return self._close(display_name, pids)

    def _close(self, display_name: str, pids: list[int]) -> CloseResult:
        if not pids:
            return CloseResult(f"{display_name} no parece estar abierto.", [])
        # Como hacer clic en la X: si hay cambios sin guardar, la app te pregunta
        request_close(pids)
        alive = wait_until_closed(pids)
        if not alive:
            return CloseResult(f"He cerrado {display_name}.", [])
        return CloseResult(
            f"{display_name} no se cerró solo; puede tener algo sin guardar. ¿Lo cierro a la fuerza?",
            alive, display_name,
        )

    def force_close(self, pids: list[int], display_name: str) -> str:
        killed = force_kill(pids)
        return f"Cerré {display_name} a la fuerza." if killed else f"No pude cerrar {display_name}."

    def open_installed(self, app: InstalledApp) -> str:
        """Abre un programa del índice del sistema (nunca texto del usuario)."""
        try:
            os.startfile(app.launch) if os.path.isabs(app.launch) else subprocess.Popen(
                ["cmd", "/c", "start", "", app.launch], creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Abriendo {app.name}."
        except OSError as e:
            return f"No pude abrir {app.name}: {e}"

    def search_web(self, query: str) -> str:
        webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
        return f"Buscando {query} en Google."

    def search_site(self, site_key: str, query: str) -> str:
        site = SITES[site_key]
        webbrowser.open(search_url(site_key, query))
        return f"Buscando {query} en {site.display_name}." if query else f"Abriendo {site.display_name}."

    def open_url(self, url: str) -> str:
        """Solo para URLs que vienen de tu configuración (modes.json), nunca del texto hablado."""
        webbrowser.open(url)
        return "Listo."

    def play_music(self) -> str:
        """Que suene música de verdad: si ya hay un reproductor abierto lo reanuda; si no, abre Apple Music y le da play."""
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        if playing := media_players_running():
            _press_key(VK_MEDIA_PLAY_PAUSE)
            return f"Dándole play en {playing}."

        # El reproductor lo elige cada usuario al configurar (MUSIC_APP)
        if settings.MUSIC_APP == "web" or settings.MUSIC_APP not in APPS:
            self.search_site("youtube_music", "")
            threading.Thread(target=self._play_when_ready, args=(None,), daemon=True).start()
            return "Abriendo YouTube Music."

        entry = APPS[settings.MUSIC_APP]
        self.open_application(settings.MUSIC_APP)
        # La app tarda en abrir: se espera su ventana y se insiste con el play
        threading.Thread(target=self._play_when_ready, args=(entry.process,), daemon=True).start()
        return f"Abriendo {entry.display_name} y poniendo música."

    def _play_when_ready(self, process: Optional[str]):
        deadline = time.time() + MUSIC_WAIT_SECONDS
        while process and time.time() < deadline and not pids_of(process):
            time.sleep(0.5)
        time.sleep(MUSIC_START_DELAY)  # la app necesita cargar su biblioteca antes de aceptar el play
        for _ in range(MUSIC_PLAY_ATTEMPTS):
            _press_key(VK_MEDIA_PLAY_PAUSE)
            time.sleep(2)
            if media_players_running():
                return

    def tell_time(self) -> str:
        now = datetime.now()
        return (f"Son las {now:%H:%M} del {DAYS[now.weekday()]} "
                f"{now.day} de {MONTHS[now.month - 1]} de {now.year}.")

    def volume_up(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        _press_key(VK_VOLUME_UP, times=5)  # cada pulsación son 2%
        return "Volumen arriba."

    def volume_down(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        _press_key(VK_VOLUME_DOWN, times=5)
        return "Volumen abajo."

    def volume_mute(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        _press_key(VK_VOLUME_MUTE)
        return "Listo, cambié el silencio."

    def media_play_pause(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        _press_key(VK_MEDIA_PLAY_PAUSE)
        return "Hecho."

    def media_next(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        _press_key(VK_MEDIA_NEXT)
        return "Siguiente canción."

    def media_previous(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        _press_key(VK_MEDIA_PREVIOUS)
        return "Canción anterior."

    def lock_pc(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        ctypes.windll.user32.LockWorkStation()
        return "Equipo bloqueado."

    def show_desktop(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, 0, 0)
        _press_key(ord("D"))
        ctypes.windll.user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
        return "Listo."

    def open_folder(self, folder_key: str) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        path = folder_path(folder_key)
        if path is None:
            return f"No encontré la carpeta {display_name(folder_key)} en este equipo."
        os.startfile(path)  # la ruta viene de Windows, no del texto del usuario
        return f"Abriendo {display_name(folder_key)}."

    def shutdown_pc(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        subprocess.run(["shutdown", "/s", "/t", str(SHUTDOWN_DELAY)], creationflags=subprocess.CREATE_NO_WINDOW)
        return f"Apagando en {SHUTDOWN_DELAY} segundos. Dime 'cancela el apagado' si te arrepientes."

    def restart_pc(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        subprocess.run(["shutdown", "/r", "/t", str(SHUTDOWN_DELAY)], creationflags=subprocess.CREATE_NO_WINDOW)
        return f"Reiniciando en {SHUTDOWN_DELAY} segundos. Dime 'cancela el apagado' si te arrepientes."

    def cancel_shutdown(self) -> str:
        if not IS_WINDOWS:
            return NOT_SUPPORTED
        result = subprocess.run(["shutdown", "/a"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return "Cancelado, el equipo sigue encendido." if result.returncode == 0 else "No había ningún apagado programado."
