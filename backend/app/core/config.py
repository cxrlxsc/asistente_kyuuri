import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Carga las variables del archivo .env

BACKEND_DIR = Path(__file__).resolve().parents[2]
MODELS_DIR = BACKEND_DIR / "models"


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "si", "sí", "yes")


class Settings:
    BACKEND_DIR: Path = BACKEND_DIR
    ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "Kyuuri")
    PROJECT_NAME: str = f"{ASSISTANT_NAME} Virtual Assistant"
    VERSION: str = "1.1.0"

    # Clave que deben enviar los clientes en el header X-API-Key (vacío = sin protección)
    API_KEY: str = os.getenv("API_KEY", "")

    # Modelo propio de intenciones (se ajusta con training/train.py)
    INTENT_BASE_MODEL: str = os.getenv("INTENT_BASE_MODEL", "dccuchile/bert-base-spanish-wwm-uncased")
    INTENT_MODEL_DIR: Path = MODELS_DIR / "intent"
    # Guardar lo que le dices para poder reentrenar con tus frases (solo en tu equipo)
    DATA_DIR: Path = BACKEND_DIR / "data"
    LOG_INTERACTIONS: bool = _flag("LOG_INTERACTIONS", "true")
    # Por debajo de esta confianza la frase se trata como conversación libre
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    # Confianza mínima para ejecutar algo en el equipo (abrir, cerrar, volumen, bloquear...)
    ACTION_CONFIDENCE_THRESHOLD: float = float(os.getenv("ACTION_CONFIDENCE_THRESHOLD", "0.8"))

    # Voz
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "openai/whisper-large-v3-turbo")
    PIPER_VOICE: str = os.getenv("PIPER_VOICE", "es_MX-claude-high")
    PIPER_DIR: Path = MODELS_DIR / "piper"
    # Palabras que activan al asistente, separadas por coma: el nombre y cómo suele escribirlo Whisper
    WAKE_WORDS: list[str] = [w.strip().lower() for w in os.getenv("WAKE_WORDS", "kyuuri,kyuri,kiuri,quiuri").split(",") if w.strip()]
    # Parte del nombre del micrófono a usar (vacío = el predeterminado de Windows)
    MIC_DEVICE: str = os.getenv("MIC_DEVICE", "")

    # Con qué poner música: una clave de app_catalog (applemusic, spotify...) o "web" para YouTube Music
    MUSIC_APP: str = os.getenv("MUSIC_APP", "web")

    # LLM local para conversación libre (vacío = sin conversación, solo comandos)
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
    # Cuánto contexto carga el LLM: más grande no cabe en la GPU y se va al procesador (mucho más lento)
    LLM_CONTEXT: int = int(os.getenv("LLM_CONTEXT", "4096"))

    @property
    def chat_enabled(self) -> bool:
        return bool(self.OLLAMA_MODEL.strip())


settings = Settings()
