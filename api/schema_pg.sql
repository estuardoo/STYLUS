-- Solo PostgreSQL: el ledger no admite UPDATE ni DELETE.
CREATE OR REPLACE RULE ledger_no_update AS ON UPDATE TO wallet_ledger DO INSTEAD NOTHING;
CREATE OR REPLACE RULE ledger_no_delete AS ON DELETE TO wallet_ledger DO INSTEAD NOTHING
