import re
import unicodedata


def normalize(text: str) -> str:
    """Minúsculas, sin acentos ni signos, espacios simples. Se usa igual al entrenar y al predecir."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
