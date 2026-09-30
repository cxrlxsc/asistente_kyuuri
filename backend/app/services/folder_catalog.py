import ctypes
import platform
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Lista blanca de carpetas: clave -> (nombre para hablar, GUID de Windows, alias normalizados)
# El GUID es la forma correcta de preguntarle a Windows dónde está cada carpeta,
# porque OneDrive o el idioma pueden haberla movido de sitio.
FOLDERS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "downloads": ("Descargas", "{374DE290-123F-4565-9164-39C4925E467B}", ("descargas", "downloads")),
    "documents": ("Documentos", "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}", ("documentos", "documents", "mis documentos", "docs")),
    "desktop": ("Escritorio", "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}", ("escritorio", "desktop")),
    "pictures": ("Imágenes", "{33E28130-4E1E-4676-835A-98395C3BC3BB}", ("imagenes", "fotos", "pictures", "photos")),
    "music": ("Música", "{4BD8D571-6D19-48D3-BE97-422220080E43}", ("musica", "canciones", "music")),
    "videos": ("Vídeos", "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}", ("videos", "peliculas", "movies")),
}


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


@lru_cache(maxsize=None)
def folder_path(key: str) -> Optional[Path]:
    if platform.system() != "Windows":
        return None
    _, guid, _ = FOLDERS[key]
    folder_id, buffer = _GUID(), ctypes.c_wchar_p()
    if ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid), ctypes.byref(folder_id)) != 0:
        return None
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(buffer)) != 0:
        return None
    path = Path(buffer.value)
    ctypes.windll.ole32.CoTaskMemFree(buffer)
    return path if path.is_dir() else None


def display_name(key: str) -> str:
    return FOLDERS[key][0]


def folder_aliases() -> list[tuple[str, str]]:
    pairs = [(alias, key) for key, (_, _, aliases) in FOLDERS.items() for alias in aliases]
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)
