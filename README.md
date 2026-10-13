# MoneyKata

A self-hosted personal finance server for a household: bank, card, brokerage, retirement,
529 and bitcoin accounts in one place, kept current from files the household downloads
(OFX/QFX, CSV, PDF statements and photos of them, read on the server). It charts portfolios,
tracks options, projects retirement and education goals, keeps budgets, gifts, giving,
receipts and tax books, and prepares the numbers a tax return needs. Several people share one
server, and households on other MoneyKata servers can share with named people here, read
only, in a window of their own.

**Status:** the first two milestones (requirements S17.9.1–S17.9.2) are built in `web/`;
the third (S17.9.3) is next.

## Where to start

1. [`docs/requirements/`](docs/requirements/README.md): what MoneyKata is and does, in the
   present tense. Its README holds the decisions (R1), the terminology (R2) and the design
   principles (R3), and lists the sections S1–S17, the gaps not yet specified (G1, G2, …)
   and the open questions (Q1, Q2, …). S17 has the stack, the layout and the milestones
   (S17.9: the order to build in).
2. [`docs/schema.md`](docs/schema.md): the database conventions: naming, prefixed UUIDv7
   ids, soft deletes and the table prefixes.
3. [`docs/mockups/MoneyKata-mock.html`](docs/mockups/MoneyKata-mock.html): the clickable
   mockup, the design reference for every screen. Open it in a browser from disk; it sends
   nothing anywhere. The purple **MOCK** pill jumps to any screen, switches users, changes
   state and opens every dialog. **F1** toggles the help pane.
4. [`docs/mockups/MoneyKata-app.html`](docs/mockups/MoneyKata-app.html): the mockup generated
   from the app for the screens built so far (`web/dev.sh mockup`), on recorded sample data.
   It opens from disk too; its **MOCK** pill jumps to screens and dialogs and switches users.
   The help guides' screenshots are made from it (`web/dev.sh help-shots`).
5. [`CLAUDE.md`](CLAUDE.md): the working rules: keep the mockup in step with the
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
tests. No Node.js. One Docker image for amd64 and arm64, on port 37373. See requirements S17.

## Development

Needs Python 3.12, [uv](https://docs.astral.sh/uv/) and curl; `setup` fetches the pinned Deno
and Playwright's Chromium.

```
web/dev.sh setup                 # once
web/dev.sh run --seed --stubs    # https://localhost:37373, seed users and stub prices
web/check                        # every check, as CI runs it
```

`web/dev.sh` alone lists its commands. [`web/dev.md`](web/dev.md) covers testing the dev
server from a browser on another machine (an SSH forward, a name of its own, port 443). The image builds from the repository's root:

```
docker buildx build -f web/install/Dockerfile -t moneykata:$(cat web/VERSION) --load .
```

and `web/install/compose.yaml` is the example to run it from. A new server has one user,
`admin`, with the published password `moneykata-setup`: its first sign-in leads only to choosing
a password and an email address. A running server serves the clickable mockup at `/demo`.

## License

GPL-3.0, see [`LICENSE`](LICENSE).
