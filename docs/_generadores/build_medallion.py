"""Lámina ejecutiva del modelo medallion (todas las tablas y su volumen) para presentar.
Uso: python docs/_generadores/build_medallion.py -> docs/guia/img/modelo_medallion.png (+ .jpg local)
Volúmenes: dataset H&M completo (manifiesto + auditoría de datos); streaming y Cloud SQL crecen con la operación.
"""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrow

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "docs/guia/img"
gen = json.loads((ROOT / "config/generated/plataforma.json").read_text(encoding="utf-8"))
DS = gen["derived"]["datasets"]
RAW, LAKE = gen["derived"]["bucket_raw"], gen["derived"]["bucket_lake"]

NAVY, GREY, INK = "#1F3864", "#595959", "#1F1F1F"
SRC, BRONZE, SILVER, GOLD, CONS, SQLC = "#5B6573", "#B87333", "#7D8A97", "#C9A227", "#1F3864", "#E07A1F"
BG = "#F4F6FA"

# (nombre, filas (int o texto), descripción, es_vista)
COLS = [
    ("FUENTE", "Dataset público H&M · Kaggle", SRC, [
        (None, [("articles.csv", 105_542, "catálogo · 36 MB", False),
                ("customers.csv", 1_371_980, "clientes · 207 MB", False),
                ("transactions_train.csv", 31_788_324, "compras 2018-2020 · 3.5 GB", False),
                ("images/", "105,100 fotos", "opcional · 29 GB", False),
                ("Replay 2026", "streaming", "re-emisión de compras reales", False)])]),
    ("BRONZE", f"{DS['bronze']} · gs://…-retail-raw", BRONZE, [
        (None, [("ext_articles", 105_542, "tabla externa sobre el CSV", False),
                ("ext_customers", 1_371_980, "tabla externa sobre el CSV", False),
                ("ext_transactions", 31_788_324, "tabla externa sobre el CSV", False),
                ("transactions", 31_788_324, "nativa · partición por día", False),
                ("events_raw", "5,000 / replay", "eventos Pub/Sub tal como llegan", False)])]),
    ("SILVER", f"{DS['silver']} · Parquet en GCS", SILVER, [
        (None, [("articles", 105_542, "tipados · descripción imputada", False),
                ("customers", 1_371_980, "nulos tratados · banda de edad", False),
                ("transactions", 31_788_324, "validadas · rechazos aparte", False),
                ("v_events", "dedup", "eventos sin duplicados (event_id)", True)])]),
    ("GOLD", f"{DS['gold']} · modelo estrella", GOLD, [
        ("Hechos", [("fact_sales", 31_788_324, "línea de venta + eventos 2026", False),
                    ("fact_orders", 9_080_179, "pedido = cliente + día + fuente", False)]),
        ("Dimensiones", [("dim_customer", 1_371_980, "cliente seudonimizado", False),
                         ("dim_article", 105_542, "producto", False),
                         ("dim_date", 3_409, "calendario 2018-2027", False),
                         ("dim_channel", 2, "tienda física · online", False)]),
        ("Servicio y BI", [("reco_popular", 17_986, "top por grupo · última semana", False),
                           ("v_catalog_serving", 105_542, "catálogo para la tienda", True),
                           ("3 vistas BI", "vistas", "ventas mensuales · top · recurrencia", True)])]),
    ("CONSUMO", "operación · tienda · tableros", CONS, [
        (f"OPS · {DS['ops']}", [("stream_metrics_1m", "1 fila / min", "eventos, compras, lag p50/p95", False),
                                ("stream_dlq", "inválidos", "mensajes rechazados", False),
                                ("2 vistas", "vistas", "salud del streaming · costo real", True)]),
        ("Cloud SQL · retail", [("articles", 105_542, "catálogo de la tienda", False),
                                ("users", 6, "usuarios demo iniciales", False),
                                ("wallet_ledger", "5 + compras", "saldo append-only (ACID)", False),
                                ("orders + 2 tablas", "por compra", "order_lines · cart_items", False)])]),
]
ARROWS = ["Carga", "Spark", "SQL", "API"]

W, H = 100, 56.25
fig = plt.figure(figsize=(19.2, 10.8))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor(BG)

# Encabezado
ax.add_patch(plt.Rectangle((0, H - 6.6), W, 6.6, color=NAVY))
ax.add_patch(plt.Rectangle((0, H - 6.85), W, 0.25, color=GOLD))
ax.text(2, H - 2.6, "STYLUS · Modelo de datos Medallion", fontsize=26, fontweight="bold", color="white", va="center")
ax.text(2, H - 5.0, "Del dato crudo al dato de negocio en Google Cloud · 30 tablas y vistas · dataset público H&M (Kaggle)",
        fontsize=13, color="#C9D6EA", va="center")
for i, (v, l) in enumerate([("31.8 M", "transacciones"), ("9.08 M", "pedidos"), ("1.37 M", "clientes"), ("105.5 K", "artículos")]):
    x = 64 + i * 9
    ax.text(x, H - 2.5, v, fontsize=19, fontweight="bold", color="white", va="center")
    ax.text(x, H - 4.8, l, fontsize=10.5, color="#C9D6EA", va="center")

XS = [1.5, 21.4, 41.3, 61.2, 81.1]
CW = 17.4
TOP = H - 11.2
CARD_H, GAP, SUB_H = 3.15, 0.55, 1.7


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else n


def card(x, y, name, rows, desc, color, vista):
    ax.add_patch(FancyBboxPatch((x, y), CW, CARD_H, boxstyle="round,pad=0,rounding_size=0.45",
                                fc="white", ec=color if not vista else "#B9C2CE", lw=1.3,
                                linestyle="--" if vista else "-"))
    ax.add_patch(FancyBboxPatch((x, y), 0.55, CARD_H, boxstyle="round,pad=0,rounding_size=0.25", fc=color, ec=color))
    ax.text(x + 1.1, y + CARD_H - 0.95, name, fontsize=10.5, fontweight="bold", color=INK, va="center")
    ax.text(x + 1.1, y + 0.95, desc, fontsize=8.3, color=GREY, va="center")
    ax.text(x + CW - 0.6, y + CARD_H - 0.95, fmt(rows), fontsize=11.5, fontweight="bold", color=color, va="center", ha="right")
    if isinstance(rows, int):  # barra de volumen (log10)
        frac = max(math.log10(rows), 0.3) / math.log10(31_788_324)
        ax.add_patch(plt.Rectangle((x + CW - 4.3, y + 0.72), 3.7, 0.4, color="#E8ECF2"))
        ax.add_patch(plt.Rectangle((x + CW - 4.3, y + 0.72), 3.7 * frac, 0.4, color=color, alpha=0.85))


for ci, (title, sub, color, groups) in enumerate(COLS):
    x = XS[ci]
    ax.add_patch(FancyBboxPatch((x, TOP - 0.2), CW, 3.2, boxstyle="round,pad=0,rounding_size=0.6", fc=color, ec=color))
    ax.text(x + CW / 2, TOP + 2.0, title, fontsize=15, fontweight="bold", color="white", ha="center", va="center")
    ax.text(x + CW / 2, TOP + 0.6, sub, fontsize=8.6, color="white", ha="center", va="center")
    y = TOP - 1.0
    for gname, items in groups:
        if gname:
            y -= SUB_H
            ax.text(x + 0.2, y + 0.55, gname.upper(), fontsize=8.8, fontweight="bold", color=color, va="center")
            ax.plot([x + 0.2 + 0.62 * len(gname) + 0.6, x + CW], [y + 0.55, y + 0.55], color=color, lw=0.8, alpha=0.5)
        for name, rows, desc, vista in items:
            y -= CARD_H
            card(x, y, name, rows, desc, color, vista)
            y -= GAP

# Flechas entre capas
for i, lab in enumerate(ARROWS):
    x0 = XS[i] + CW + 0.35
    x1 = XS[i + 1] - 0.35
    ym = TOP - 12.5
    ax.add_patch(FancyArrow(x0, ym, x1 - x0, 0, width=0.9, head_width=2.0, head_length=0.9, length_includes_head=True,
                            fc=COLS[i + 1][2], ec="none", alpha=0.9))
    ax.text((x0 + x1) / 2, ym + 1.9, lab, fontsize=8.5, fontweight="bold", color=NAVY, ha="center", va="center")

# Pie de lámina
ax.add_patch(plt.Rectangle((0, 0), W, 2.6, color="#E3E8F0"))
ax.text(2, 1.3, "■ Tabla      ▭ Vista (se calcula al consultar)      La barra indica el volumen relativo (escala logarítmica).   "
        "Ninguna fila se pierde: entrada = salida + rechazadas (cuarentena).", fontsize=9.5, color=GREY, va="center")
ax.text(W - 2, 1.3, f"gs://{RAW} · gs://{LAKE}", fontsize=8.5, color=GREY, va="center", ha="right")

out = IMG / "modelo_medallion.png"
fig.savefig(out, dpi=200, facecolor=BG)
fig.savefig(IMG / "modelo_medallion.jpg", dpi=200, facecolor=BG, pil_kwargs={"quality": 92})
print("ok", out)
