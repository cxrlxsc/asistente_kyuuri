"""
Ajusta (fine-tuning) el modelo neuronal de intenciones del asistente sobre training/intents.json.

Uso (desde la carpeta backend):
    python -m training.train
"""
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

from app.core.config import settings
from app.nlu.intent_model import best_device
from app.services.app_catalog import all_aliases as app_aliases
from app.services.folder_catalog import folder_aliases
from app.services.modes import mode_names
from app.services.site_catalog import site_aliases

DATA_PATH = Path(__file__).parent / "intents.json"
SAMPLES_PER_TEMPLATE = 5
REAL_PHRASE_WEIGHT = 3   # cuántas veces cuenta cada frase tuya corregida a mano
VALIDATION_SHARE = 0.15
EPOCHS = 10
BATCH_SIZE = 16
LEARNING_RATE = 4e-5
SEED = 42


def augment(text: str, rng: random.Random) -> str:
    """Variaciones naturales de cómo se le habla a un asistente de voz."""
    if rng.random() < 0.25:
        text = f"{rng.choice(settings.WAKE_WORDS)} {text}"
    if rng.random() < 0.15:
        text = f"{text} por favor"
    if rng.random() < 0.5:
        text = text.capitalize()
    return text


def build_dataset(rng: random.Random) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[str]]:
    """Separa por PLANTILLA: la validación usa frases cuya forma el modelo nunca vio al entrenar."""
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    slots = data.pop("_slots")
    # Apps, sitios y modos salen de sus catálogos, así no hay que copiarlos a mano aquí
    slots["app"] = sorted({alias for alias, _ in app_aliases()} | set(slots.get("app", [])))
    slots["site"] = [alias for alias, _ in site_aliases()]
    slots["mode"] = mode_names()
    slots["folder"] = sorted({alias for alias, _ in folder_aliases()} | set(slots.get("folder", [])))

    # Generador aparte para la división: así la validación no cambia al cambiar el nombre o la aumentación
    split_rng = random.Random(SEED)
    train, validation = [], []
    for intent, templates in data.items():
        templates = templates[:]
        split_rng.shuffle(templates)
        cut = max(1, round(len(templates) * VALIDATION_SHARE))
        for position, template in enumerate(templates):
            slot_names = [name for name in slots if "{" + name + "}" in template]
            variants = {
                augment(template.format(**{name: rng.choice(slots[name]) for name in slot_names}), rng)
                for _ in range(SAMPLES_PER_TEMPLATE)
            }
            (validation if position < cut else train).extend((text, intent) for text in variants)

    # Tus propias frases (de training/review.py) pesan más: son cómo hablas de verdad
    for intent, phrases in load_corrections().items():
        if intent not in data:
            print(f"  Aviso: la corrección con intención desconocida '{intent}' se ignora")
            continue
        for phrase in phrases:
            train += [(phrase, intent)] * REAL_PHRASE_WEIGHT
    return train, validation, list(data.keys())


def load_corrections() -> dict[str, list[str]]:
    path = Path(__file__).parent / "corrections.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@torch.inference_mode()
def evaluate(model, tokenizer, examples, label2id, device, verbose: bool) -> float:
    model.eval()
    hits = defaultdict(int)
    totals = defaultdict(int)
    for start in range(0, len(examples), 64):
        batch = examples[start:start + 64]
        inputs = tokenizer([t for t, _ in batch], padding=True, truncation=True, max_length=64, return_tensors="pt").to(device)
        predictions = model(**inputs).logits.argmax(dim=-1).tolist()
        for (_, label), predicted in zip(batch, predictions):
            totals[label] += 1
            hits[label] += int(predicted == label2id[label])
    if verbose:
        for label in sorted(totals):
            print(f"    {label:18} {hits[label]}/{totals[label]}")
    return sum(hits.values()) / sum(totals.values())


def main():
    rng = random.Random(SEED)
    device = best_device()

    train, validation, labels = build_dataset(rng)
    corrected = sum(len(v) for v in load_corrections().values())
    if corrected:
        print(f"Incluyendo {corrected} frases tuyas corregidas a mano (peso x{REAL_PHRASE_WEIGHT})")
    label2id = {label: i for i, label in enumerate(labels)}
    id2label = {i: label for label, i in label2id.items()}
    tokenizer = AutoTokenizer.from_pretrained(settings.INTENT_BASE_MODEL)
    print(f"Dataset: {len(train)} entrenamiento / {len(validation)} validación, {len(labels)} intenciones, dispositivo {device}")

    # 1) Medir: entrenar sin las plantillas de validación y ver cómo le va con frases nuevas
    print("\n== Paso 1: evaluación honesta ==")
    model = fit(train, tokenizer, label2id, id2label, device, validation)
    accuracy = evaluate(model, tokenizer, validation, label2id, device, verbose=True)
    print(f"Precisión estimada con frases nuevas: {accuracy:.1%}")
    del model
    torch.cuda.empty_cache()

    # 2) Modelo final: aprende de TODAS las plantillas (la medición anterior es su estimación)
    print("\n== Paso 2: modelo final con todos los datos ==")
    model = fit(train + validation, tokenizer, label2id, id2label, device)
    settings.INTENT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(settings.INTENT_MODEL_DIR)
    tokenizer.save_pretrained(settings.INTENT_MODEL_DIR)
    print(f"Modelo guardado en {settings.INTENT_MODEL_DIR}")


def fit(examples, tokenizer, label2id, id2label, device, validation=None):
    torch.manual_seed(SEED)
    model = AutoModelForSequenceClassification.from_pretrained(
        settings.INTENT_BASE_MODEL, num_labels=len(label2id), id2label=id2label, label2id=label2id
    ).to(device)

    def collate(batch):
        inputs = tokenizer([t for t, _ in batch], padding=True, truncation=True, max_length=64, return_tensors="pt")
        inputs["labels"] = torch.tensor([label2id[label] for _, label in batch])
        return inputs

    loader = DataLoader(examples, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    total_steps = EPOCHS * len(loader)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.1 * total_steps), total_steps)
    use_amp = device.type == "cuda"

    for epoch in range(1, EPOCHS + 1):
        model.train()
        started, running_loss = time.time(), 0.0
        for batch in loader:
            batch = batch.to(device)
            with torch.autocast(device.type, dtype=torch.bfloat16, enabled=use_amp):
                loss = model(**batch).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            running_loss += loss.item()
        line = f"Época {epoch}: pérdida {running_loss / len(loader):.4f} ({time.time() - started:.1f}s)"
        if validation:
            line += f" | validación {evaluate(model, tokenizer, validation, label2id, device, verbose=False):.1%}"
        print(line)
    return model


if __name__ == "__main__":
    main()
