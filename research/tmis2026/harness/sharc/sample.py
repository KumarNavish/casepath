"""Draw the pilot sample from the ShARC TRAIN split: seed 20261110, 80 utterances per decision class
(Yes, No, Irrelevant, Inquire = the answer is a follow-up question). Writes runs/sharc/sample_ids.json.
Run with python3 -I. Usage: python3 -I sample.py <path to sharc_train.json>"""
import json
import random
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "runs" / "sharc"
SEED, PER_CLASS = 20261110, 80


def label(answer):
    return answer if answer in ("Yes", "No", "Irrelevant") else "Inquire"


def main(path):
    assert Path(path).name == "sharc_train.json", "train split only"
    rows = json.loads(Path(path).read_text())
    by = {}
    for r in sorted(rows, key=lambda r: r["utterance_id"]):
        by.setdefault(label(r["answer"]), []).append(r["utterance_id"])
    rng = random.Random(SEED)
    picked = {c: sorted(rng.sample(by[c], PER_CLASS)) for c in ("Yes", "No", "Irrelevant", "Inquire")}
    order = [u for c in picked for u in picked[c]]
    rng.shuffle(order)
    dev60 = order[:60]  # development subset for prompt revisions (first 60 of a seeded shuffle)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample_ids.json").write_text(json.dumps(
        {"split": "train", "seed": SEED, "per_class": PER_CLASS, "pool_sizes": {c: len(v) for c, v in by.items()},
         "ids_by_class": picked, "order": order, "dev60": dev60}, indent=1) + "\n")
    print({c: len(v) for c, v in by.items()}, len(order))


if __name__ == "__main__":
    main(sys.argv[1])
