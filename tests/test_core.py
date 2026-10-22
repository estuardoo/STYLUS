import sys, unittest, datetime as dt
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ingestion/streaming"), str(ROOT / "cost")]
import replay_publisher as rp
import estimate_costs as ec


class TestReplay(unittest.TestCase):
    row = {"t_dat": "2019-06-15", "customer_id": "c1", "article_id": "0108775015", "price": "0.05", "sales_channel_id": "2"}

    def test_event_2026_preserva_origen_e_idempotente(self):
        a = rp.to_event(self.row, 7, dt.date(2026, 11, 1), "r1")
        b = rp.to_event(self.row, 7, dt.date(2026, 11, 1), "r2")
        self.assertEqual(a["event_id"], b["event_id"])          # reintento = mismo id
        self.assertEqual(a["source_t_dat"], "2019-06-15")       # fecha real intacta
        self.assertTrue(a["event_time"].startswith(("2026", "2027")))
        self.assertTrue(a["is_synthetic"])


class TestCost(unittest.TestCase):
    def test_free_tier_y_total(self):
        cfg = yaml.safe_load((ROOT / "cost/assumptions.yaml").read_text(encoding="utf-8"))
        r = ec.compute(cfg)
        self.assertEqual(r["dev"]["detalle"]["bq_query_tib"], 0)  # 0.8 TiB < 1 TiB gratis
        self.assertAlmostEqual(r["anio1"], r["produccion"]["total"] * 11 + r["pico_black_friday"]["total"], 6)


if __name__ == "__main__":
    unittest.main()
