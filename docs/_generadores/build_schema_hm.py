"""Lámina del esquema original del dataset H&M (3 CSV) con tipos, nulos y valores.
Uso: python docs/_generadores/build_schema_hm.py -> docs/guia/img/schema_hm.png (+ .jpg local)
Cifras: perfilado con DuckDB sobre data/raw (conteos exactos de nulos y distintos).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "docs/guia/img"
NAVY, GREY, INK, BG = "#1F3864", "#595959", "#1F1F1F", "#F4F6FA"
ART, CUS, TRX = "#2E75B6", "#1B998B", "#C9A227"
OKF, OKC, WAF, WAC = "#E3F1E4", "#2E7D32", "#FFF1D6", "#9A6700"

ARTICLES = [
    ("article_id", "STRING", 0, "PK · 105,542 únicos · 0108775015", "pk"),
    ("product_code", "STRING", 0, "47,224 productos · 0108775", ""),
    ("prod_name", "STRING", 0, "45,875 nombres · Strap top", ""),
    ("product_type_no", "INT", 0, "132 códigos · 253", ""),
    ("product_type_name", "STRING", 0, "131 tipos · Vest top", ""),
    ("product_group_name", "STRING", 0, "19 grupos · Garment Upper body", ""),
    ("graphical_appearance_no", "INT", 0, "30 códigos · 1010016", ""),
    ("graphical_appearance_name", "STRING", 0, "30 estampados · Solid", ""),
    ("colour_group_code", "STRING", 0, "50 códigos · 09", ""),
    ("colour_group_name", "STRING", 0, "50 colores · Black", ""),
    ("perceived_colour_value_id", "INT", 0, "8 · 4", ""),
    ("perceived_colour_value_name", "STRING", 0, "8 tonos · Dark", ""),
    ("perceived_colour_master_id", "INT", 0, "20 · 5", ""),
    ("perceived_colour_master_name", "STRING", 0, "20 colores base · Black", ""),
    ("department_no", "INT", 0, "299 códigos · 1676", ""),
    ("department_name", "STRING", 0, "250 departamentos · Jersey Basic", ""),
    ("index_code", "STRING", 0, "10 códigos · A", ""),
    ("index_name", "STRING", 0, "10 índices · Ladieswear", ""),
    ("index_group_no", "INT", 0, "5 · 1", ""),
    ("index_group_name", "STRING", 0, "5 grupos · Ladieswear · Baby/Children…", ""),
    ("section_no", "INT", 0, "57 códigos · 16", ""),
    ("section_name", "STRING", 0, "56 secciones · Womens Everyday Basics", ""),
    ("garment_group_no", "INT", 0, "21 códigos · 1002", ""),
    ("garment_group_name", "STRING", 0, "21 grupos de prenda · Jersey Basic", ""),
    ("detail_desc", "STRING", 416, "43,404 textos · Jersey top with narrow…", ""),
]
TRANSACTIONS = [
    ("t_dat", "DATE", 0, "2018-09-20 → 2020-09-22 (2 años)", ""),
    ("customer_id", "STRING(64)", 0, "FK → customers · hash seudonimizado", "fk"),
    ("article_id", "STRING(10)", 0, "FK → articles · 0663713001", "fk"),
    ("price", "FLOAT", 0, "normalizado · máx. 0.59 · sin moneda", ""),
    ("sales_channel_id", "INT", 0, "1 = tienda (29.6%) · 2 = online (70.4%)", ""),
]
CUSTOMERS = [
    ("customer_id", "STRING(64)", 0, "PK · 1,371,980 únicos · hash", "pk"),
    ("FN", "FLOAT", 895_050, "1.0 o vacío · recibe noticias", ""),
    ("Active", "FLOAT", 907_576, "1.0 o vacío · cliente activo", ""),
    ("club_member_status", "STRING", 6_062, "ACTIVE 1.27 M · PRE-CREATE 93 k · LEFT CLUB 467", ""),
    ("fashion_news_frequency", "STRING", 16_009, "NONE 878 k · Regularly 477 k · Monthly 842", ""),
    ("age", "INT", 15_861, "16 a 99 años · 84 edades distintas", ""),
    ("postal_code", "STRING(64)", 0, "352,899 códigos · hash", ""),
]

W, H = 100, 56.25
fig = plt.figure(figsize=(19.2, 10.8))
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor(BG)

ax.add_patch(plt.Rectangle((0, H - 6.6), W, 6.6, color=NAVY))
ax.add_patch(plt.Rectangle((0, H - 6.85), W, 0.25, color=TRX))
ax.text(2, H - 2.6, "Dataset H&M · Esquema de los datos originales", fontsize=24, fontweight="bold", color="white", va="center")
ax.text(2, H - 5.0, "Kaggle · H&M Personalized Fashion Recommendations · 3 archivos CSV · 3.7 GB · datos públicos y seudonimizados",
        fontsize=12.5, color="#C9D6EA", va="center")
for i, (v, l) in enumerate([("31.8 M", "transacciones"), ("1.37 M", "clientes"), ("105.5 K", "artículos"), ("2 años", "sep-2018 a sep-2020")]):
    x = 65 + i * 8.6
    ax.text(x, H - 2.5, v, fontsize=18, fontweight="bold", color="white", va="center")
    ax.text(x, H - 4.8, l, fontsize=10, color="#C9D6EA", va="center")

ROW = 1.42
ROWS_Y = {}


def table(x, top, width, title, meta, color, rows, colw):
    """colw: anchos relativos de columna, tipo, nulos, valores."""
    tot = sum(colw)
    cw = [width * c / tot for c in colw]
    h = 2.6 + ROW * (len(rows) + 1) + 0.4
    y0 = top - h
    ax.add_patch(FancyBboxPatch((x, y0), width, h, boxstyle="round,pad=0,rounding_size=0.6", fc="white", ec=color, lw=1.6))
    ax.add_patch(FancyBboxPatch((x, top - 2.6), width, 2.6, boxstyle="round,pad=0,rounding_size=0.6", fc=color, ec=color))
    ax.add_patch(plt.Rectangle((x, top - 2.6), width, 0.7, color=color))
    ax.text(x + 0.8, top - 1.3, title, fontsize=14, fontweight="bold", color="white", va="center")
    ax.text(x + width - 0.8, top - 1.3, meta, fontsize=9.5, color="white", va="center", ha="right")
    y = top - 2.6 - ROW
    heads = ["Columna", "Tipo", "Nulos", "Valores / ejemplo"]
    cx = x
    for hname, w_ in zip(heads, cw):
        ax.text(cx + 0.6, y + ROW / 2, hname, fontsize=8.6, fontweight="bold", color=color, va="center")
        cx += w_
    ax.plot([x + 0.4, x + width - 0.4], [y, y], color=color, lw=1)
    for i, (col, tipo, nul, val, key) in enumerate(rows):
        y -= ROW
        if i % 2:
            ax.add_patch(plt.Rectangle((x + 0.3, y), width - 0.6, ROW, color="#F3F6FA"))
        cx = x + 0.6
        ax.text(cx, y + ROW / 2, col, fontsize=9, fontweight="bold" if key else "normal", color=INK, va="center")
        if key:
            ax.text(x + cw[0] - 0.4, y + ROW / 2, key.upper(), fontsize=7, fontweight="bold", color="white", va="center", ha="right",
                    bbox=dict(boxstyle="round,pad=0.25", fc=NAVY if key == "pk" else TRX, ec="none"))
        cx = x + cw[0]
        ax.text(cx + 0.6, y + ROW / 2, tipo, fontsize=8.6, color=GREY, va="center", family="DejaVu Sans Mono")
        cx += cw[1]
        fc, tc = (OKF, OKC) if nul == 0 else (WAF, WAC)
        ax.text(cx + 0.6, y + ROW / 2, f"{nul:,}", fontsize=8.6, fontweight="bold", color=tc, va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc=fc, ec="none"))
        cx += cw[2]
        ax.text(cx + 0.6, y + ROW / 2, val, fontsize=8.6, color=INK, va="center")
        ROWS_Y[(title, col)] = (y + ROW / 2, x, x + width)
    return y0


TOP = H - 8.4
table(1.5, TOP, 46, "articles.csv", "105,542 filas · 25 columnas · 36 MB", ART, ARTICLES, [12.5, 4.2, 3.4, 15])
yb = table(50.5, TOP, 48, "transactions_train.csv", "31,788,324 filas · 5 columnas · 3.5 GB", TRX, TRANSACTIONS, [8.5, 5.5, 3.4, 16])
yc = table(50.5, yb - 3.2, 48, "customers.csv", "1,371,980 filas · 7 columnas · 207 MB", CUS, CUSTOMERS, [9.5, 5.5, 3.6, 18])

# Relaciones
ya, _, _ = ROWS_Y[("transactions_train.csv", "article_id")]
yp, _, _ = ROWS_Y[("articles.csv", "article_id")]
ax.add_patch(FancyArrowPatch((50.4, ya), (47.6, yp), arrowstyle="-|>,head_length=5,head_width=3.5", color=ART, lw=2.4, mutation_scale=2.2))
ax.text(49.0, max(ya, yp) + 1.0, "N : 1", fontsize=9.5, fontweight="bold", color=ART, ha="center")
ax.add_patch(FancyArrowPatch((62, yb - 0.1), (62, yb - 3.1), arrowstyle="-|>,head_length=5,head_width=3.5", color=CUS, lw=2.4, mutation_scale=2.2))
ax.text(63, yb - 1.6, "customer_id  ·  N : 1  (muchas compras por cliente)", fontsize=9.5, fontweight="bold", color=CUS, va="center")
ax.text(49.0, min(ya, yp) - 1.4, "article_id", fontsize=8, color=ART, ha="center")

# Hallazgos
hy = yc - 1.2
hx, hw = 50.5, 48
hh = hy - 3.4
ax.add_patch(FancyBboxPatch((hx, 3.4), hw, hh, boxstyle="round,pad=0,rounding_size=0.6", fc="#FFFFFF", ec="#C9D1DC", lw=1.2))
ax.add_patch(plt.Rectangle((hx, 3.4), 0.5, hh, color=NAVY))
ax.text(hx + 1.2, hy - 1.1, "Qué hay que saber de estos datos", fontsize=11.5, fontweight="bold", color=NAVY, va="center")
notas = [
    "**article_id** y **product_code** tienen ceros a la izquierda: se leen como texto, no como número.",
    "No existe **order_id**: un pedido se define como cliente + día + fuente (9.08 M pedidos).",
    "**FN** y **Active** vienen vacíos en ~65%: vacío = no activo (se convierte a 0).",
    "**price** está normalizado (máx. 0.59) y sin moneda; la tienda demo usa un factor de precio declarado.",
    "416 artículos sin **detail_desc**: se reemplaza por el nombre del producto.",
    "**customer_id** y **postal_code** son hashes: el dataset no contiene datos personales.",
]
for i, t in enumerate(notas):
    yy = hy - 2.9 - i * 1.75
    parts = t.split("**")
    ax.text(hx + 1.2, yy, "■", fontsize=8, color=TRX, va="center")
    xx = hx + 2.1
    for j, p_ in enumerate(parts):
        txt = ax.text(xx, yy, p_, fontsize=10, color=INK, va="center", fontweight="bold" if j % 2 else "normal")
        fig.canvas.draw() if i == 0 and j == 0 else None
        bb = txt.get_window_extent(renderer=fig.canvas.get_renderer())
        xx += bb.width / fig.bbox.width * W

ax.add_patch(plt.Rectangle((0, 0), W, 2.6, color="#E3E8F0"))
ax.text(2, 1.3, "Nulos: ■ 0 = completo   ■ > 0 = con vacíos.   PK = identificador único · FK = referencia a otra tabla.   "
        "Fuente: kaggle.com/competitions/h-and-m-personalized-fashion-recommendations",
        fontsize=9.5, color=GREY, va="center")

fig.savefig(IMG / "schema_hm.png", dpi=200, facecolor=BG)
fig.savefig(IMG / "schema_hm.jpg", dpi=200, facecolor=BG, pil_kwargs={"quality": 92})
print("ok")
