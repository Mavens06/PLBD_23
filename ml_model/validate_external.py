"""
validate_external.py — Validation du modèle ML ET du moteur de règles sur un
jeu de données EXTERNE (réel ou tiers), au-delà du dataset synthétique interne.

Le modèle de production est entraîné sur un dataset synthétique calibré sur
`rules/crop_catalog.py` : ses bons scores internes ne prouvent donc pas grand
chose (il réapprend les règles). Ce script permet de mesurer ML et règles
côte à côte sur des données qu'aucun des deux n'a vues — c'est la vraie preuve
de validité, et l'outil à utiliser dès que de vraies mesures terrain seront
collectées.

Usage :
    python ml_model/validate_external.py --csv mesures_reelles.csv
    python ml_model/validate_external.py --csv mesures_reelles.csv --disagreements

CSV attendu : colonnes `ph, humidity, temperature, ec, label`
(le label doit être l'une des 10 cultures cibles ; les autres lignes sont ignorées).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

try:
    from .model_registry import LEGACY_MODEL_PATH, LEGACY_SCALER_PATH
    from .rules.crop_catalog import CROP_CATALOG
    from .rules.engine import Measurement, top_k as rules_top_k
except ImportError:
    from model_registry import LEGACY_MODEL_PATH, LEGACY_SCALER_PATH
    from rules.crop_catalog import CROP_CATALOG
    from rules.engine import Measurement, top_k as rules_top_k

FEATURE_ORDER = ["ph", "humidity", "temperature", "ec"]
REQUIRED_COLS = FEATURE_ORDER + ["label"]


def _load_ml():
    """Charge (model, scaler) de production, ou (None, None) si indisponible."""
    if not (LEGACY_MODEL_PATH.exists() and LEGACY_SCALER_PATH.exists()):
        return None, None
    try:
        import joblib
        return joblib.load(LEGACY_MODEL_PATH), joblib.load(LEGACY_SCALER_PATH)
    except Exception as err:  # version pickle/sklearn incompatible, etc.
        print(f"[warn] modèle ML illisible ({err}) — validation des règles seulement.")
        return None, None


def _ml_topk(model, scaler, row: pd.Series, k: int) -> List[str]:
    X = scaler.transform([[float(row[f]) for f in FEATURE_ORDER]])
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)[0]
        order = sorted(zip(model.classes_, probs), key=lambda c: c[1], reverse=True)
        return [str(c) for c, _ in order[:k]]
    return [str(model.predict(X)[0])]


def _rules_topk(row: pd.Series, k: int) -> List[str]:
    m = Measurement(ph=float(row["ph"]), humidity=float(row["humidity"]),
                    temperature=float(row["temperature"]), ec=float(row["ec"]))
    return [s.crop for s in rules_top_k(m, k=k)]


def validate(csv_path: Path, show_disagreements: bool = False) -> dict:
    df = pd.read_csv(csv_path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"Colonnes manquantes dans {csv_path} : {missing}. Attendu : {REQUIRED_COLS}.")

    known = set(CROP_CATALOG)
    total = len(df)
    df = df[df["label"].isin(known)].reset_index(drop=True)
    ignored = total - len(df)
    if df.empty:
        raise SystemExit(f"Aucune ligne avec un label parmi les 10 cultures cibles : {sorted(known)}.")

    model, scaler = _load_ml()
    ml_ok = model is not None

    stats = {"n": len(df), "ignored": ignored,
             "ml_top1": 0, "ml_top3": 0, "rules_top1": 0, "rules_top3": 0,
             "disagreements": []}

    for _, row in df.iterrows():
        label = str(row["label"])
        rules_k = _rules_topk(row, 3)
        if label == rules_k[0]:
            stats["rules_top1"] += 1
        if label in rules_k:
            stats["rules_top3"] += 1
        ml_k: Optional[List[str]] = None
        if ml_ok:
            ml_k = _ml_topk(model, scaler, row, 3)
            if label == ml_k[0]:
                stats["ml_top1"] += 1
            if label in ml_k:
                stats["ml_top3"] += 1
            if ml_k[0] != rules_k[0]:
                stats["disagreements"].append(
                    {"label": label, "ml_top1": ml_k[0], "rules_top1": rules_k[0],
                     "ph": row["ph"], "humidity": row["humidity"],
                     "temperature": row["temperature"], "ec": row["ec"]}
                )

    _print_report(csv_path, stats, ml_ok, show_disagreements)
    return stats


def _pct(n: int, d: int) -> str:
    return f"{(100.0 * n / d):5.1f}%" if d else "   n/a"


def _print_report(csv_path: Path, s: dict, ml_ok: bool, show_disagreements: bool) -> None:
    n = s["n"]
    print(f"\nValidation externe — {csv_path}  ({n} lignes évaluées, {s['ignored']} ignorées)\n")
    print(f"{'Méthode':<18}{'top-1':>10}{'top-3':>10}")
    print("-" * 38)
    if ml_ok:
        print(f"{'ML (production)':<18}{_pct(s['ml_top1'], n):>10}{_pct(s['ml_top3'], n):>10}")
    else:
        print(f"{'ML (production)':<18}{'indispo':>10}{'indispo':>10}")
    print(f"{'Règles':<18}{_pct(s['rules_top1'], n):>10}{_pct(s['rules_top3'], n):>10}")
    print()
    if ml_ok:
        d = s["disagreements"]
        print(f"Désaccords ML vs règles sur le top-1 : {len(d)} / {n}")
        if show_disagreements and d:
            print(f"\n{'label':<16}{'ML top1':<16}{'règles top1':<16}  (ph,hum,temp,ec)")
            print("-" * 72)
            for r in d:
                print(f"{r['label']:<16}{r['ml_top1']:<16}{r['rules_top1']:<16}  "
                      f"({r['ph']},{r['humidity']},{r['temperature']},{r['ec']})")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Valide ML + règles sur un CSV externe.")
    p.add_argument("--csv", required=True, help="CSV externe (ph,humidity,temperature,ec,label).")
    p.add_argument("--disagreements", action="store_true",
                   help="Liste les cas où ML et règles divergent sur le top-1.")
    args = p.parse_args(argv)
    validate(Path(args.csv), show_disagreements=args.disagreements)
    return 0


if __name__ == "__main__":
    sys.exit(main())
