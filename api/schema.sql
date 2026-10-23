-- Base transaccional de la tienda demo (SQLite local / PostgreSQL en Cloud SQL).
-- Montos en centavos (enteros). El saldo NO se guarda: es la suma del ledger.
CREATE TABLE IF NOT EXISTS users (
  user_id     TEXT PRIMARY KEY,
  nombre      TEXT NOT NULL,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (          -- catálogo de servicio (copia desde Gold)
  article_id     TEXT PRIMARY KEY,
  prod_name      TEXT NOT NULL,
  product_type   TEXT,
  product_group  TEXT,
  index_group    TEXT,
  section        TEXT,
  colour         TEXT,
  detail_desc    TEXT,
  price_cents    INTEGER NOT NULL,             -- precio demo (sintético, derivado del precio normalizado H&M)
  popularity     INTEGER NOT NULL DEFAULT 0,   -- ventas recientes (real, H&M)
  stock          INTEGER NOT NULL DEFAULT 0    -- inventario simulado
);
CREATE INDEX IF NOT EXISTS ix_articles_group ON articles (index_group, popularity);

CREATE TABLE IF NOT EXISTS cart_items (
  user_id     TEXT NOT NULL REFERENCES users(user_id),
  article_id  TEXT NOT NULL REFERENCES articles(article_id),
  qty         INTEGER NOT NULL CHECK (qty > 0 AND qty <= 10),
  PRIMARY KEY (user_id, article_id)
);

CREATE TABLE IF NOT EXISTS orders (
  order_id         TEXT PRIMARY KEY,
  user_id          TEXT NOT NULL REFERENCES users(user_id),
  total_cents      INTEGER NOT NULL CHECK (total_cents > 0),
  idempotency_key  TEXT NOT NULL UNIQUE,       -- evita doble cobro por doble clic o reintento
  created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_lines (
  order_id     TEXT NOT NULL REFERENCES orders(order_id),
  article_id   TEXT NOT NULL REFERENCES articles(article_id),
  qty          INTEGER NOT NULL,
  price_cents  INTEGER NOT NULL,
  PRIMARY KEY (order_id, article_id)
);

CREATE TABLE IF NOT EXISTS wallet_ledger (     -- append-only: recargas (+) y compras (-)
  entry_id      TEXT PRIMARY KEY,
  user_id       TEXT NOT NULL REFERENCES users(user_id),
  amount_cents  INTEGER NOT NULL,
  kind          TEXT NOT NULL CHECK (kind IN ('demo_topup', 'purchase')),
  ref           TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_ledger_user ON wallet_ledger (user_id)
