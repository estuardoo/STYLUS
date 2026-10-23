import json, os, sys, tempfile, unittest
from pathlib import Path

TMP = Path(tempfile.mkdtemp())
DB = TMP / "t.db"
(TMP / "seed.json").write_text(json.dumps({"users": [{"user_id": "demo", "nombre": "Demo", "saldo_inicial_cents": 0},
                                                    {"user_id": "demo2", "nombre": "Demo 2", "saldo_inicial_cents": 700}]}))
os.environ.update(DATABASE_URL=f"sqlite:///{DB}", ADMIN_TOKEN="secreto", ASSISTANT_MODE="rules", SEED_FILE=str(TMP / "seed.json"))
os.environ.pop("PUBSUB_TOPIC", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
import main  # noqa: E402

ARTS = [("0001", "Body bebé", "Bodysuit", "Baby/Children", "Baby Essentials & Complements", 1500, 90),
        ("0002", "Pijama bebé", "Pyjama", "Baby/Children", "Baby Boy", 2500, 80),
        ("0003", "Polo hombre", "T-shirt", "Menswear", "Men Edition", 3000, 70)]


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.init_db()
        with main.engine.begin() as c:
            for a in ARTS:
                c.execute(text("INSERT INTO articles (article_id, prod_name, product_type, index_group, section, price_cents, popularity, stock) "
                               "VALUES (:a,:n,:t,:g,:s,:p,:pop,5)"), dict(zip(["a", "n", "t", "g", "s", "p", "pop"], a)))
        cls.c = TestClient(main.app)

    def test_flujo_compra_segura(self):
        c, h = self.c, {"X-User-Id": "demo"}
        self.assertEqual(c.post("/api/v1/wallet/demo-topups", json={"amount_cents": 5000}, headers=h).status_code, 403)
        c.post("/api/v1/wallet/demo-topups", json={"amount_cents": 5000}, headers={**h, "X-Admin-Token": "secreto"})
        r = c.post("/api/v1/assistant/message", json={"mensaje": "necesito algo para mi bebé"}, headers=h).json()
        self.assertTrue(r["requiere_confirmacion"])
        self.assertEqual({p["index_group"] for p in r["productos"]}, {"Baby/Children"})
        for it in r["carrito_propuesto"]:
            c.post("/api/v1/cart/items", json=it, headers=h)
        self.assertEqual(c.post("/api/v1/checkout", json={"confirmar": False, "idempotency_key": "k-00000001"}, headers=h).status_code, 400)
        ok = c.post("/api/v1/checkout", json={"confirmar": True, "idempotency_key": "k-00000001"}, headers=h).json()
        self.assertEqual(ok["total_cents"], 4000)
        dup = c.post("/api/v1/checkout", json={"confirmar": True, "idempotency_key": "k-00000001"}, headers=h).json()
        self.assertTrue(dup["duplicado"])                                    # doble clic: un solo cobro
        self.assertEqual(c.get("/api/v1/wallet", headers=h).json()["saldo_cents"], 1000)
        c.post("/api/v1/cart/items", json={"article_id": "0003", "qty": 1}, headers=h)
        r = c.post("/api/v1/checkout", json={"confirmar": True, "idempotency_key": "k-00000002"}, headers=h)
        self.assertEqual(r.status_code, 409)                                 # sin sobregiro
        self.assertEqual(c.get("/api/v1/wallet", headers=h).json()["saldo_cents"], 1000)

    def test_reco_cold_start_y_health(self):
        self.assertEqual(self.c.get("/ready").json()["articulos"], 3)
        r = self.c.post("/api/v1/recommendations", json={"k": 2}, headers={"X-User-Id": "demo2"}).json()
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(self.c.get("/api/v1/wallet", headers={"X-User-Id": "nadie"}).status_code, 401)
        main.init_db()  # reinicio: la semilla no duplica el saldo inicial
        self.assertEqual(self.c.get("/api/v1/wallet", headers={"X-User-Id": "demo2"}).json()["saldo_cents"], 700)


if __name__ == "__main__":
    unittest.main()
