"""The ledger's calculations (requirements §3.2, §4, §5): balances, lots, gains, transfers and
reconciliation, derived from transactions on every request. No module here imports
SQLAlchemy: it is handed plain entities and returns plain results (§17.1.2)."""
