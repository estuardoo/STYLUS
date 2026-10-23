"""Streaming: re-emite transacciones reales de H&M como eventos 2026 hacia Pub/Sub.

- source_t_dat conserva la fecha original (2018-2020); event_time es la fecha simulada 2026.
- event_id determinista (sha1) => reintentos idempotentes; BigQuery/Dataflow deduplican.
- is_synthetic=true en el tiempo, no en el contenido: el producto, cliente y precio son reales.

Uso:
  python ingestion/streaming/replay_publisher.py --limit 20 --dry-run
  python ingestion/streaming/replay_publisher.py --limit 5000 --project P --topic retail-events
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import time
import uuid

SOURCE_START = dt.date(2018, 9, 20)  # primer día de transactions_train.csv


def to_event(row, line_no, target_start, run_id):
    src = dt.date.fromisoformat(row["t_dat"])
    day = target_start + (src - SOURCE_START) % dt.timedelta(days=365)
    now = dt.datetime.now(dt.timezone.utc)
    event_time = dt.datetime.combine(day, now.time(), dt.timezone.utc)
    eid = hashlib.sha1(f'{row["t_dat"]}|{row["customer_id"]}|{row["article_id"]}|{line_no}'.encode()).hexdigest()
    return {
        "event_id": eid,
        "event_type": "purchase",
        "event_time": event_time.isoformat(),
        "source_t_dat": row["t_dat"],
        "customer_id": row["customer_id"],
        "article_id": row["article_id"],
        "price": float(row["price"]),
        "sales_channel_id": int(row["sales_channel_id"]),
        "source_system": "hm_transactions_replay",
        "schema_version": 1,
        "is_synthetic": True,
        "simulation_run_id": run_id,
        "simulated_at": now.isoformat(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.join(os.getenv("LOCAL_RAW_DIR", "data/raw"), "transactions_train.csv"))
    ap.add_argument("--project", default=os.getenv("GCP_PROJECT_ID"))
    ap.add_argument("--topic", default=os.getenv("PUBSUB_TOPIC", "retail-events"))
    ap.add_argument("--target-start", default=os.getenv("REPLAY_TARGET_START", "2026-11-01"))
    ap.add_argument("--rate", type=float, default=float(os.getenv("REPLAY_EVENTS_PER_SEC", 50)))
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--skip", type=int, default=0, help="saltar N filas (reanudar)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    target = dt.date.fromisoformat(a.target_start)
    run_id = uuid.uuid4().hex[:12]
    publisher = topic_path = None
    if not a.dry_run:
        from google.cloud import pubsub_v1  # solo necesario en modo real
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(a.project, a.topic)

    sent, t0, futures = 0, time.time(), []
    with open(a.file, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if i < a.skip:
                continue
            if sent >= a.limit:
                break
            ev = to_event(row, i, target, run_id)
            data = json.dumps(ev).encode()
            if a.dry_run:
                print(data.decode())
            else:
                futures.append(publisher.publish(topic_path, data, event_type=ev["event_type"], event_id=ev["event_id"]))
            sent += 1
            if a.rate > 0:  # ponytail: ritmo fijo; usar flow control de Pub/Sub si se necesita > 1k ev/s
                time.sleep(max(0.0, sent / a.rate - (time.time() - t0)))
    errores = 0
    for f in futures:  # sin esperar, los últimos mensajes se pierden al terminar el proceso
        try:
            f.result(timeout=60)
        except Exception:
            errores += 1
    print(f"run={run_id} enviados={sent} confirmados={sent - errores if futures else 0} errores={errores} "
          f"seg={time.time() - t0:.1f}", flush=True)


if __name__ == "__main__":
    main()
