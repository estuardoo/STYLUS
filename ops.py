#!/usr/bin/env python3
"""Orquestador de la plataforma (Windows, Linux, Mac y Cloud Shell).
Fuente única de configuración: config/control_plataforma.json (editable con 'python ops.py panel')

  python ops.py config [--check]   Excel -> archivos generados (Terraform, ops, API)
  python ops.py estado             nombres y valores efectivos
  python ops.py local              tienda en http://localhost:8080 con el catálogo H&M local
  python ops.py bootstrap          APIs, red, bucket de estado y terraform init
  python ops.py plan | apply | destroy [--yes]
  python ops.py subir-datos [--con-imagenes]
  python ops.py bronze | silver | gold
  python ops.py api                imagen + Cloud Run + carga de catálogo
  python ops.py catalogo           solo carga de catálogo (job)
  python ops.py replay [--limite N]
  python ops.py dataflow-iniciar | dataflow-detener
  python ops.py verificar          tablas/columnas reales vs Excel + prueba de la API
  python ops.py github             valor de GCP_WIF_PROVIDER para GitHub Actions
  python ops.py costo-real         vista de costo real por pedido (requiere billing export)
  python ops.py todo [--yes]       bootstrap, apply, bronze, silver, gold, api, verificar
  python ops.py panel              panel web local (editar JSON de control + desplegar con botones)
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import string
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_JSON = ROOT / "config/control_plataforma.json"
GEN = ROOT / "config/generated/plataforma.json"
TFVARS = ROOT / "infra/terraform/plataforma.auto.tfvars.json"
SEED = ROOT / "api/seed.json"
TF_DIR = ROOT / "infra/terraform"
LOG = []  # (paso, estado, segundos, detalle)

SCOPES = {"proyecto": "project", "project": "project"}
LEGACY_BQ = {"INT64": "INTEGER", "FLOAT64": "FLOAT", "BOOL": "BOOLEAN"}
BQ_TYPES = {"STRING", "INT64", "FLOAT64", "BOOL", "DATE", "TIMESTAMP", "NUMERIC", "BYTES", "JSON", "DATETIME"}


class ConfigError(Exception):
    pass


# ======================= JSON -> configuración =======================
def _cast(clave, valor, tipo):
    try:
        if tipo == "numero":
            n = float(valor)
            return int(n) if n.is_integer() else n
        if tipo == "booleano":
            return valor if isinstance(valor, bool) else str(valor).strip().lower() in ("true", "verdadero", "si", "sí", "1")
        if tipo == "lista_numeros":
            return [float(x) for x in str(valor).split(";") if x.strip()]
        if tipo == "mapa":
            return dict(kv.split("=", 1) for kv in str(valor).split(";") if kv.strip())
        return "" if valor is None else str(valor)
    except Exception as e:
        raise ConfigError(f"Parametros/{clave}: valor '{valor}' no es {tipo} ({e})")


def read_config():
    need = ["parametros", "apis", "cuentas_servicio", "permisos", "usuarios", "datasets", "tablas", "columnas", "secretos"]
    try:
        data = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"No existe {CONFIG_JSON}. Editar con 'python ops.py panel' o copiar config/control_plataforma.json.example.")
    falta = [s for s in need if s not in data]
    if falta:
        raise ConfigError(f"Faltan secciones en {CONFIG_JSON.name}: {falta}")
    # las claves de build_config() siguen en mayúscula/capitalizado histórico (Parametros, APIs, ...)
    alias = {"parametros": "Parametros", "apis": "APIs", "cuentas_servicio": "Cuentas_Servicio",
              "permisos": "Permisos", "usuarios": "Usuarios", "datasets": "Datasets",
              "tablas": "Tablas", "columnas": "Columnas", "secretos": "Secretos"}
    return {alias[k]: data[k] for k in need}


def build_config(x):
    errs = []
    p = {r["clave"]: _cast(r["clave"], r["valor"], r["tipo"]) for r in x["Parametros"]}
    req = ["project_id", "region", "env", "pubsub_topic", "artifact_repo", "cloudrun_service"]
    errs += [f"Parametros/{k}: obligatorio" for k in req if p.get(k) in ("", None)]
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", str(p.get("project_id", ""))):
        errs.append("Parametros/project_id: 6-30 caracteres, minúsculas, dígitos o guiones")
    if p.get("billing_account") and not re.fullmatch(r"[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}", p["billing_account"]):
        errs.append("Parametros/billing_account: formato XXXXXX-XXXXXX-XXXXXX")

    ds = {r["clave"]: {"dataset_id": r["dataset_id"], "description": r["descripcion"],
                       "delete_contents_on_destroy": _cast("dataset", r["borrar_contenido_en_destroy"], "booleano")}
          for r in x["Datasets"]}
    sas = {r["clave"]: {"account_id": r["account_id"], "display_name": r["nombre"], "description": r["descripcion"]}
           for r in x["Cuentas_Servicio"]}
    for k, s in sas.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", s["account_id"]):
            errs.append(f"Cuentas_Servicio/{k}: account_id inválido")

    tables, cols = x["Tablas"], x["Columnas"]
    tkeys = {(t["motor"], t["dataset"], t["tabla"]) for t in tables}
    for c in cols:
        if (c["motor"], c["dataset"], c["tabla"]) not in tkeys:
            errs.append(f"Columnas: {c['dataset']}.{c['tabla']}.{c['columna']} no está en la hoja Tablas")
        if c["motor"] == "bigquery" and c["tipo"].upper() not in BQ_TYPES:
            errs.append(f"Columnas: tipo BigQuery inválido {c['tipo']} en {c['tabla']}.{c['columna']}")
    tf_tables = []
    for t in tables:
        if t["motor"] == "bigquery" and t["dataset"] not in ds:
            errs.append(f"Tablas/{t['tabla']}: dataset '{t['dataset']}' no existe en la hoja Datasets")
        if t["creado_por"] != "terraform":
            continue
        schema = [{"name": c["columna"], "type": LEGACY_BQ.get(c["tipo"].upper(), c["tipo"].upper()),
                   "mode": c["modo"] or "NULLABLE", "description": c["descripcion"]}
                  for c in cols if (c["motor"], c["dataset"], c["tabla"]) == (t["motor"], t["dataset"], t["tabla"])]
        if not schema:
            errs.append(f"Tablas/{t['tabla']}: creada por terraform pero sin columnas")
        tf_tables.append({"dataset": t["dataset"], "table_id": t["tabla"], "description": t["descripcion"],
                          "partition_field": t["particion"], "clustering": [c for c in str(t["cluster"]).split(",") if c],
                          "schema": json.dumps(schema, ensure_ascii=False)})
    if p.get("pubsub_bq_table") not in {f"{t['dataset']}.{t['table_id']}" for t in tf_tables}:
        errs.append("Parametros/pubsub_bq_table debe ser una tabla con creado_por = terraform")

    team, app_users = [], []
    iam = []
    for u in x["Usuarios"]:
        if u["tipo"] == "app":
            app_users.append({"user_id": u["id"], "nombre": u["nombre"], "saldo_inicial_cents": int(u["saldo_inicial_cents"] or 0)})
        elif u["tipo"] == "gcp":
            team.append({k: u[k] for k in ("id", "nombre", "email", "perfil", "roles_gcp")})
            if u["email"]:
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", u["email"]):
                    errs.append(f"Usuarios/{u['id']}: email inválido")
                for role in filter(None, (r.strip() for r in str(u["roles_gcp"]).split(";"))):
                    iam.append({"member": f"user:{u['email']}", "role": role, "scope": "project", "motivo": f"Equipo: {u['perfil']}"})

    valid_scope = re.compile(r"project|bucket:(raw|lake)|dataset:\w+|topic:(events|dlq)|subscription:(bq|dataflow)|sa:\w+")
    for r in x["Permisos"]:
        if r["gestion"] != "excel":
            continue
        scope = SCOPES.get(r["alcance"], r["alcance"].replace("cuenta:", "sa:"))
        iam.append({"member": r["principal"], "role": r["rol"], "scope": scope, "motivo": r["motivo"]})
    for b in iam:
        where = f"Permisos/{b['member']} {b['role']}"
        if not b["role"].startswith("roles/"):
            errs.append(f"{where}: el rol debe empezar con roles/")
        if not valid_scope.fullmatch(b["scope"]):
            errs.append(f"{where}: alcance inválido '{b['scope']}'")
        if b["scope"].startswith("dataset:") and b["scope"][8:] not in ds:
            errs.append(f"{where}: dataset '{b['scope'][8:]}' no existe")
        if b["scope"].startswith("sa:") and b["scope"][3:] not in sas:
            errs.append(f"{where}: cuenta '{b['scope'][3:]}' no existe")
        m = b["member"]
        if m.startswith("sa:") and m[3:] not in sas:
            errs.append(f"{where}: cuenta '{m[3:]}' no existe en Cuentas_Servicio")
        elif not (m.startswith(("sa:", "user:", "group:", "serviceAccount:")) or m in ("compute-default", "pubsub-agent")):
            errs.append(f"{where}: principal inválido")
        if b["role"] == "roles/owner" and m.startswith("user:"):
            errs.append(f"{where}: roles/owner no se puede otorgar por API; usar invitación en consola")
    if p.get("deployer_sa_key") not in sas:
        errs.append("Parametros/deployer_sa_key no existe en Cuentas_Servicio")
    if errs:
        raise ConfigError("\n  - " + "\n  - ".join(errs))

    pid = p["project_id"]
    derived = {
        "bucket_raw": f"{pid}-{p['bucket_raw_suffix']}", "bucket_lake": f"{pid}-{p['bucket_lake_suffix']}",
        "bucket_tfstate": f"{pid}-{p['bucket_tfstate_suffix']}", "tfstate_prefix": f"{p['tfstate_prefix']}/{p['env']}",
        "image_repo": f"{p['region']}-docker.pkg.dev/{pid}/{p['artifact_repo']}/{p['cloudrun_service']}",
        "sa_emails": {k: f"{s['account_id']}@{pid}.iam.gserviceaccount.com" for k, s in sas.items()},
        "datasets": {k: v["dataset_id"] for k, v in ds.items()},
    }
    tfvars = {
        "project_id": pid, "region": p["region"], "env": p["env"], "labels": p["labels"],
        "apis": sorted(r["api"] for r in x["APIs"]),
        "billing_account": p["billing_account"], "monthly_budget_usd": p["monthly_budget_usd"],
        "budget_thresholds": p["budget_thresholds"], "budget_topic": p["budget_topic"],
        "buckets": {"raw": derived["bucket_raw"], "lake": derived["bucket_lake"]},
        "force_destroy_buckets": p["force_destroy_buckets"], "images_nearline_days": p["images_nearline_days"],
        "noncurrent_version_days": p["noncurrent_version_days"],
        "datasets": ds, "tables": tf_tables,
        "pubsub": {"topic": p["pubsub_topic"], "dlq_topic": p["pubsub_dlq_topic"], "bq_subscription": p["pubsub_bq_subscription"],
                   "bq_table": p["pubsub_bq_table"], "dataflow_subscription": p["pubsub_dataflow_subscription"],
                   "dlq_subscription": p["pubsub_dlq_subscription"], "max_delivery_attempts": p["pubsub_max_delivery_attempts"],
                   "retention": p["pubsub_retention"]},
        "service_accounts": sas,
        "iam": [{k: b[k] for k in ("member", "role", "scope")} for b in iam],
        "artifact_repo": p["artifact_repo"],
        "cloudsql": {"enabled": p["cloudsql_enabled"], "instance": p["cloudsql_instance"], "version": p["cloudsql_version"],
                     "tier": p["cloudsql_tier"], "ha": p["cloudsql_ha"], "disk_gb": p["cloudsql_disk_gb"],
                     "db_name": p["cloudsql_db_name"], "user": p["cloudsql_user"], "backup_start": p["cloudsql_backup_start"],
                     "deletion_protection": p["cloudsql_deletion_protection"]},
        "secrets": {"db_url": p["secret_db_url"], "admin_token": p["secret_admin_token"]},
        "cloudrun": {"enabled": p["cloudsql_enabled"], "service": p["cloudrun_service"], "image": p["api_image"],
                     "min_instances": p["api_min_instances"], "max_instances": p["api_max_instances"],
                     "cpu": str(p["api_cpu"]), "memory": p["api_memory"], "public": p["api_public"]},
        "api_env": {"ASSISTANT_MODE": p["assistant_mode"], "GEMINI_MODEL": p["gemini_model"],
                    "GEMINI_LOCATION": p["gemini_location"], "PRICE_DEMO_FACTOR": str(p["price_demo_factor"]),
                    "DEMO_TOPUP_MAX_CENTS": str(p["demo_topup_max_cents"])},
        "github": {"repo": p["github_repo"], "pool_id": f"{p['wif_pool']}-{p['env']}", "deployer_key": p["deployer_sa_key"]},
    }
    full = {"params": p, "derived": derived, "team": team, "app_users": app_users, "iam": iam,
            "tables": tables, "columns": cols, "secrets": x["Secretos"], "terraform": tfvars}
    return full, tfvars, {"users": app_users}


def _dump(o):
    return json.dumps(o, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def cmd_config(a):
    full, tfvars, seed = build_config(read_config())
    files = {GEN: _dump(full), TFVARS: _dump(tfvars), SEED: _dump(seed)}
    stale = [str(f.relative_to(ROOT)) for f, txt in files.items() if not f.exists() or f.read_text(encoding="utf-8") != txt]
    if a.check:
        if stale:
            raise ConfigError(f"Generados desactualizados respecto al Excel: {stale}. Ejecutar: python ops.py config")
        print("config OK: generados al día")
        return
    for f, txt in files.items():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt, encoding="utf-8")
    print(f"config OK · {len(full['iam'])} permisos · {len(tfvars['tables'])} tablas Terraform · {len(seed['users'])} usuarios app")
    print("actualizados:", stale or "ninguno (sin cambios)")
    if full["params"]["project_id"] == "tu-proyecto-gcp":
        print("AVISO: project_id sigue en 'tu-proyecto-gcp'. Editar config/control_plataforma.json (o 'python ops.py panel') antes de desplegar.")


def cfg(cloud=True):
    if not GEN.exists():
        raise ConfigError("Falta config/generated/plataforma.json. Ejecutar: python ops.py config")
    if CONFIG_JSON.exists() and CONFIG_JSON.stat().st_mtime > GEN.stat().st_mtime + 1:
        print("AVISO: config/control_plataforma.json es más reciente que los generados; se regeneran.")
        cmd_config(argparse.Namespace(check=False))
    c = json.loads(GEN.read_text(encoding="utf-8"))
    if cloud and c["params"]["project_id"] == "tu-proyecto-gcp":
        raise ConfigError("project_id = 'tu-proyecto-gcp'. Definirlo en config/control_plataforma.json (sección parametros) o con 'python ops.py panel'.")
    return c


# ======================= utilidades =======================
def exe(name):
    path = shutil.which(name)
    if not path:
        raise ConfigError(f"No se encontró '{name}' en el PATH. Ver docs/DEPLOY.md (Herramientas).")
    return path


def run(cmd, check=True, capture=False, env=None, input_text=None):
    cmd = [exe(cmd[0])] + [str(c) for c in cmd[1:]]
    print("$", " ".join(Path(cmd[0]).stem if i == 0 else c for i, c in enumerate(cmd)), flush=True)
    r = subprocess.run(cmd, text=True, capture_output=capture, env={**os.environ, **(env or {})}, input=input_text)
    if check and r.returncode != 0:
        raise ConfigError(f"Falló: {' '.join(cmd[1:3])}...\n{(r.stderr or '')[-2000:]}")
    return r


def terraform():
    return "terraform" if shutil.which("terraform") else "tofu"


def tf_outputs():
    r = run([terraform(), f"-chdir={TF_DIR}", "output", "-json"], capture=True)
    return {k: v["value"] for k, v in json.loads(r.stdout or "{}").items()}


def step(name):
    def deco(fn):
        def wrapper(*args, **kw):
            t0 = time.time()
            print(f"\n=== {name} ===", flush=True)
            try:
                out = fn(*args, **kw)
                LOG.append((name, "OK", time.time() - t0, out if isinstance(out, str) else ""))
                return out
            except BaseException as e:
                LOG.append((name, "ERROR", time.time() - t0, str(e).strip().splitlines()[0][:80] if str(e) else type(e).__name__))
                raise
        return wrapper
    return deco


def print_log():
    if not LOG:
        return
    print("\n| Paso | Estado | Segundos | Detalle |\n|---|---|---:|---|")
    for n, s, t, d in LOG:
        print(f"| {n} | {s} | {t:,.1f} | {d} |")


def sql_vars(c):
    p, d = c["params"], c["derived"]
    return {"PROJECT": p["project_id"], "RAW_BUCKET": d["bucket_raw"], "LAKE_BUCKET": d["bucket_lake"],
            "PRICE_DEMO_FACTOR": p["price_demo_factor"], "BILLING_TABLE": p.get("billing_export_table", ""),
            **{f"DS_{k.upper()}": v for k, v in d["datasets"].items()}}


def run_sql(c, rel):
    from google.cloud import bigquery
    sql = string.Template((ROOT / rel).read_text(encoding="utf-8")).safe_substitute(sql_vars(c))
    left = re.findall(r"\$\{\w+\}", sql)
    if left:
        raise ConfigError(f"{rel}: variables sin valor {sorted(set(left))}")
    print(f"BigQuery <- {rel}", flush=True)
    client = bigquery.Client(project=c["params"]["project_id"], location=c["params"]["region"])
    rows = list(client.query(sql).result())
    for r in rows[:10]:
        print("  ", dict(r.items()))
    return f"{rel}"


# ======================= comandos =======================
def cmd_estado(a):
    c = cfg(cloud=False)
    p, d = c["params"], c["derived"]
    filas = [("Proyecto", p["project_id"]), ("Región / ambiente", f"{p['region']} / {p['env']}"),
             ("Bucket Bronze", d["bucket_raw"]), ("Bucket Silver/Gold", d["bucket_lake"]),
             ("Estado Terraform", f"gs://{d['bucket_tfstate']}/{d['tfstate_prefix']}"),
             ("Datasets", ", ".join(d["datasets"].values())), ("Tópico", p["pubsub_topic"]),
             ("Imagen API", d["image_repo"]), ("Asistente", f"{p['assistant_mode']} ({p['gemini_model']})"),
             ("Cloud SQL", f"{p['cloudsql_tier']} habilitado={p['cloudsql_enabled']}"),
             ("Permisos IAM", len(c["iam"])), ("Usuarios app", ", ".join(u["user_id"] for u in c["app_users"])),
             ("Equipo con email", sum(1 for t in c["team"] if t["email"]))]
    print("| Elemento | Valor |\n|---|---|")
    for k, v in filas:
        print(f"| {k} | {v} |")


@step("bootstrap")
def cmd_bootstrap(a):
    c = cfg()
    p, d = c["params"], c["derived"]
    pid = p["project_id"]
    run(["gcloud", "config", "set", "project", pid])
    run(["gcloud", "services", "enable", *c["terraform"]["apis"], "--project", pid])
    r = run(["gcloud", "compute", "networks", "subnets", "update", p["dataproc_subnet"], "--region", p["region"],
             "--enable-private-ip-google-access", "--project", pid], check=False)
    if r.returncode:
        print("AVISO: no se pudo activar Private Google Access (¿existe la red default?). Serverless Spark lo necesita.")
    run(["gcloud", "auth", "application-default", "set-quota-project", pid], check=False)
    bucket = f"gs://{d['bucket_tfstate']}"
    if run(["gcloud", "storage", "buckets", "describe", bucket, "--project", pid], check=False, capture=True).returncode:
        run(["gcloud", "storage", "buckets", "create", bucket, f"--location={p['region']}", "--uniform-bucket-level-access",
             "--public-access-prevention", "--project", pid])
        run(["gcloud", "storage", "buckets", "update", bucket, "--versioning"])
    run([terraform(), f"-chdir={TF_DIR}", "init", "-reconfigure", "-input=false",
         f"-backend-config=bucket={d['bucket_tfstate']}", f"-backend-config=prefix={d['tfstate_prefix']}"])
    return bucket


@step("terraform plan")
def cmd_plan(a):
    cfg()
    run([terraform(), f"-chdir={TF_DIR}", "plan", "-input=false"])


@step("terraform apply")
def cmd_apply(a):
    cfg()
    run([terraform(), f"-chdir={TF_DIR}", "apply", "-input=false"] + (["-auto-approve"] if a.yes else []))
    o = tf_outputs()
    return f"api_url={o.get('api_url', '')}"


@step("terraform destroy")
def cmd_destroy(a):
    cfg()
    run([terraform(), f"-chdir={TF_DIR}", "destroy", "-input=false"] + (["-auto-approve"] if a.yes else []))


@step("subir datos a Bronze")
def cmd_subir(a):
    c = cfg()
    p = c["params"]
    args = [sys.executable, str(ROOT / "ingestion/batch/upload_raw.py"), "--raw-dir", p["local_raw_dir"],
            "--bucket", c["derived"]["bucket_raw"]]
    if not a.con_imagenes:
        args.append("--skip-images")
    run(args)


def _need_raw(c):
    obj = f"gs://{c['derived']['bucket_raw']}/hm/transactions_train.csv"
    if run(["gcloud", "storage", "ls", obj], check=False, capture=True).returncode:
        raise ConfigError(f"No existe {obj}. Ejecutar primero desde la PC con los datos: python ops.py subir-datos")


@step("bronze (BigQuery)")
def cmd_bronze(a):
    c = cfg()
    _need_raw(c)
    return run_sql(c, "sql/bronze/01_bronze_hm.sql")


@step("silver (Spark + BigQuery)")
def cmd_silver(a):
    c = cfg()
    p, d = c["params"], c["derived"]
    batch = "silver-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run(["gcloud", "dataproc", "batches", "submit", "pyspark", str(ROOT / "pipelines/batch/silver_hm.py"),
         "--project", p["project_id"], "--region", p["region"], "--version", p["dataproc_runtime"], "--batch", batch,
         "--subnet", p["dataproc_subnet"], "--service-account", d["sa_emails"]["pipeline"],
         "--deps-bucket", f"gs://{d['bucket_lake']}",
         "--", "--raw", f"gs://{d['bucket_raw']}/hm", "--out", f"gs://{d['bucket_lake']}/silver"])
    run_sql(c, "sql/silver/01_load_silver.sql")
    return batch


@step("gold (BigQuery)")
def cmd_gold(a):
    c = cfg()
    run_sql(c, "sql/gold/01_gold_model.sql")
    run_sql(c, "sql/gold/02_kpi_views.sql")


def _job_args(c, image):
    p, d, o = c["params"], c["derived"], tf_outputs()
    if not o.get("cloudsql_connection"):
        raise ConfigError("Cloud SQL no está creado (cloudsql_enabled = false o falta apply)")
    return ["--image", image, "--region", p["region"], "--project", p["project_id"],
            "--service-account", d["sa_emails"]["api"], "--set-cloudsql-instances", o["cloudsql_connection"],
            "--set-secrets", f"DATABASE_URL={p['secret_db_url']}:latest",
            "--set-env-vars", (f"GCP_PROJECT_ID={p['project_id']},STOCK_DEMO={p['stock_demo']},"
                               f"PRICE_DEMO_FACTOR={p['price_demo_factor']},"
                               f"CATALOG_VIEW={p['project_id']}.{d['datasets']['gold']}.v_catalog_serving"),
            "--command", "python", "--args", "load_catalog.py,--source,bigquery",
            "--task-timeout", "1800", "--max-retries", "0"]


@step("catálogo Gold -> Cloud SQL (job)")
def cmd_catalogo(a, image=None):
    c = cfg()
    p = c["params"]
    if not image:
        image = run(["gcloud", "run", "services", "describe", p["cloudrun_service"], "--region", p["region"], "--project",
                     p["project_id"], "--format", "value(spec.template.spec.containers[0].image)"], capture=True).stdout.strip()
    run(["gcloud", "run", "jobs", "deploy", p["catalog_job"], *_job_args(c, image)])
    run(["gcloud", "run", "jobs", "execute", p["catalog_job"], "--region", p["region"], "--project", p["project_id"], "--wait"])


@step("API: imagen + Cloud Run")
def cmd_api_deploy(a):
    c = cfg()
    p, d = c["params"], c["derived"]
    image = f"{d['image_repo']}:{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run(["gcloud", "builds", "submit", str(ROOT / "api"), "--tag", image, "--project", p["project_id"]])
    run(["gcloud", "run", "deploy", p["cloudrun_service"], "--image", image, "--region", p["region"],
         "--project", p["project_id"], "--quiet"])
    return image


def cmd_api(a):
    image = cmd_api_deploy(a)
    cmd_catalogo(a, image=image)
    url = tf_outputs().get("api_url", "")
    print(f"\nTienda: {url}\nOpenAPI: {url}/docs")


@step("replay de eventos 2026")
def cmd_replay(a):
    c = cfg()
    p = c["params"]
    run([sys.executable, str(ROOT / "ingestion/streaming/replay_publisher.py"),
         "--file", str(Path(p["local_raw_dir"]) / "transactions_train.csv"), "--project", p["project_id"],
         "--topic", p["pubsub_topic"], "--target-start", p["replay_target_start"],
         "--rate", p["replay_events_per_sec"], "--limit", a.limite or p["replay_limit"]])


@step("dataflow iniciar")
def cmd_dataflow_start(a):
    c = cfg()
    p, d = c["params"], c["derived"]
    ops = f"{p['project_id']}:{d['datasets']['ops']}"
    run([sys.executable, str(ROOT / "pipelines/streaming/dataflow_events.py"), "--runner", "DataflowRunner",
         "--project", p["project_id"], "--region", p["region"], "--temp_location", f"gs://{d['bucket_lake']}/tmp",
         "--job_name", p["dataflow_job_name"],
         "--subscription", f"projects/{p['project_id']}/subscriptions/{p['pubsub_dataflow_subscription']}",
         "--metrics_table", f"{ops}.stream_metrics_1m", "--dlq_table", f"{ops}.stream_dlq",
         "--service_account_email", d["sa_emails"]["pipeline"], "--machine_type", p["dataflow_machine_type"],
         "--max_num_workers", p["dataflow_max_workers"], "--streaming", "--enable_streaming_engine"])


@step("dataflow detener")
def cmd_dataflow_stop(a):
    p = cfg()["params"]
    ids = run(["gcloud", "dataflow", "jobs", "list", "--region", p["region"], "--project", p["project_id"], "--status", "active",
               f"--filter=name={p['dataflow_job_name']}", "--format", "value(id)"], capture=True).stdout.split()
    for i in ids:
        run(["gcloud", "dataflow", "jobs", "drain", i, "--region", p["region"], "--project", p["project_id"]])
    return f"{len(ids)} job(s) drenados"


@step("verificar")
def cmd_verificar(a):
    from google.cloud import bigquery
    c = cfg()
    p, d = c["params"], c["derived"]
    client = bigquery.Client(project=p["project_id"], location=p["region"])
    norm = lambda t: {"INTEGER": "INT64", "FLOAT": "FLOAT64", "BOOLEAN": "BOOL"}.get(t, t)
    real = {}
    for key, dsid in d["datasets"].items():
        try:
            q = f"SELECT table_name, column_name, data_type FROM `{p['project_id']}.{dsid}`.INFORMATION_SCHEMA.COLUMNS"
            for r in client.query(q).result():
                real.setdefault((key, r.table_name), {})[r.column_name] = norm(r.data_type)
        except Exception as e:
            print(f"AVISO: dataset {dsid}: {type(e).__name__}")
    filas, ok = [], 0
    for t in (t for t in c["tables"] if t["motor"] == "bigquery"):
        esperado = {x["columna"]: x["tipo"].upper() for x in c["columns"]
                    if (x["motor"], x["dataset"], x["tabla"]) == ("bigquery", t["dataset"], t["tabla"])}
        have = real.get((t["dataset"], t["tabla"]))
        if have is None:
            estado = "opcional" if "opcional" in t["creado_por"] else f"FALTA → {t['creado_por']}"
            filas.append((f"{t['dataset']}.{t['tabla']}", estado, "", ""))
            continue
        faltan = sorted(set(esperado) - set(have))
        sobran = sorted(set(have) - set(esperado))
        tipos = sorted(k for k in set(esperado) & set(have) if esperado[k] != have[k])
        good = not (faltan or sobran or tipos)
        ok += good
        filas.append((f"{t['dataset']}.{t['tabla']}", "OK" if good else "DIFERENTE",
                      ", ".join(faltan + [f"tipo:{k}" for k in tipos]), ", ".join(sobran)))
    print("| Tabla | Estado | Falta / tipo distinto | Sobra |\n|---|---|---|---|")
    for f in filas:
        print("| " + " | ".join(f) + " |")
    url = ""
    try:
        url = tf_outputs().get("api_url", "")
    except ConfigError:
        pass
    if url:
        for path in ("/health", "/ready"):
            try:
                with urllib.request.urlopen(url + path, timeout=30) as r:
                    print(f"API {path}: {r.status} {r.read().decode()[:120]}")
            except Exception as e:
                print(f"API {path}: ERROR {e}")
    return f"{ok}/{len(filas)} tablas conformes"


def cmd_github(a):
    c = cfg()
    o = tf_outputs()
    if not o.get("wif_provider"):
        raise ConfigError("Definir github_repo en el Excel y ejecutar apply primero.")
    print("| Variable de GitHub (Settings > Secrets and variables > Actions > Variables) | Valor |\n|---|---|")
    print(f"| GCP_WIF_PROVIDER | {o['wif_provider']} |")
    if shutil.which("gh"):
        run(["gh", "variable", "set", "GCP_WIF_PROVIDER", "--body", o["wif_provider"], "--repo", c["params"]["github_repo"]], check=False)


@step("costo real por pedido")
def cmd_costo_real(a):
    c = cfg()
    if not c["params"].get("billing_export_table"):
        raise ConfigError("Definir billing_export_table en el Excel (activar antes el billing export a BigQuery).")
    return run_sql(c, "cost/real_cost_per_order.sql")


def cmd_local(a):
    c = cfg(cloud=False)
    p = c["params"]
    db = ROOT / "data/retail_demo.db"
    env = {"DATABASE_URL": f"sqlite:///{db.as_posix()}", "ASSISTANT_MODE": p["assistant_mode"],
           "GEMINI_MODEL": p["gemini_model"], "GCP_PROJECT_ID": p["project_id"], "ADMIN_TOKEN": p["admin_token_local"],
           "PRICE_DEMO_FACTOR": str(p["price_demo_factor"]), "STOCK_DEMO": str(p["stock_demo"]),
           "IMAGES_DIR": str((ROOT / p["local_raw_dir"] / "images").resolve())}
    if p["assistant_mode"] == "gemini" and p["project_id"] == "tu-proyecto-gcp":
        env["ASSISTANT_MODE"] = "rules"
    db.parent.mkdir(exist_ok=True)
    if not db.exists():
        run([sys.executable, str(ROOT / "api/load_catalog.py"), "--source", "local", "--raw-dir", str(ROOT / p["local_raw_dir"])], env=env)
    print(f"Tienda local: http://localhost:8080  (token de recarga: {p['admin_token_local']})")
    subprocess.run([sys.executable, "-m", "uvicorn", "main:app", "--port", "8080"], cwd=ROOT / "api", env={**os.environ, **env})


def cmd_panel(a):
    """Panel web local: edita config/control_plataforma.json y ejecuta estos mismos comandos con botones."""
    subprocess.run([sys.executable, str(ROOT / "panel/app.py")])


def cmd_todo(a):
    cmd_bootstrap(a)
    cmd_apply(a)
    cmd_bronze(a)
    cmd_silver(a)
    cmd_gold(a)
    cmd_api(a)
    cmd_verificar(a)


COMMANDS = {
    "config": cmd_config, "estado": cmd_estado, "local": cmd_local, "bootstrap": cmd_bootstrap,
    "plan": cmd_plan, "apply": cmd_apply, "destroy": cmd_destroy, "subir-datos": cmd_subir,
    "bronze": cmd_bronze, "silver": cmd_silver, "gold": cmd_gold, "api": cmd_api, "catalogo": cmd_catalogo,
    "replay": cmd_replay, "dataflow-iniciar": cmd_dataflow_start, "dataflow-detener": cmd_dataflow_stop,
    "verificar": cmd_verificar, "github": cmd_github, "costo-real": cmd_costo_real, "panel": cmd_panel, "todo": cmd_todo,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=COMMANDS)
    ap.add_argument("--check", action="store_true", help="config: solo verificar")
    ap.add_argument("--yes", action="store_true", help="apply/destroy/todo sin confirmación")
    ap.add_argument("--con-imagenes", action="store_true", help="subir-datos: incluir 29 GB de imágenes")
    ap.add_argument("--limite", type=int, help="replay: cantidad de eventos")
    a = ap.parse_args()
    try:
        COMMANDS[a.comando](a)
    except ConfigError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print_log()
        sys.exit(1)
    print_log()


if __name__ == "__main__":
    main()
