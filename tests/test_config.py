"""El Excel de control es válido, los generados están al día y el contrato de Cloud SQL coincide con api/schema.sql."""
import importlib.util
import json
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ops", ROOT / "ops.py")
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)


class TestConfig(unittest.TestCase):
    def test_generados_al_dia(self):
        full, tfvars, seed = ops.build_config(ops.read_excel())
        self.assertEqual(ops.TFVARS.read_text(encoding="utf-8"), ops._dump(tfvars))
        self.assertEqual(ops.SEED.read_text(encoding="utf-8"), ops._dump(seed))

    def test_validacion_detecta_errores(self):
        x = ops.read_excel()
        x["Permisos"].append({"principal": "sa:inexistente", "rol": "editor", "alcance": "proyecto", "motivo": "", "gestion": "excel"})
        with self.assertRaises(ops.ConfigError) as e:
            ops.build_config(x)
        self.assertIn("roles/", str(e.exception))
        self.assertIn("inexistente", str(e.exception))

    def test_contrato_cloudsql_igual_a_schema_sql(self):
        db = sqlite3.connect(":memory:")
        db.executescript((ROOT / "api/schema.sql").read_text(encoding="utf-8"))
        cols = json.loads(ops.GEN.read_text(encoding="utf-8"))["columns"]
        tablas = {c["tabla"] for c in cols if c["motor"] == "cloudsql"}
        for t in tablas:
            real = [r[1] for r in db.execute(f"PRAGMA table_info({t})")]
            esperado = [c["columna"] for c in cols if c["motor"] == "cloudsql" and c["tabla"] == t]
            self.assertEqual(real, esperado, t)


if __name__ == "__main__":
    unittest.main()
