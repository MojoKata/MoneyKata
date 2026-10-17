"""The ledger's calculations (requirements R3.2, S1, S2): balances, lots, gains, transfers and
reconciliation, derived from transactions on every request. No module here imports
SQLAlchemy: it is handed plain entities and returns plain results (S14.1.2)."""
