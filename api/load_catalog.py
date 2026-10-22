"""Carga el catálogo de servicio en la base de la API (SQLite local o Cloud SQL).

  python api/load_catalog.py --source local      # data/raw (H&M) -> base local
  python api/load_catalog.py --source bigquery   # retail_gold.v_catalog_serving -> Cloud SQL
Popularidad = ventas reales de los últimos 28 días. Precio demo y stock son sintéticos (declarados).
"""
import argparse
import csv
import datetime as dt
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sqlalchemy import text  # noqa: E402

FACTOR = float(os.getenv("PRICE_DEMO_FACTOR", "500"))
STOCK_DEMO = int(os.getenv("STOCK_DEMO", "50"))


def tail_transactions(path, days=28, tail_bytes=200_000_000):
    """Lee solo el final del archivo (está ordenado por fecha): sin recorrer 3.5 GB."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        f.seek(max(0, size - tail_bytes))
        f.readline()
        rows = [l.decode().rstrip("\n").split(",") for l in f if l.strip()]
    last = dt.date.fromisoformat(rows[-1][0])
    start = (last - dt.timedelta(days=days - 1)).isoformat()
    return [r for r in rows if r[0] >= start], start, last.isoformat()


def from_local(raw):
    tx, desde, hasta = tail_transactions(raw / "transactions_train.csv")
    pop, prices = Counter(), defaultdict(list)
    for t_dat, _cust, art, price, _ch in tx:
        pop[art] += 1
        prices[art].append(float(price))
    arts = list(csv.DictReader(open(raw / "articles.csv", encoding="utf-8")))
    by_type = defaultdict(list)
    for a in arts:
        if a["article_id"] in prices:
            by_type[a["product_type_name"]].append(statistics.median(prices[a["article_id"]]))
    out = []
    for a in arts:
        aid = a["article_id"]
        p = statistics.median(prices[aid]) if aid in prices else statistics.median(by_type.get(a["product_type_name"]) or [0.03])
        out.append({"article_id": aid, "prod_name": a["prod_name"], "product_type": a["product_type_name"],
                    "product_group": a["product_group_name"], "index_group": a["index_group_name"],
                    "section": a["section_name"], "colour": a["colour_group_name"], "detail_desc": a["detail_desc"],
                    "price_cents": max(99, round(p * FACTOR * 100)), "popularity": pop[aid], "stock": STOCK_DEMO})
    print(f"popularidad: {len(tx):,} líneas reales entre {desde} y {hasta}")
    return out


def from_bigquery():
    from google.cloud import bigquery
    q = f"SELECT * FROM `{os.environ['GCP_PROJECT_ID']}.retail_gold.v_catalog_serving`"
    return [dict(r) | {"stock": STOCK_DEMO} for r in bigquery.Client().query(q).result()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["local", "bigquery"], default="local")
    ap.add_argument("--raw-dir", default=os.getenv("LOCAL_RAW_DIR", "data/raw"))
    a = ap.parse_args()
    from main import engine, init_db
    init_db()
    rows = from_local(Path(a.raw_dir)) if a.source == "local" else from_bigquery()
    cols = list(rows[0])
    with engine.begin() as c:
        c.execute(text("DELETE FROM cart_items"))
        # ponytail: recarga completa; con pedidos previos se conservan los artículos ya referenciados
        c.execute(text("DELETE FROM articles WHERE article_id NOT IN (SELECT article_id FROM order_lines)"))
        ins = text(f"INSERT INTO articles ({', '.join(cols)}) VALUES ({', '.join(':' + x for x in cols)}) ON CONFLICT DO NOTHING")
        for i in range(0, len(rows), 5000):
            c.execute(ins, rows[i:i + 5000])
        n = c.execute(text("SELECT COUNT(*) FROM articles")).scalar_one()
    print(f"catálogo cargado: {n:,} artículos (precio demo = precio H&M x {FACTOR:g}; stock demo = {STOCK_DEMO})")


if __name__ == "__main__":
    main()
