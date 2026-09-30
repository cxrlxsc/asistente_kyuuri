"""
Revisa que todo lo que Kyuuri necesita esté en su lugar y dice cómo arreglar lo que falte.

Uso (desde la carpeta backend):
    python -m app.diagnose
"""
import sys

from .core.config import settings
from .core.hardware import detect, ollama_path, summary

OK, FAIL, WARN = "[ OK ]", "[FALTA]", "[AVISO]"


def check(label: str, passed: bool, detail: str = "", fix: str = "", warn_only: bool = False) -> bool:
    mark = OK if passed else (WARN if warn_only else FAIL)
    print(f"{mark} {label}" + (f": {detail}" if detail else ""))
    if not passed and fix:
        print(f"        → {fix}")
    return passed


def check_llm_on_gpu(hardware):
    """Ollama a veces elige la gráfica integrada (Vulkan) en vez de la NVIDIA y la charla se vuelve lentísima."""
    if not hardware.has_gpu:
        return
    import httpx
    try:
        loaded = httpx.post(f"{settings.OLLAMA_URL}/api/generate", timeout=300,
                            json={"model": settings.OLLAMA_MODEL, "keep_alive": "5m",
                                  "options": {"num_ctx": settings.LLM_CONTEXT}})
        loaded.raise_for_status()
        running = httpx.get(f"{settings.OLLAMA_URL}/api/ps", timeout=20).json().get("models", [])
    except Exception:
        return
    if not running:
        return
    model = running[0]
    on_gpu = model.get("size_vram", 0) > model.get("size", 1) * 0.9
    check("La conversación usa la tarjeta NVIDIA", on_gpu,
          f"{model.get('size_vram', 0) / 2**30:.1f} de {model.get('size', 0) / 2**30:.1f} GB en la GPU",
          "Ollama eligió la gráfica integrada. Arréglalo con estas dos líneas y reinicia Ollama:\n"
          '          setx OLLAMA_VULKAN 0\n          setx OLLAMA_IGPU_ENABLE 0',
          warn_only=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 64)
    print(f" Diagnóstico de {settings.ASSISTANT_NAME}")
    print("=" * 64)
    problems = 0

    hardware = detect()
    print(f"\nEquipo: {summary(hardware)}\n")

    # 1. Librerías
    try:
        import torch
        check("PyTorch instalado", True, torch.__version__)
        check("GPU disponible para los modelos", torch.cuda.is_available(),
              torch.cuda.get_device_name(0) if torch.cuda.is_available() else "usará el procesador (más lento)",
              "Instala torch con CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu128",
              warn_only=True)
    except ImportError:
        problems += not check("PyTorch instalado", False, fix="Ejecuta instalar.bat o pip install -r requirements.txt")

    for module, nombre in [("transformers", "transformers"), ("piper", "Piper (voz)"),
                           ("sounddevice", "sounddevice (micrófono)"), ("fastapi", "FastAPI (API)")]:
        try:
            __import__(module)
            check(f"{nombre} instalado", True)
        except ImportError:
            problems += not check(f"{nombre} instalado", False, fix="pip install -r requirements.txt")

    # 2. Modelo propio
    model_ok = (settings.INTENT_MODEL_DIR / "config.json").exists()
    problems += not check("Modelo de intenciones entrenado", model_ok, str(settings.INTENT_MODEL_DIR),
                          "Entrénalo con: python -m training.train")

    # 3. Configuración
    check("Archivo .env", (settings.BACKEND_DIR / ".env").exists(), fix="Ejecuta: python -m app.configure",
          warn_only=True)
    check("Modelo de oído (Whisper)", True, settings.WHISPER_MODEL)
    check("Voz (Piper)", True, settings.PIPER_VOICE)

    # 4. Micrófono
    try:
        from .voice.microphone import Microphone, input_devices
        devices = input_devices()
        problems += not check("Micrófonos detectados", bool(devices), f"{len(devices)} encontrados",
                              "Conecta un micrófono y revisa los permisos de Windows")
        if devices:
            try:
                microphone = Microphone(settings.MIC_DEVICE)
                microphone.calibrate(0.5)
                check("El micrófono entrega audio", True, f"{microphone.name} (umbral {microphone.threshold:.4f})")
            except Exception as e:
                problems += not check("El micrófono entrega audio", False, str(e).split(".")[0],
                                      "Elige otro con: python -m app.configure")
    except ImportError:
        pass

    # 5. Conversación libre
    if settings.chat_enabled:
        path = ollama_path()
        problems += not check("Ollama instalado", path is not None, path or "",
                              "Instálalo desde https://ollama.com")
        if path:
            import httpx
            try:
                response = httpx.get(f"{settings.OLLAMA_URL}/api/tags", timeout=10)
                models = [m["name"] for m in response.json().get("models", [])]
                check("Ollama respondiendo", True, f"{len(models)} modelos")
                problems += not check(f"Modelo {settings.OLLAMA_MODEL} descargado",
                                      any(settings.OLLAMA_MODEL in m for m in models),
                                      fix=f"ollama pull {settings.OLLAMA_MODEL}")
                check_llm_on_gpu(hardware)
            except Exception:
                problems += not check("Ollama respondiendo", False, fix="Abre la app de Ollama y reintenta")
    else:
        check("Conversación libre", True, "desactivada (solo comandos)", warn_only=True)

    print()
    if problems:
        print(f"Hay {problems} cosa(s) por arreglar; arriba dice cómo.")
    else:
        print(f"Todo listo. Para hablarle: python -m app.voice")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
