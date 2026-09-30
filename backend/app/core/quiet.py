"""Silencia los mensajes técnicos de transformers y Hugging Face para que la consola solo muestre la conversación."""
import os
import warnings

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")


def silence():
    warnings.filterwarnings("ignore", category=FutureWarning)
    try:
        from transformers.utils import logging as transformers_logging
        transformers_logging.set_verbosity_error()
        transformers_logging.disable_progress_bar()
    except ImportError:
        pass
    try:
        from huggingface_hub.utils import disable_progress_bars, logging as hub_logging
        disable_progress_bars()
        hub_logging.set_verbosity_error()
    except ImportError:
        pass


silence()
