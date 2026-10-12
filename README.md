# MoneyKata

A self-hosted personal finance server for a household: bank, card, brokerage, retirement,
529 and bitcoin accounts in one place, kept current from files the household downloads
(OFX/QFX, CSV, PDF statements and photos of them, read on the server). It charts portfolios,
tracks options, projects retirement and education goals, keeps budgets, gifts, giving,
receipts and tax books, and prepares the numbers a tax return needs. Several people share one
server, and households on other MoneyKata servers can share with named people here, read
only, in a window of their own.

**Status:** design complete for the first milestone; no code yet.

## Where to start

1. [`docs/requirements.md`](docs/requirements.md): what MoneyKata is and does, in the present
   tense. §1 lists the decisions; §20 the stack, the layout and the milestones (§20.9: what
   to build first); §21 the open questions; §22 the gaps not yet specified, each with a
   lasting id (G1, G2, …).
2. [`docs/schema.md`](docs/schema.md): the database conventions: naming, prefixed UUIDv7
   ids, soft deletes and the table prefixes.
3. [`docs/mockups/MoneyKata-mock.html`](docs/mockups/MoneyKata-mock.html): the clickable
   mockup, the design reference for every screen. Open it in a browser from disk; it sends
   nothing anywhere. The purple **MOCK** pill jumps to any screen, switches users, changes
   state and opens every dialog. **F1** toggles the help pane.
4. [`CLAUDE.md`](CLAUDE.md): the working rules: keep the mockup in step with the
   requirements, keep the requirements a statement rather than a changelog, keep the repo
   free standing, and track gaps by id.

Check the mockup after a change with

```
pip install playwright && playwright install chromium
python docs/mockups/check.py shots/
```

It opens every screen, tab, Settings section and dialog, fails on any page or console error
or a field without a help entry, and writes a screenshot of each to `shots/`.

## Stack

A Python server (FastAPI under Hypercorn, SQLite encrypted with SQLCipher, SQLAlchemy Core
tables mapped onto plain dataclasses, Alembic migrations) and a browser app with no build step
(Preact, HTM, signals and preact-iso as vendored ES modules under a strict CSP, charts with
Apache ECharts). Deno type-checks the JavaScript, and Playwright for Python runs the browser
tests. No Node.js. One Docker image for amd64 and arm64, on port 37373. See requirements §20.

## License

GPL-3.0, see [`LICENSE`](LICENSE).
