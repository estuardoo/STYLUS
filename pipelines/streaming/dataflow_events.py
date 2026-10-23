"""Streaming (Apache Beam / Dataflow): Pub/Sub -> validación -> dedup por event_id ->
ventanas de 1 minuto con datos tardíos -> métricas en BigQuery (retail_ops) + DLQ.

GCP:
  python ops.py dataflow-iniciar   (arma todos los argumentos desde el Excel de control)
Local (prueba con archivo JSONL del replay):
  python ingestion/streaming/replay_publisher.py --limit 500 --dry-run > /tmp/ev.jsonl
  python pipelines/streaming/dataflow_events.py --input_file /tmp/ev.jsonl --output_dir /tmp/stream_out
"""
import argparse
import json
import time

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions
from apache_beam.transforms import trigger, window

REQUIRED = ("event_id", "event_type", "event_time", "article_id", "customer_id", "price")
METRICS_SCHEMA = ("window_start:TIMESTAMP,window_end:TIMESTAMP,eventos:INTEGER,compras:INTEGER,"
                  "importe:FLOAT,lag_p50_s:FLOAT,lag_p95_s:FLOAT,emitido:TIMESTAMP")
DLQ_SCHEMA = "recibido:TIMESTAMP,error:STRING,payload:STRING"


class Parse(beam.DoFn):
    """Valida el contrato del evento; lo inválido sale por la etiqueta 'dlq' (no se pierde)."""

    def process(self, raw, ts=beam.DoFn.TimestampParam):
        try:
            ev = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            faltan = [k for k in REQUIRED if ev.get(k) in (None, "")]
            if faltan:
                raise ValueError(f"faltan campos: {faltan}")
            ev["price"] = float(ev["price"])
            ev["_lag_s"] = max(0.0, time.time() - float(ts))  # publicación -> procesamiento
            yield ev
        except Exception as e:
            yield beam.pvalue.TaggedOutput("dlq", {"recibido": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                                   "error": str(e)[:300], "payload": str(raw)[:2000]})


class Metrics(beam.CombineFn):
    def create_accumulator(self):
        return [0, 0, 0.0, []]

    def add_input(self, acc, ev):
        acc[0] += 1
        acc[1] += ev["event_type"] == "purchase"
        acc[2] += ev["price"] * ev.get("qty", 1)
        if len(acc[3]) < 5000:  # ponytail: muestra acotada para percentiles; t-digest si se necesita exactitud
            acc[3].append(ev["_lag_s"])
        return acc

    def merge_accumulators(self, accs):
        out = self.create_accumulator()
        for a in accs:
            out[0] += a[0]; out[1] += a[1]; out[2] += a[2]; out[3] += a[3][: 5000 - len(out[3])]
        return out

    def extract_output(self, acc):
        lags = sorted(acc[3]) or [0.0]
        pct = lambda q: lags[min(len(lags) - 1, int(q * len(lags)))]
        return {"eventos": acc[0], "compras": acc[1], "importe": round(acc[2], 6),
                "lag_p50_s": round(pct(0.5), 3), "lag_p95_s": round(pct(0.95), 3)}


class AddWindow(beam.DoFn):
    def process(self, m, w=beam.DoFn.WindowParam):
        fmt = lambda t: t.to_utc_datetime().strftime("%Y-%m-%dT%H:%M:%S")
        yield {"window_start": fmt(w.start), "window_end": fmt(w.end), **m,
               "emitido": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())}


def build(p, a):
    if a.input_file:
        raw = (p | "Leer archivo" >> beam.io.ReadFromText(a.input_file)
                 | "Marca de tiempo" >> beam.Map(lambda l: window.TimestampedValue(l, time.time())))
    else:
        raw = p | "Leer Pub/Sub" >> beam.io.ReadFromPubSub(subscription=a.subscription)
    parsed = raw | "Validar" >> beam.ParDo(Parse()).with_outputs("dlq", main="ok")
    metrics = (parsed.ok
               | "Ventana 1 min" >> beam.WindowInto(
                   window.FixedWindows(60), allowed_lateness=300,
                   trigger=trigger.AfterWatermark(late=trigger.AfterCount(1)),
                   accumulation_mode=trigger.AccumulationMode.ACCUMULATING)
               | "Clave event_id" >> beam.Map(lambda e: (e["event_id"], e))
               | "Agrupar duplicados" >> beam.GroupByKey()
               | "Dedup" >> beam.Map(lambda kv: next(iter(kv[1])))
               | "Métricas" >> beam.CombineGlobally(Metrics()).without_defaults()
               | "Con ventana" >> beam.ParDo(AddWindow()))
    if a.output_dir:
        metrics | "Métricas a archivo" >> beam.Map(json.dumps) | beam.io.WriteToText(f"{a.output_dir}/metrics")
        parsed.dlq | "DLQ a archivo" >> beam.Map(json.dumps) | "Escribir DLQ" >> beam.io.WriteToText(f"{a.output_dir}/dlq")
    else:
        bq = dict(create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED,
                  write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND)
        metrics | "Métricas a BQ" >> beam.io.WriteToBigQuery(a.metrics_table, schema=METRICS_SCHEMA, **bq)
        parsed.dlq | "DLQ a BQ" >> beam.io.WriteToBigQuery(a.dlq_table, schema=DLQ_SCHEMA, **bq)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--subscription")
    ap.add_argument("--input_file")
    ap.add_argument("--output_dir")
    ap.add_argument("--project")
    ap.add_argument("--metrics_table", help="proyecto:dataset.stream_metrics_1m")
    ap.add_argument("--dlq_table", help="proyecto:dataset.stream_dlq")
    a, beam_args = ap.parse_known_args(argv)
    opts = PipelineOptions(beam_args + ([f"--project={a.project}"] if a.project else []), save_main_session=True)
    opts.view_as(StandardOptions).streaming = bool(a.subscription)
    with beam.Pipeline(options=opts) as p:
        build(p, a)


if __name__ == "__main__":
    main()
