import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ..core import quiet  # noqa: F401  (silencia los avisos de transformers al importarse)
from ..core.config import settings


def best_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


class IntentModel:
    """Clasificador neuronal propio (BETO ajustado con training/train.py)."""

    def __init__(self):
        model_dir = settings.INTENT_MODEL_DIR
        if not (model_dir / "config.json").exists():
            raise RuntimeError(
                f"No existe el modelo en {model_dir}. Entrénalo primero con: python -m training.train"
            )
        self.device = best_device()
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(self.device).eval()

    @torch.inference_mode()
    def predict(self, text: str) -> tuple[str, float]:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=64).to(self.device)
        probabilities = self.model(**inputs).logits.softmax(dim=-1)[0]
        confidence, index = probabilities.max(dim=-1)
        return self.model.config.id2label[index.item()], confidence.item()
