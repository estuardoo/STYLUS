"""Evaluación del recomendador con split temporal (sin fuga de datos), MAP@12 como en la competencia H&M.

Test = última semana del dataset; entrenamiento = semanas previas.
  A) Popularidad: los 12 más vendidos de la última semana de entrenamiento (igual para todos).
  B) Recompra + popularidad: lo último que compró el cliente (8 semanas) y se completa con A.
  python pipelines/reco/baseline_eval.py            # escribe docs/evaluacion_recomendador.md
"""
import datetime as dt
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
from load_catalog import tail_transactions  # noqa: E402

K = 12


def apk(actual, pred, k=K):
    hits, score = 0, 0.0
    for i, p in enumerate(pred[:k]):
        if p in actual and p not in pred[:i]:
            hits += 1
            score += hits / (i + 1)
    return score / min(len(actual), k) if actual else 0.0


def main():
    raw = Path(os.getenv("LOCAL_RAW_DIR", ROOT / "data/raw"))
    tx, desde, hasta = tail_transactions(raw / "transactions_train.csv", days=63, tail_bytes=450_000_000)
    last = dt.date.fromisoformat(hasta)
    test_start = (last - dt.timedelta(days=6)).isoformat()
    pop_start = (last - dt.timedelta(days=13)).isoformat()
    train = [r for r in tx if r[0] < test_start]
    test = defaultdict(set)
    for t, c, a, *_ in tx:
        if t >= test_start:
            test[c].add(a)

    pop = [a for a, _ in Counter(r[2] for r in train if r[0] >= pop_start).most_common(K)]
    hist = defaultdict(list)
    for t, c, a, *_ in sorted(train, key=lambda r: r[0], reverse=True):
        if a not in hist[c]:
            hist[c].append(a)

    res = {"A_popularidad": 0.0, "B_recompra_mas_popularidad": 0.0}
    for c, actual in test.items():
        res["A_popularidad"] += apk(actual, pop)
        res["B_recompra_mas_popularidad"] += apk(actual, (hist.get(c, [])[:K] + [p for p in pop if p not in hist.get(c, [])])[:K])
    n = len(test)
    res = {k: round(v / n, 5) for k, v in res.items()}
    cold = sum(1 for c in test if c not in hist)
    meta = {"ventana_lectura": f"{desde} a {hasta}", "test": f"{test_start} a {hasta}", "clientes_test": n,
            "clientes_cold_start": cold, "lineas_entrenamiento": len(train), "map@12": res,
            "uplift_B_vs_A": round(res["B_recompra_mas_popularidad"] / res["A_popularidad"] - 1, 3) if res["A_popularidad"] else None}
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    md = [
        "# Evaluación del recomendador (datos reales H&M)", "",
        f"Split temporal: entrenamiento hasta {test_start} (exclusivo); test {test_start} a {hasta}. Métrica MAP@12.", "",
        "| Modelo | MAP@12 |", "|---|---:|",
        f"| A. Popularidad última semana | {res['A_popularidad']} |",
        f"| B. Recompra (8 semanas) + popularidad | {res['B_recompra_mas_popularidad']} |", "",
        f"Uplift B vs A: {meta['uplift_B_vs_A']:+.1%}. Clientes evaluados: {n:,}; sin historial (cold-start, reciben A): {cold:,}.",
        "", "Generado por `pipelines/reco/baseline_eval.py`. B es el modelo batch para clientes H&M con historial; la API de la tienda demo usa popularidad por grupo (perfil del historial) y popularidad global para cold-start.",
    ]
    (ROOT / "docs/evaluacion_recomendador.md").write_text("\n".join(md), encoding="utf-8")
    (ROOT / "docs/evaluacion_recomendador.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
