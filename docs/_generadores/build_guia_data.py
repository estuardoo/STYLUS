"""Datos y figuras de la Guía Técnica STYLUS (todo sale del repo real).
Uso: python docs/_generadores/build_guia_data.py   -> docs/guia/guia_data.json + docs/guia/img/*.png
Luego: node docs/_generadores/build_guia.js
"""
import importlib.util
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import openpyxl

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/guia"
IMG = OUT / "img"
IMG.mkdir(parents=True, exist_ok=True)

# Paleta de la guía
NAVY, ACCENT, GREY = "#1F3864", "#2E75B6", "#595959"
BRONZE, SILVER, GOLD = "#B87333", "#8C99A6", "#C9A227"
TEAL, ORANGE, PURPLE, GREEN, RED = "#1B998B", "#E07A1F", "#6A4C93", "#2E7D32", "#C62828"
OK, LISTO, PEND = "#2E7D32", "#F2A900", "#C62828"

cfg = json.loads((ROOT / "config/control_plataforma.json").read_text(encoding="utf-8"))
gen = json.loads((ROOT / "config/generated/plataforma.json").read_text(encoding="utf-8"))
D = gen["derived"]
P = {r["clave"]: r["valor"] for r in cfg["parametros"]}

spec = importlib.util.spec_from_file_location("bm", ROOT / "docs/_generadores/build_matriz.py")
bm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bm)

# ---------------- costos ----------------
wb = openpyxl.load_workbook(ROOT / "docs/entrega1/Calculadora_Costos_GCP.xlsx", data_only=True)
ws = wb["Costo mensual"]
esc = ["dev", "demo", "produccion", "pico_black_friday"]
por_servicio = defaultdict(lambda: [0.0] * 4)
totales = {}
for r in ws.iter_rows(min_row=2, values_only=True):
    if r[0] and r[1]:
        for i in range(4):
            por_servicio[r[1]][i] += float(r[2 + i] or 0)
    elif r[0] in ("TOTAL MENSUAL", "Pedidos/mes", "Costo por pedido"):
        totales[r[0]] = [float(x) for x in r[2:6]]

# ---------------- tareas ----------------
# ID, paso, fase, nombre, acción, entregable, comando, depende, responsable, apoyo, estado, evidencia
tareas = [dict(zip(["id", "paso", "fase", "nombre", "accion", "entregable", "comando", "depende",
                    "responsable", "apoyo", "estado", "evidencia"], t)) for t in bm.TAREAS]

# ---------------- archivos del repo ----------------
files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()


def lines(p):
    try:
        return sum(1 for _ in open(ROOT / p, encoding="utf-8", errors="ignore"))
    except Exception:
        return 0


code_ext = (".py", ".sql", ".tf", ".js", ".html", ".yml", ".json", ".md")
loc = Counter()
for f in files:
    ext = Path(f).suffix
    if ext in code_ext and "generated" not in f and not f.endswith("seed.json"):
        loc[ext] += lines(f)

# ---------------- figuras ----------------
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 12,
                     "axes.titlecolor": NAVY})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(IMG / name, dpi=170)
    plt.close(fig)


# 1. Costo mensual por escenario
fig, ax = plt.subplots(figsize=(7.2, 3.4))
lbl = ["Desarrollo", "Demo", "Producción", "Pico Black Friday"]
vals = totales["TOTAL MENSUAL"]
bars = ax.bar(lbl, vals, color=[ACCENT, TEAL, NAVY, ORANGE], width=0.6)
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width() / 2, v * 1.15, f"USD {v:,.2f}", ha="center", fontsize=9, fontweight="bold", color=NAVY)
ax.set_yscale("log")
ax.set_ylabel("USD / mes (escala log)")
ax.set_title("Costo mensual estimado por escenario")
ax.set_ylim(1, max(vals) * 4)
save(fig, "costo_escenarios.png")

# 2. Desglose producción por servicio
serv = sorted(por_servicio.items(), key=lambda kv: kv[1][2])
fig, ax = plt.subplots(figsize=(7.2, 3.8))
names = [k for k, _ in serv]
v = [x[2] for _, x in serv]
pal = [GREY if x < 5 else ACCENT if x < 50 else NAVY for x in v]
ax.barh(names, v, color=pal)
for i, x in enumerate(v):
    ax.text(x + 2, i, f"USD {x:,.2f}", va="center", fontsize=8.5, color=NAVY)
ax.set_xlabel("USD / mes")
ax.set_title("Producción: USD/mes por servicio (total 370.83)")
ax.set_xlim(0, max(v) * 1.25)
save(fig, "costo_servicios.png")

# 3. Avance por paso (apilado)
fig, ax = plt.subplots(figsize=(7.2, 2.9))
pasos = [1, 2, 3]
cnt = {p: Counter(t["estado"] for t in tareas if t["paso"] == p) for p in pasos}
hh = [cnt[p]["Hecho"] for p in pasos]
ll = [cnt[p]["Listo para desplegar"] for p in pasos]
pp = [cnt[p]["Pendiente"] for p in pasos]
ylab = ["Paso 1 · 24-oct", "Paso 2 · 07-nov", "Paso 3 · 20-nov"]
ax.barh(ylab, hh, color=OK, label="Hecho")
ax.barh(ylab, ll, left=hh, color=LISTO, label="Listo para desplegar")
ax.barh(ylab, pp, left=[a + b for a, b in zip(hh, ll)], color=PEND, label="Pendiente")
for i, p in enumerate(pasos):
    tot = hh[i] + ll[i] + pp[i]
    ax.text(tot + 0.3, i, f"{hh[i] / tot:.0%} hecho", va="center", fontsize=9, fontweight="bold", color=NAVY)
ax.invert_yaxis()
ax.set_xlabel("Tareas")
ax.set_xlim(0, 25)
ax.set_title("Avance por entrega")
ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.3), frameon=False)
save(fig, "avance_pasos.png")

# 4. Tareas por persona (apilado por estado)
personas = ["Estuardo Oliver", "Winston Quispe", "Nicole Arenas", "Gianmarco Mejia"]
fig, ax = plt.subplots(figsize=(7.2, 3.0))
c = {n: Counter(t["estado"] for t in tareas if t["responsable"] == n) for n in personas}
h = [c[n]["Hecho"] for n in personas]
l2 = [c[n]["Listo para desplegar"] for n in personas]
p2 = [c[n]["Pendiente"] for n in personas]
ax.barh(personas, h, color=OK, label="Hecho")
ax.barh(personas, l2, left=h, color=LISTO, label="Listo para desplegar")
ax.barh(personas, p2, left=[a + b for a, b in zip(h, l2)], color=PEND, label="Pendiente")
for i in range(4):
    ax.text(h[i] + l2[i] + p2[i] + 0.3, i, str(h[i] + l2[i] + p2[i]), va="center", fontsize=9, fontweight="bold", color=NAVY)
ax.invert_yaxis()
ax.set_xlabel("Tareas como responsable (51 en total)")
ax.set_title("Carga por persona y estado")
ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.28), frameon=False)
save(fig, "tareas_persona.png")

# 5. Volumen de datos
fig, ax = plt.subplots(figsize=(7.2, 2.8))
dl = ["articles.csv", "customers.csv", "transactions_train.csv", "pedidos derivados"]
dv = [105_542, 1_371_980, 31_788_324, 9_080_179]
b = ax.bar(dl, dv, color=[GOLD, TEAL, NAVY, ACCENT], width=0.6)
for bb, x in zip(b, dv):
    ax.text(bb.get_x() + bb.get_width() / 2, x * 1.3, f"{x:,}", ha="center", fontsize=9, fontweight="bold", color=NAVY)
ax.set_yscale("log")
ax.set_ylim(10_000, 3e8)
ax.set_ylabel("Filas (escala log)")
ax.set_title("Volumen del dataset público H&M")
save(fig, "volumen_datos.png")

# 6. MAP@12
fig, ax = plt.subplots(figsize=(6.0, 2.6))
mv = [0.00875, 0.02622]
b = ax.barh(["A. Popularidad última semana", "B. Recompra 8 sem. + popularidad"], mv, color=[GREY, PURPLE])
for i, x in enumerate(mv):
    ax.text(x + 0.0005, i, f"{x:.5f}", va="center", fontsize=9, fontweight="bold", color=NAVY)
ax.set_xlim(0, 0.033)
ax.set_xlabel("MAP@12 (split temporal real)")
ax.set_title("Recomendador: +200% vs. línea base")
save(fig, "map12.png")

# 7. Código por tipo
fig, ax = plt.subplots(figsize=(7.2, 2.6))
lk = sorted(loc.items(), key=lambda kv: -kv[1])
ax.bar([k for k, _ in lk], [x for _, x in lk], color=ACCENT)
for i, (_, x) in enumerate(lk):
    ax.text(i, x + 20, f"{x:,}", ha="center", fontsize=8.5, color=NAVY)
ax.set_ylabel("Líneas")
ax.set_title(f"Código y configuración versionados ({sum(loc.values()):,} líneas, {len(files)} archivos)")
save(fig, "codigo_tipo.png")

# 8. Cronograma
import datetime as dt
fig, ax = plt.subplots(figsize=(7.2, 1.9))
hitos = [("Entrega 1", dt.date(2026, 10, 24), NAVY), ("Entrega 2", dt.date(2026, 11, 7), TEAL),
         ("Repositorio", dt.date(2026, 11, 20), ORANGE), ("Sustentación", dt.date(2026, 11, 21), PURPLE)]
ini = dt.date(2026, 10, 15)
ax.axhline(0, color=GREY, lw=2)
for i, (n, d, col) in enumerate(hitos):
    x = (d - ini).days
    ax.plot(x, 0, "o", ms=13, color=col)
    ax.text(x, 0.35 if i % 2 == 0 else -0.55, f"{n}\n{d:%d-%b}", ha="center", fontsize=9, color=col, fontweight="bold")
hoy = (dt.date(2026, 10, 24) - ini).days
ax.axvline(hoy, ymin=0.05, ymax=0.35, color=RED, ls="--", lw=1)
ax.text(hoy, -0.85, "hoy", ha="center", fontsize=8, color=RED)
ax.set_ylim(-1, 1)
ax.set_xlim(0, 40)
ax.axis("off")
ax.set_title("Cronograma de entregas")
save(fig, "cronograma.png")


# 9. Costo mensual vs anual por escenario (dos paneles)
fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.4), sharey=True)
mens = totales["TOTAL MENSUAL"]
anual = [x * 12 for x in mens]
cols = [ACCENT, TEAL, NAVY, ORANGE]
for ax, vals_, tit in ((axs[0], mens, "USD / mes"), (axs[1], anual, "USD / año (× 12)")):
    b = ax.barh(lbl, vals_, color=cols, height=0.6)
    ax.set_xscale("log")
    ax.set_xlim(1, max(vals_) * 12)
    ax.set_title(tit)
    for bb, v in zip(b, vals_):
        ax.text(v * 1.15, bb.get_y() + bb.get_height() / 2, f"USD {v:,.2f}", va="center", fontsize=9, fontweight="bold", color=NAVY)
    ax.tick_params(axis="x", labelsize=8)
axs[0].invert_yaxis()
fig.suptitle("Costo por escenario: mensual y anual", fontweight="bold", color=NAVY, fontsize=12)
save(fig, "costo_mes_anio.png")

# 10. Dona: distribución del costo de producción
serv_items = sorted(((k, v[2]) for k, v in por_servicio.items()), key=lambda kv: -kv[1])
grandes = [(k, v) for k, v in serv_items if v >= 5]
otros = sum(v for k, v in serv_items if v < 5)
etq = [k.replace("Vertex AI Gemini 3.1 Flash-Lite", "Vertex AI Gemini") for k, _ in grandes] + ["Otros (Spark, Pub/Sub, GCS, AR)"]
val = [v for _, v in grandes] + [otros]
fig, ax = plt.subplots(figsize=(7.2, 3.6))
w, _ = ax.pie(val, colors=[PURPLE, ACCENT, NAVY, ORANGE, TEAL, GREY][: len(val)], startangle=90, counterclock=False,
              wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2))
tot = sum(val)
ax.text(0, 0.08, f"USD {tot:,.0f}", ha="center", fontsize=15, fontweight="bold", color=NAVY)
ax.text(0, -0.16, "al mes en producción", ha="center", fontsize=8.5, color=GREY)
ax.legend(w, [f"{e}  ·  USD {v:,.2f}  ({v / tot:.0%})" for e, v in zip(etq, val)], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=9)
fig.suptitle("¿En qué se va el costo de producción?", fontweight="bold", color=NAVY, fontsize=12)
ax.axis("equal")
save(fig, "costo_donut.png")

# 11. Banner del README
fig = plt.figure(figsize=(12, 3.0))
fig.patch.set_facecolor(NAVY)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 12)
ax.set_ylim(0, 3)
ax.axis("off")
ax.add_patch(plt.Rectangle((0, 0), 12, 0.09, color=GOLD))
ax.text(0.45, 2.45, "STYLUS", fontsize=40, fontweight="bold", color="white", va="center")
ax.text(0.47, 1.85, "Retail de moda con compras inteligentes asistidas por IA en tiempo real", fontsize=13, color="#DCE6F4", va="center")
ax.text(0.47, 1.47, "Google Cloud · BigQuery · Spark · Dataflow · Cloud Run · Vertex AI Gemini · dataset público H&M", fontsize=9.5, color="#9FB4D3", va="center")
tiles = [("31.8 M", "transacciones reales", NAVY), ("+200%", "MAP@12 vs. popularidad", PURPLE), ("USD 0.00098", "costo por pedido", TEAL), ("51", "tareas · 4 personas", ORANGE)]
for i, (v, l, c) in enumerate(tiles):
    x = 0.47 + i * 2.85
    ax.add_patch(matplotlib.patches.FancyBboxPatch((x, 0.25), 2.6, 0.85, boxstyle="round,pad=0.02,rounding_size=0.08", color=c if c != NAVY else "#2B4C82"))
    ax.text(x + 1.3, 0.8, v, fontsize=16, fontweight="bold", color="white", va="center", ha="center")
    ax.text(x + 1.3, 0.45, l, fontsize=9, color="white", va="center", ha="center")
fig.savefig(IMG / "banner.png", dpi=150, facecolor=NAVY)
plt.close(fig)


# ---------------- diagramas Graphviz ----------------
def dot(name, src):
    (IMG / f"{name}.dot").write_text(src, encoding="utf-8")
    subprocess.run(["dot", "-Tpng", "-Gdpi=170", str(IMG / f"{name}.dot"), "-o", str(IMG / f"{name}.png")], check=True)
    (IMG / f"{name}.dot").unlink()


BASE = ('graph [fontname="DejaVu Sans" fontsize=11 rankdir=LR nodesep=0.35 ranksep=0.45 bgcolor="white" pad=0.2];\n'
        'node [fontname="DejaVu Sans" fontsize=10 shape=box style="rounded,filled" penwidth=1.2 margin="0.15,0.07"];\n'
        'edge [fontname="DejaVu Sans" fontsize=8.5 color="#595959" arrowsize=0.7];\n')


def n(id_, txt, fill, font="white"):
    txt = txt.replace("|", "\\n")  # "|" = salto de línea en la etiqueta
    return f'{id_} [label="{txt}" fillcolor="{fill}" fontcolor="{font}" color="{fill}"];\n'


raw, lake, ds = D["bucket_raw"], D["bucket_lake"], D["datasets"]

# Arquitectura
dot("arquitectura", "digraph G {" + BASE.replace("rankdir=LR", "rankdir=TB").replace("ranksep=0.45", "ranksep=0.55") + f"""
subgraph cluster_f {{label="1. FUENTES" style="rounded,filled" fillcolor="#F3F5F8" color="#C9D1DC" fontcolor="{NAVY}";
 {n("csv", "H&M Kaggle|3 CSV · 3.9 GB", GREY)} {n("rep", "Replay 2026|replay_publisher.py", GREY)} {n("web", "Tienda web|(compras demo)", GREY)} }}
subgraph cluster_i {{label="2. INGESTA" style="rounded,filled" fillcolor="#EAF4F3" color="#B5DAD5" fontcolor="{NAVY}";
 {n("up", "upload_raw.py|manifiesto SHA-256", TEAL)} {n("ps", "Pub/Sub|retail-events + DLQ", TEAL)} }}
subgraph cluster_s {{label="3. LAKEHOUSE MEDALLION (GCS + BigQuery)" style="rounded,filled" fillcolor="#FBF6EC" color="#E6D6B0" fontcolor="{NAVY}";
 {n("br", "BRONZE|GCS raw + retail_bronze", BRONZE)} {n("op", "OPS|retail_ops: métricas + DLQ", NAVY)}
 {n("sv", "SILVER|Parquet + retail_silver", SILVER)} {n("gd", "GOLD|modelo estrella · retail_gold", GOLD, "#1F1F1F")} }}
subgraph cluster_x {{label="4. EXPOSICIÓN" style="rounded,filled" fillcolor="#FDF1E7" color="#F2C9A5" fontcolor="{NAVY}";
 {n("bi", "Looker Studio|tableros", NAVY)} {n("api", "Cloud Run|FastAPI + web", ORANGE)} {n("sql", "Cloud SQL|wallet ACID", ORANGE)} {n("gem", "Vertex AI|Gemini 3.1 Flash-Lite", PURPLE)} }}
csv -> up -> br; rep -> ps; web -> api;
ps -> br [label=" suscripción BQ"]; ps -> op [label=" Dataflow · ventanas 1 min" color="{ACCENT}" fontcolor="{ACCENT}" penwidth=1.6];
br -> sv [label=" Serverless Spark" color="{ACCENT}" fontcolor="{ACCENT}" penwidth=1.6]; sv -> gd [label=" SQL BigQuery" color="{ACCENT}" fontcolor="{ACCENT}" penwidth=1.6];
gd -> bi; op -> bi; gd -> api [label=" catálogo"]; api -> sql; api -> gem; api -> ps [label=" eventos web" style=dashed];
}}""")

# Pipeline batch
dot("pipeline_batch", "digraph G {" + BASE.replace("rankdir=LR", "rankdir=TB") + f"""
{n("a", "data/raw/*.csv|(PC del equipo)", GREY)}
{n("b", "python ops.py subir-datos|ingestion/batch/upload_raw.py", TEAL)}
{n("c", f"gs://{raw}/hm/|+ _manifests/hm_raw_manifest.json", BRONZE)}
{n("d", f"python ops.py bronze · sql/bronze/01_bronze_hm.sql|{ds['bronze']}.ext_articles · ext_customers · ext_transactions → transactions", BRONZE)}
{n("e", "python ops.py silver · pipelines/batch/silver_hm.py (Serverless Spark)|valida fecha, cliente, artículo, precio, canal → quarantine/", ACCENT)}
{n("f", f"gs://{lake}/silver/*.parquet|+ _quality_report (conciliado = true)", SILVER)}
{n("g", f"sql/silver/01_load_silver.sql (LOAD DATA)|{ds['silver']}.articles · customers · transactions · v_events", SILVER)}
{n("h", f"python ops.py gold · sql/gold/01_gold_model.sql + 02_kpi_views.sql|{ds['gold']}.dim_* · fact_sales · fact_orders · reco_popular · v_*", GOLD, "#1F1F1F")}
{n("i", "python ops.py catalogo · api/load_catalog.py|Cloud SQL retail.articles", ORANGE)}
a -> b -> c -> d -> e -> f -> g -> h -> i;
q [label="quarantine/transactions\\n(filas rechazadas, contadas)" shape=note style=filled fillcolor="#FDECEC" color="{RED}" fontcolor="{RED}"];
e -> q [style=dashed color="{RED}"];
}}""")

# Pipeline streaming
dot("pipeline_streaming", "digraph G {" + BASE.replace("rankdir=LR", "rankdir=TB") + f"""
{n("tx", "silver.transactions|(histórico real)", SILVER)}
{n("rp", "python ops.py replay|replay_publisher.py|fecha 2026 · is_synthetic", TEAL)}
{n("tp", f"Pub/Sub|{P['pubsub_topic']}", TEAL)}
{n("sbq", "suscripción BigQuery|(ruta económica)", TEAL)}
{n("raw", f"{ds['bronze']}.events_raw", BRONZE)}
{n("ve", f"{ds['silver']}.v_events|dedup event_id", SILVER)}
{n("fs", f"{ds['gold']}.fact_sales", GOLD, "#1F1F1F")}
{n("sdf", "suscripción Dataflow", TEAL)}
{n("df", "Dataflow (Beam)|validar → dedup →|ventana 60 s · tardíos 300 s", ACCENT)}
{n("m", f"{ds['ops']}.stream_metrics_1m|lag p50 / p95", NAVY)}
{n("dl", f"{ds['ops']}.stream_dlq|+ tópico DLQ (5 intentos)", RED)}
tx -> rp -> tp; tp -> sbq -> raw -> ve -> fs; tp -> sdf -> df -> m; df -> dl [style=dashed color="{RED}" label="inválidos"];
}}""")

# Serving
dot("pipeline_serving", "digraph G {" + BASE.replace("rankdir=LR", "rankdir=TB") + f"""
{n("u", "Cliente|(navegador)", GREY)}
{n("cr", f"Cloud Run · {P['cloudrun_service']}|api/main.py (FastAPI)|api/static/index.html", ORANGE)}
{n("as", "api/assistant.py|reglas + Gemini", PURPLE)}
{n("vx", f"Vertex AI|{P['gemini_model']}", PURPLE)}
{n("db", "Cloud SQL Postgres 15|users · articles · cart_items|orders · order_lines · wallet_ledger", ORANGE)}
{n("sm", "Secret Manager|retail-db-url · admin token", NAVY)}
{n("gcs", "GCS imágenes|hm/images/", BRONZE)}
{n("ev", "Pub/Sub|eventos web_demo", TEAL)}
u -> cr [label="HTTPS"]; cr -> as -> vx; cr -> db [label="checkout ACID\\nidempotency key"]; sm -> cr [style=dashed]; cr -> gcs; cr -> ev [label="purchase"];
}}""")

# CI/CD y control
dot("control_cicd", "digraph G {" + BASE.replace("rankdir=LR", "rankdir=TB") + f"""
{n("j", "config/control_plataforma.json|(fuente única)", NAVY)}
{n("pn", "python ops.py panel|http://127.0.0.1:8765", ACCENT)}
{n("cf", "python ops.py config|valida + genera", ACCENT)}
{n("tv", "infra/terraform/|plataforma.auto.tfvars.json", GREY)}
{n("pj", "config/generated/|plataforma.json", GREY)}
{n("sd", "api/seed.json", GREY)}
{n("tf", "Terraform / OpenTofu|plan · apply", TEAL)}
{n("gcp", f"GCP|{P['project_id']}", ORANGE)}
{n("gh", "GitHub estuardoo/STYLUS|.github/workflows/ci.yml · deploy.yml", PURPLE)}
pn -> j [label="edita"]; j -> cf -> tv -> tf -> gcp; cf -> pj; cf -> sd; pj -> gh [label="push"]; gh -> gcp [label="WIF sin llaves"];
}}""")

# Estrella (anexo)
def tbl(name, cols, color, font="white"):
    rows = "".join(f'<TR><TD ALIGN="LEFT" BGCOLOR="white"><FONT POINT-SIZE="9">{c}</FONT></TD></TR>' for c in cols)
    return (f'{name} [shape=plaintext style="" label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="{color}">'
            f'<TR><TD BGCOLOR="{color}"><FONT COLOR="{font}"><B>{name}</B></FONT></TD></TR>{rows}</TABLE>>];\n')


gcols = defaultdict(list)
for col in cfg["columnas"]:
    if col["dataset"] == "gold":
        gcols[col["tabla"]].append(f'{col["columna"]} : {col["tipo"]}')
dot("estrella", "digraph G {" + BASE.replace("rankdir=LR", "rankdir=LR") + "".join([
    tbl("fact_sales", gcols["fact_sales"], GOLD, "#1F1F1F"),
    tbl("fact_orders", gcols["fact_orders"], GOLD, "#1F1F1F"),
    tbl("dim_customer", gcols["dim_customer"], NAVY),
    tbl("dim_article", gcols["dim_article"], NAVY),
    tbl("dim_date", gcols["dim_date"], NAVY),
    tbl("dim_channel", gcols["dim_channel"], NAVY),
    tbl("reco_popular", gcols["reco_popular"], PURPLE),
]) + """
dim_customer -> fact_sales [label="customer_id"]; dim_article -> fact_sales [label="article_id"];
dim_date -> fact_sales [label="sale_date"]; dim_channel -> fact_sales [label="sales_channel_id"];
fact_sales -> fact_orders [label="agrega"]; dim_article -> reco_popular [label="article_id"];
}""")

# ---------------- datos para el Word ----------------
data = {
    "params": P, "derived": D, "costos": {"por_servicio": {k: v for k, v in por_servicio.items()}, "totales": totales},
    "tareas": tareas, "perfiles": [list(p) for p in bm.PERFILES], "despliegue": [list(d) for d in bm.DESPLIEGUE],
    "tablas": cfg["tablas"], "columnas": cfg["columnas"], "permisos": cfg["permisos"], "usuarios": cfg["usuarios"],
    "cuentas": cfg["cuentas_servicio"], "datasets": cfg["datasets"], "secretos": cfg["secretos"], "apis": cfg["apis"],
    "parametros": cfg["parametros"], "files": [{"ruta": f, "lineas": lines(f)} for f in files], "loc": dict(loc),
}
(OUT / "guia_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("ok:", sorted(p.name for p in IMG.glob("*.png")))
