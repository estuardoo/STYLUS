"""Bronze: sube data/raw (H&M) a GCS sin modificarla y deja un manifiesto verificable.

Uso:
  python ingestion/batch/upload_raw.py --manifest-only        # solo manifiesto local
  python ingestion/batch/upload_raw.py --bucket MI-BUCKET      # manifiesto + subida
Idempotente: `gcloud storage rsync` solo copia lo que cambió.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

CSV_FILES = ["articles.csv", "customers.csv", "transactions_train.csv", "sample_submission.csv"]


def sha256_rows(path, chunk=1 << 24):
    """Una sola lectura: hash SHA-256 y número de filas (sin cabecera)."""
    h, lines = hashlib.sha256(), 0
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
            lines += b.count(b"\n")
    return h.hexdigest(), lines - 1


def build_manifest(raw_dir: Path):
    items = []
    for name in CSV_FILES:
        p = raw_dir / name
        if not p.exists():
            continue
        with open(p, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        digest, rows = sha256_rows(p)
        items.append({
            "file": f"hm/{name}", "bytes": p.stat().st_size, "rows": rows,
            "columns": header, "sha256": digest, "format": "csv", "encoding": "utf-8",
        })
    # ponytail: solo conteo; sumar tamaños exige stat de 105k archivos (minutos en discos montados)
    n_img = sum(1 for _ in (raw_dir / "images").rglob("*.jpg"))
    items.append({"file": "hm/images/", "files": n_img, "format": "jpg"})
    return {
        "source": "H&M Personalized Fashion Recommendations (Kaggle)",
        "license_note": "Uso según reglas de la competencia Kaggle; no redistribuir.",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema_version": 1,
        "items": items,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=os.getenv("LOCAL_RAW_DIR", "data/raw"))
    ap.add_argument("--bucket", default=os.getenv("GCS_RAW_BUCKET"))
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--skip-images", action="store_true", help="sube solo los CSV (29 GB de imágenes después)")
    a = ap.parse_args()

    raw = Path(a.raw_dir)
    manifest = build_manifest(raw)
    out = Path("data/manifests")
    out.mkdir(parents=True, exist_ok=True)
    (out / "hm_raw_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps([{k: i[k] for k in i if k != "columns"} for i in manifest["items"]], indent=2))

    if a.manifest_only:
        return
    if not a.bucket:
        raise SystemExit("Falta --bucket o GCS_RAW_BUCKET")
    dst = f"gs://{a.bucket}/hm/"
    extra = ["--exclude", r"images/.*"] if a.skip_images else []
    subprocess.run(["gcloud", "storage", "rsync", "--recursive", *extra, str(raw), dst], check=True)
    subprocess.run(["gcloud", "storage", "cp", str(out / "hm_raw_manifest.json"),
                    f"gs://{a.bucket}/_manifests/hm_raw_manifest.json"], check=True)
    print("OK ->", dst)


if __name__ == "__main__":
    main()
