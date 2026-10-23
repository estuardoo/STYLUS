"""API de la tienda demo: catálogo, recomendaciones, asistente, carrito, saldo simulado y pedidos.
El saldo es la suma de un ledger append-only y nunca lo escribe el cliente. Sin dinero real."""
import datetime as dt
import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

import assistant

HERE = Path(__file__).parent
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/retail_demo.db")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
TOPUP_MAX = int(os.getenv("DEMO_TOPUP_MAX_CENTS", "50000"))
SEED_FILE = Path(os.getenv("SEED_FILE", HERE / "seed.json"))  # generado desde el Excel de control
PRICE_DEMO_FACTOR = float(os.getenv("PRICE_DEMO_FACTOR", "500"))
log = logging.getLogger("api")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
IS_PG = engine.dialect.name == "postgresql"
app = FastAPI(title="Retail Intelligence API", version="1.0.0",
              description="Tienda demo H&M sobre GCP. Precios y saldo simulados.")


def init_db():
    files = ["schema.sql"] + (["schema_pg.sql"] if IS_PG else [])
    with engine.begin() as c:
        for f in files:
            for stmt in filter(str.strip, (HERE / f).read_text(encoding="utf-8").split(";")):
                c.execute(text(stmt))
        users = json.loads(SEED_FILE.read_text(encoding="utf-8"))["users"] if SEED_FILE.exists() else []
        for u in users:  # idempotente: no duplica usuarios ni saldo inicial
            c.execute(text("INSERT INTO users (user_id, nombre) VALUES (:u, :n) ON CONFLICT DO NOTHING"),
                      {"u": u["user_id"], "n": u["nombre"]})
            if u.get("saldo_inicial_cents"):
                c.execute(text("INSERT INTO wallet_ledger (entry_id, user_id, amount_cents, kind, ref) "
                               "VALUES (:e, :u, :m, 'demo_topup', 'seed') ON CONFLICT DO NOTHING"),
                          {"e": f"seed-{u['user_id']}", "u": u["user_id"], "m": int(u["saldo_inicial_cents"])})


@app.on_event("startup")
def _startup():
    init_db()


def user_id(x_user_id: str = Header(default="demo")) -> str:
    with engine.connect() as c:
        if not c.execute(text("SELECT 1 FROM users WHERE user_id = :u"), {"u": x_user_id}).first():
            raise HTTPException(401, "Usuario demo desconocido")
    return x_user_id


def balance(c, uid):
    return c.execute(text("SELECT COALESCE(SUM(amount_cents), 0) FROM wallet_ledger WHERE user_id = :u"),
                     {"u": uid}).scalar_one()


COLS = "article_id, prod_name, product_type, product_group, index_group, section, colour, price_cents, popularity, stock"


def search(f, k):
    where, p = ["stock > 0"], {"k": min(int(k), 50)}
    if f.get("grupo"):
        where.append("index_group = :g"); p["g"] = f["grupo"]
    if f.get("seccion"):
        where.append("section LIKE :s"); p["s"] = f"%{f['seccion']}%"
    if f.get("tipos"):
        keys = [f"t{i}" for i in range(len(f["tipos"]))]  # prefijo: 'Pyjama' cubre 'Pyjama set', etc.
        where.append("(" + " OR ".join(f"product_type LIKE :{x}" for x in keys) + ")")
        p.update({x: t + "%" for x, t in zip(keys, f["tipos"])})
    if f.get("palabras"):
        ors = []
        for i, w in enumerate(f["palabras"][:5]):
            ors.append(f"(LOWER(prod_name) LIKE :w{i} OR LOWER(detail_desc) LIKE :w{i})"); p[f"w{i}"] = f"%{w.lower()}%"
        where.append("(" + " OR ".join(ors) + ")")
    if f.get("presupuesto_max"):
        where.append("price_cents <= :pmax"); p["pmax"] = int(f["presupuesto_max"])
    sql = f"SELECT {COLS} FROM articles WHERE {' AND '.join(where)} ORDER BY popularity DESC, article_id LIMIT :k"
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), p)]


def tipos_validos():
    with engine.connect() as c:
        return [r[0] for r in c.execute(text("SELECT DISTINCT product_type FROM articles WHERE product_type IS NOT NULL"))]


_PUBLISHER = None


def publish_purchase_events(order_id, uid, lines):
    """Cierra el ciclo E2E: cada compra viaja por Pub/Sub -> BigQuery como en el replay."""
    global _PUBLISHER
    topic, project = os.getenv("PUBSUB_TOPIC"), os.getenv("GCP_PROJECT_ID")
    if not (topic and project):
        return
    try:
        from google.cloud import pubsub_v1
        _PUBLISHER = _PUBLISHER or pubsub_v1.PublisherClient()
        pub = _PUBLISHER
        path = pub.topic_path(project, topic)
        futures = []
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        for i, l in enumerate(lines):
            ev = {"event_id": f"{order_id}-{i}", "event_type": "purchase", "event_time": now,
                  "source_t_dat": None, "customer_id": uid, "article_id": l["article_id"],
                  "price": round(l["price_cents"] / 100 / PRICE_DEMO_FACTOR, 6), "sales_channel_id": 2,
                  "qty": l["qty"], "order_id": order_id, "source_system": "web_demo", "schema_version": 1,
                  "is_synthetic": True, "simulation_run_id": "web", "simulated_at": now}
            futures.append(pub.publish(path, json.dumps(ev).encode(), event_type="purchase", event_id=ev["event_id"]))
        for f in futures:  # esperar: Cloud Run limita CPU tras responder y el mensaje se perdería
            f.result(timeout=10)
    except Exception:  # la compra ya está confirmada en la base; el evento no debe romperla
        log.exception("no se pudo publicar el evento de compra %s", order_id)


# ---------------- modelos ----------------
class RecoIn(BaseModel):
    necesidad: str = ""
    k: int = Field(12, ge=1, le=50)


class AssistantIn(BaseModel):
    mensaje: str = Field(..., min_length=2, max_length=500)


class CartItemIn(BaseModel):
    article_id: str
    qty: int = Field(1, ge=1, le=10)


class CheckoutIn(BaseModel):
    confirmar: bool = False
    idempotency_key: str = Field(..., min_length=8, max_length=64)


class TopupIn(BaseModel):
    amount_cents: int = Field(..., gt=0)


# ---------------- endpoints ----------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    with engine.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM articles")).scalar_one()
    return {"status": "ready" if n else "sin_catalogo", "articulos": n}


@app.get("/api/v1/catalog/products")
def catalog(q: str = "", grupo: str = "", tipo: str = "", limit: int = 20):
    f = {"grupo": grupo, "tipos": [tipo] if tipo else [], "palabras": [q] if q else []}
    return {"items": search(f, limit)}


@app.post("/api/v1/recommendations")
def recommendations(body: RecoIn, uid: str = Depends(user_id)):
    """Contenido + popularidad: perfil = grupo más comprado por el usuario (o el que pide la necesidad)."""
    f = assistant.intent_reglas(body.necesidad) if body.necesidad else {}
    if not f.get("grupo"):
        with engine.connect() as c:
            row = c.execute(text(
                "SELECT a.index_group, COUNT(*) n FROM order_lines ol JOIN orders o USING (order_id) "
                "JOIN articles a USING (article_id) WHERE o.user_id = :u GROUP BY a.index_group ORDER BY n DESC"),
                {"u": uid}).first()
        f = {**f, "grupo": row[0] if row else ""}
    items = search(f, body.k)
    why = f"Populares en {f['grupo']}" if f.get("grupo") else "Más vendidos del catálogo (sin historial: cold-start)"
    return {"items": items, "explicacion": why, "filtros": f}


@app.post("/api/v1/assistant/message")
def assistant_message(body: AssistantIn, uid: str = Depends(user_id)):
    return assistant.reply(body.mensaje, search, tipos_validos())


@app.get("/api/v1/cart")
def get_cart(uid: str = Depends(user_id)):
    with engine.connect() as c:
        rows = [dict(r._mapping) for r in c.execute(text(
            "SELECT ci.article_id, a.prod_name, ci.qty, a.price_cents, ci.qty * a.price_cents AS subtotal_cents "
            "FROM cart_items ci JOIN articles a USING (article_id) WHERE ci.user_id = :u ORDER BY a.prod_name"), {"u": uid})]
    return {"items": rows, "total_cents": sum(r["subtotal_cents"] for r in rows)}


@app.post("/api/v1/cart/items")
def add_item(body: CartItemIn, uid: str = Depends(user_id)):
    with engine.begin() as c:
        if not c.execute(text("SELECT 1 FROM articles WHERE article_id = :a"), {"a": body.article_id}).first():
            raise HTTPException(404, "Artículo no existe en el catálogo")
        c.execute(text("DELETE FROM cart_items WHERE user_id = :u AND article_id = :a"), {"u": uid, "a": body.article_id})
        c.execute(text("INSERT INTO cart_items (user_id, article_id, qty) VALUES (:u, :a, :q)"),
                  {"u": uid, "a": body.article_id, "q": body.qty})
    return get_cart(uid)


@app.delete("/api/v1/cart/items/{article_id}")
def remove_item(article_id: str, uid: str = Depends(user_id)):
    with engine.begin() as c:
        c.execute(text("DELETE FROM cart_items WHERE user_id = :u AND article_id = :a"), {"u": uid, "a": article_id})
    return get_cart(uid)


@app.post("/api/v1/checkout")
def checkout(body: CheckoutIn, uid: str = Depends(user_id)):
    if not body.confirmar:
        raise HTTPException(400, "La compra requiere confirmación explícita (confirmar=true)")
    try:
        with engine.begin() as c:  # una transacción: débito + pedido + stock, o nada
            if IS_PG:
                c.execute(text("SELECT 1 FROM users WHERE user_id = :u FOR UPDATE"), {"u": uid})
            prev = c.execute(text("SELECT order_id, total_cents FROM orders WHERE idempotency_key = :k"),
                             {"k": body.idempotency_key}).first()
            if prev:
                return {"order_id": prev[0], "total_cents": prev[1], "duplicado": True}
            lines = [dict(r._mapping) for r in c.execute(text(
                "SELECT ci.article_id, ci.qty, a.price_cents, a.stock FROM cart_items ci "
                "JOIN articles a USING (article_id) WHERE ci.user_id = :u"), {"u": uid})]
            if not lines:
                raise HTTPException(400, "Carrito vacío")
            if any(l["qty"] > l["stock"] for l in lines):
                raise HTTPException(409, "Stock insuficiente")
            total = sum(l["qty"] * l["price_cents"] for l in lines)
            saldo = balance(c, uid)
            if saldo < total:
                raise HTTPException(409, f"Saldo insuficiente: {saldo} < {total} centavos")
            oid = uuid.uuid4().hex
            c.execute(text("INSERT INTO orders (order_id, user_id, total_cents, idempotency_key) VALUES (:o, :u, :t, :k)"),
                      {"o": oid, "u": uid, "t": total, "k": body.idempotency_key})
            for l in lines:
                c.execute(text("INSERT INTO order_lines (order_id, article_id, qty, price_cents) VALUES (:o, :a, :q, :p)"),
                          {"o": oid, "a": l["article_id"], "q": l["qty"], "p": l["price_cents"]})
                c.execute(text("UPDATE articles SET stock = stock - :q WHERE article_id = :a"), {"q": l["qty"], "a": l["article_id"]})
            c.execute(text("INSERT INTO wallet_ledger (entry_id, user_id, amount_cents, kind, ref) VALUES (:e, :u, :m, 'purchase', :o)"),
                      {"e": uuid.uuid4().hex, "u": uid, "m": -total, "o": oid})
            c.execute(text("DELETE FROM cart_items WHERE user_id = :u"), {"u": uid})
    except IntegrityError:  # misma idempotency_key en paralelo: devolver el pedido ya creado
        with engine.connect() as c:
            prev = c.execute(text("SELECT order_id, total_cents FROM orders WHERE idempotency_key = :k"),
                             {"k": body.idempotency_key}).first()
        return {"order_id": prev[0], "total_cents": prev[1], "duplicado": True}
    publish_purchase_events(oid, uid, lines)
    return {"order_id": oid, "total_cents": total, "saldo_restante_cents": saldo - total, "duplicado": False}


@app.get("/api/v1/wallet")
def wallet(uid: str = Depends(user_id)):
    with engine.connect() as c:
        movs = [dict(r._mapping) for r in c.execute(text(
            "SELECT amount_cents, kind, ref, created_at FROM wallet_ledger WHERE user_id = :u ORDER BY created_at DESC LIMIT 20"),
            {"u": uid})]
        return {"saldo_cents": balance(c, uid), "movimientos": movs, "aviso": "Saldo simulado; no es dinero real."}


@app.post("/api/v1/wallet/demo-topups")
def demo_topup(body: TopupIn, uid: str = Depends(user_id), x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(403, "Recarga demo solo con X-Admin-Token")
    if body.amount_cents > TOPUP_MAX:
        raise HTTPException(400, f"Máximo por recarga: {TOPUP_MAX} centavos")
    with engine.begin() as c:
        c.execute(text("INSERT INTO wallet_ledger (entry_id, user_id, amount_cents, kind, ref) VALUES (:e, :u, :m, 'demo_topup', 'admin')"),
                  {"e": uuid.uuid4().hex, "u": uid, "m": body.amount_cents})
    return wallet(uid)


@app.get("/api/v1/orders")
def orders(uid: str = Depends(user_id)):
    with engine.connect() as c:
        return {"items": [dict(r._mapping) for r in c.execute(text(
            "SELECT order_id, total_cents, created_at FROM orders WHERE user_id = :u ORDER BY created_at DESC"), {"u": uid})]}


@app.get("/api/v1/metrics/summary")
def metrics():
    with engine.connect() as c:
        r = c.execute(text("SELECT COUNT(*), COALESCE(SUM(total_cents), 0) FROM orders")).first()
    return {"pedidos": r[0], "ventas_cents": r[1], "ticket_medio_cents": (r[1] // r[0]) if r[0] else 0,
            "nota": "Pedidos de la tienda demo (sintéticos)."}


@app.get("/api/v1/catalog/products/{article_id}/image")
def image(article_id: str):
    """Imagen H&M: carpeta local (IMAGES_DIR) o bucket privado (IMAGES_BUCKET)."""
    if not article_id.isdigit():
        raise HTTPException(400, "id inválido")
    rel = f"{article_id[:3]}/{article_id}.jpg"
    if os.getenv("IMAGES_DIR"):
        p = Path(os.environ["IMAGES_DIR"]) / rel
        if p.exists():
            return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})
    elif os.getenv("IMAGES_BUCKET"):
        from google.cloud import storage
        blob = storage.Client().bucket(os.environ["IMAGES_BUCKET"]).blob(f"hm/images/{rel}")
        if blob.exists():
            return Response(blob.download_as_bytes(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(404, "Sin imagen")


app.mount("/", StaticFiles(directory=HERE / "static", html=True), name="web")
