import csv
import ctypes
import difflib
import io
import platform
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

from ..nlu.text import normalize

WM_CLOSE = 0x10
IS_WINDOWS = platform.system() == "Windows"
MATCH_THRESHOLD = 0.7   # parecido mínimo con el nombre dicho para cerrar un programa
# Procesos de Windows que nunca se cierran, aunque tengan ventana
# Reproductores que, si están abiertos, reciben la tecla de play
MEDIA_PLAYERS = {"applemusic.exe": "Apple Music", "spotify.exe": "Spotify", "itunes.exe": "iTunes",
                 "wmplayer.exe": "Windows Media Player", "musicbee.exe": "MusicBee", "vlc.exe": "VLC"}
MEDIA_TITLE_HINTS = ("apple music", "youtube", "spotify", "soundcloud", "deezer", "tidal")
SYSTEM_PROCESSES = {"applicationframehost.exe", "textinputhost.exe", "tabtip.exe", "explorer.exe",
                    "shellexperiencehost.exe", "searchhost.exe", "startmenuexperiencehost.exe",
                    "dwm.exe", "sihost.exe", "csrss.exe", "winlogon.exe", "lockapp.exe"}


@dataclass(frozen=True)
class Window:
    hwnd: int
    pid: int
    title: str


def visible_windows() -> list[Window]:
    """Ventanas visibles con título: son los programas con los que el usuario interactúa."""
    if not IS_WINDOWS:
        return []
    windows: list[Window] = []
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def collect(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                windows.append(Window(hwnd, pid.value, buffer.value))
        return True

    user32.EnumWindows(collect, 0)
    return windows


def running_processes() -> dict[int, str]:
    """{pid: nombre.exe} de los procesos actuales."""
    if not IS_WINDOWS:
        return {}
    result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW, errors="ignore")
    processes = {}
    for row in csv.reader(io.StringIO(result.stdout)):
        if len(row) >= 2 and row[1].isdigit():
            processes[int(row[1])] = row[0]
    return processes


def pids_of(process_name: str) -> list[int]:
    wanted = process_name.lower()
    return [pid for pid, name in running_processes().items() if name.lower() == wanted]


def request_close(pids: list[int]) -> int:
    """Pide cerrar como si hicieras clic en la X: la app puede preguntar si guardas."""
    if not IS_WINDOWS:
        return 0
    closed = 0
    for window in visible_windows():
        if window.pid in pids:
            ctypes.windll.user32.PostMessageW(window.hwnd, WM_CLOSE, 0, 0)
            closed += 1
    return closed


def wait_until_closed(pids: list[int], seconds: float = 4.0) -> list[int]:
    """Espera a que se cierren y devuelve los que siguen vivos."""
    deadline = time.time() + seconds
    alive = pids
    while time.time() < deadline and alive:
        time.sleep(0.4)
        current = running_processes()
        alive = [pid for pid in alive if pid in current]
    return alive


def media_players_running() -> Optional[str]:
    """Si ya hay música abierta, la tecla de play la reanuda en vez de abrir otra app.
    Detecta reproductores dedicados y pestañas de música en el navegador (por el título de la ventana)."""
    processes = {name.lower() for name in running_processes().values()}
    for process, label in MEDIA_PLAYERS.items():
        if process in processes:
            return label
    for window in visible_windows():
        title = normalize(window.title)
        if any(hint in title for hint in MEDIA_TITLE_HINTS):
            return "el navegador"
    return None


def find_open_program(name: str) -> Optional[tuple[str, list[int]]]:
    """Programa abierto que más se parece al nombre dicho. Solo mira los que tienen ventana,
    para no tocar nunca procesos del sistema."""
    wanted = normalize(name)
    if not wanted:
        return None
    # "cierra el navegador brave" -> también se prueba palabra por palabra
    words = [word for word in wanted.split() if len(word) >= 4]
    processes = running_processes()
    candidates: dict[int, tuple[float, str]] = {}
    for window in visible_windows():
        process = processes.get(window.pid, "")
        if process.lower() in SYSTEM_PROCESSES:
            continue
        label = process.removesuffix(".exe") or window.title
        for text in (process.removesuffix(".exe"), window.title):
            clean = normalize(text)
            if not clean:
                continue
            score = 0.0
            for candidate in [wanted, *words]:
                if re.search(rf"\b{re.escape(candidate)}", clean):
                    score = max(score, 0.9 if candidate == wanted else 0.85)
                else:
                    score = max(score, difflib.SequenceMatcher(None, candidate, clean).ratio())
            if score > candidates.get(window.pid, (0.0, ""))[0]:
                candidates[window.pid] = (score, label)
    if not candidates:
        return None
    best_pid, (best_score, best_label) = max(candidates.items(), key=lambda item: item[1][0])
    if best_score < MATCH_THRESHOLD:
        return None
    # Los programas modernos abren varios procesos con el mismo nombre; se cierran todos
    process_name = processes.get(best_pid, "")
    pids = [pid for pid, name_ in processes.items() if name_ == process_name] if process_name else [best_pid]
    return best_label, pids


def force_kill(pids: list[int]) -> int:
    if not IS_WINDOWS or not pids:
        return 0
    killed = 0
    for pid in pids:
        result = subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        killed += result.returncode == 0
    return killed
