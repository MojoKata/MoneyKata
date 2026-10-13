# S17. Implementation

1. **Layout**:

   ```
   README.md
   docs/                 requirements/ (README.md and its sections), schema.md, api.md,
                         link-protocol.md, operations.md, mockups/MoneyKata-mock.html
   web/
     VERSION  dev.sh  check  pins
     ui/                 index.html, deno.json, app/{main,router,config,hooks,format}.js,
                         api/, store/, screens/, components/, charts/ (the chart wrappers),
                         account-types/ (one module per type: fields, icon, help),
                         styles/{tokens,base,components}.css, assets/icons.svg,
                         guides/, vendor/, tests/, mockup/
     server/             src/moneykata/: main.py, app.py, config.py, listener.py, middleware.py,
                         static.py, settings.py, ui/ (routes per area), auth/, store/
                         (tables/, entities/, mapping.py, alembic/), ledger/ (lots, gains, wash sales, corporate
                         actions), prices/ (one TickerSource per source), bitcoin/ (esplora,
                         electrum, core), importers/ (ofx, csv, statements), budgets/, projections/, loans/
                         (schedules, payoff planner), assets/ (items, valuations),
                         gifts/ (people, occasions, holiday tables), giving/,
                         taxes/ (8949, txf, limits tables), receipts/ (storage, thumbnails,
                         ocr/: worker, parser, models/), links/, mail/, dev/
     install/            Dockerfile, compose.yaml, moneykata.toml, reverse-proxy examples
   ```

2. **Server dependencies**, each a ruling, kept short because each runs with the database: fastapi, pydantic,
   hypercorn, sqlalchemy, alembic, argon2-cffi, cryptography (AES-GCM, Ed25519 for links),
   httpx, segno (two-step QR), **Pillow** and **pypdfium2** (thumbnails and receipt reading,
   S9.5, S9.8), **sqlcipher3** (the wheel that bundles SQLCipher, for linked copies,
   S11.9), **rapidocr** with **onnxruntime** (receipt reading, S9.8). rapidocr brings
   numpy, opencv-python-headless, shapely, pyclipper and pyyaml with it, about 100 MB in all;
   the image carries them, and they load only in the receipt worker. **ofxtools** reads OFX
   and QFX files (pure Python, GPL-3.0-only, compatible with MoneyKata's GPLv3). **pi-heif** reads iPhone photos
   (HEIC): it decodes only, so it is smaller than pillow-heif, which also encodes. **numpy** is a direct dependency for projections
   (S6) as well as RapidOCR's.
   Standard library for email (`smtplib`), config (`tomllib`), logging and the command line.
   Pinned exactly in `uv.lock`, Python 3.12.
3. **The browser app: no build step.** The files in `web/ui` are the files the browser loads.
   1. **Libraries**: Preact (rendering), HTM (JSX-like tagged templates, no `eval`),
      @preact/signals (state), preact-iso (routes and lazy screens), plus the chart library
      (S17.4). Each is **vendored**: its npm tarball is committed under `web/ui/vendor/`,
      named with its exact version in `manifest.json`, and `vendor.py extract` unpacks the
      files the import map points at. No npm, no network at install.
   2. **An import map** in `index.html` resolves `import 'preact'` to the vendored file.
      JavaScript with JSDoc types, type-checked by Deno. No minification and no source maps,
      so a stack trace names a file in the repository.
   3. **Strict Content Security Policy**: `script-src 'self' 'nonce-…'` (the nonce covers only
      the import map), `style-src 'self'`, no inline scripts or styles, no `eval`. No
      third-party requests: no CDN, no web fonts, no analytics.
   4. **Size budget**: under 150 KB compressed for the first screen; every other screen is a
      module loaded by a native `import()` on first visit.
   5. **Cache-busting**: the app is served under `/ui/v/<version>/` with a one-year cache;
      `index.html`, templated with the version and the nonce, is `no-store`.
   6. **Plain CSS** with custom properties and `@layer`: `tokens.css` (colours and sizes, dark
      first), `base.css`, `components.css`. Icons are one SVG sprite.
   7. **The server is the only state.** The browser remembers only how the page looks: theme,
      sidebar, help pane, page size, privacy mode.
   8. Current Chrome, Edge, Safari and Firefox; no polyfills.
4. **Charts.** The constraints come from S17.3: an ES module the import map can point
   at, vendored with no bundler, working under `script-src 'self'` and `style-src 'self'`
   with no `eval` and no injected `<style>`, colours from `tokens.css`, both themes, and a
   size that is fine if it loads only with the chart screens. Three candidates are worth
   considering:

   | | **Apache ECharts** 5/6 (Apache-2.0) | **uPlot** (MIT) | **Lightweight Charts** (TradingView, Apache-2.0) |
   | --- | --- | --- | --- |
   | Size (gzip) | ~330 KB full ESM build; ~150 KB hand-picked, but picking needs a bundler, so we'd vendor the full file | ~20 KB | ~45 KB |
   | Charts we need | **all**: line/area with range zoom, donut, **treemap**, **Sankey** (cash flow), candlesticks, stacked bars, Monte Carlo fan (stacked bands), markers | line/area/bars, bands for the fan, markers; **no** donut, treemap or Sankey: we'd draw those as our own SVG | financial time series only: line, area, candles, histogram, markers for trades; **no** donut, treemap, Sankey, fan |
   | Rendering | canvas or **SVG** (switchable; SVG suits theming and print) | canvas | canvas |
   | Performance | good to ~100k points | best by far: millions of points | very good, built for price series |
   | Theming | registered themes, built from our CSS variables at run time | CSS file plus options | options |
   | CSP | clean (sets inline styles only through the DOM, which `style-src` allows) | clean; ships its own CSS file, served as ours | clean |
   | Accessibility | ARIA description generation built in | none | none |
   | Catch | size; a large API surface | we write and maintain the non-time-series charts | **requires a TradingView attribution link on the chart**; only covers prices |

   **Apache ECharts**, lazily imported by the chart screens through a small
   `app/charts/` wrapper (theme from tokens, table-view toggle, number formatting). Sign-in and
   the first screen's budget (S17.3.4: under 150 KB) stay unaffected. It is the only one
   of the three that covers every chart in S5–S7 without code of our own. **uPlot** is the
   choice if size and a minimal surface matter more than coverage, at the cost of a few
   hundred lines of our own SVG for donut, treemap and Sankey. **Lightweight Charts** is
   best kept as a possible *addition* for the holding-detail price chart, not the base.
   Chart.js (MIT, ~70 KB) was considered: it is wide enough except for treemap and Sankey
   (plugins), but its time axis needs a separate date-adapter dependency and its ESM build
   imports a further package. It offers less than ECharts for little size saved.

   The mockup draws its charts with small hand-written SVG functions, so it stays one small
   file and doesn't pre-empt this choice.
5. **Tests and checks**, all run by `web/check`, with no Node.js: pytest with a throwaway SQLite per test (most of the
   weight: lots, gains, wash sales, option assignment, imports, budgets, projections, sharing,
   links), browser component tests in headless Chromium driven by Playwright for Python, Deno
   check/lint/fmt, ruff, OpenAPI and typedef drift, mockup drift and the help-guide checks.
   Browser tests use a small in-page runner (`web/ui/tests/run.js`) and a fake API; one
   smoke test drives a running dev server. **Golden files**: a fixture portfolio with known
   8949 rows and TXF output, checked byte for byte. **Receipt reading**: the field parser is
   tested on OCR text, and a set of fixture receipts (phone photos, flatbed scans, text-layer
   PDFs; skewed, faded, rotated) runs through the real RapidOCR worker against expected date,
   total and merchant, with an accuracy floor that a change must not drop below.
6. **`web/dev.sh`** is the developer's front door: alone it prints its commands (`setup`,
   `run`, `test`, `check`, `mail`, `mockup`, `help-shots`, `deno`). `web/pins` holds the
   versions and hashes of the dev-only downloads (Deno, Playwright's Chromium).
7. **Dev mode** (`web/dev.sh run --seed --stubs`, `moneykata dev`) runs the whole server from a
   checkout as the current user, relaxing the surroundings, never the rules: sessions, CSP,
   encryption and sharing behave as in production. `https://localhost:37373` with a
   self-signed certificate, `web/.dev/` for data, receipts and mail, seed users
   (`admin`, `alice`, `bob`, a *Household* group), a year of seeded transactions across every
   account type, open and closed option positions with an assignment and a wash sale, budgets,
   two projections, receipts, and a **stub price source** (deterministic random walks,
   `--stubs`). A second dev server on another port with `--peer` lets links be exercised on
   one machine. Emails are written to `web/.dev/mail/` and their links printed. A red **DEV**
   pill shows on every screen. For testing from another machine, `--listen` sets the address
   it listens on and each `--hostname` adds a name (or address) to its certificate, which is
   made again when it doesn't cover them all; `web/dev.md` describes the setups. Dev mode
   refuses to run as root or on an installed server's
   data directory, and never calls a real provider unless one is configured.
8. **Packaging: one Docker (OCI) image** holding its own Python and venv, the browser app,
   RapidOCR's models and the `moneykata` command, running as an unprivileged user (uid
   10001). It serves on port 37373 and takes three mounts: the **data directory** (database,
   receipts, linked copies), the **backup directory**, and the **key directory**, read only
   for the server and kept out of the backups (S15.4). `moneykata.toml` is mounted too;
   secrets never come from environment variables. `install/compose.yaml` is the example to
   start from. The image is about 600 MB, most of it the receipt reader (ONNX Runtime,
   OpenCV and the models); the reader's worker takes about 350 MB more while it runs, which
   a host too small for it avoids by turning reading off (S9.8.7).
   1. **Architectures**: one multi-architecture image for **amd64** and **arm64**, both built
      on an amd64 build server with `docker buildx` (arm64 under QEMU emulation). Every
      dependency must install from a published wheel for both (onnxruntime, opencv, numpy,
      pi-heif, sqlcipher3 among them), since compiling under emulation is too slow; a check
      fails when one has no arm64 wheel.
   2. **No registry.** The image is built locally and carried to its host (`docker save` and
      `docker load`), or built on the host itself.
   3. **Documented hosts**: **Proxmox** (Docker in a VM, or in an LXC container with nesting
      on) and **TrueNAS** (a custom app from the compose file). `operations.md` covers
      both: mounts, the key directory, backups and upgrades.
   4. **TLS**: the example `compose.yaml` runs in `proxy` mode behind the household's
      reverse proxy. A second example runs `tls` mode with a self-signed certificate for
      testing on a local network (S13.3).
9. **Milestones** *(proposed)*. The requirements describe the finished product; this is the
   order to build it in. Each milestone ends with `web/check` passing, a Docker image that
   runs, and the generated mockup covering what was built.
   1. **Milestone 1, the foundation and one household's accounts:**
      1. **Repository and tooling**: the layout of S17.1, `web/dev.sh`, `web/check`
         (pytest, ruff, Deno, Playwright, OpenAPI and typedef drift), `uv.lock`, and the
         Docker image for amd64 and arm64 with `compose.yaml` (S17.8).
      2. **Server core**: configuration, the listener in both modes (S13.3), the refused
         start (S13.6), the security policies (S13.7), the API conventions (S13.8), the live
         stream (S12.6), background tasks (S13.4) and dev mode with seed data (S17.7).
      3. **Storage and keys**: the SQLCipher database, the master key with its recovery
         phrase, `keys` commands and data key (S15), Alembic, the schema conventions with
         prefixed ids, soft-delete fields and `<Table>Effective` views, and the schema
         checks (`schema.md`); backups (S14.6).
      4. **Users**: the default admin's setup, invitations (email written to a folder until
         SMTP is set), sign-in, sessions, password reset, the active flag, groups, and
         Profile (time zone, theme). Two-step sign-in can wait for milestone 2.
      5. **Accounts and transactions**: account types for banking, cards, brokerage and
         retirement (S1.1, without loans, 529s, physical assets or crypto); manual entry,
         CSV and OFX/QFX import (S1.3.1–S1.3.2); transactions with categories; holdings and
         lots from brokers' files (S2); transfers matched (S1.7); reconciliation's coverage
         and anchors (S1.11).
      6. **Prices**: the `TickerSource` interface with Tiingo, Coinbase, manual and the dev
         stub (S4), the daily refresh, stored closes and staleness.
      7. **Sharing between users**: accounts and portfolios, read and write, users and
         groups (S10.3–S10.7), and Activity (S10.8).
      8. **The app**: the frame, navigation, help pane with its guides, theme and privacy
         mode (S12); Dashboard (net worth, accounts, needs attention), Accounts, an account's
         Overview, Transactions and Reconcile, the Transactions screen, Portfolios with
         Performance and Holdings, Settings (General, Sign-in and sessions, Passwords,
         Prices, Imports, Backups, Key storage) and Users and Groups.
      9. **The mockup** generated from the app for these screens (S12.9); the hand-written
         mockup stays the reference for everything not built yet.
   2. **Milestone 2**, in nine parts:
      1. **Two-step sign-in** (S10.1.6): TOTP set up from a QR code in Profile, the code
         after the password, ten recovery codes, and an admin's reset.
      2. **SMTP and emails**: Settings › Email with **Send a test email**, every email of
         S10.1.9 sent through it, and sign-up with its approval (S10.1.4).
      3. **Alerts** (S12.11): the screen, its badge, the emails and their daily summary,
         Settings › Alerts, and the causes milestone 1 and 2 have built.
      4. **Budgets** (S7.1–S7.5): planned, actual and rollover per category, the budget
         screens and recurring transactions.
      5. **Receipts** (S9.1–S9.7): upload, encrypted storage, thumbnails, the viewer, links
         and the inbox, sharing and retention.
      6. **Reading receipts** (S9.8): the worker process, RapidOCR with its shipped models,
         the field parser, matching, search and Settings › Receipts.
      7. **Statement import** (S1.3.3): bank and card statements, read and checked, with
         their layout learned per institution; the rest of G8 waits.
      8. **Projections and assumptions** (S6.1–S6.9): Profile › Assumptions, the models,
         scenarios, active projections with tracking, the Dashboard's Plans card, and
         Settings › Tax tables with the contribution limits and the bitcoin models' figures.
         Retirement and savings-target goals; the education goal comes with 529s.
      9. **The mockup** generated from the app for these screens, and the Docker image.
   3. **Milestone 3**, in nine parts:
      1. **Loans** (S1.9): terms, the amortization schedule, payments split from their
         transfers, reconciling with the servicer, and the loan's screen.
      2. **The payoff planner** (S6.10): plans against the schedule, recast, and the extra
         invested instead.
      3. **Physical assets** (S1.10): items, their valuations (spot for metals, dated
         values, depreciation), real estate with its loans' equity, and selling.
      4. **529 plans** (S1.8) and the **education goal** (S6.2.2), with the college-cost
         averages in the tax tables.
      5. **Gifts** (S7.7–S7.8): people, occasions and holidays, gifts and ideas, history,
         privacy, the gift-tax flag and the occasion alerts.
      6. **Charitable giving** (S7.9): giving plans, donations and organisations, pledges,
         donor-advised funds and the Giving screen.
      7. **Tax books** (S8.14–S8.17): filers, accounts counted, sharing, filings, tax
         documents and what is carried forward.
      8. **The tax panels and exports** (S8.1–S8.13): Form 8949 and Schedule D with wash
         sales, income, retirement, deductions, the documents checklist, giving, education,
         gifts, loans and physical assets; 8949 CSV, TXF and the PDF summary.
      9. **The mockup** generated from the app for these screens, and the Docker image.
   4. **Milestone 4**: positions and options (S3), bitcoin wallets and own node (S1.6, G9),
      the MCP endpoint (S10.9).
   5. **Milestone 5**: linked servers and linked households (S11, S12.10, G1).
