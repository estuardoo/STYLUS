"""Lámina del modelo estrella (Gold) con todas sus tablas, columnas, claves, origen y volumen.
Uso: python docs/_generadores/build_estrella.py -> docs/guia/img/modelo_estrella.png (+ .jpg local)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "docs/guia/img"
NAVY, GREY, INK, BG = "#1F3864", "#595959", "#1F1F1F", "#F4F6FA"
FACT, ART, CUS, DATE, CHAN, RECO = "#C9A227", "#2E75B6", "#1B998B", "#1F3864", "#E07A1F", "#6A4C93"

# nombre: (color, rol, filas, grano, [(columna, tipo, clave, origen)])
T = {
    "fact_sales": (FACT, "HECHO", "31,788,324 + eventos", "1 fila = 1 línea de venta", [
        ("customer_id", "STRING", "fk", "transactions.customer_id"),
        ("sale_date", "DATE", "fk", "transactions.t_dat"),
        ("article_id", "STRING", "fk", "transactions.article_id"),
        ("sales_channel_id", "INT64", "fk", "transactions.sales_channel_id"),
        ("qty", "INT64", "", "1 por línea"),
        ("price", "FLOAT64", "", "transactions.price"),
        ("source", "STRING", "", "hm_hist | replay | web_demo"),
        ("is_synthetic", "BOOL", "", "true en eventos 2026"),
        ("order_id", "STRING", "", "solo compras web"),
    ]),
    "fact_orders": (FACT, "HECHO", "9,080,179", "1 fila = 1 pedido (cliente + día + fuente)", [
        ("order_id", "STRING", "pk", "hash cliente + día + fuente"),
        ("order_date", "DATE", "fk", "fact_sales.sale_date"),
        ("customer_id", "STRING", "fk", "fact_sales.customer_id"),
        ("sales_channel_id", "INT64", "fk", "fact_sales.sales_channel_id"),
        ("source", "STRING", "", "fact_sales.source"),
        ("is_synthetic", "BOOL", "", "fact_sales.is_synthetic"),
        ("lineas", "INT64", "", "COUNT(*)"),
        ("unidades", "INT64", "", "SUM(qty)"),
        ("importe", "FLOAT64", "", "SUM(price × qty)"),
    ]),
    "dim_article": (ART, "DIMENSIÓN", "105,542", "1 fila = 1 artículo", [
        ("article_id", "STRING", "pk", "articles.article_id"),
        ("product_code", "STRING", "", "articles"),
        ("prod_name", "STRING", "", "articles"),
        ("product_type_name", "STRING", "", "articles"),
        ("product_group_name", "STRING", "", "articles"),
        ("colour_group_name", "STRING", "", "articles"),
        ("perceived_colour_master_name", "STRING", "", "articles"),
        ("department_name", "STRING", "", "articles"),
        ("index_name", "STRING", "", "articles"),
        ("index_group_name", "STRING", "", "articles"),
        ("section_name", "STRING", "", "articles"),
        ("garment_group_name", "STRING", "", "articles"),
        ("detail_desc", "STRING", "", "articles (imputada)"),
    ]),
    "reco_popular": (RECO, "SERVICIO", "17,986", "1 fila = artículo top por grupo (7 días)", [
        ("index_group_name", "STRING", "", "dim_article"),
        ("article_id", "STRING", "fk", "fact_sales"),
        ("ventas_7d", "INT64", "", "COUNT última semana"),
        ("rank_grupo", "INT64", "", "RANK por grupo"),
    ]),
    "dim_customer": (CUS, "DIMENSIÓN", "1,371,980", "1 fila = 1 cliente", [
        ("customer_id", "STRING", "pk", "customers.customer_id"),
        ("age", "INT64", "", "customers.age"),
        ("age_band", "STRING", "", "derivada de age"),
        ("club_member_status", "STRING", "", "customers"),
        ("fashion_news_frequency", "STRING", "", "customers"),
        ("fn", "INT64", "", "FN (vacío → 0)"),
        ("active", "INT64", "", "Active (vacío → 0)"),
    ]),
    "dim_date": (DATE, "DIMENSIÓN", "3,409", "1 fila = 1 día (2018-09-01 a 2027-12-31)", [
        ("date_key", "DATE", "pk", "calendario generado"),
        ("anio", "INT64", "", ""),
        ("mes", "INT64", "", ""),
        ("anio_mes", "STRING", "", "AAAA-MM"),
        ("semana_iso", "INT64", "", ""),
        ("dia_semana", "STRING", "", ""),
        ("fin_de_semana", "BOOL", "", "sábado o domingo"),
    ]),
    "dim_channel": (CHAN, "DIMENSIÓN", "2", "1 fila = 1 canal de venta", [
        ("sales_channel_id", "INT64", "pk", "1 = tienda · 2 = online"),
        ("canal", "STRING", "", "Tienda física / Online"),
        ("nota", "STRING", "", "supuesto documentado"),
    ]),
}

W, H = 100, 56.25
fig = plt.figure(figsize=(19.2, 10.8))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor(BG)

ax.add_patch(plt.Rectangle((0, H - 6.6), W, 6.6, color=NAVY))
ax.add_patch(plt.Rectangle((0, H - 6.85), W, 0.25, color=FACT))
ax.text(2, H - 2.6, "STYLUS · Modelo estrella (capa Gold)", fontsize=24, fontweight="bold", color="white", va="center")
ax.text(2, H - 5.0, "Dataset BigQuery retail_gold · 2 tablas de hechos · 4 dimensiones · 1 tabla de recomendación · datos públicos H&M",
        fontsize=12.5, color="#C9D6EA", va="center")
for i, (v, l) in enumerate([("31.8 M", "líneas de venta"), ("9.08 M", "pedidos"), ("1.37 M", "clientes"), ("105.5 K", "artículos")]):
    x = 65 + i * 8.6
    ax.text(x, H - 2.5, v, fontsize=18, fontweight="bold", color="white", va="center")
    ax.text(x, H - 4.8, l, fontsize=10, color="#C9D6EA", va="center")

ROW, HEAD, GRAIN = 1.3, 2.6, 1.25
POS = {}  # (tabla, columna) -> (y, x_izq, x_der)


def card(name, x, top, width, colw):
    color, rol, filas, grano, cols = T[name]
    tot = sum(colw)
    cw = [width * c / tot for c in colw]
    h = HEAD + GRAIN + ROW * (len(cols) + 1) + 0.35
    y0 = top - h
    lw = 2.4 if rol == "HECHO" else 1.5
    ax.add_patch(FancyBboxPatch((x, y0), width, h, boxstyle="round,pad=0,rounding_size=0.6", fc="white", ec=color, lw=lw))
    ax.add_patch(FancyBboxPatch((x, top - HEAD), width, HEAD, boxstyle="round,pad=0,rounding_size=0.6", fc=color, ec=color))
    ax.add_patch(plt.Rectangle((x, top - HEAD), width, 0.7, color=color))
    tc = INK if color == FACT else "white"
    ax.text(x + 0.7, top - HEAD / 2, name, fontsize=13, fontweight="bold", color=tc, va="center")
    ax.text(x + width - 0.7, top - HEAD / 2 + 0.45, rol, fontsize=7.5, fontweight="bold", color=tc, va="center", ha="right")
    ax.text(x + width - 0.7, top - HEAD / 2 - 0.5, filas + " filas", fontsize=9, fontweight="bold", color=tc, va="center", ha="right")
    ax.text(x + 0.7, top - HEAD - GRAIN / 2, grano, fontsize=8.6, style="italic", color=GREY, va="center")
    y = top - HEAD - GRAIN - ROW
    cx = x
    for hn, w_ in zip(["Columna", "Tipo", "Origen"], cw):
        ax.text(cx + 0.6, y + ROW / 2, hn, fontsize=8.2, fontweight="bold", color=color if color != FACT else "#8A6D00", va="center")
        cx += w_
    ax.plot([x + 0.4, x + width - 0.4], [y, y], color=color, lw=0.9)
    for i, (col, tipo, key, origen) in enumerate(cols):
        y -= ROW
        if i % 2:
            ax.add_patch(plt.Rectangle((x + 0.3, y), width - 0.6, ROW, color="#F3F6FA"))
        ax.text(x + 0.6, y + ROW / 2, col, fontsize=8.8, fontweight="bold" if key else "normal", color=INK, va="center")
        if key:
            ax.text(x + cw[0] - 0.3, y + ROW / 2, key.upper(), fontsize=6.8, fontweight="bold", color="white", va="center", ha="right",
                    bbox=dict(boxstyle="round,pad=0.22", fc=NAVY if key == "pk" else "#B8860B", ec="none"))
        ax.text(x + cw[0] + 0.6, y + ROW / 2, tipo, fontsize=8.2, color=GREY, va="center", family="DejaVu Sans Mono")
        ax.text(x + cw[0] + cw[1] + 0.6, y + ROW / 2, origen, fontsize=8.2, color=GREY, va="center")
        POS[(name, col)] = (y + ROW / 2, x, x + width)
    return y0


TOP = H - 8.4
b_art = card("dim_article", 1.5, TOP, 25, [11, 4, 7])
card("reco_popular", 1.5, b_art - 2.6, 25, [11, 4, 7])
b_fs = card("fact_sales", 36, TOP, 28, [9, 4.5, 10.5])
card("fact_orders", 36, b_fs - 4.6, 28, [9, 4.5, 10.5])
b_cu = card("dim_customer", 74, TOP, 24.5, [10.5, 4, 8])
b_da = card("dim_date", 74, b_cu - 1.9, 24.5, [10.5, 4, 8])
card("dim_channel", 74, b_da - 1.9, 24.5, [10.5, 4, 8])


def link(a, b, color, xm, dashed=False):
    """Conector ortogonal: a = (dimensión, columna) lado 1 ; b = (hecho, columna) lado N ; xm = carril vertical."""
    ya, xla, xra = POS[a]
    yb, xlb, xrb = POS[b]
    dim_right = xla > xrb
    xd = xla - 0.15 if dim_right else xra + 0.15
    xf = xrb + 0.15 if dim_right else xlb - 0.15
    ax.plot([xf, xm, xm, xd], [yb, yb, ya, ya], color=color, lw=1.3 if dashed else 2.4, alpha=0.8 if dashed else 0.95,
            linestyle=(0, (4, 3)) if dashed else "-", solid_capstyle="round", solid_joinstyle="round")
    sgn = 1 if dim_right else -1
    ax.text(xd - sgn * 0.7, ya + 0.5, "1", fontsize=8.5, fontweight="bold", color=color, ha="center", va="center")
    ax.text(xf + sgn * 0.7, yb + 0.5, "N", fontsize=8.5, fontweight="bold", color=color, ha="center", va="center")


link(("dim_article", "article_id"), ("fact_sales", "article_id"), ART, 31.0)
link(("dim_customer", "customer_id"), ("fact_sales", "customer_id"), CUS, 69.0)
link(("dim_date", "date_key"), ("fact_sales", "sale_date"), DATE, 71.0)
link(("dim_channel", "sales_channel_id"), ("fact_sales", "sales_channel_id"), CHAN, 67.0)
link(("dim_customer", "customer_id"), ("fact_orders", "customer_id"), CUS, 68.0, dashed=True)
link(("dim_date", "date_key"), ("fact_orders", "order_date"), DATE, 70.0, dashed=True)
link(("dim_channel", "sales_channel_id"), ("fact_orders", "sales_channel_id"), CHAN, 66.0, dashed=True)
ya, xla, _ = POS[("dim_article", "article_id")]
yr, xlr, _ = POS[("reco_popular", "article_id")]
ax.plot([xla - 0.15, 0.6, 0.6, xlr - 0.15], [ya, ya, yr, yr], color=RECO, lw=2.0, solid_joinstyle="round")
ax.text(xla - 0.5, ya + 0.5, "1", fontsize=8.5, fontweight="bold", color=RECO, ha="center")
ax.text(xlr - 0.5, yr + 0.5, "N", fontsize=8.5, fontweight="bold", color=RECO, ha="center")

# fact_sales -> fact_orders
ax.add_patch(FancyArrowPatch((50, b_fs - 0.15), (50, b_fs - 4.45), arrowstyle="-|>,head_length=5,head_width=3.5",
                             color=FACT, lw=2.6, mutation_scale=2.2))
ax.text(51.2, b_fs - 2.3, "agrega por cliente + día + fuente", fontsize=9, fontweight="bold", color="#8A6D00", va="center")

ax.add_patch(plt.Rectangle((0, 0), W, 2.6, color="#E3E8F0"))
ax.text(2, 1.3, "PK = clave única · FK = referencia a una dimensión · 1 : N = una fila de la dimensión, muchas filas en el hecho · "
        "línea continua = fact_sales, punteada = fact_orders.   Fuente: sql/gold/01_gold_model.sql", fontsize=9.3, color=GREY, va="center")

fig.savefig(IMG / "modelo_estrella.png", dpi=200, facecolor=BG)
fig.savefig(IMG / "modelo_estrella.jpg", dpi=200, facecolor=BG, pil_kwargs={"quality": 92})
print("ok")
