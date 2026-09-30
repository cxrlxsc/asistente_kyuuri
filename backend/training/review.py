"""
Revisa lo que le has dicho al asistente y corrige lo que entendió mal.
Tus frases se guardan en training/corrections.json y se usan en el siguiente entrenamiento.

Uso (desde la carpeta backend):
    python -m training.review
    python -m training.review --solo-dudosas   solo lo que entendió con poca confianza
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.core.config import settings
from app.learning import load_interactions
from app.nlu.text import normalize

CORRECTIONS_PATH = Path(__file__).parent / "corrections.json"
REVIEWED_PATH = settings.DATA_DIR / "reviewed.json"
DOUBTFUL = 0.9


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Revisar y corregir lo que entendió el asistente")
    parser.add_argument("--solo-dudosas", action="store_true", help=f"solo frases con confianza menor a {DOUBTFUL}")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    interactions = load_interactions()
    if not interactions:
        print(f"Todavía no hay nada registrado en {settings.DATA_DIR / 'interactions.jsonl'}.")
        print("Habla con el asistente y vuelve a ejecutar esto.")
        return

    corrections = load_json(CORRECTIONS_PATH, {})
    reviewed = set(load_json(REVIEWED_PATH, []))
    intents = sorted(json.loads((Path(__file__).parent / "intents.json").read_text(encoding="utf-8")).keys() - {"_slots"})

    # Una frase se revisa una sola vez, aunque la hayas dicho muchas veces
    seen, pending = Counter(), {}
    for entry in interactions:
        key = normalize(entry["texto"])
        if not key:
            continue
        seen[key] += 1
        if key not in reviewed and (not args.solo_dudosas or entry["confianza"] < DOUBTFUL):
            pending[key] = entry

    print(f"{len(interactions)} interacciones registradas, {len(pending)} frases por revisar.\n")
    print("Enter = estuvo bien (se agrega a tus datos) · número = intención correcta · s = saltar · q = salir")
    print("Intenciones: " + ", ".join(f"{i}={name}" for i, name in enumerate(intents)) + "\n")

    added = 0
    for key, entry in pending.items():
        print(f'  "{entry["texto"]}"  (dicho {seen[key]} vez/veces)')
        print(f'  entendió: {entry["intencion"]} ({entry["confianza"]:.0%}) -> {entry["respuesta"]}')
        answer = input("  > ").strip().lower()
        if answer == "q":
            break
        if answer == "s":
            continue
        if answer == "":
            intent = entry["intencion"]
        elif answer.isdigit() and int(answer) < len(intents):
            intent = intents[int(answer)]
        elif answer in intents:
            intent = answer
        else:
            print("  (no entendí la respuesta, la salto)\n")
            continue
        corrections.setdefault(intent, [])
        if entry["texto"] not in corrections[intent]:
            corrections[intent].append(entry["texto"])
            added += 1
        reviewed.add(key)
        print(f"  guardado como {intent}\n")

    save_json(CORRECTIONS_PATH, corrections)
    save_json(REVIEWED_PATH, sorted(reviewed))
    total = sum(len(v) for v in corrections.values())
    print(f"\n{added} frases nuevas ({total} en total en {CORRECTIONS_PATH.name}).")
    if added:
        print("Entrena para que las aprenda:  python -m training.train")


if __name__ == "__main__":
    main()
