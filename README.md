# MoneyKata

A self-hosted personal finance server for a household: bank, brokerage, retirement and crypto
accounts in one place, with portfolio charts, options tracking, future-value projections,
budgets, receipts and tax-preparation worksheets. Several people share one server, and
accounts and portfolios can be shared read-only with other MoneyKata servers on other LANs.

**Status:** design. Nothing is built yet.

- [`docs/requirements.md`](docs/requirements.md): the design, decision by decision, with
  its open questions.
- [`docs/mockups/MoneyKata-mock.html`](docs/mockups/MoneyKata-mock.html): the clickable
  mockup. Open it in a browser from disk; it sends nothing anywhere. The purple **MOCK** pill
  jumps to any screen, switches users and opens the dialogs. **F1** toggles the help pane.

## Planned stack

A Python server (FastAPI under Hypercorn, SQLite through SQLAlchemy, Alembic migrations) and a
browser app with no build step (Preact, HTM, signals and preact-iso as vendored ES modules
under a strict CSP). Deno type-checks the JavaScript, and Playwright for Python runs the
browser tests. No Node.js. See requirements §20.

## License

GPL-3.0, see [`LICENSE`](LICENSE).
