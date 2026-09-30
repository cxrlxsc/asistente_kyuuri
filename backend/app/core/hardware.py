"""Detecta de qué es capaz el equipo y elige los modelos que le caben.

Así el mismo Kyuuri funciona en una laptop con RTX 4060 y en una PC sin tarjeta gráfica.
"""
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Profile:
    key: str
    description: str
    whisper: str          # modelo de Whisper (oído)
    ollama: Optional[str]  # modelo de conversación; None = sin conversación libre
    piper_voice: str       # calidad de la voz


PROFILES: dict[str, Profile] = {
    "completo": Profile(
        "completo", "GPU con 7 GB o más: todo al máximo",
        "openai/whisper-large-v3-turbo", "qwen3:4b-instruct-2507-q4_K_M", "es_MX-claude-high"),
    "medio": Profile(
        "medio", "GPU de 4 a 7 GB: oído bueno y conversación más liviana",
        "openai/whisper-small", "qwen3:1.7b", "es_MX-claude-high"),
    "ligero": Profile(
        "ligero", "GPU pequeña o sin GPU: comandos rápidos, conversación básica",
        "openai/whisper-base", "qwen3:1.7b", "es_MX-claude-high"),
    "sin_conversacion": Profile(
        "sin_conversacion", "Sin GPU y equipo modesto: solo comandos, sin charla libre",
        "openai/whisper-base", None, "es_MX-claude-high"),
}


@dataclass(frozen=True)
class Hardware:
    system: str
    gpu_name: Optional[str]
    vram_gb: float
    cpu_cores: int
    ram_gb: float
    has_ollama: bool

    @property
    def has_gpu(self) -> bool:
        return self.gpu_name is not None


@lru_cache(maxsize=1)
def detect() -> Hardware:
    gpu_name, vram = _detect_gpu()
    return Hardware(
        system=platform.system(),
        gpu_name=gpu_name,
        vram_gb=vram,
        cpu_cores=_cpu_cores(),
        ram_gb=_ram_gb(),
        has_ollama=ollama_path() is not None,
    )


def _detect_gpu() -> tuple[Optional[str], float]:
    try:
        import torch
        if torch.cuda.is_available():
            properties = torch.cuda.get_device_properties(0)
            return properties.name, round(properties.total_memory / 2 ** 30, 1)
    except (ImportError, RuntimeError, AssertionError):
        pass
    # Sin torch todavía (durante la instalación) se pregunta al driver
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            name, memory = result.stdout.strip().splitlines()[0].split(",")
            return name.strip(), round(int(memory) / 1024, 1)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None, 0.0


def _cpu_cores() -> int:
    return os.cpu_count() or 2


def _ram_gb() -> float:
    if platform.system() == "Windows":
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        status = Status()
        status.dwLength = ctypes.sizeof(Status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.ullTotalPhys / 2 ** 30, 1)
    return 0.0


def ollama_path() -> Optional[str]:
    """Ollama no siempre queda en el PATH, así que también se busca donde lo instala su instalador."""
    if found := shutil.which("ollama"):
        return found
    candidate = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(candidate) if candidate.exists() else None


def recommend(hardware: Optional[Hardware] = None) -> Profile:
    """Perfil que mejor le queda al equipo."""
    hardware = hardware or detect()
    if hardware.vram_gb >= 7:
        return PROFILES["completo"]
    if hardware.vram_gb >= 4:
        return PROFILES["medio"]
    if hardware.has_gpu:
        return PROFILES["ligero"]
    # Sin GPU: el LLM va por CPU y necesita músculo para no desesperar
    if hardware.cpu_cores >= 8 and hardware.ram_gb >= 16:
        return PROFILES["ligero"]
    return PROFILES["sin_conversacion"]


def summary(hardware: Optional[Hardware] = None) -> str:
    hardware = hardware or detect()
    gpu = f"{hardware.gpu_name} ({hardware.vram_gb} GB)" if hardware.has_gpu else "sin GPU NVIDIA"
    return f"{gpu}, {hardware.cpu_cores} núcleos, {hardware.ram_gb} GB de RAM"
